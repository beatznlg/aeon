"""Regression coverage for the SLO/load-test evidence tooling.

Tests the pure SLO evaluation logic, the markdown renderer, and the offline
load-harness request path against a tiny local HTTP server.
"""

from __future__ import annotations

import http.server
import threading

from scripts.slo_report import _percentile, compute_slos, render_markdown

SAMPLE_REPORT = {
    "generated_at": "2026-08-04T00:00:00+00:00",
    "concurrency": 10,
    "total_requests": 200,
    "endpoints": {
        "/health": {
            "requests": 100,
            "errors": 0,
            "latencies_ms": [50, 60, 70, 80, 90, 100, 110, 120, 130, 140],
            "status_codes": {"200": 100},
        },
        "/chat": {
            "requests": 100,
            "errors": 10,
            "latencies_ms": [200, 400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000],
            "status_codes": {"200": 90, "500": 10},
        },
    },
}


def test_compute_slos_meets_targets() -> None:
    results = compute_slos(SAMPLE_REPORT)
    endpoints = {entry["endpoint"]: entry for entry in results["endpoints"]}

    health = endpoints["/health"]
    assert health["availability_pct"] == 100.0
    assert health["all_met"] is True

    chat = endpoints["/chat"]
    assert chat["error_rate_pct"] == 10.0
    assert chat["met"]["availability"] is False  # 90% < 99.9%
    assert chat["all_met"] is False

    overall = results["overall"]
    assert overall["requests"] == 200
    assert overall["errors"] == 10
    assert overall["availability_pct"] == 95.0
    assert overall["met"]["availability"] is False
    assert overall["all_met"] is False


def test_compute_slos_passes_when_healthy() -> None:
    healthy = {
        "endpoints": {
            "/health": {
                "requests": 200,
                "errors": 0,
                "latencies_ms": [30, 40, 45, 50, 55, 60, 65, 70, 75, 80],
            }
        }
    }
    results = compute_slos(healthy)
    assert results["overall"]["all_met"] is True
    assert results["overall"]["latency"]["p99_ms"] <= 80


def test_compute_slos_with_custom_targets() -> None:
    results = compute_slos(SAMPLE_REPORT, targets={"availability_pct": 90.0, "error_rate_pct": 10.0})
    chat = next(entry for entry in results["endpoints"] if entry["endpoint"] == "/chat")
    assert chat["met"]["availability"] is True
    assert chat["met"]["error_rate"] is True


def test_percentile_helper() -> None:
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert _percentile(sorted(values), 50) == 5
    assert _percentile(sorted(values), 100) == 10
    assert _percentile([], 50) == 0.0


def test_render_markdown_includes_pass_fail() -> None:
    results = compute_slos(SAMPLE_REPORT)
    markdown = render_markdown(results)
    assert "# AEON OS — SLO Evidence Report" in markdown
    assert "NOT met" in markdown
    assert "| /health |" in markdown
    assert "PASS" in markdown and "FAIL" in markdown


def test_loadtest_request_against_local_server() -> None:
    from scripts.loadtest_api import _request

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):  # silence
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        result = _request(f"http://127.0.0.1:{port}", "/health", token=None, timeout=5)
        assert result["ok"] is True
        assert result["status"] == 200
        assert result["latency_ms"] >= 0
    finally:
        server.shutdown()


def test_loadtest_request_error_path() -> None:
    from scripts.loadtest_api import _request

    result = _request("http://127.0.0.1:1", "/health", token=None, timeout=1)
    assert result["ok"] is False
    assert result["latency_ms"] >= 0
