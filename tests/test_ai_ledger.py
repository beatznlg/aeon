"""Regression tests for the AI Execution Ledger (aeon_ai_ledger).

Verifies that:
- Records are created and stored correctly
- Query filtering works (workspace, sector, provider, status)
- Summary aggregates tokens, cost, latency, and dimensions
- The ledger flushes to disk and reads back correctly
- The convenience function creates records properly
- Shutdown flushes the buffer
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from aeon_ai_ledger import (
    AIExecutionLedger,
    ExecutionRecord,
    get_ai_ledger,
    record_ai_execution,
)


def _make_record(**overrides) -> ExecutionRecord:
    defaults = dict(
        workspace_id="ws-test",
        user_id="u-1",
        sector="health",
        provider="openai",
        model="gpt-4",
        query_hash="abc123",
        query_length=10,
        status="ok",
        tokens_output=100,
        tokens_total=100,
        cost_usd=0.003,
        latency_ms=500,
    )
    defaults.update(overrides)
    return ExecutionRecord(**defaults)


def test_record_and_query():
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger = AIExecutionLedger(tmpdir)
        rec = _make_record()
        ledger.record(rec)
        ledger.flush()

        # Read back
        records = ledger.query(workspace_id="ws-test")
        assert len(records) == 1
        assert records[0]["workspace_id"] == "ws-test"
        assert records[0]["provider"] == "openai"
        assert records[0]["tokens_total"] == 100


def test_query_filters():
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger = AIExecutionLedger(tmpdir)
        ledger.record(_make_record(workspace_id="ws-a", sector="health", provider="openai", status="ok"))
        ledger.record(_make_record(workspace_id="ws-b", sector="finance", provider="anthropic", status="failed"))
        ledger.record(_make_record(workspace_id="ws-a", sector="finance", provider="openai", status="ok"))
        ledger.flush()

        # Filter by sector
        health = ledger.query(workspace_id="ws-a", sector="health")
        assert len(health) == 1

        # Filter by status
        failed = ledger.query(status="failed")
        assert len(failed) == 1
        assert failed[0]["workspace_id"] == "ws-b"

        # Filter by provider
        anthropic = ledger.query(provider="anthropic")
        assert len(anthropic) == 1


def test_summary_aggregation():
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger = AIExecutionLedger(tmpdir)
        ledger.record(_make_record(workspace_id="ws-x", tokens_output=100, tokens_total=100, cost_usd=0.003, latency_ms=200))
        ledger.record(_make_record(workspace_id="ws-x", tokens_output=200, tokens_total=200, cost_usd=0.006, latency_ms=400))
        ledger.record(_make_record(workspace_id="ws-y", tokens_output=50, tokens_total=50, cost_usd=0.001, latency_ms=100))
        ledger.flush()

        summary = ledger.summary(workspace_id="ws-x")
        assert summary["ok"] is True
        assert summary["total_executions"] == 2
        assert summary["total_tokens"] == 300
        assert abs(summary["total_cost_usd"] - 0.009) < 1e-6
        assert summary["avg_latency_ms"] == 300


def test_flush_prunes_old_records():
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger = AIExecutionLedger(tmpdir, max_records=5)
        for i in range(10):
            ledger.record(_make_record(query_hash=f"q{i}", query_length=i))
        ledger.flush()

        records = ledger.query()
        assert len(records) == 5
        # Most recent records should be kept
        assert records[-1]["query_length"] > 0


def test_convenience_function():
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger = AIExecutionLedger(tmpdir)
        # Monkey-patch the global singleton for this test
        import aeon_ai_ledger as mod
        old = mod._ledger
        mod._ledger = ledger
        try:
            rec = record_ai_execution(
                workspace_id="ws-conv",
                user_id="u-conv",
                sector="cybersecurity",
                query="test convenience",
                status="ok",
                tokens_output=50,
                latency_ms=100,
            )
            assert isinstance(rec, ExecutionRecord)
            assert rec.workspace_id == "ws-conv"
            assert rec.sector == "cybersecurity"
            assert rec.tokens_total == 50

            # Verify stored
            ledger.flush()
            records = ledger.query(workspace_id="ws-conv")
            assert len(records) == 1
            assert records[0]["sector"] == "cybersecurity"
        finally:
            mod._ledger = old


def test_shutdown_flushes():
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger = AIExecutionLedger(tmpdir)
        ledger.record(_make_record())
        assert len(ledger._buffer) == 1
        ledger.shutdown()
        assert len(ledger._buffer) == 0
        records = ledger.query()
        assert len(records) == 1


def test_execution_record_to_dict():
    rec = ExecutionRecord(workspace_id="ws-1", status="ok")
    d = rec.to_dict()
    assert d["workspace_id"] == "ws-1"
    assert d["query_length"] == 0
    assert d["status"] == "ok"
    assert "id" in d
    assert "timestamp" in d
