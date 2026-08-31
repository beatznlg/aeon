"""High-value production security regression tests.

These tests are intentionally dependency-light and exercise the shared
authorization/JWT boundary rather than individual route implementations.
They are release blockers: a regression here should stop deployment.
"""

from datetime import datetime, timedelta, timezone

import jwt

from aeon_auth import (
    JWT_SECRET,
    ROLE_HIERARCHY,
    create_access_token,
    decode_token,
    has_permission,
    has_role,
)


def test_role_hierarchy_is_monotonic():
    assert ROLE_HIERARCHY["OWNER"] == ROLE_HIERARCHY["SUPER_ADMIN"]
    assert ROLE_HIERARCHY["OWNER"] > ROLE_HIERARCHY["ADMIN"]
    assert ROLE_HIERARCHY["ADMIN"] > ROLE_HIERARCHY["OPERATOR"]
    assert ROLE_HIERARCHY["OPERATOR"] > ROLE_HIERARCHY["VIEWER"]


def test_unknown_roles_fail_closed():
    assert not has_role(None, "VIEWER")
    assert not has_role("UNKNOWN", "VIEWER")
    assert not has_permission(None, "workspace.read")
    assert not has_permission("UNKNOWN", "workspace.read")
    assert not has_permission("ADMIN", "not-a-real-permission")


def test_permission_boundaries():
    assert has_permission("VIEWER", "workspace.read")
    assert not has_permission("VIEWER", "workspace.write")
    assert has_permission("OPERATOR", "automation.write")
    assert not has_permission("VIEWER", "automation.write")
    assert has_permission("ADMIN", "billing.manage")
    assert not has_permission("OPERATOR", "billing.manage")


def test_access_token_contains_required_claims_and_expires():
    token = create_access_token("user-1", "user@example.test", "VIEWER", "workspace-1")
    claims = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    assert claims["sub"] == "user-1"
    assert claims["email"] == "user@example.test"
    assert claims["role"] == "VIEWER"
    assert claims["workspace_id"] == "workspace-1"
    assert claims["type"] == "access"
    assert claims["exp"] > claims["iat"]


def test_invalid_signature_is_rejected():
    token = create_access_token("user-1", "user@example.test", "VIEWER", "workspace-1")
    assert decode_token(token + "tampered") is None


def test_expired_token_is_rejected():
    expired = jwt.encode(
        {
            "sub": "user-1",
            "email": "user@example.test",
            "role": "VIEWER",
            "workspace_id": "workspace-1",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "type": "access",
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    assert decode_token(expired) is None
