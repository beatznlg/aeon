#!/usr/bin/env python3
"""
AEON OS — Phase 12 HTTP Load Test

Runs concurrent requests against the Flask app using the test client
so no external server or ports are needed.

Run with:
    python scripts/load_test_phase12.py
"""

import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Isolate state
_tmp_root = tempfile.mkdtemp(prefix="aeon_loadtest_")
os.environ["AEON_ROOT"] = _tmp_root
os.environ["AEON_ENV"] = "test"
os.environ["AEON_DATABASE_URL"] = f"sqlite:///{_tmp_root}/aeon.db"
os.environ["NEXTAUTH_SECRET"] = "loadtest-secret"

import aeon_server
from aeon_db import init_db


def _hit_health(client):
    return client.get("/health").status_code


def _hit_ready(client):
    return client.get("/ready").status_code


def _hit_metrics(client):
    return client.get("/metrics").status_code


def run_load_test(iterations: int = 500, concurrency: int = 10) -> None:
    init_db()
    client = aeon_server.app.test_client()

    # Warmup
    for _ in range(10):
        client.get("/health")
        client.get("/ready")

    endpoints = {
        "/health": _hit_health,
        "/ready": _hit_ready,
        "/metrics": _hit_metrics,
    }

    results = {name: {"times": [], "errors": 0} for name in endpoints}

    def worker(args):
        name, fn = args
        t0 = time.perf_counter()
        try:
            status = fn(client)
        except Exception as exc:  # pragma: no cover
            return name, t0, None, str(exc)
        t1 = time.perf_counter()
        return name, t0, status, t1 - t0

    tasks = [(name, fn) for name, fn in endpoints.items() for _ in range(iterations)]
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for name, _, status, elapsed in pool.map(worker, tasks):
            if status == 200:
                results[name]["times"].append(elapsed)
            else:
                results[name]["errors"] += 1
    total_time = time.perf_counter() - start

    print("\n=== HTTP Load Test ===")
    print(f"Iterations/endpoint: {iterations}")
    print(f"Concurrency:         {concurrency}")
    print(f"Total wall time:     {total_time * 1000:.2f} ms")
    print(f"Combined RPS:        {len(tasks) / total_time:.2f}")

    for name, data in results.items():
        times = data["times"]
        if not times:
            print(f"  {name}: no successful requests ({data['errors']} errors)")
            continue
        mean = sum(times) / len(times)
        times_sorted = sorted(times)
        p50 = times_sorted[len(times) // 2]
        p95 = times_sorted[int(len(times) * 0.95)]
        p99 = times_sorted[int(len(times) * 0.99)]
        rps = len(times) / sum(times)
        print(f"  {name}:")
        print(f"    requests: {len(times)}, errors: {data['errors']}")
        print(f"    mean: {mean * 1000:.2f} ms, p50: {p50 * 1000:.2f} ms, p95: {p95 * 1000:.2f} ms, p99: {p99 * 1000:.2f} ms")
        print(f"    throughput: ~{rps:.2f} req/s")


if __name__ == "__main__":
    run_load_test()
