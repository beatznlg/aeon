"""AEON OS — LLM execution tracing (observability).

Records execution traces for agent runs: one trace per ``act()`` tick with
spans for the LLM call and every tool invocation. Spans capture latency,
token usage, model backend, status, and short input/output summaries so
operators can audit what an agent did and why without storing raw payloads.

Traces are stored as one JSON file per trace under ``<root>/traces/`` so the
store stays lock-friendly and independent of SQL/state-file migrations. All
queries are workspace-scoped; ``get_trace`` and ``add_span`` enforce tenant
isolation by requiring the caller's workspace id.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TRACE_VERSION = 1
_SPAN_KINDS = {"agent", "llm", "tool", "workflow", "mcp"}
_SPAN_STATUSES = {"ok", "error", "running"}

_TRACE_STORE: TraceStore | None = None
_TRACE_STORE_LOCK = threading.Lock()


def _generate_id() -> str:
    return uuid.uuid4().hex[:16]


def _now() -> float:
    return time.time()


def _iso(ts: float | None = None) -> str:
    stamp = ts if ts is not None else time.time()
    return datetime.fromtimestamp(stamp, tz=timezone.utc).isoformat()


def _short(text: Any, limit: int = 240) -> str:
    """Summarize an arbitrary value for trace storage (no raw secrets)."""
    if text is None:
        return ""
    if not isinstance(text, str):
        try:
            text = json.dumps(text, ensure_ascii=False, default=str)[:limit]
        except Exception:
            text = str(text)
    return text[:limit]


@dataclass
class TraceSpan:
    """A single step inside a trace (LLM call or tool invocation)."""

    span_id: str
    trace_id: str
    workspace_id: str
    kind: str
    name: str
    status: str
    started_at: float
    ended_at: float | None = None
    model: str = ""
    tool: str = ""
    tokens: int = 0
    latency_ms: int = 0
    input_summary: str = ""
    output_summary: str = ""
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def finish(self, status: str = "ok", output_summary: Any = "", error: str = "") -> None:
        self.ended_at = _now()
        self.latency_ms = int((self.ended_at - self.started_at) * 1000)
        self.status = status
        self.output_summary = _short(output_summary)
        self.error = _short(error, limit=500)

    def to_dict(self) -> dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "workspace_id": self.workspace_id,
            "kind": self.kind,
            "name": self.name,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "model": self.model,
            "tool": self.tool,
            "tokens": self.tokens,
            "latency_ms": self.latency_ms,
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TraceSpan:
        return cls(
            span_id=data["span_id"],
            trace_id=data["trace_id"],
            workspace_id=data["workspace_id"],
            kind=data.get("kind", "agent"),
            name=data.get("name", "step"),
            status=data.get("status", "ok"),
            started_at=float(data.get("started_at", 0)),
            ended_at=data.get("ended_at"),
            model=data.get("model", ""),
            tool=data.get("tool", ""),
            tokens=int(data.get("tokens", 0)),
            latency_ms=int(data.get("latency_ms", 0)),
            input_summary=data.get("input_summary", ""),
            output_summary=data.get("output_summary", ""),
            error=data.get("error", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Trace:
    """A workspace-scoped execution trace (one agent tick)."""

    trace_id: str
    workspace_id: str
    agent_id: str
    query: str
    status: str
    created_at: float
    ended_at: float | None = None
    model: str = ""
    backend: str = ""
    tokens: int = 0
    latency_ms: int = 0
    tool_count: int = 0
    tools: list[str] = field(default_factory=list)
    spans: list[TraceSpan] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "workspace_id": self.workspace_id,
            "agent_id": self.agent_id,
            "query": self.query,
            "status": self.status,
            "created_at": self.created_at,
            "created_iso": _iso(self.created_at),
            "ended_at": self.ended_at,
            "model": self.model,
            "backend": self.backend,
            "tokens": self.tokens,
            "latency_ms": self.latency_ms,
            "tool_count": self.tool_count,
            "tools": self.tools,
            "error": self.error,
            "spans": [span.to_dict() for span in self.spans],
            "version": TRACE_VERSION,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Trace:
        return cls(
            trace_id=data["trace_id"],
            workspace_id=data["workspace_id"],
            agent_id=data.get("agent_id", ""),
            query=data.get("query", ""),
            status=data.get("status", "ok"),
            created_at=float(data.get("created_at", 0)),
            ended_at=data.get("ended_at"),
            model=data.get("model", ""),
            backend=data.get("backend", ""),
            tokens=int(data.get("tokens", 0)),
            latency_ms=int(data.get("latency_ms", 0)),
            tool_count=int(data.get("tool_count", 0)),
            tools=list(data.get("tools", [])),
            spans=[TraceSpan.from_dict(span) for span in data.get("spans", [])],
            error=data.get("error", ""),
        )


class TraceStore:
    """Append-style per-trace JSON store with workspace isolation."""

    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root)
        self._traces_dir = self.root / "traces"
        self._lock = threading.Lock()

    # -- persistence ---------------------------------------------------------
    def _path(self, trace_id: str) -> Path:
        return self._traces_dir / f"{trace_id}.json"

    def _load_trace(self, trace_id: str) -> Trace | None:
        path = self._path(trace_id)
        if not path.exists():
            return None
        try:
            return Trace.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None

    def _save_trace(self, trace: Trace) -> None:
        self._traces_dir.mkdir(parents=True, exist_ok=True)
        path = self._path(trace.trace_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(trace.to_dict(), ensure_ascii=False, sort_keys=True), encoding="utf-8")
        tmp.replace(path)

    # -- lifecycle -----------------------------------------------------------
    def start_trace(
        self,
        workspace_id: str,
        agent_id: str = "",
        query: str = "",
        model: str = "",
        backend: str = "",
    ) -> Trace:
        trace = Trace(
            trace_id=_generate_id(),
            workspace_id=workspace_id,
            agent_id=agent_id,
            query=_short(query, limit=500),
            status="running",
            created_at=_now(),
            model=model,
            backend=backend,
        )
        with self._lock:
            self._save_trace(trace)
        return trace

    def add_span(
        self,
        trace_id: str,
        workspace_id: str,
        kind: str,
        name: str,
        *,
        model: str = "",
        tool: str = "",
        input_summary: Any = "",
    ) -> TraceSpan | None:
        if kind not in _SPAN_KINDS:
            kind = "agent"
        span = TraceSpan(
            span_id=_generate_id(),
            trace_id=trace_id,
            workspace_id=workspace_id,
            kind=kind,
            name=name[:120],
            status="running",
            started_at=_now(),
            model=model,
            tool=tool,
            input_summary=_short(input_summary),
        )
        with self._lock:
            trace = self._load_trace(trace_id)
            if trace is None or trace.workspace_id != workspace_id:
                return None
            trace.spans.append(span)
            trace.tool_count = sum(1 for s in trace.spans if s.kind == "tool")
            trace.tools = [s.tool for s in trace.spans if s.tool]
            self._save_trace(trace)
        return span

    def finish_span(self, span: TraceSpan, status: str = "ok", output_summary: Any = "", error: str = "") -> None:
        span.finish(status=status, output_summary=output_summary, error=error)

    def end_trace(
        self,
        trace_id: str,
        workspace_id: str,
        status: str = "ok",
        error: str = "",
        tokens: int = 0,
        latency_ms: int | None = None,
        output_summary: Any = "",
    ) -> Trace | None:
        with self._lock:
            trace = self._load_trace(trace_id)
            if trace is None or trace.workspace_id != workspace_id:
                return None
            trace.status = status
            trace.error = _short(error, limit=500)
            trace.tokens = max(trace.tokens, tokens)
            trace.ended_at = _now()
            trace.latency_ms = int(latency_ms or ((trace.ended_at - trace.created_at) * 1000))
            if output_summary:
                for span in reversed(trace.spans):
                    if not span.output_summary:
                        span.output_summary = _short(output_summary)
                        break
            self._save_trace(trace)
        return trace

    # -- queries -------------------------------------------------------------
    def list_traces(self, workspace_id: str, limit: int = 50, offset: int = 0, status: str | None = None) -> list[dict[str, Any]]:
        traces = self._all_traces(workspace_id)
        if status:
            traces = [t for t in traces if t.status == status]
        traces.sort(key=lambda t: t.created_at, reverse=True)
        items = []
        for trace in traces[offset : offset + limit]:
            data = trace.to_dict()
            data["span_count"] = len(trace.spans)
            data.pop("spans", None)
            items.append(data)
        return items

    def get_trace(self, trace_id: str, workspace_id: str) -> dict[str, Any] | None:
        trace = self._load_trace(trace_id)
        if trace is None or trace.workspace_id != workspace_id:
            return None
        return trace.to_dict()

    def _all_traces(self, workspace_id: str) -> list[Trace]:
        if not self._traces_dir.exists():
            return []
        traces: list[Trace] = []
        for path in self._traces_dir.glob("*.json"):
            trace = self._load_trace(path.stem)
            if trace is not None and trace.workspace_id == workspace_id:
                traces.append(trace)
        return traces

    def summary(self, workspace_id: str, days: int = 7) -> dict[str, Any]:
        cutoff = _now() - max(1, days) * 86400
        traces = [t for t in self._all_traces(workspace_id) if t.created_at >= cutoff]
        completed = [t for t in traces if t.status != "running"]
        latencies = [t.latency_ms for t in completed if t.latency_ms > 0]
        error_count = sum(1 for t in traces if t.status == "error")
        tool_calls = sum(t.tool_count for t in traces)
        tokens = sum(t.tokens for t in traces)
        return {
            "workspace_id": workspace_id,
            "days": days,
            "traces": len(traces),
            "completed": len(completed),
            "running": sum(1 for t in traces if t.status == "running"),
            "errors": error_count,
            "error_rate": round(error_count / len(traces), 4) if traces else 0.0,
            "tool_calls": tool_calls,
            "tokens": tokens,
            "avg_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
            "p50_latency_ms": _percentile(latencies, 50) if latencies else 0,
            "p95_latency_ms": _percentile(latencies, 95) if latencies else 0,
            "p99_latency_ms": _percentile(latencies, 99) if latencies else 0,
            "models": sorted({t.model for t in traces if t.model}),
        }


def _percentile(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    index = max(0, int((percentile / 100.0) * len(ordered)) - 1)
    return ordered[index]


def get_trace_store(root: str | os.PathLike[str] | None = None) -> TraceStore:
    """Return the process-wide trace store bound to AEON_ROOT."""
    global _TRACE_STORE
    with _TRACE_STORE_LOCK:
        if _TRACE_STORE is None:
            base = Path(root or os.environ.get("AEON_ROOT", ""))
            if not base or not base.exists():
                base = Path.cwd()
            _TRACE_STORE = TraceStore(base)
        return _TRACE_STORE


def reset_trace_store() -> None:
    """Reset the singleton (used by tests)."""
    global _TRACE_STORE
    with _TRACE_STORE_LOCK:
        _TRACE_STORE = None
