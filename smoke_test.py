#!/usr/bin/env python3
"""
smoke_test.py — minimal verification of aeon core contracts.

Runs in seconds without GPU, Telegram, Gemini API, real Drive, or any
external network call when the infer backends are stripped. Exits 0 on
all-pass, 1 on first FAIL.

Usage from the repo root:
    python smoke_test.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from pathlib import Path

# Make `import aeon` resolve regardless of where the test is invoked from.
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))


def _report(name: str, fn) -> bool:
    try:
        fn()
        print(f"PASS  {name}")
        return True
    except AssertionError as e:
        print(f"FAIL  {name}: {e}")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"FAIL  {name}: {type(e).__name__}: {e}")
        print(traceback.format_exc())
        return False


# ─── Test 1: atomic_write round-trip on tmp fs ────────────────────────────────
def t_atomic_write() -> None:
    import aeon
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "sub" / "x" / "y.txt"
        aeon.atomic_write(p, "hello\nworld\n")
        assert p.exists(), "file not created"
        assert p.read_text() == "hello\nworld\n", "round-trip mismatch"
        aeon.atomic_write(p, "second")
        assert p.read_text() == "second", "overwrite failed"
        # bytes path
        aeon.atomic_write(p, b"\x00\x01\x02")
        assert p.read_bytes() == b"\x00\x01\x02", "bytes round-trip mismatch"


# ─── Test 2: Intero defaults (incl. observability slots) ──────────────────────
def t_intero_init() -> None:
    import aeon
    INT = aeon.Intero()
    assert INT.queries == 0, f"queries={INT.queries}"
    assert INT.boot_count == 0, f"boot_count={INT.boot_count}"
    assert INT.last_backend == "", f"last_backend={INT.last_backend!r}"
    assert INT.last_latency_ms == 0.0, f"last_latency_ms={INT.last_latency_ms}"
    snap = INT.snap()
    assert set(snap.keys()) >= {
        "queries", "skill_hit_rate", "energy", "disk_pct",
        "errors", "boot_count", "last_backend", "last_latency_ms",
    }, f"snap keys missing: {set(snap.keys())}"


# ─── Test 3: Intero bump + EMA (covers the int-fix + the float path) ────────
def t_intero_bump_ema() -> None:
    import aeon
    INT = aeon.Intero()
    INT.bump("queries", 3)
    assert INT.queries == 3, f"queries={INT.queries}"
    # EMA on int (the previously-silent-no-op case). alpha=0.3 ⇒ (1-0.3)*3 + 0.3*4 = 3.3
    INT.EMA("queries", 4)
    assert abs(INT.queries - 3.3) < 1e-6, f"int EMA queries={INT.queries}"
    # EMA on float still works
    INT.EMA("error_rate", 0.5)
    assert abs(INT.error_rate - 0.5) < 1e-6, f"float EMA error_rate={INT.error_rate}"
    # EMA on unknown slot is a no-op (no AttributeError)
    INT.EMA("__nonexistent__", 1.0)  # must not raise


# ─── Test 4: sandbox_run deny-list blocks the obvious footguns ──────────────
def t_sandbox_refuse() -> None:
    import aeon
    bad = "import os\nos.system('echo PWNED')\n"
    r = aeon.sandbox_run(bad)
    assert r["rc"] == -1, f"deny-list did not refuse os.system: {r}"
    assert "refused" in r["stderr"], f"missing 'refused' marker in stderr: {r}"

    benign = "print(1 + 1)\n"
    r = aeon.sandbox_run(benign, timeout=3)
    assert r["rc"] == 0, f"benign code should run: {r}"
    assert "2" in r["stdout"], f"benign code did not print 2: {r}"


# ─── Test 5: Skill DAG roundtrip on a tmp AEON_ROOT ──────────────────────────
def t_dag_roundtrip() -> None:
    import aeon
    with tempfile.TemporaryDirectory() as td:
        ae_root = Path(td) / "aeon_alpha"
        for sub in ("hot", "skill_dag", "skill_dag/cards",
                    "trajectories", "diary", "receipts"):
            (ae_root / sub).mkdir(parents=True, exist_ok=True)
        # Point the module at our tmp root BEFORE constructing DAG.
        aeon.AEON_ROOT = ae_root
        dag = aeon.SkillDAG(hot_cap=4)
        h = dag.add(
            "addtwo",
            "def addtwo(a, b):\n    return a + b\n",
            ["addtwo(2, 3)"],
        )
        assert 8 <= len(h) <= 16, f"hash length odd: {h!r}"
        out = dag.execute("addtwo", {"a": 2, "b": 3})
        assert out == 5, f"execute returned {out}"
        dag.execute("addtwo", {"a": 4, "b": 6})
        rec = dag.index["addtwo"]
        assert rec["calls"] == 2, f"calls={rec['calls']}"
        assert rec["success"] == 2, f"success={rec['success']}"
        dag.add("typo_intent", "def typo_intent(", [""])
        # Note: ast.parse raises on the bad source and dag.add returns "err: ..."
        # which is the expected behaviour per §6.


# ─── Test 6: wallet_state with no private key ───────────────────────────────
def t_wallet_no_pkey() -> None:
    import aeon
    saved = os.environ.pop("WEB3_PRIVATE_KEY", None)
    try:
        # Force the module-level W3 back to None so we exercise the no-wallet path
        # even if some other test set it.
        aeon.W3, aeon.ACCT, aeon.AEON_ADDR = None, None, None
        s = aeon.wallet_state()
        assert s["ok"] is False, f"wallet ok without pkey: {s}"
        assert s.get("reason") == "no-wallet", f"wallet reason: {s}"
    finally:
        if saved is not None:
            os.environ["WEB3_PRIVATE_KEY"] = saved


# ─── Test 7: ask() with all infer backends stripped ─────────────────────────
def t_ask_no_backend() -> None:
    import aeon
    # Detach any backend the module may have picked up from env at import.
    aeon._brain = None
    aeon.GROQ = None
    aeon.GEMINI = None
    for k in ("GROQ_API_KEY", "GEMINI_API_KEY",
              "GROQ", "GOOGLE_API_KEY", "GEMINI"):
        os.environ.pop(k, None)
    import asyncio
    out = asyncio.run(aeon.ask("hello"))
    assert "no inference backend" in out, f"unexpected ask() output: {out!r}"
    assert aeon.INT.last_backend == "none", f"last_backend={aeon.INT.last_backend!r}"
    assert aeon.INT.queries == 1, f"queries should bump to 1, got {aeon.INT.queries}"


# ─── Driver ─────────────────────────────────────────────────────────────────
CHECKS = [
    ("atomic_write round-trip",          t_atomic_write),
    ("Intero init defaults",             t_intero_init),
    ("Intero bump + EMA (int + float)",  t_intero_bump_ema),
    ("sandbox_run refuse-list",          t_sandbox_refuse),
    ("Skill DAG add+execute roundtrip",  t_dag_roundtrip),
    ("wallet_state no-pkey path",        t_wallet_no_pkey),
    ("ask() all-backends-stripped path", t_ask_no_backend),
]


def main() -> int:
    fails = 0
    for name, fn in CHECKS:
        if not _report(name, fn):
            fails += 1
    print()
    total = len(CHECKS)
    print(f"== {total - fails}/{total} checks passed ==")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
