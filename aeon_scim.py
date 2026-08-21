"""
AEON OS — SCIM 2.0 Provisioning (Phase 44)
===========================================
Provides a minimal but conformant SCIM 2.0 service provider surface for
automated user/group provisioning from enterprise identity providers.

Authentication:
  Authorization: Bearer <scim_token>
  Tokens are stored as SHA-256 hashes in the ScimToken table and are scoped
  to a single workspace.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Any

from flask import g, jsonify, request

from aeon_db import Membership, ScimToken, User, add_audit_log, get_db

logger = logging.getLogger("aeon_scim")

SCIM_MIME = "application/scim+json"


def _scim_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _generate_scim_token() -> str:
    return secrets.token_urlsafe(32)


def create_scim_token(workspace_id: str, description: str | None = None) -> tuple[str, ScimToken]:
    """Return a plaintext SCIM token and persist its hash."""
    db = get_db()
    plain = _generate_scim_token()
    token = ScimToken(
        workspace_id=str(workspace_id),
        token_hash=_hash_token(plain),
        description=description,
    )
    with db.session() as s:
        s.add(token)
        s.commit()
        return plain, token


def _scim_user_response(user: User, workspace_id: str) -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:User"],
        "id": str(user.id),
        "userName": user.email,
        "name": {
            "formatted": user.name or user.email,
            "givenName": "",
            "familyName": "",
        },
        "emails": [
            {
                "value": user.email,
                "type": "work",
                "primary": True,
            }
        ],
        "active": True,
        "meta": {
            "resourceType": "User",
            "created": user.created_at.isoformat() if user.created_at else _scim_now(),
            "lastModified": _scim_now(),
            "location": f"/scim/v2/Users/{user.id}",
        },
    }


def _scim_group_response(group_id: str, display_name: str, members: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:Group"],
        "id": group_id,
        "displayName": display_name,
        "members": members,
        "meta": {
            "resourceType": "Group",
            "created": _scim_now(),
            "lastModified": _scim_now(),
            "location": f"/scim/v2/Groups/{group_id}",
        },
    }


def _extract_primary_email(payload: dict[str, Any]) -> str:
    emails = payload.get("emails", [])
    if emails:
        primary = next((e for e in emails if e.get("primary")), emails[0])
        return (primary.get("value") or "").lower()
    return (payload.get("userName") or "").lower()


def _role_from_display_name(display_name: str) -> str:
    name = display_name.lower()
    if "admin" in name:
        return "ADMIN"
    if "operator" in name or "editor" in name:
        return "OPERATOR"
    return "VIEWER"


def _touch_token(token: ScimToken) -> None:
    db = get_db()
    with db.session() as s:
        token.last_used_at = datetime.now(timezone.utc)
        s.add(token)
        s.commit()


def require_scim_token(func: Any) -> Any:
    """Decorator that validates a SCIM bearer token and scopes the request to a workspace."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return _scim_error("Authentication scheme not supported", 401)
        token_plain = auth_header.split(" ", 1)[1]
        token_hash = _hash_token(token_plain)
        db = get_db()
        with db.session() as s:
            token = s.query(ScimToken).filter_by(token_hash=token_hash).first()
        if not token:
            return _scim_error("Invalid bearer token", 401)
        g.scim_token = token
        g.scim_workspace_id = str(token.workspace_id)
        _touch_token(token)
        return func(*args, **kwargs)

    return wrapper


def _scim_error(detail: str, status: int = 400) -> tuple[dict[str, Any], int]:
    response = jsonify(
        {
            "schemas": ["urn:ietf:params:scim:api:messages:2.0:Error"],
            "detail": detail,
            "status": str(status),
        }
    )
    response.headers["Content-Type"] = SCIM_MIME
    return response, status


def scim_create_user(workspace_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    email = _extract_primary_email(payload)
    if not email:
        return _scim_error("userName/email is required", 400)

    name = payload.get("name", {}).get("formatted") or email.split("@")[0]
    role = _role_from_display_name(payload.get("displayName") or "")

    db = get_db()
    with db.session() as s:
        user = s.query(User).filter_by(email=email.lower()).first()
        if not user:
            user = User(
                email=email.lower(),
                name=name,
                password=secrets.token_urlsafe(32),
                role=role,
            )
            s.add(user)
            s.flush()
        membership = (
            s.query(Membership)
            .filter_by(workspace_id=str(workspace_id), user_id=str(user.id))
            .first()
        )
        if not membership:
            membership = Membership(workspace_id=str(workspace_id), user_id=str(user.id), role=role)
            s.add(membership)
        s.commit()
        try:
            add_audit_log(
                action="SCIM_USER_CREATED",
                module="scim",
                user_id=str(user.id),
                workspace_id=str(workspace_id),
                email=email,
                metadata={"role": role},
            )
        except Exception:  #nosec B110 - provisioning must not fail on audit
            pass
        response = jsonify(_scim_user_response(user, str(workspace_id)))
        response.headers["Content-Type"] = SCIM_MIME
        return response, 201


def scim_list_users(workspace_id: str, filter_expr: str | None = None) -> tuple[dict[str, Any], int]:
    db = get_db()
    with db.session() as s:
        membership_ids = [
            m.user_id for m in s.query(Membership).filter_by(workspace_id=str(workspace_id)).all()
        ]
        users = s.query(User).filter(User.id.in_(membership_ids)).all() if membership_ids else []
        # Simple filter parsing for userName eq "value" or userName sw "value"
        if filter_expr:
            if "userName eq " in filter_expr:
                value = filter_expr.split("userName eq ", 1)[1].strip('"').lower()
                users = [u for u in users if u.email.lower() == value]
            elif "userName sw " in filter_expr:
                value = filter_expr.split("userName sw ", 1)[1].strip('"').lower()
                users = [u for u in users if u.email.lower().startswith(value)]
        resources = [_scim_user_response(u, str(workspace_id)) for u in users]

    result = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": len(resources),
        "Resources": resources,
    }
    response = jsonify(result)
    response.headers["Content-Type"] = SCIM_MIME
    return response, 200


