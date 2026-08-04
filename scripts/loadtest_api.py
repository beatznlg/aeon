#!/usr/bin/env python3
"""AEON OS — concurrent API load harness.

Drives concurrent HTTP requests against a running AEON deployment and writes a
JSON report consumable by ``scripts/slo_report.py``.

Run against a production-shaped deployment:

    AEON_TEST_TOKEN=... python scripts/loadtest_api.py \
        --base-url http://127.0.0.1:8000 \
        --concurrency 20 --total 400 \
        --endpoints /health,/metrics,/marketplace/agent-tools \
        --out scripts/output/load_report.json

Notes:
- Uses only the stdlib (no Locust install required) so it runs anywhere.
- ``--token-env`` names an env var holding a bearer token; when present it is
  attached as ``Authorization: Bearer <token>`` to every request.
- Latency samples are recorded per request and percentiles are computed in
  ``scripts/slo_report.py``.
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def _request(base_url: str, endpoint: str, token: str | None, timeout: float) -> dict[str, Any]:
    url = base_url.rstrip("/") + endpoint
    headers = {"User-Agent": "aeon-loadtest/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            latency_ms = (time.monotonic() - started) * 1000
            status = resp.status
            return {"ok": True, "status": status, "latency_ms": latency_ms}
    except urllib.error.HTTPError as exc:
        latency_ms = (time.monotonic() - started) * 1000
        return {"ok": exc.code < 400, "status": exc.code, "latency_ms": latency_ms}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        latency_ms = (time.monotonic() - started) * 1000
        return {"ok": False, "status": 0, "latency_ms": latency_ms, "error": type(exc).__name__}


def run_load_test(
    base_url: str,
    endpoints: list[str],
    concurrency: int,
    total: int,
    token: str | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Run the load test and return the raw report dict."""
    per_endpoint_count = max(1, total // len(endpoints))
    results: dict[str, list[dict[str, Any]]] = {endpoint: [] for endpoint in endpoints}
    lock = threading.Lock()

    def worker(endpoint: str, count: int) -> None:
        for _ in range(count):
            result = _request(base_url, endpoint, token, timeout)
            with lock:
                results[endpoint].append(result)

    threads = []
    for endpoint in endpoints:
        for _ in range(concurrency):
            thread = threading.Thread(target=worker, args=(endpoint, per_endpoint_count // concurrency))
            threads.append(thread)
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    report: dict[str, Any] = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "base_url": base_url,
        "concurrency": concurrency,
        "total_requests": sum(len(values) for values in results.values()),
        "endpoints": {},
    }
    for endpoint, samples in results.items():
        report["endpoints"][endpoint] = {
            "requests": len(samples),
            "errors": sum(1 for sample in samples if not sample["ok"]),
            "latencies_ms": [sample["latency_ms"] for sample in samples],
            "status_codes": _count_statuses(samples),
        }
    return report


def _count_statuses(samples: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for sample in samples:
        key = str(sample.get("status", "error"))
        counts[key] = counts.get(key, 0) + 1
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Deployment base URL, e.g. http://127.0.0.1:8000")
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--total", type=int, default=200)
    parser.add_argument("--endpoints", default="/health", help="Comma-separated endpoint paths")
    parser.add_argument("--token-env", default="AEON_TEST_TOKEN", help="Env var holding a bearer token (optional)")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--out", default="scripts/output/load_report.json")
    args = parser.parse_args(argv)

    if args.concurrency < 1 or args.total < 1:
        print("concurrency and total must be >= 1", file=sys.stderr)
        return 1
    endpoints = [endpoint.strip() for endpoint in args.endpoints.split(",") if endpoint.strip()]
    token = __import__("os").environ.get(args.token_env) or None
    print(f"load testing {args.base_url} — {args.concurrency} workers, ~{args.total} requests over {len(endpoints)} endpoints")
    started = time.monotonic()
    report = run_load_test(
        args.base_url,
        endpoints,
        concurrency=args.concurrency,
        total=args.total,
        token=token,
        timeout=args.timeout,
    )
    report["wall_seconds"] = round(time.monotonic() - started, 2)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {out_path} ({report['total_requests']} requests in {report['wall_seconds']}s)")
    for endpoint, data in report["endpoints"].items():
        errors = data["errors"]
        print(f"  {endpoint}: {data['requests']} requests, {errors} errors, statuses={data['status_codes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
