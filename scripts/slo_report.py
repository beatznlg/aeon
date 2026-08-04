#!/usr/bin/env python3
"""AEON OS — SLO evaluation report generator.

Evaluates latency/availability targets against a load-test report produced by
``scripts/loadtest_api.py`` (or any compatible JSON) and renders a markdown
evidence report for the production-readiness documentation.

Pure logic lives in :func:`compute_slos` and is unit-tested in
``tests/test_slo.py``. Run:

    python scripts/slo_report.py --report scripts/output/load_report.json \
        --out scripts/output/slo_report.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_TARGETS: dict[str, Any] = {
    "availability_pct": 99.9,
    "p50_ms": 500,
    "p95_ms": 1500,
    "p99_ms": 3000,
    "error_rate_pct": 0.5,
}


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        return 0.0
    index = max(0, min(len(sorted_values) - 1, int((percentile / 100.0) * len(sorted_values)) - 1))
    return sorted_values[index]


def compute_slos(report: dict[str, Any], targets: dict[str, Any] | None = None) -> dict[str, Any]:
    """Evaluate SLO targets against a load-test report.

    Expected report shape (produced by ``scripts/loadtest_api.py``)::

        {
          "generated_at": "...",
          "concurrency": 20,
          "total_requests": 400,
          "endpoints": {
            "/health": {"requests": 200, "errors": 0, "latencies_ms": [...], "status_codes": {...}}
          }
        }

    Returns per-endpoint and overall SLO evaluations.
    """
    targets = {**DEFAULT_TARGETS, **(targets or {})}
    availability_target = float(targets["availability_pct"])
    error_rate_target = float(targets["error_rate_pct"])
    latency_targets = {
        "p50_ms": float(targets["p50_ms"]),
        "p95_ms": float(targets["p95_ms"]),
        "p99_ms": float(targets["p99_ms"]),
    }

    endpoints = report.get("endpoints", {})
    evaluated: list[dict[str, Any]] = []
    overall_requests = 0
    overall_errors = 0
    overall_latencies: list[float] = []
    for name, data in endpoints.items():
        requests_count = int(data.get("requests", 0))
        errors = int(data.get("errors", 0))
        latencies = sorted(float(value) for value in data.get("latencies_ms", []))
        error_rate = round(errors / requests_count * 100, 4) if requests_count else 0.0
        availability = round((1 - errors / requests_count) * 100, 4) if requests_count else 100.0
        percentiles = {
            "p50_ms": _percentile(latencies, 50),
            "p95_ms": _percentile(latencies, 95),
            "p99_ms": _percentile(latencies, 99),
        }
        met = {
            "availability": availability >= availability_target,
            "error_rate": error_rate <= error_rate_target,
        }
        for key, target in latency_targets.items():
            met[key] = percentiles[key] <= target
        overall_requests += requests_count
        overall_errors += errors
        overall_latencies.extend(latencies)
        evaluated.append(
            {
                "endpoint": name,
                "requests": requests_count,
                "errors": errors,
                "error_rate_pct": error_rate,
                "availability_pct": availability,
                "latency": percentiles,
                "met": met,
                "all_met": all(met.values()),
            }
        )

    overall_error_rate = round(overall_errors / overall_requests * 100, 4) if overall_requests else 0.0
    overall_availability = round((1 - overall_errors / overall_requests) * 100, 4) if overall_requests else 100.0
    overall_percentiles = {
        "p50_ms": _percentile(sorted(overall_latencies), 50),
        "p95_ms": _percentile(sorted(overall_latencies), 95),
        "p99_ms": _percentile(sorted(overall_latencies), 99),
    }
    overall_met = {
        "availability": overall_availability >= availability_target,
        "error_rate": overall_error_rate <= error_rate_target,
        **{key: overall_percentiles[key] <= target for key, target in latency_targets.items()},
    }
    return {
        "targets": targets,
        "generated_at": report.get("generated_at", ""),
        "concurrency": report.get("concurrency"),
        "total_requests": overall_requests,
        "endpoints": evaluated,
        "overall": {
            "requests": overall_requests,
            "errors": overall_errors,
            "error_rate_pct": overall_error_rate,
            "availability_pct": overall_availability,
            "latency": overall_percentiles,
            "met": overall_met,
            "all_met": all(overall_met.values()),
        },
    }


def render_markdown(results: dict[str, Any]) -> str:
    """Render an SLO evaluation as a markdown evidence report."""
    lines: list[str] = [
        "# AEON OS — SLO Evidence Report",
        "",
        f"- Generated: {results.get('generated_at', 'n/a')}",
        f"- Concurrency: {results.get('concurrency', 'n/a')}",
        f"- Total requests: {results.get('total_requests', 0)}",
        "",
        "## Targets",
        "",
        "| SLO | Target |",
        "| --- | --- |",
    ]
    targets = results["targets"]
    for key, label in [
        ("availability_pct", "Availability"),
        ("error_rate_pct", "Error rate"),
        ("p50_ms", "Latency p50"),
        ("p95_ms", "Latency p95"),
        ("p99_ms", "Latency p99"),
    ]:
        lines.append(f"| {label} | {targets.get(key)} |")
    lines.append("")
    lines.append("## Overall")
    lines.append("")
    overall = results["overall"]
    lines.append(
        f"- Availability: **{overall['availability_pct']}%** ({'met' if overall['met']['availability'] else 'NOT met'})"
    )
    lines.append(f"- Error rate: **{overall['error_rate_pct']}%** ({'met' if overall['met']['error_rate'] else 'NOT met'})")
    for key, label in [("p50_ms", "p50"), ("p95_ms", "p95"), ("p99_ms", "p99")]:
        lines.append(f"- Latency {label}: **{overall['latency'][key]:.0f} ms** ({'met' if overall['met'][key] else 'NOT met'})")
    lines.append(f"- **Overall: {'PASS' if overall['all_met'] else 'FAIL'}**")
    lines.append("")
    lines.append("## Per endpoint")
    lines.append("")
    lines.append("| Endpoint | Requests | Errors | Avail % | p50 ms | p95 ms | p99 ms | Result |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for entry in results["endpoints"]:
        latency = entry["latency"]
        lines.append(
            f"| {entry['endpoint']} | {entry['requests']} | {entry['errors']} | "
            f"{entry['availability_pct']:.2f} | {latency['p50_ms']:.0f} | {latency['p95_ms']:.0f} | "
            f"{latency['p99_ms']:.0f} | {'PASS' if entry['all_met'] else 'FAIL'} |"
        )
    lines.append("")
    lines.append("> Evidence produced by `scripts/loadtest_api.py` + `scripts/slo_report.py`. "
                 "Run against a production-shaped deployment; results are point-in-time measurements.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, help="Path to load-test JSON report")
    parser.add_argument("--out", default="", help="Output markdown path (default: stdout)")
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"report not found: {report_path}", file=sys.stderr)
        return 1
    report = json.loads(report_path.read_text(encoding="utf-8"))
    results = compute_slos(report)
    markdown = render_markdown(results)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(markdown, encoding="utf-8")
        print(f"wrote {out_path}")
    else:
        print(markdown)
    return 0 if results["overall"]["all_met"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
