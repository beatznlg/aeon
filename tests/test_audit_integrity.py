"""Tests for the tamper-evident audit hash chain.

Every audit log row is hash-chained to its predecessor so edits, deletions
(within the chain), and reordering are detectable. The report must never
expose audit row contents such as emails or metadata.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from aeon_db import AuditLog, add_audit_log, get_db, verify_audit_chain


def _seed_logs(count: int = 3, workspace: str = "ws-audit-test") -> list[AuditLog]:
    """Append *count* audit rows through the normal write path."""
    created: list[AuditLog] = []
    for index in range(count):
        created.append(
            add_audit_log(
                action=f"test.action.{index}",
                module="audit-integrity",
                user_id="u-1",
                workspace_id=workspace,
                email="audit@test.local",
                metadata={"seq": index},
            )
        )
    return created


def _admin_token(client) -> str:
    """Return a JWT for the fallback admin used by the test environment."""
    response = client.post(
        "/auth/login",
        json={"email": "admin@test.local", "password": "adminpass"},
    )
    assert response.status_code == 200, response.get_json()
    return response.get_json()["token"]


def test_chain_links_and_genesis(client):
    logs = _seed_logs(3)

    assert logs[0].previous_hash == "0" * 64
    assert logs[1].previous_hash == logs[0].record_hash
    assert logs[2].previous_hash == logs[1].record_hash
    assert all(len(record.record_hash) == 64 for record in logs)

    report = verify_audit_chain()
    assert report["ok"] is True
    assert report["records"] >= 3
    assert report["hashed"] >= 3
    assert report["legacy_unhashed"] == 0
    assert report["errors"] == []


def test_tampering_is_detected(client):
    _seed_logs(2)

    db = get_db()
    with db.session() as s:
        row = s.query(AuditLog).order_by(AuditLog.timestamp.asc(), AuditLog.id.asc()).first()
        row.action = "tampered-by-attacker"
        s.commit()

    report = verify_audit_chain()
    assert report["ok"] is False
    assert any("hash mismatch" in error for error in report["errors"])


def test_metadata_tampering_is_detected(client):
    _seed_logs(2)

    db = get_db()
    with db.session() as s:
        row = s.query(AuditLog).order_by(AuditLog.timestamp.asc(), AuditLog.id.asc()).first()
        row.metadata_json = {"seq": 999}
        s.commit()

    report = verify_audit_chain()
    assert report["ok"] is False
    assert any("hash mismatch" in error for error in report["errors"])


def test_legacy_unhashed_rows_are_reported(client):
    # A row written before the hash-chain feature has NULL hashes.
    db = get_db()
    with db.session() as s:
        legacy = AuditLog(
            id=str(uuid.uuid4()),
            user_id=None,
            email=None,
            action="legacy.action",
            module="old",
            workspace_id=None,
            timestamp=datetime.now(timezone.utc),
        )
        s.add(legacy)
        s.commit()

    _seed_logs(1)

    report = verify_audit_chain()
    assert report["legacy_unhashed"] == 1
    assert report["ok"] is False
    assert any("without hash" in error for error in report["errors"])


def test_integrity_endpoint_requires_admin(client):
    token = _admin_token(client)
    _seed_logs(2)

    unauth = client.get("/audit/integrity")
    assert unauth.status_code == 401

    registered = client.post(
        "/auth/register",
        json={"email": "viewer@test.local", "password": "secure123", "name": "Viewer"},
    )
    assert registered.status_code == 201
    viewer_token = registered.get_json()["token"]
    forbidden = client.get("/audit/integrity", headers={"Authorization": f"Bearer {viewer_token}"})
    assert forbidden.status_code == 403

    allowed = client.get("/audit/integrity", headers={"Authorization": f"Bearer {token}"})
    assert allowed.status_code == 200
    payload = allowed.get_json()
    assert payload["ok"] is True
    assert payload["audit_chain"]["records"] >= 2
    # The report must not expose audit row contents.
    assert "audit@test.local" not in str(payload)
    assert "tampered" not in str(payload)


def test_integrity_endpoint_fails_closed_on_tamper(client):
    token = _admin_token(client)
    _seed_logs(2)

    db = get_db()
    with db.session() as s:
        row = s.query(AuditLog).order_by(AuditLog.timestamp.asc(), AuditLog.id.asc()).first()
        row.action = "tampered-by-attacker"
        s.commit()

    response = client.get("/audit/integrity", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 503
    assert response.get_json()["ok"] is False


def test_readiness_gate_verifies_immutable_audit_chain(client, monkeypatch):
    """With AEON_AUDIT_IMMUTABLE=true the readiness probe verifies the live chain."""
    import aeon_server

    monkeypatch.setenv("AEON_ENV", "production")
    monkeypatch.setenv("AEON_AUDIT_IMMUTABLE", "true")

    _seed_logs(2)
    report = aeon_server.validate_environment()
    # The chain itself must verify even though other production config is absent.
    assert report["audit_integrity"]["ok"] is True
    assert report["audit_integrity"]["records"] >= 2

    db = get_db()
    with db.session() as s:
        row = s.query(AuditLog).order_by(AuditLog.timestamp.asc(), AuditLog.id.asc()).first()
        row.action = "tampered-by-attacker"
        s.commit()

    report = aeon_server.validate_environment()
    assert report["audit_integrity"]["ok"] is False
    assert any("audit chain:" in missing for missing in report["missing"])


def test_readiness_gate_skips_audit_check_when_not_immutable(client, monkeypatch):
    """The audit chain is only enforced when immutable audit is declared."""
    import aeon_server

    monkeypatch.setenv("AEON_ENV", "production")
    monkeypatch.delenv("AEON_AUDIT_IMMUTABLE", raising=False)

    _seed_logs(1)
    report = aeon_server.validate_environment()
    assert "audit_integrity" not in report
