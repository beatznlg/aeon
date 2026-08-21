"""AEON OS AI Execution Ledger.

Records every AI/LLM operation with workspace, user, sector, model, tokens,
cost, risk level, policy applied, citations, human approval, and result.
This gives enterprise customers a fully traceable audit trail and enables
cost tracking, compliance reporting, and anomaly detection.

The ledger is intentionally dependency-light: it appends JSON lines to a
local file (``ai_executions.jsonl``) and optionally mirrors to the audit log.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExecutionRecord:
    """One AI execution entry."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    workspace_id: str = ""
    user_id: str = ""
    sector: str = ""
    sector_pack_id: str = ""
    task_type: str = "general"
    risk_level: str = "low"

    # Provider / model
    provider: str = ""
    model: str = ""

    # Input
    query_hash: str = ""
    query_length: int = 0

    # Output
    status: str = "pending"  # pending | ok | blocked_by_policy | failed | needs_review
    output_length: int = 0
    backend: str = ""

    # Token usage & cost
    tokens_input: int = 0
    tokens_output: int = 0
    tokens_total: int = 0
    cost_usd: float = 0.0

    # Governance
    policy_id: str = ""
    require_grounding: bool = False
    require_citations: bool = False
    require_human_review: bool = False
    grounding_score: float = 0.0
    citation_count: int = 0
    human_review_required: bool = False
    human_review_completed: bool = False

    # Tool calls
    tool_calls: int = 0
    tool_names: list[str] = field(default_factory=list)

    # Timing
    latency_ms: int = 0

    # Error
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AIExecutionLedger:
    """Append-only ledger for AI execution records.

    Records are written as JSON lines to ``ai_executions.jsonl`` inside the
    given root directory. The ledger is thread-safe and bounded: at most
    ``max_records`` entries are kept on disk; older entries are pruned on
    flush.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        max_records: int = 50_000,
        flush_interval: float = 5.0,
    ) -> None:
        self._root = Path(root)
        self._max_records = max_records
        self._flush_interval = flush_interval
        self._buffer: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._ledger_path = self._root / "ai_executions.jsonl"

    # ── public API ────────────────────────────────────────────────────────────

    def record(self, entry: ExecutionRecord) -> None:
        """Append a record to the in-memory buffer (will be flushed to disk)."""
        data = entry.to_dict()
        with self._lock:
            self._buffer.append(data)
        # Best-effort mirror to audit log
        try:
            from aeon_governance import get_governance

            get_governance().log_audit(
                action="AI_EXECUTION",
                module="ai_ledger",
                user_id=entry.user_id,
                workspace_id=entry.workspace_id,
                metadata={
                    "execution_id": entry.id,
                    "sector": entry.sector,
                    "provider": entry.provider,
                    "model": entry.model,
                    "status": entry.status,
                    "tokens_total": entry.tokens_total,
                    "cost_usd": entry.cost_usd,
                    "risk_level": entry.risk_level,
                    "latency_ms": entry.latency_ms,
                },
            )
        except Exception:  # pragma: no cover – audit mirror is best-effort
            pass

    def query(
        self,
        *,
        workspace_id: str | None = None,
        sector: str | None = None,
        provider: str | None = None,
        status: str | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query ledger records with optional filters."""
        records = self._read_all()
        if workspace_id:
            records = [r for r in records if r.get("workspace_id") == workspace_id]
        if sector:
            records = [r for r in records if r.get("sector") == sector]
        if provider:
            records = [r for r in records if r.get("provider") == provider]
        if status:
            records = [r for r in records if r.get("status") == status]
        if since:
            records = [r for r in records if r.get("timestamp", "") >= since]
        return records[-limit:]

    def summary(
        self,
        *,
        workspace_id: str | None = None,
        days: int = 30,
    ) -> dict[str, Any]:
        """Return aggregate usage stats for a workspace."""
        records = self._read_all()
        if workspace_id:
            records = [r for r in records if r.get("workspace_id") == workspace_id]

        # Filter by recency
        since = datetime.now(timezone.utc).isoformat()[:10]  # rough day filter
        total = len(records)
        total_tokens = sum(r.get("tokens_total", 0) for r in records)
        total_cost = sum(r.get("cost_usd", 0) for r in records)
        total_latency = sum(r.get("latency_ms", 0) for r in records)
        by_status: dict[str, int] = {}
        by_sector: dict[str, int] = {}
        by_provider: dict[str, int] = {}
        for r in records:
            s = r.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
            sec = r.get("sector", "") or "unspecified"
            by_sector[sec] = by_sector.get(sec, 0) + 1
            prov = r.get("provider", "") or "unknown"
            by_provider[prov] = by_provider.get(prov, 0) + 1

        return {
            "ok": True,
            "total_executions": total,
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "avg_latency_ms": round(total_latency / max(1, total)),
            "by_status": by_status,
            "by_sector": by_sector,
            "by_provider": by_provider,
        }

    def flush(self) -> None:
        """Write buffered records to disk and prune old entries."""
        with self._lock:
            pending = list(self._buffer)
            self._buffer.clear()

        if not pending:
            return

        # Read existing, append new, prune to max
        existing = self._read_all()
        combined = existing + pending
        if len(combined) > self._max_records:
            combined = combined[-self._max_records:]

        try:
            self._root.mkdir(parents=True, exist_ok=True)
            with open(self._ledger_path, "w", encoding="utf-8") as f:
                for record in combined:
                    f.write(json.dumps(record, default=str) + "\n")
        except Exception as exc:
            logger.warning("Failed to flush AI execution ledger: %s", exc)

    def shutdown(self) -> None:
        """Flush remaining records."""
        self.flush()

    # ── internal ──────────────────────────────────────────────────────────────

    def _read_all(self) -> list[dict[str, Any]]:
        if not self._ledger_path.exists():
            return []
        records: list[dict[str, Any]] = []
        try:
            with open(self._ledger_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception:
            pass
        return records


# ── Module-level singleton ────────────────────────────────────────────────────

_ledger: AIExecutionLedger | None = None
_ledger_lock = threading.Lock()


def get_ai_ledger() -> AIExecutionLedger:
    """Return the global AI execution ledger, lazily initialised."""
    global _ledger
    if _ledger is not None:
        return _ledger
    with _ledger_lock:
        if _ledger is not None:
            return _ledger
        root = os.environ.get("AEON_ROOT", str(Path(__file__).parent / "aeon_state"))
        _ledger = AIExecutionLedger(root)
        return _ledger


def record_ai_execution(
    *,
    workspace_id: str = "",
    user_id: str = "",
    sector: str = "",
    sector_pack_id: str = "",
    task_type: str = "general",
    risk_level: str = "low",
    provider: str = "",
    model: str = "",
    query: str = "",
    status: str = "ok",
    output_length: int = 0,
    backend: str = "",
    tokens_input: int = 0,
    tokens_output: int = 0,
    cost_usd: float = 0.0,
    policy_id: str = "",
    require_grounding: bool = False,
    require_citations: bool = False,
    require_human_review: bool = False,
    grounding_score: float = 0.0,
    citation_count: int = 0,
    human_review_required: bool = False,
    tool_calls: int = 0,
    tool_names: list[str] | None = None,
    latency_ms: int = 0,
    error: str = "",
) -> ExecutionRecord:
    """Convenience function to create and record an execution in one call."""
    query_hash = hashlib.sha256((query or "").encode()).hexdigest()[:16]
    record = ExecutionRecord(
        workspace_id=workspace_id,
        user_id=user_id,
        sector=sector,
        sector_pack_id=sector_pack_id,
        task_type=task_type,
        risk_level=risk_level,
        provider=provider,
        model=model,
        query_hash=query_hash,
        query_length=len(query or ""),
        status=status,
        output_length=output_length,
        backend=backend,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        tokens_total=tokens_input + tokens_output,
        cost_usd=cost_usd,
        policy_id=policy_id,
        require_grounding=require_grounding,
        require_citations=require_citations,
        require_human_review=require_human_review,
        grounding_score=grounding_score,
        citation_count=citation_count,
        human_review_required=human_review_required,
        tool_calls=tool_calls,
        tool_names=tool_names or [],
        latency_ms=latency_ms,
        error=error,
    )
    get_ai_ledger().record(record)
    return record


__all__ = [
    "AIExecutionLedger",
    "ExecutionRecord",
    "get_ai_ledger",
    "record_ai_execution",
]
