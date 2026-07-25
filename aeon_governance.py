"""
AEON OS Phase 8 — Audit, Compliance & Governance
==================================================
Lightweight governance layer for the Python backend.

- Buffers audit events in a queue and flushes them to Supabase in batches.
- Detects/redacts common PII patterns.
- Runs compliance checks (retention, PII, consent).

Usage:
    from aeon_governance import GovernanceManager
    gm = GovernanceManager()
    gm.log_audit(action="CHAT", module="global", user_id="...", workspace_id="...", metadata={...})
"""

import json
import os
import queue
import re
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

import requests

# === PII patterns ==========================================================

PII_PATTERNS = [
    ("email", re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")),
    ("credit_card", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("phone", re.compile(r"\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
    ("api_key", re.compile(r"\b(?:api[_-]?key|token)\s*[:=]\s*[\w-]{16,}\b", re.IGNORECASE)),
]


def detect_pii(text: str) -> list[dict[str, Any]]:
    """Return list of PII findings with type, matched text, and position."""
    findings = []
    if not text:
        return findings
    for label, pattern in PII_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({
                "type": label,
                "match": match.group(0),
                "start": match.start(),
                "end": match.end(),
            })
    return findings


def redact_pii(text: str) -> str:
    """Redact detected PII from text."""
    if not text:
        return text
    redacted = text
    for label, pattern in PII_PATTERNS:
        redacted = pattern.sub(f"[{label.upper()}_REDACTED]", redacted)
    return redacted


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Recursively sanitize metadata dict, redacting PII in string values."""
    if not isinstance(metadata, dict):
        return metadata
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, str):
            cleaned[key] = redact_pii(value)
        elif isinstance(value, dict):
            cleaned[key] = sanitize_metadata(value)
        elif isinstance(value, list):
            cleaned[key] = [
                redact_pii(v) if isinstance(v, str) else (sanitize_metadata(v) if isinstance(v, dict) else v)
                for v in value
            ]
        else:
            cleaned[key] = value
    return cleaned


# === Audit event model =====================================================

@dataclass
class AuditEvent:
    action: str
    module: str
    user_id: str | None
    workspace_id: str | None
    email: str | None
    metadata: dict[str, Any]
    timestamp: float
    pii_redacted: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["metadata"] = sanitize_metadata(data["metadata"])
        return data


# === Governance manager ====================================================

class GovernanceManager:
    def __init__(self, batch_size: int = 20, flush_interval: float = 5.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._queue: queue.Queue[AuditEvent] = queue.Queue()
        self._lock = threading.Lock()
        self._stopped = False
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()
        self._supabase_url = os.environ.get("SUPABASE_URL")
        self._supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

    def _worker_loop(self):
        while True:
            batch: list[AuditEvent] = []
            try:
                item = self._queue.get(timeout=self.flush_interval)
                if item is None:
                    break
                batch.append(item)
            except queue.Empty:
                pass

            # Drain up to batch_size
            while len(batch) < self.batch_size:
                try:
                    item = self._queue.get_nowait()
                    if item is None:
                        self._stopped = True
                        break
                    batch.append(item)
                except queue.Empty:
                    break

            if batch:
                self._flush(batch)

    def log_audit(
        self,
        action: str,
        module: str = "global",
        user_id: str | None = None,
        workspace_id: str | None = None,
        email: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        meta = metadata or {}
        raw_text = json.dumps(meta)
        findings = detect_pii(raw_text)
        redacted = bool(findings)
        if redacted:
            meta = sanitize_metadata(meta)

        event = AuditEvent(
            action=action,
            module=module,
            user_id=user_id,
            workspace_id=workspace_id,
            email=email,
            metadata=meta,
            timestamp=time.time(),
            pii_redacted=redacted,
        )
        self._queue.put(event)
        return event

    def _flush(self, events: list[AuditEvent]):
        if not self._supabase_url or not self._supabase_key:
            return

        rows = []
        for ev in events:
            rows.append({
                "action": ev.action,
                "module": ev.module,
                "user_id": ev.user_id,
                "workspace_id": ev.workspace_id,
                "email": ev.email,
                "metadata": ev.metadata,
                "timestamp": datetime.fromtimestamp(ev.timestamp, tz=timezone.utc).isoformat(),
                "pii_redacted": ev.pii_redacted,
                "archived": False,
                "review_status": "pending",
            })

        try:
            requests.post(
                f"{self._supabase_url}/rest/v1/audit_logs",
                headers={
                    "apikey": self._supabase_key,
                    "Authorization": f"Bearer {self._supabase_key}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates",
                },
                json=rows,
                timeout=10,
            )
        except Exception:
            # Logging must never break the main flow
            pass

    # === Audit query ======================================================
    def query_audit(
        self,
        workspace_id: str | None = None,
        action: str | None = None,
        module: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Query audit logs from Supabase with optional filters."""
        if not self._supabase_url or not self._supabase_key:
            return {"ok": True, "rows": [], "count": 0, "limit": limit, "offset": offset}

        params = {"limit": min(limit, 1000), "offset": offset, "order": "timestamp.desc"}
        conditions = []
        if workspace_id:
            conditions.append(f"workspace_id.eq.{workspace_id}")
        if action:
            conditions.append(f"action.eq.{action}")
        if module:
            conditions.append(f"module.eq.{module}")
        if conditions:
            params["and"] = "(" + ",".join(conditions) + ")"

        try:
            resp = requests.get(
                f"{self._supabase_url}/rest/v1/audit_logs",
                headers={
                    "apikey": self._supabase_key,
                    "Authorization": f"Bearer {self._supabase_key}",
                    "Accept": "application/json",
                },
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            rows = resp.json()
            return {"ok": True, "rows": rows, "count": len(rows), "limit": limit, "offset": offset}
        except Exception as e:
            return {"ok": False, "error": str(e), "rows": [], "count": 0, "limit": limit, "offset": offset}

    def export_audit(self, rows: list[dict[str, Any]], format: str = "json") -> dict[str, Any]:
        """Export audit rows with PII redaction applied to every metadata field."""
        sanitized = [sanitize_metadata(row) for row in rows]
        return {"ok": True, "format": format, "count": len(sanitized), "rows": sanitized}

    def run_pii_scan(self, workspace_id: str | None = None) -> dict[str, Any]:
        """Scan recent audit metadata for PII and return findings."""
        result = self.query_audit(workspace_id=workspace_id, limit=500)
        rows = result.get("rows", [])
        findings = []
        for row in rows:
            meta = row.get("metadata") or {}
            text = json.dumps(meta)
            if pii := detect_pii(text):
                findings.append({
                    "audit_id": row.get("id"),
                    "action": row.get("action"),
                    "module": row.get("module"),
                    "pii_findings": pii,
                })
        status = "failed" if findings else "success"
        return {"ok": True, "check_type": "pii_scan", "status": status, "findings": findings, "scanned": len(rows)}

    def run_retention_check(self, workspace_id: str | None = None) -> dict[str, Any]:
        """Check whether audit logs exceed configured retention."""
        if not self._supabase_url or not self._supabase_key:
            return {"ok": True, "check_type": "retention_run", "status": "warning", "findings": [], "note": "Supabase not configured"}

        policy = self.get_retention_policy(workspace_id)
        retention_days = policy.get("retention_days", 365)

        try:
            cutoff = (datetime.now(timezone.utc).timestamp() - (retention_days * 24 * 3600))
            resp = requests.get(
                f"{self._supabase_url}/rest/v1/audit_logs",
                headers={
                    "apikey": self._supabase_key,
                    "Authorization": f"Bearer {self._supabase_key}",
                    "Accept": "application/json",
                },
                params={
                    "limit": 1,
                    "select": "count",
                    "lt": f"timestamp.{datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()}",
                },
                timeout=10,
            )
            resp.raise_for_status()
            rows = resp.json()
            count = rows[0].get("count", 0) if rows else 0
            status = "success" if count == 0 else "warning"
            return {"ok": True, "check_type": "retention_run", "status": status, "findings": [f"{count} rows older than {retention_days} days"]}
        except Exception as e:
            return {"ok": False, "check_type": "retention_run", "status": "failed", "findings": [str(e)]}

    def run_consent_audit(self, workspace_id: str | None = None) -> dict[str, Any]:
        """Return a consent audit placeholder — real implementation would query consent_logs."""
        return {"ok": True, "check_type": "consent_audit", "status": "success", "findings": [], "note": "Consent audit stub; populate consent_logs for real checks"}

    def run_role_review(self, workspace_id: str | None = None) -> dict[str, Any]:
        """Return a role review placeholder."""
        return {"ok": True, "check_type": "role_review", "status": "success", "findings": [], "note": "Role review stub; implement workspace membership query"}

    def run_compliance_check(self, check_type: str, workspace_id: str | None = None) -> dict[str, Any]:
        if check_type == "pii_scan":
            return self.run_pii_scan(workspace_id)
        if check_type == "retention_run":
            return self.run_retention_check(workspace_id)
        if check_type == "consent_audit":
            return self.run_consent_audit(workspace_id)
        if check_type == "role_review":
            return self.run_role_review(workspace_id)
        return {"ok": False, "error": f"unknown check_type: {check_type}"}

    # === Retention policies ================================================
    def get_retention_policy(self, workspace_id: str | None = None) -> dict[str, Any]:
        if not self._supabase_url or not self._supabase_key:
            return {"workspace_id": workspace_id, "retention_days": 365, "action": "archive"}
        try:
            params = {"limit": 1}
            if workspace_id:
                params["workspace_id"] = f"eq.{workspace_id}"
            resp = requests.get(
                f"{self._supabase_url}/rest/v1/retention_policies",
                headers={
                    "apikey": self._supabase_key,
                    "Authorization": f"Bearer {self._supabase_key}",
                    "Accept": "application/json",
                },
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            rows = resp.json()
            if rows:
                return rows[0]
            return {"workspace_id": workspace_id, "retention_days": 365, "action": "archive"}
        except Exception as e:
            return {"workspace_id": workspace_id, "retention_days": 365, "action": "archive", "error": str(e)}

    def set_retention_policy(self, workspace_id: str, retention_days: int, action: str = "archive") -> dict[str, Any]:
        if not self._supabase_url or not self._supabase_key:
            return {"ok": False, "error": "Supabase not configured"}
        try:
            resp = requests.post(
                f"{self._supabase_url}/rest/v1/retention_policies",
                headers={
                    "apikey": self._supabase_key,
                    "Authorization": f"Bearer {self._supabase_key}",
                    "Content-Type": "application/json",
                    "Prefer": "resolution=merge-duplicates",
                },
                json={
                    "workspace_id": workspace_id,
                    "table_name": "audit_logs",
                    "retention_days": retention_days,
                    "action": action,
                },
                timeout=10,
            )
            resp.raise_for_status()
            return {"ok": True, "workspace_id": workspace_id, "retention_days": retention_days, "action": action}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def shutdown(self):
        self._queue.put(None)
        self._worker.join(timeout=5)


# === Singleton =============================================================
_governance: GovernanceManager | None = None


def get_governance() -> GovernanceManager:
    global _governance
    if _governance is None:
        _governance = GovernanceManager()
    return _governance
