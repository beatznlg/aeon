"""
AEON OS — Authentication & Authorization (Phase 0 Foundation)
================================================================
Provides JWT validation, password hashing, and role-based access control
for the Flask backend. Designed to work alongside the NextAuth-based
frontend and the Supabase user schema.

Env:
  AEON_JWT_SECRET        Secret used to sign/verify access tokens.
                         A development-only fallback is available only when
                         AEON_ENV is dev/development/local/test.
  NEXTAUTH_SECRET        Also accepted so the frontend and backend share a secret.
  ADMIN_EMAIL            Fallback admin email (development only).
  ADMIN_PASSWORD_HASH    Fallback admin password hash (development only).
"""

import hmac
import os
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any

import jwt
from flask import g, jsonify, request
from werkzeug.security import check_password_hash

# === Configuration ============================================================

def _dev_mode() -> bool:
    return os.environ.get("AEON_ENV", "development").lower() in ("dev", "development", "local", "test")


def _resolve_jwt_secret() -> str:
    """Resolve the signing key and fail closed in production-like environments."""
    configured = os.environ.get("AEON_JWT_SECRET") or os.environ.get("NEXTAUTH_SECRET")
    if configured:
        if not _dev_mode() and len(configured) < 32:
            raise RuntimeError("AEON_JWT_SECRET/NEXTAUTH_SECRET must be at least 32 characters")
        return configured
    if _dev_mode():
        return "dev-only-change-me"
    raise RuntimeError("AEON_JWT_SECRET or NEXTAUTH_SECRET must be configured")


# === JWT secret rotation support =============================================

def _resolve_jwt_secrets() -> list[str]:
    """Return a list of valid JWT secrets for token verification.

    The primary secret is used for signing new tokens. Older secrets are kept
    for rotation windows so existing tokens remain valid until they expire.
    """
    secrets = []
    primary = _resolve_jwt_secret()
    if primary:
        secrets.append(primary)
    # Optional previous/rotated secrets for key rotation (comma-separated)
    for old in os.environ.get("AEON_JWT_SECRET_PREVIOUS", "").split(","):
        old = old.strip()
        if old and old not in secrets:
            secrets.append(old)
    return secrets


# Primary secret used for signing new tokens
JWT_SECRET = _resolve_jwt_secret()
# All valid secrets (primary + previous) used for verification
JWT_SECRETS = _resolve_jwt_secrets()
ACCESS_TOKEN_TTL = int(os.environ.get("AEON_ACCESS_TOKEN_TTL", "3600"))  # seconds
REFRESH_TOKEN_TTL_DAYS = int(os.environ.get("AEON_REFRESH_TOKEN_TTL_DAYS", "30"))


# === Role helpers ============================================================

ROLE_HIERARCHY = {
    "SUPER_ADMIN": 4,
    "ADMIN": 3,
    "OPERATOR": 2,
    "VIEWER": 1,
}


def has_role(user_role: str | None, required: str) -> bool:
    """Return True if user_role is at least required in the hierarchy."""
    if not user_role:
        return False
    return ROLE_HIERARCHY.get(user_role.upper(), 0) >= ROLE_HIERARCHY.get(required.upper(), 0)


def can_access_workspace(user_id: str | None, workspace_id: str | None) -> bool:
    """Return whether a user is a member of a workspace.

    Development may use header-only identities, but production-like requests
    never gain access merely because the membership database is unavailable.
    """
    if not user_id or not workspace_id:
        return False
    try:
        from aeon_db import get_db
        db = get_db()
        membership = db.get_membership(workspace_id, user_id)
        if membership:
            return True
    except Exception:  #nosec B110
        return _dev_mode()
    return _dev_mode()


# === Fallback admin (development only) =======================================

class _FallbackAdmin:
    id = "admin-fallback"
    email = os.environ.get("ADMIN_EMAIL", "admin@aeon.local")
    name = "Administrator"
    role = "ADMIN"
    tenant_id = None
    workspace_id = "00000000-0000-0000-0000-000000000000"

    @classmethod
    def matches(cls, email: str, password: str) -> bool:
        if not _dev_mode():
            return False
        pw_hash = os.environ.get("ADMIN_PASSWORD_HASH")
        if not pw_hash or email != cls.email:
            return False
        return check_password_hash(pw_hash, password)


# === Token helpers ============================================================

