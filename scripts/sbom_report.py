#!/usr/bin/env python3
"""Generate a point-in-time SBOM report from the project requirements.

Stdlib-only so it runs anywhere. Produces a JSON report with package
name/version/scope, the installed version (when resolvable), and a SHA-256
of the report for the assurance ledger. Regenerate and retain per release.

Usage:
    python scripts/sbom_report.py [--requirements requirements.txt requirements-dev.txt] \
        --out scripts/output/sbom.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

_REQ_RE = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*(.*?)\s*$")


def _parse_requirement(line: str) -> dict | None:
    line = line.strip()
    if not line or line.startswith(("#", "-", "git+", "http")):
        return None
    m = _REQ_RE.match(line)
    if not m:
        return None
    name, spec = m.group(1), m.group(2)
    return {"name": name, "spec": spec or "*"}


def _installed_version(name: str) -> str | None:
    try:
        return metadata.version(name)
    except Exception:
        return None


def _build_report(req_files: list[str]) -> dict:
    packages = []
    for req_file in req_files:
        p = Path(req_file)
        if not p.exists():
            continue
        for raw in p.read_text(errors="replace").splitlines():
            item = _parse_requirement(raw)
            if not item:
                continue
            installed = _installed_version(item["name"])
            packages.append(
                {
                    "name": item["name"],
                    "spec": item["spec"],
                    "installed": installed,
                    "scope": "runtime" if "dev" not in req_file else "development",
                    "purl": "pkg:pypi/" + item["name"].lower().replace("_", "-") + "@" + (installed or item["spec"]),
                }
            )
    packages.sort(key=lambda p: (p["scope"], p["name"]))
    report = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": "aeon-" + hashlib.sha256((datetime.now(timezone.utc).isoformat() + json.dumps(packages)).encode()).hexdigest()[:12],
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": [{"name": "aeon-sbom-report", "version": "1.0"}],
            "component": {"type": "application", "name": "aeon-os", "version": "3.0"},
        },
        "components": packages,
    }
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description="AEON SBOM report generator (stdlib-only).")
    ap.add_argument("--requirements", nargs="*", default=["requirements.txt", "requirements-dev.txt"])
    ap.add_argument("--out", default="scripts/output/sbom.json")
    args = ap.parse_args()

    report = _build_report(args.requirements)
    payload = json.dumps(report, indent=2, sort_keys=True)
    digest = hashlib.sha256(payload.encode()).hexdigest()
    report["sha256"] = digest
    payload = json.dumps(report, indent=2, sort_keys=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload + chr(10))
    print("SBOM written: " + str(out) + " (" + str(len(report["components"])) + " components)")
    print("SHA-256: " + digest)


if __name__ == "__main__":
    main()
