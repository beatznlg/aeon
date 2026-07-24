"""
AEON OS — Authentication & Authorization (Phase 0 Foundation)
================================================================
Provides JWT validation, password hashing, and role-based access control
for the Flask backend. Designed to work alongside the NextAuth-based
frontend and the Supabase user schema.

Env:
  AEON_JWT_SECRET        Secret used to sign/verify access tokens.
                         Defaults to a dev-only secret (do not use in prod).
  NEXTAUTH_SECRET        Also accepted so the frontend and backend share a secret.
  ADMIN_EMAIL            Fallback admin email (development only).
  ADMIN_PASSWORD_HASH    Fallback admin password hash (development only).
"""

import os
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from functools import wraps
from typing import Optional, Dict, Any, Callable

import jwt
from werkzeug.security import generate_password_hash, check_password_hash
from flask import request, g, jsonify


# === Configuration ============================================================

def _resolve_jwt_secret() -> str:
    return os.environ.get("AEON_JWT_SECRET") or os.environ.get("NEXTAUTH_SECRET") or "dev-only-change-me"


def _dev_mode() -> bool:
    return os.environ.get("AEON_ENV", "development").lower() in ("dev", "development", "local")


JWT_SECRET = _resolve_jwt_secret()
ACCESS_TOKEN_TTL = int(os.environ.get("AEON_ACCESS_TOKEN_TTL", "3600"))  # seconds
REFRESH_TOKEN_TTL_DAYS = int(os.environ.get("AEON_REFRESH_TOKEN_TTL_DAYS", "30"))


# === Role helpers ============================================================

ROLE_HIERARCHY = {
    "SUPER_ADMIN": 4,
    "ADMIN": 3,
    "OPERATOR": 2,
    "VIEWER": 1,
}


def has_role(user_role: Optional[str], required: str) -> bool:
    """Return True if user_role is at least required in the hierarchy."""
    if not user_role:
        return False
    return ROLE_HIERARCHY.get(user_role.upper(), 0) >= ROLE_HIERARCHY.get(required.upper(), 0)


def can_access_workspace(user_id: Optional[str], workspace_id: Optional[str]) -> bool:
    """Check workspace membership using the DB if available; otherwise trust headers in dev."""
    if not user_id or not workspace_id:
        return False
    try:
        from aeon_db import get_db
        db = get_db()
        m = db.get_membership(workspace_id, user_id)
        if m:
            return True
    except Exception:
        pass
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
        pw_hash = os.environ.get("ADMIN_PASSWORD_HASH")
        if not pw_hash or email != cls.email:
            return False
        return check_password_hash(pw_hash, password)


# === Token helpers ============================================================

def create_access_token(user_id: str, email: str, role: str, workspace_id: Optional[str] = None, extra: Optional[Dict[str, Any]] = None) -> str:
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


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT. Returns None if invalid/expired."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return None


def get_auth_token_from_request() -> Optional[str]:
    """Extract the bearer token from the Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1]
    return None


def get_current_user_context() -> Optional[Dict[str, Any]]:
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
            return {
                "user_id": "service",
                "email": "service@aeon.local",
                "role": "ADMIN",
                "workspace_id": request.headers.get("X-Workspace-Id") or "default",
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

def require_auth(func: Callable) -> Callable:
    """Decorator that requires a valid authenticated user."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        ctx = get_current_user_context()
        if not ctx:
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        g.user = ctx
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