def _hash_secret(secret: str) -> str:
    """Return a short, safe fingerprint of a secret for status endpoints."""
    import hashlib
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:16]


def rotate_jwt_secret(new_secret: str | None = None) -> dict[str, Any]:
    """Rotate the primary JWT signing secret.

    The current primary secret is moved to the previous-secrets list so existing
    tokens remain valid during the rotation window. Returns a safe summary.
    """
    global JWT_SECRET, JWT_SECRETS
    old_secret = JWT_SECRET
    JWT_SECRET = new_secret or secrets.token_urlsafe(32)

    updated = [JWT_SECRET]
    if old_secret and old_secret not in updated:
        updated.append(old_secret)
    for s in JWT_SECRETS:
        if s and s not in updated:
            updated.append(s)

    JWT_SECRETS = updated
    return {
        "rotated_at": datetime.now(timezone.utc).isoformat(),
        "active_secret_hash": _hash_secret(JWT_SECRET),
        "previous_secrets_count": len(updated) - 1,
    }


def jwt_status() -> dict[str, Any]:
    """Return non-sensitive status information about the current JWT configuration."""
    return {
        "active_secret_hash": _hash_secret(JWT_SECRET),
        "previous_secrets_count": len([s for s in JWT_SECRETS if s != JWT_SECRET]),
        "access_token_ttl": ACCESS_TOKEN_TTL,
        "algorithm": "HS256",
    }


def create_access_token(user_id: str, email: str, role: str, workspace_id: str | None = None, extra: dict[str, Any] | None = None) -> str:
    """Create a short-lived JWT access token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id) if user_id else None,
        "email": email,
        "role": role,
        "workspace_id": str(workspace_id) if workspace_id else None,
        "iat": now,
        "exp": now + timedelta(seconds=ACCESS_TOKEN_TTL),
        "type": "access",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT. Returns None if invalid/expired.

    Tries the primary secret first, then any configured previous secrets so
    rolling key rotation does not immediately invalidate active sessions.
    """
    errors = []
    for secret in JWT_SECRETS:
        try:
            return jwt.decode(token, secret, algorithms=["HS256"])
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
            continue
    return None


def get_auth_token_from_request() -> str | None:
    """Extract the bearer token from the Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1]
    return None


def get_current_user_context() -> dict[str, Any] | None:
    """
    Resolve the current user from the request.
    Priority:
      1. Authorization: Bearer <jwt>
      2. X-API-Token header (for service accounts / integrations)
      3. X-User-Id / X-Workspace-Id headers (dev fallback)
    """
    # 1. JWT bearer token
    token = get_auth_token_from_request()
    if token:
        payload = decode_token(token)
        if payload:
            return {
                "user_id": payload.get("sub"),
                "email": payload.get("email"),
                "role": payload.get("role", "VIEWER"),
                "workspace_id": payload.get("workspace_id"),
                "auth_method": "jwt",
            }

    # 2. API token (simple shared secret for service-to-service)
    api_token = request.headers.get("X-API-Token")
    if api_token:
        expected = os.environ.get("AEON_API_TOKEN")
        if expected and hmac.compare_digest(api_token, expected):
            # Preserve the actual caller's identity when the frontend proxy
            # forwards a valid service token alongside user context headers.
            user_id = request.headers.get("X-User-Id") or "service"
            user_role = request.headers.get("X-User-Role") or "ADMIN"
            workspace_id = request.headers.get("X-Workspace-Id")
            return {
                "user_id": user_id,
                "email": request.headers.get("X-User-Email") or f"{user_id}@aeon.local",
                "role": user_role,
                "workspace_id": workspace_id or "default",
                "auth_method": "api_token",
            }

    # 3. Dev fallback: trust headers
    if _dev_mode():
        user_id = request.headers.get("X-User-Id")
        if user_id:
            return {
                "user_id": user_id,
                "email": request.headers.get("X-User-Email") or "dev@aeon.local",
                "role": request.headers.get("X-User-Role") or "ADMIN",
                "workspace_id": request.headers.get("X-Workspace-Id"),
                "auth_method": "dev_header",
            }

    return None


# === Flask decorators =========================================================

def _authorize_sensitive_workspace_request(ctx: dict[str, Any]):
    """Enforce tenant scope for legacy auth-protected billing/usage routes.

    These endpoints historically used ``@require_auth`` because their workspace
    identifier can arrive in JSON or a query string rather than a route path.
    Keep the rule centralized so a caller cannot turn a valid token into access
    to another tenant's billing or usage data.
    """
    path = request.path
    if path not in {"/usage", "/usage/summary", "/stripe/checkout", "/stripe/portal"} and not path.startswith("/stripe/subscription/"):
        return None

    workspace_id = None
    if path == "/usage/summary":
        workspace_id = request.args.get("workspace_id")
    elif path.startswith("/stripe/subscription/"):
        workspace_id = (request.view_args or {}).get("workspace_id")
    else:
        payload = request.get_json(silent=True) or {}
        if isinstance(payload, dict):
            workspace_id = payload.get("workspace_id")

    workspace_id = str(workspace_id or ctx.get("workspace_id") or "").strip()
    if not workspace_id:
        return jsonify({"ok": False, "error": "workspace_id required"}), 400
    is_super_admin = has_role(ctx.get("role"), "SUPER_ADMIN")
    membership = None
    try:
        from aeon_db import get_db
        membership = get_db().get_membership(workspace_id, ctx.get("user_id"))
    except Exception:
        membership = None
    service_auth = ctx.get("auth_method") == "api_token"
    if not is_super_admin and not membership and not service_auth:
        return jsonify({"ok": False, "error": "workspace access denied"}), 403

    if path in {"/stripe/checkout", "/stripe/portal"}:
        if not is_super_admin and not service_auth and not has_role(getattr(membership, "role", None), "ADMIN"):
            return jsonify({"ok": False, "error": "workspace admin required"}), 403

    g.workspace_id = workspace_id
    return None


def require_auth(func: Callable) -> Callable:
    """Decorator that requires a valid authenticated user."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        ctx = get_current_user_context()
        if not ctx:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        g.user = ctx
        scope_error = _authorize_sensitive_workspace_request(ctx)
        if scope_error is not None:
            return scope_error
        return func(*args, **kwargs)
    return wrapper


