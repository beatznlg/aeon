#!/usr/bin/env python3
"""
AEON OS — Phase 12 Performance Benchmark

Quick micro-benchmarks for the three main Phase 12 optimisations:
1. SQLAlchemy connection pooling (aeon_db.py)
2. Redis/in-memory cache (aeon_cache.py)
3. Vector-store keyword-scorer + chunk caching (aeon_vector_store.py)

Run with:
    python scripts/benchmark_phase12.py

Env:
    AEON_DATABASE_URL   override DB URL (defaults to temp SQLite)
    AEON_REDIS_URL      override Redis URL (defaults to in-memory fallback)
"""

import os
import sys
import tempfile
import time
from pathlib import Path

# Allow imports of aeon_*.py modules from the repo root even when the script
# is executed from the scripts/ directory.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── Setup a temporary AEON_ROOT so we don't touch real state ─────────────────
_tmp_root = tempfile.mkdtemp(prefix="aeon_benchmark_")
os.environ.setdefault("AEON_ROOT", _tmp_root)
os.environ.setdefault("AEON_ENV", "test")
os.environ.setdefault("AEON_DATABASE_URL", f"sqlite:///{_tmp_root}/aeon.db")
os.environ.setdefault("NEXTAUTH_SECRET", "benchmark-secret")

from aeon_cache import Cache
from aeon_db import Database, User, init_db
from aeon_vector_store import DiskVectorStore


# ── helpers ──────────────────────────────────────────────────────────────────
def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _fmt_us(seconds: float) -> str:
    return f"{seconds * 1_000_000:.2f} µs"


def _fmt_ms(seconds: float) -> str:
    return f"{seconds * 1000:.2f} ms"


# ── benchmark: DB connection pooling ───────────────────────────────────────
def benchmark_db(db: Database, iterations: int = 500) -> None:
    print("\n=== DB connection pooling ===")
    print(f"Database URL: {db.url}")

    # Insert a test user to fetch
    with db.session() as s:
        user = User(email="benchmark@aeon.local", name="Benchmark", password="x", role="VIEWER")
        s.add(user)
        s.commit()

    # Warmup
    for _ in range(10):
        db.get_user_by_email("benchmark@aeon.local")

    times: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        db.get_user_by_email("benchmark@aeon.local")
        t1 = time.perf_counter()
        times.append(t1 - t0)

    print(f"  Iterations:        {iterations}")
    print(f"  Mean latency:      {_fmt_us(_mean(times))}")
    print(f"  P50:               {_fmt_us(sorted(times)[len(times) // 2])}")
    print(f"  P95:               {_fmt_us(sorted(times)[int(len(times) * 0.95)])}")
    print(f"  Total time:        {_fmt_ms(sum(times))}")


# ── benchmark: cache layer ─────────────────────────────────────────────────
def benchmark_cache(cache: Cache, iterations: int = 10_000) -> None:
    print("\n=== Cache layer (get/set) ===")
    print(f"Redis backend:       {cache._redis is not None}")

    # SET
    set_times: list[float] = []
    for i in range(iterations):
        t0 = time.perf_counter()
        cache.set(f"key:{i}", {"value": i, "payload": "x" * 100})
        t1 = time.perf_counter()
        set_times.append(t1 - t0)

    # GET (warm)
    get_times: list[float] = []
    for i in range(iterations):
        t0 = time.perf_counter()
        cache.get(f"key:{i}")
        t1 = time.perf_counter()
        get_times.append(t1 - t0)

    print(f"  Iterations:        {iterations}")
    print(f"  SET mean:          {_fmt_us(_mean(set_times))}")
    print(f"  GET mean (warm):   {_fmt_us(_mean(get_times))}")


# ── benchmark: vector store caching ────────────────────────────────────────
def benchmark_vector_store(root: Path, chunks_per_kb: int = 1000) -> None:
    print("\n=== Vector store (DiskVectorStore) ===")
    store = DiskVectorStore(root)
    kb_id = "benchmark_kb"

    chunks: list[dict] = []
    for i in range(chunks_per_kb):
        # 384-dim pseudo-embedding so the test runs fast but exercises the path
        embedding = [0.01] * 384
        chunks.append({
            "id": f"chunk_{i}",
            "doc_id": "doc_1",
            "text": f"This is sample text for chunk {i} covering performance benchmarking.",
            "embedding": embedding,
            "metadata": {"index": i},
        })
    store.add_chunks(kb_id, "doc_1", chunks)

    # Cold search (populates caches)
    query_vec = [0.01] * 384
    t0 = time.perf_counter()
    store.search_vector(kb_id, query_vec, top_k=5)
    t1 = time.perf_counter()
    cold_vector = t1 - t0

    t0 = time.perf_counter()
    store.search_keyword(kb_id, "performance benchmarking", top_k=5)
    t1 = time.perf_counter()
    cold_keyword = t1 - t0

    # Warm searches
    warm_vector_times: list[float] = []
    for _ in range(50):
        t0 = time.perf_counter()
        store.search_vector(kb_id, query_vec, top_k=5)
        t1 = time.perf_counter()
        warm_vector_times.append(t1 - t0)

    warm_keyword_times: list[float] = []
    for _ in range(50):
        t0 = time.perf_counter()
        store.search_keyword(kb_id, "performance benchmarking", top_k=5)
        t1 = time.perf_counter()
        warm_keyword_times.append(t1 - t0)

    print(f"  Chunks indexed:    {chunks_per_kb}")
    print(f"  Vector search cold:{_fmt_ms(cold_vector)}")
    print(f"  Vector search warm:  {_fmt_us(_mean(warm_vector_times))} (avg over 50)")
    print(f"  Keyword search cold:{_fmt_ms(cold_keyword)}")
    print(f"  Keyword search warm: {_fmt_us(_mean(warm_keyword_times))} (avg over 50)")


# ── main ───────────────────────────────────────────────────────────────────
def main() -> int:
    print("AEON OS — Phase 12 Performance Benchmark")
    print(f"Temp root: {_tmp_root}")

    init_db()
    db = Database()
    benchmark_db(db)

    cache = Cache()
    benchmark_cache(cache)

    root = Path(_tmp_root)
    benchmark_vector_store(root)

    print("\nBenchmark complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
