"""Regression tests for audit coverage of security-sensitive authentication actions.

Login success, failed login, registration, and JWT rotation must each write a
tamper-evident audit record (so the events are reconstructable for security
review), must never persist the supplied password, and must not break the
audit hash chain in the process.
"""

from __future__ import annotations

import uuid

from aeon_db import query_audit_logs, verify_audit_chain


def _register(client, label: str = "audit") -> tuple[str, str, str]:
    """Register a fresh user; return (token, workspace_id, email)."""
    email = f"{label}-{uuid.uuid4().hex[:8]}@test.local"
    response = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Audit Tester"},
    )
    assert response.status_code == 201, response.get_json()
    payload = response.get_json()
    return payload["token"], payload["user"]["workspace_id"], email


def test_registration_writes_audit_record(client):
    _token, workspace_id, _email = _register(client, "reg")
    rows = query_audit_logs(action="USER_REGISTERED", module="auth")
    assert rows, "expected a USER_REGISTERED audit record"
    assert any(row["workspace_id"] == workspace_id for row in rows)


def test_login_success_writes_audit_record(client):
    email = f"login-{uuid.uuid4().hex[:8]}@test.local"
    client.post("/auth/register", json={"email": email, "password": "secure123", "name": "Login"})
    response = client.post("/auth/login", json={"email": email, "password": "secure123"})
    assert response.status_code == 200, response.get_json()

    rows = query_audit_logs(action="LOGIN_SUCCESS", module="auth")
    assert rows, "expected a LOGIN_SUCCESS audit record"
    assert any(row["email"] == email for row in rows)


def test_login_failure_writes_audit_record_without_password(client):
    email = f"fail-{uuid.uuid4().hex[:8]}@test.local"
    client.post("/auth/register", json={"email": email, "password": "secure123", "name": "Fail"})

    response = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert response.status_code == 401, response.get_json()

    rows = query_audit_logs(action="LOGIN_FAILED", module="auth")
    assert rows, "expected a LOGIN_FAILED audit record"
    failed = [r for r in rows if r["email"] == email]
    assert failed, "LOGIN_FAILED record must carry the attempted email"

    # Never persist raw secrets: dump every row to be sure.
    import json

    for row in query_audit_logs(action="LOGIN_FAILED"):
        blob = json.dumps(row)
        assert "wrong-password" not in blob
        assert "secure123" not in blob


def test_jwt_rotate_writes_audit_record(client):
    # JWT rotation is a system-admin action; use the bootstrap admin account.
    login = client.post(
        "/auth/login",
        json={"email": "admin@test.local", "password": "adminpass"},
    )
    assert login.status_code == 200, login.get_json()
    token = login.get_json()["token"]
    response = client.post(
        "/auth/jwt/rotate",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    assert response.status_code == 200, response.get_json()
    rows = query_audit_logs(action="JWT_ROTATED", module="auth")
    assert rows, "expected a JWT_ROTATED audit record"


def test_audit_chain_remains_valid_after_auth_events(client):
    _token, _workspace_id, _email = _register(client, "chain")
    # failed login
    client.post("/auth/login", json={"email": _email, "password": "bad"})

    report = verify_audit_chain()
    assert report["ok"] is True, report
    assert report["errors"] == []