def scim_get_user(workspace_id: str, user_id: str) -> tuple[dict[str, Any], int]:
    db = get_db()
    with db.session() as s:
        membership = (
            s.query(Membership)
            .filter_by(workspace_id=str(workspace_id), user_id=str(user_id))
            .first()
        )
        if not membership:
            return _scim_error("User not found", 404)
        user = s.query(User).filter_by(id=str(user_id)).first()
        if not user:
            return _scim_error("User not found", 404)
        response = jsonify(_scim_user_response(user, str(workspace_id)))
        response.headers["Content-Type"] = SCIM_MIME
        return response, 200


def scim_replace_user(workspace_id: str, user_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    email = _extract_primary_email(payload)
    if not email:
        return _scim_error("userName/email is required", 400)
    db = get_db()
    with db.session() as s:
        user = s.query(User).filter_by(id=str(user_id)).first()
        if not user:
            return _scim_error("User not found", 404)
        user.email = email.lower()
        user.name = payload.get("name", {}).get("formatted") or user.name
        s.commit()
        response = jsonify(_scim_user_response(user, str(workspace_id)))
        response.headers["Content-Type"] = SCIM_MIME
        return response, 200


def scim_patch_user(workspace_id: str, user_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    operations = payload.get("Operations", [])
    db = get_db()
    with db.session() as s:
        user = s.query(User).filter_by(id=str(user_id)).first()
        if not user:
            return _scim_error("User not found", 404)
        membership = (
            s.query(Membership)
            .filter_by(workspace_id=str(workspace_id), user_id=str(user_id))
            .first()
        )
        active = None
        for op in operations:
            if op.get("op", "").lower() in ("replace", "add"):
                if op.get("path") == "active":
                    active = op.get("value")
                elif op.get("value") and "active" in op.get("value"):
                    active = op["value"]["active"]
        # Deactivation is represented by removing the workspace membership.
        if active is False:
            if membership:
                s.delete(membership)
            s.commit()
            user.active = False  # type: ignore[attr-defined]
            try:
                add_audit_log(
                    action="SCIM_USER_DEACTIVATED",
                    module="scim",
                    user_id=str(user.id),
                    workspace_id=str(workspace_id),
                    email=user.email,
                    metadata={},
                )
            except Exception:  #nosec B110
                pass
        response = jsonify(_scim_user_response(user, str(workspace_id)))
        response.headers["Content-Type"] = SCIM_MIME
        return response, 200


def scim_create_group(workspace_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    display_name = payload.get("displayName", "group")
    group_id = str(uuid.uuid4())
    members = payload.get("members", [])
    db = get_db()
    role = _role_from_display_name(display_name)
    with db.session() as s:
        for member in members:
            user_id = member.get("value")
            if not user_id:
                continue
            membership = (
                s.query(Membership)
                .filter_by(workspace_id=str(workspace_id), user_id=str(user_id))
                .first()
            )
            if membership:
                membership.role = role
            else:
                membership = Membership(workspace_id=str(workspace_id), user_id=str(user_id), role=role)
                s.add(membership)
        s.commit()
    response = jsonify(_scim_group_response(group_id, display_name, members))
    response.headers["Content-Type"] = SCIM_MIME
    return response, 201


def scim_list_groups(workspace_id: str) -> tuple[dict[str, Any], int]:
    result = {
        "schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
        "totalResults": 0,
        "Resources": [],
    }
    response = jsonify(result)
    response.headers["Content-Type"] = SCIM_MIME
    return response, 200


def scim_get_group(workspace_id: str, group_id: str) -> tuple[dict[str, Any], int]:
    return _scim_error("Group not found", 404)


def scim_replace_group(workspace_id: str, group_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    return scim_create_group(workspace_id, payload)


def scim_patch_group(workspace_id: str, group_id: str, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    operations = payload.get("Operations", [])
    db = get_db()
    with db.session() as s:
        for op in operations:
            if op.get("op", "").lower() in ("add", "replace"):
                members = op.get("value", [])
                for member in members:
                    user_id = member.get("value")
                    role = _role_from_display_name(member.get("display", "member"))
                    if not user_id:
                        continue
                    membership = (
                        s.query(Membership)
                        .filter_by(workspace_id=str(workspace_id), user_id=str(user_id))
                        .first()
                    )
                    if membership:
                        membership.role = role
                    else:
                        membership = Membership(workspace_id=str(workspace_id), user_id=str(user_id), role=role)
                        s.add(membership)
        s.commit()
    response = jsonify(_scim_group_response(group_id, "workspace-group", []))
    response.headers["Content-Type"] = SCIM_MIME
    return response, 200
