#!/usr/bin/env python3
"""Disaster-recovery drill with measured RTO/RPO evidence.

Drives the real aeon_dr machinery (BackupManager, DRDrillSimulator) and
writes a point-in-time evidence report with measured timings.  Retain each
report and append its digest to the assurance ledger per release.

Usage:
    python scripts/dr_drill.py --workspace-id <ws> [--plan-id <plan>] \
        --mode simulate --out scripts/output/dr_report.json
"""

from __future__ import annotations

import argparse
import sys
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _report_digest(report: dict) -> str:
    payload = json.dumps(report, indent=2, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def main() -> None:
    ap = argparse.ArgumentParser(description="AEON DR drill with measured RTO/RPO.")
    ap.add_argument("--workspace-id", required=True)
    ap.add_argument("--plan-id", default=None)
    ap.add_argument("--mode", choices=["simulate", "backup"], default="simulate")
    ap.add_argument("--out", default="scripts/output/dr_report.json")
    args = ap.parse_args()

    from aeon_dr import BackupManager, DRDrillSimulator

    events = []
    started = time.perf_counter()

    sim_start = time.perf_counter()
    simulator = DRDrillSimulator(args.workspace_id)
    try:
        simulator.simulate_failover(args.plan_id or "default-plan")
        events.append({"step": "failover_simulation", "seconds": round(time.perf_counter() - sim_start, 4), "status": "ok"})
    except ValueError as exc:
        events.append({"step": "failover_simulation", "seconds": None, "status": "skipped", "reason": str(exc)})

    rto_seconds = None
    rpo_seconds = None
    if args.mode == "backup":
        manager = BackupManager(args.workspace_id)
        backup_start = time.perf_counter()
        try:
            job = manager.run_backup(args.plan_id or "default-policy")
            events.append({"step": "backup", "seconds": round(time.perf_counter() - backup_start, 4), "status": "ok"})
        except Exception as exc:  # noqa: BLE001
            events.append({"step": "backup", "seconds": None, "status": "error", "reason": str(exc)})

        restore_start = time.perf_counter()
        try:
            manager.restore_backup(getattr(job, "id", ""))
            events.append({"step": "restore", "seconds": round(time.perf_counter() - restore_start, 4), "status": "ok"})
        except Exception as exc:  # noqa: BLE001
            events.append({"step": "restore", "seconds": None, "status": "error", "reason": str(exc)})

        rto_seconds = round(restore_elapsed, 4)
        rpo_seconds = round(backup_elapsed, 4)

    report = {
        "tool": "aeon-dr-drill",
        "workspace_id": args.workspace_id,
        "mode": args.mode,
        "started_at": _now_iso(),
        "total_seconds": round(time.perf_counter() - started, 4),
        "measured": {
            "rto_seconds": rto_seconds,
            "rpo_seconds": rpo_seconds,
            "slo_rto": None,
            "slo_rpo": None,
        },
        "events": events,
        "notes": "Point-in-time evidence. Re-run per release; retain with the assurance ledger. "
        "A passing drill is engineering evidence, not a certification.",
    }
    report["sha256"] = _report_digest(report)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + chr(10))
    print(json.dumps(report, indent=2, sort_keys=True))
    print("Report: " + str(out))


if __name__ == "__main__":
    main()
