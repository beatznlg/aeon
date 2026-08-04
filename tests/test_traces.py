"""Regression coverage for AEON OS LLM execution tracing.

Covers the trace store lifecycle, span recording, tenant isolation, summary
statistics, and the read-only /traces routes.
"""

from __future__ import annotations

import uuid

from aeon_traces import TraceStore, reset_trace_store


def _register(client, label: str) -> tuple[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": f"traces-{label}-{uuid.uuid4().hex[:8]}@test.local",
            "password": "secure123",
            "name": f"Traces {label}",
        },
    )
    assert response.status_code == 201, response.get_json()
    data = response.get_json()
    return data["token"], data["user"]["workspace_id"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── store lifecycle ─────────────────────────────────────────────────────────


def test_store_lifecycle_records_spans_and_summary(tmp_path) -> None:
    store = TraceStore(tmp_path)
    trace = store.start_trace("ws-a", agent_id="agent-1", query="analyze risk", model="stub", backend="stub")
    assert trace.status == "running"

    tool_span = store.add_span(trace.trace_id, "ws-a", "tool", "math", tool="math", input_summary={"expr": "1+1"})
    assert tool_span is not None
    store.finish_span(tool_span, status="ok", output_summary="2")

    finished = store.end_trace(trace.trace_id, "ws-a", tokens=42, output_summary="done")
    assert finished is not None
    assert finished.status == "ok"
    assert finished.tokens == 42
    assert finished.tool_count == 1
    assert finished.tools == ["math"]

    listed = store.list_traces("ws-a")
    assert len(listed) == 1
    assert listed[0]["trace_id"] == trace.trace_id
    assert listed[0]["tool_count"] == 1
    assert "spans" not in listed[0]

    detail = store.get_trace(trace.trace_id, "ws-a")
    assert detail is not None
    assert len(detail["spans"]) == 1
    assert detail["spans"][0]["kind"] == "tool"
    assert detail["spans"][0]["latency_ms"] >= 0

    summary = store.summary("ws-a", days=7)
    assert summary["traces"] == 1
    assert summary["tool_calls"] == 1
    assert summary["tokens"] == 42
    assert summary["errors"] == 0
    assert summary["error_rate"] == 0.0


def test_store_tenant_isolation(tmp_path) -> None:
    store = TraceStore(tmp_path)
    trace = store.start_trace("ws-a", query="secret")
    store.add_span(trace.trace_id, "ws-a", "tool", "search", tool="search")

    # Other workspace cannot see the trace or mutate it.
    assert store.get_trace(trace.trace_id, "ws-b") is None
    assert store.add_span(trace.trace_id, "ws-b", "tool", "x", tool="x") is None
    assert store.end_trace(trace.trace_id, "ws-b") is None
    assert store.list_traces("ws-b") == []
    assert store.summary("ws-b")["traces"] == 0


def test_store_error_status_and_percentiles(tmp_path) -> None:
    store = TraceStore(tmp_path)
    trace = store.start_trace("ws-a", query="boom")
    store.end_trace(trace.trace_id, "ws-a", status="error", error="timeout", tokens=10)
    summary = store.summary("ws-a")
    assert summary["errors"] == 1
    assert summary["error_rate"] == 1.0
    listed = store.list_traces("ws-a", status="error")
    assert len(listed) == 1
    assert store.list_traces("ws-a", status="ok") == []


# ── routes ──────────────────────────────────────────────────────────────────


def test_trace_routes_require_auth(client) -> None:
    assert client.get("/traces").status_code == 401
    assert client.get("/traces/summary").status_code == 401
    assert client.get("/traces/abc").status_code == 401


def test_trace_routes_list_and_detail(client) -> None:
    token, workspace_id = _register(client, "list")
    store = TraceStore(__import__("pathlib").Path(__import__("os").environ["AEON_ROOT"]))
    trace = store.start_trace(workspace_id, agent_id="a1", query="hello")
    store.end_trace(trace.trace_id, workspace_id, status="ok", tokens=7)

    response = client.get("/traces", headers=_headers(token))
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["count"] >= 1

    response = client.get(f"/traces/{trace.trace_id}", headers=_headers(token))
    assert response.status_code == 200
    assert response.get_json()["trace"]["tokens"] == 7

    response = client.get("/traces/summary?days=7", headers=_headers(token))
    assert response.status_code == 200
    assert response.get_json()["summary"]["traces"] >= 1

    # Tenant isolation at the route level.
    token_b, _ = _register(client, "other")
    response = client.get(f"/traces/{trace.trace_id}", headers=_headers(token_b))
    assert response.status_code == 404


def test_trace_routes_validate_status_filter(client) -> None:
    token, _ = _register(client, "filter")
    response = client.get("/traces?status=banana", headers=_headers(token))
    assert response.status_code == 400


def test_reset_singleton(tmp_path) -> None:
    reset_trace_store()
    store = TraceStore(tmp_path)
    trace = store.start_trace("ws", query="x")
    assert trace.trace_id
