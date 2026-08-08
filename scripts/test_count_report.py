#!/usr/bin/env python3
"""Generate a shields.io endpoint JSON for the AEON passing-test count.

Counts the passing tests from the CI quality gate and writes a shields.io
endpoint JSON so the count can render as a live README badge
(``https://img.shields.io/endpoint?url=<raw URL of the endpoint JSON>``).

Three input modes, in priority order:

* ``--junit-xml`` — count passing tests from the gate's own pytest report
  (the CI path: the suite runs exactly once, the badge reads that run).
* (default) — run ``python -m pytest -q --tb=no`` like the gate and parse
  the summary line.
* ``--summary-line`` — parse a saved summary (e.g. ``"414 passed, 2 warnings
  in 34.12s"``) for constrained environments that cannot execute the suite.

Stdlib-only.

Usage:
    python scripts/test_count_report.py --junit-xml pytest-report.xml
    python scripts/test_count_report.py --out docs/badges/tests-passing.json
    python scripts/test_count_report.py --summary-line "414 passed, 2 warnings in 34.12s"
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

_PASSED_RE = re.compile(r"(\d+)\s+passed")
_FAILED_RE = re.compile(r"(\d+)\s+failed")


def _parse_summary(text: str) -> tuple[int, int] | None:
    """Return (passed, failed) from a pytest summary line, or None if unparseable."""
    passed_m = _PASSED_RE.search(text)
    if passed_m is None:
        return None
    failed_m = _FAILED_RE.search(text)
    return int(passed_m.group(1)), int(failed_m.group(1)) if failed_m else 0


def _run_pytest() -> tuple[int, str]:
    """Run the suite like CI; returns (returncode, combined output)."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def _count_from_junit_xml(path: str) -> tuple[int, int]:
    """Count (passed, failed) from a pytest junit XML report."""
    root = ET.parse(path).getroot()
    cases = root.findall(".//testcase")
    total = len(cases)
    failed = len(root.findall(".//failure")) + len(root.findall(".//error"))
    passed = total - failed - len(root.findall(".//skipped"))
    return passed, failed


def _endpoint(passed: int, failed: int, ok: bool) -> dict:
    if ok:
        message = f"{passed} passing"
        color = "#97ca00"  # green
    else:
        message = f"{passed} passing, {failed} failing" if failed else f"{passed} passing, failures"
        color = "#e05d44"  # red
    return {
        "schemaVersion": 1,
        "label": "tests passing",
        "message": message,
        "color": color,
        "cacheSeconds": 3600,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="AEON tests-passing badge generator (stdlib-only).")
    ap.add_argument("--out", default="docs/badges/tests-passing.json")
    ap.add_argument(
        "--junit-xml",
        default=None,
        help="Count passing tests from a pytest junit XML report (CI path)",
    )
    ap.add_argument(
        "--summary-line",
        default=None,
        help="Parse this saved pytest summary instead of running the suite "
        "(e.g. '414 passed, 2 warnings in 34.12s')",
    )
    args = ap.parse_args()

    if args.junit_xml is not None:
        passed, failed = _count_from_junit_xml(args.junit_xml)
        ok = failed == 0
        source = f"junit XML {args.junit_xml}"
    elif args.summary_line is not None:
        parsed = _parse_summary(args.summary_line)
        if parsed is None:
            print(f"FAIL: could not parse summary line: {args.summary_line!r}", file=sys.stderr)
            return 1
        passed, failed = parsed
        ok = failed == 0
        source = "summary line"
    else:
        returncode, output = _run_pytest()
        parsed = _parse_summary(output)
        if parsed is None:
            print(
                "FAIL: pytest produced no parseable summary "
                f"(returncode {returncode})",
                file=sys.stderr,
            )
            return 1
        passed, failed = parsed
        ok = returncode == 0 and failed == 0
        source = "live pytest run"

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(_endpoint(passed, failed, ok), indent=2) + "\n")
    print(f"wrote {out} (from {source}): {passed} passing, {failed} failing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