def require_role(role: str):
    """Decorator factory that requires at least the given role."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            ctx = get_current_user_context()
            if not ctx:
                return jsonify({"ok": False, "error": "unauthorized"}), 401
            if not has_role(ctx.get("role"), role):
                return jsonify({"ok": False, "error": "forbidden"}), 403
            g.user = ctx
            return func(*args, **kwargs)
        return wrapper
    return decorator


def require_workspace_access(func: Callable) -> Callable:
    """Decorator ensuring the authenticated user can access the requested workspace."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        ctx = get_current_user_context()
        if not ctx:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        workspace_id = kwargs.get("workspace_id") or request.view_args.get("workspace_id") if request.view_args else None
        workspace_id = workspace_id or request.args.get("workspace_id") or ctx.get("workspace_id")
        if workspace_id and not can_access_workspace(ctx.get("user_id"), workspace_id):
            return jsonify({"ok": False, "error": "workspace access denied"}), 403
        g.user = ctx
        g.workspace_id = workspace_id
        return func(*args, **kwargs)
    return wrapper


def require_workspace_role(role: str):
    """Decorator factory that requires the user to have at least `role` in the current workspace.

    The decorated function must receive a `workspace_id` as a route argument or query param.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            ctx = get_current_user_context()
            if not ctx:
                return jsonify({"ok": False, "error": "unauthorized"}), 401

            workspace_id = (
                kwargs.get("workspace_id")
                or (request.view_args.get("workspace_id") if request.view_args else None)
                or request.args.get("workspace_id")
                or ctx.get("workspace_id")
            )
            if not workspace_id:
                return jsonify({"ok": False, "error": "workspace_id required"}), 400

            # SUPER_ADMIN bypasses workspace role checks
            if has_role(ctx.get("role"), "SUPER_ADMIN"):
                g.user = ctx
                g.workspace_id = workspace_id
                return func(*args, **kwargs)

            try:
                from aeon_db import get_db
                db = get_db()
                membership = db.get_membership(workspace_id, ctx.get("user_id"))
                if not membership:
                    return jsonify({"ok": False, "error": "workspace access denied"}), 403
                if not has_role(membership.role, role):
                    return jsonify({"ok": False, "error": f"workspace role {role} required"}), 403
                g.user = ctx
                g.workspace_id = workspace_id
                g.membership = membership
                return func(*args, **kwargs)
            except Exception:
                return jsonify({"ok": False, "error": "workspace access denied"}), 403
        return wrapper
    return decorator
