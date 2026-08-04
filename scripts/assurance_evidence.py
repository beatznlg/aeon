#!/usr/bin/env python3
"""Record or verify AEON OS assurance evidence metadata.

The ledger stores summaries and artifact digests only. Keep PHI, secrets,
assessment reports, and other sensitive material in an approved evidence system.
This helper never reads an artifact into the ledger; it records only its SHA-256.

Examples:
    python scripts/assurance_evidence.py verify --ledger /secure/evidence.ndjson
    python scripts/assurance_evidence.py append --ledger /secure/evidence.ndjson \
        --profile baseline --control-id kms_validation --status verified \
        --summary "KMS validation passed" --source "release-2026-08-04" \
        --artifact /secure/reports/kms.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow invocation from the repository root without installing AEON as a package.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aeon_assurance import EvidenceLedger, sha256_file  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify", help="verify a ledger and optional external last-hash anchor")
    verify.add_argument("--ledger", required=True, type=Path)
    verify.add_argument("--expected-last-hash")

    append = subparsers.add_parser("append", help="append one non-sensitive evidence record")
    append.add_argument("--ledger", required=True, type=Path)
    append.add_argument("--profile", required=True)
    append.add_argument("--control-id", required=True)
    append.add_argument("--status", required=True, choices=("verified", "failed", "pending", "not_applicable"))
    append.add_argument("--summary", required=True)
    append.add_argument("--source", required=True)
    append.add_argument("--artifact", type=Path, help="artifact to hash; its contents are never stored")
    append.add_argument("--observed-at")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    ledger = EvidenceLedger(args.ledger)
    if args.command == "verify":
        report = ledger.verify(expected_last_hash=args.expected_last_hash)
    else:
        artifact_sha256 = sha256_file(args.artifact) if args.artifact else None
        record = ledger.append(
            control_id=args.control_id,
            profile=args.profile,
            status=args.status,
            summary=args.summary,
            source=args.source,
            artifact_sha256=artifact_sha256,
            observed_at=args.observed_at,
        )
        report = {"ok": True, "record": record.to_dict()}
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
