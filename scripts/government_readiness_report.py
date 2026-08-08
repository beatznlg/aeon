#!/usr/bin/env python3
"""Generate a machine-readable government-readiness report for AEON OS.

Stdlib-only so it runs anywhere. Emits an SBOM-style JSON document
(``bomFormat: AEON-GovReadiness``) that mirrors
``docs/GOVERNMENT_READINESS_CHECKLIST.md``: every certification, agreement,
organizational process, personnel item, external-technical item, and
procurement item with its status (BLOCKING / PARTIAL / GAP), owner, cost/time,
requirement, and supporting repo references, plus per-category and overall
rollups that procurement teams and tooling can parse directly.

Usage:
    python scripts/government_readiness_report.py --out scripts/output/government_readiness.json
    python scripts/government_readiness_report.py --badge-out docs/badges/government-readiness.svg
    python scripts/government_readiness_report.py --badge-endpoint-out docs/badges/government-readiness.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

BOM_FORMAT = "AEON-GovReadiness"
SPEC_VERSION = "1.0"
STATUSES = ("BLOCKING", "PARTIAL", "GAP")

# (id, title, status, owner, cost_time, requirement, links)
# Mirrors docs/GOVERNMENT_READINESS_CHECKLIST.md section by section.
_CONTROLS: list[tuple[str, str, str, str, str, str, str]] = [
    # ── 1. Certifications & authorizations ────────────────────────────────
    ("1.1", "FedRAMP authorization (Low → Moderate → High)", "BLOCKING", "External 3PAO + FedRAMP program", "$150k–$500k+ / 9–18 months", "Required for most US federal SaaS procurement; only a 3PAO assessment + agency/JAB authorization can issue it — no repo can", "docs/COMPLIANCE_READINESS.md"),
    ("1.2", "SOC 2 Type II (trust services criteria)", "BLOCKING", "External CPA firm", "$30k–$120k / 4–9 months", "Commercial prerequisite and de-facto FedRAMP readiness input; independent auditor opinion", "docs/COMPLIANCE_READINESS.md"),
    ("1.3", "ISO/IEC 27001 certification", "GAP", "Certification body", "$20k–$80k / 6–12 months", "Common international/state requirement; certification body audit", ""),
    ("1.4", "StateRAMP / Texas RAMP", "GAP", "3PAO + state program", "$30k–$150k / 6–12 months", "State-level FedRAMP-equivalent for US state/local procurement", ""),
    ("1.5", "CMMC Level 2 (DoD supply chain)", "GAP", "C3PAO assessment", "$50k–$200k / 6–12 months", "Required to hold CUI from DoD primes; only if DoD is a target", ""),
    ("1.6", "NIST SP 800-171 / DFARS 252.204-7012", "GAP", "Internal + C3PAO", "Variable", "DoD CUI handling; self-assessment + eventual CMMC; DoD only", ""),
    ("1.7", "HIPAA compliance posture + executed BAA", "PARTIAL", "Legal + security", "Ongoing", "Required if any covered entity / PHI; template + healthcare compliance profile exist, executed BAA + controls evidence do not", "docs/compliance/BAAS_TEMPLATE.md"),
    ("1.8", "CJIS approval (law enforcement / criminal justice)", "BLOCKING", "Agency + state CJIS units", "Variable, per state", "FBI CJIS Security Policy + state/agency agreements + personnel vetting + authorized boundary — explicitly not grantable by app features", "docs/security/IDP_INTEROP_MATRIX.md"),
    ("1.9", "PCI DSS (only if card data in scope)", "GAP", "QSA", "$20k–$60k / 3–6 months", "Only if AEON processes/transmits cardholder data; not in scope unless finance module holds PAN data", ""),
    ("1.10", "Section 508 / WCAG 2.1 AA accessibility conformance", "GAP", "UX + testers", "$15k–$50k", "Federal procurement requirement for IT products", ""),
    # ── 2. Agreements & contracts ─────────────────────────────────────────
    ("2.1", "Executed Business Associate Agreements (BAA) per customer", "PARTIAL", "Legal", "Per deal", "HIPAA; template exists, executed agreements do not", "docs/compliance/BAAS_TEMPLATE.md"),
    ("2.2", "CJIS security addendum + state agreements", "BLOCKING", "Legal + agency", "Per state", "CJIS requires agency/state agreements + personnel policies; no app feature can grant", ""),
    ("2.3", "FedRAMP agency authorization agreement (Agency ATO path)", "BLOCKING", "Agency CIO/CISO", "Per agency", "Authorizing agency must accept the package", ""),
    ("2.4", "Data use / data processing agreements per state", "GAP", "Legal", "Per state", "State-specific privacy and records requirements", ""),
    ("2.5", "FAR/DFARS clauses + TAA (Trade Agreements Act) compliance", "GAP", "Legal + supply chain", "Variable", "Federal contract boilerplate; affects source-of-manufacture of infrastructure", ""),
    ("2.6", "Pilot MOUs / NDAs", "GAP", "BD + Legal", "Days", "First agency engagements should be structured pilots, not procurement", ""),
    # ── 3. Organizational & operational processes ─────────────────────────
    ("3.1", "Incident response exercised with measured times + evidence", "PARTIAL", "Security lead", "Ongoing", "Docs exist; auditors require executed drills + records", "docs/policies/INCIDENT_RESPONSE.md"),
    ("3.2", "Recurring access reviews on a published cadence with records", "PARTIAL", "Security lead", "Quarterly", "Docs exist; recurring execution + sign-off does not", "docs/policies/ACCESS_REVIEW.md"),
    ("3.3", "Enforced retention & legal hold schedules", "PARTIAL", "Legal + Ops", "Ongoing", "Docs exist; automated enforcement in the production boundary does not", "docs/policies/RETENTION.md"),
    ("3.4", "Support/SLA process — severity tiers, response targets", "PARTIAL", "Ops", "Ongoing", "Docs exist; staffing + SLAs do not", "docs/policies/SUPPORT.md"),
    ("3.5", "Change management & release process for the ATO boundary", "PARTIAL", "Engineering", "Ongoing", "CI gate exists; formal change records do not", ".github/workflows/quality-gate.yml"),
    ("3.6", "Vulnerability management program — scans, triage SLAs, remediation", "PARTIAL", "Security", "Ongoing", "Per-commit Bandit/pip-audit exist; continuous program + reporting does not", ".github/workflows/quality-gate.yml"),
    ("3.7", "Independent penetration testing (annual + pre-pilot)", "BLOCKING", "External firm", "$30k–$150k / 2–4 weeks", "Threat model defines scope; an external firm's report is required", "docs/security/THREAT_MODEL.md"),
    ("3.8", "Business continuity / DR program with measured RTO/RPO", "PARTIAL", "Ops", "Ongoing", "Drill script + CI evidence exist; scheduled drills in the production boundary do not", "scripts/dr_drill.py"),
    ("3.9", "Privacy program — PIA/SORN inputs, notices, data-subject handling", "GAP", "Privacy + Legal", "Variable", "No privacy program exists yet", ""),
    # ── 4. Personnel & identity ───────────────────────────────────────────
    ("4.1", "Background checks per agency requirements (incl. CJIS fingerprinting)", "GAP", "HR", "Per hire", "Personnel vetting is a CJIS/fed prerequisite", ""),
    ("4.2", "PIV/CAC issuance for staff accessing federal-facing environments", "GAP", "Security/HR", "Per staff", "HSPD-12; identity for operator/admin access", ""),
    ("4.3", "Annual role-based security awareness training with records", "GAP", "HR/Security", "Annual", "Audit evidence requirement", ""),
    ("4.4", "Privileged-access controls — MFA, break-glass, least privilege", "PARTIAL", "Security", "Ongoing", "RBAC/MFA primitives exist; formal privileged-access program does not", "docs/security/THREAT_MODEL.md"),
    # ── 5. Technical items needing an external environment ────────────────
    ("5.1", "FedRAMP-authorized hosting (CSP) with documented data residency", "BLOCKING", "Hosting/Cloud", "Variable", "FedRAMP requires authorized infrastructure; current self-host path is not assessed", "docs/PRODUCTION_READINESS.md"),
    ("5.2", "KMS/HSM-managed secrets with key rotation procedures", "PARTIAL", "Security/Infra", "2–4 weeks", "Secrets are env-config today; regulated deployments require managed keys", "docs/COMPLIANCE_READINESS.md"),
    ("5.3", "Live IdP tenants — Entra ID, Okta, PIV/CAC verified", "PARTIAL", "Security", "2–4 weeks", "Harness + matrix exist; live-tenant verification does not", "tests/test_sso_interop.py, docs/security/IDP_INTEROP_MATRIX.md"),
    ("5.4", "SIEM/SOC ingestion in production with 24×7 monitoring", "PARTIAL", "SOC/Provider", "Variable", "SIEM module + audit exports exist; operating SOC does not", "aeon_siem.py"),
    ("5.5", "Backup/restore + DR validated in the production boundary", "PARTIAL", "Ops", "2–4 weeks", "Scripts + models exist; boundary validation does not", "scripts/dr_drill.py"),
    ("5.6", "SBOM attestation practice — signed SBOMs, vulnerability-response SLA", "PARTIAL", "Security", "2–4 weeks", "SBOM generator + CI artifact exist; signing + attestation practice does not", "scripts/sbom_report.py"),
    # ── 6. Procurement readiness (company-level) ──────────────────────────
    ("6.1", "SAM.gov registration, UEI, CAGE code", "GAP", "BD", "Hours–days", "Required to sell to US federal entities", "sam.gov"),
    ("6.2", "Security contact + reps & certs in SAM.gov", "GAP", "BD", "Hours", "Federal requirement", "sam.gov"),
    ("6.3", "Pricing vehicles — GSA schedule, state contracts, approved pricing", "GAP", "BD", "Months", "Procurement path for agencies", ""),
    ("6.4", "Incident reporting procedures to CISA/US-CERT", "GAP", "Security", "Days", "FedRAMP/contractual requirement", ""),
    ("6.5", "Records management — NARA-aligned retention of government records", "GAP", "Legal/Records", "Variable", "FedRAMP control family + contract terms", ""),
]


def _summary() -> dict:
    status_counts = dict.fromkeys(STATUSES, 0)
    per_category: dict[str, dict[str, int]] = {}
    for cid, _, status, *_ in _CONTROLS:
        status_counts[status] += 1
        category = cid.split(".")[0]
        bucket = per_category.setdefault(category, dict.fromkeys(STATUSES, 0))
        bucket[status] += 1

    total = len(_CONTROLS)
    categories = []
    for category in sorted(per_category):
        bucket = per_category[category]
        blocking = bucket["BLOCKING"]
        categories.append(
            {
                "id": category,
                "items": sum(bucket.values()),
                "blocking": blocking,
                "partial": bucket["PARTIAL"],
                "gap": bucket["GAP"],
                "non_blocking_ratio": round(1 - blocking / max(1, sum(bucket.values())), 3),
            }
        )
    return {
        "total_items": total,
        "by_status": status_counts,
        "categories": categories,
        "overall_non_blocking_ratio": round(1 - status_counts["BLOCKING"] / max(1, total), 3),
    }


def _build_report() -> dict:
    components = []
    for cid, title, status, owner, cost_time, requirement, links in _CONTROLS:
        components.append(
            {
                "type": "control",
                "bom-ref": cid,
                "name": title,
                "properties": [
                    {"name": "status", "value": status},
                    {"name": "category", "value": cid.split(".")[0]},
                    {"name": "owner", "value": owner},
                    {"name": "cost_time", "value": cost_time},
                    {"name": "requirement", "value": requirement},
                    {"name": "links", "value": links},
                ],
            }
        )
    report = {
        "bomFormat": BOM_FORMAT,
        "specVersion": SPEC_VERSION,
        "serialNumber": "gov-readiness-"
        + hashlib.sha256(
            (datetime.now(timezone.utc).isoformat() + json.dumps(_CONTROLS)).encode()
        ).hexdigest()[:12],
        "version": 1,
        "metadata": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tools": [{"name": "aeon-government-readiness-report", "version": "1.0"}],
            "component": {"type": "application", "name": "aeon-os", "version": "3.0"},
            "source": "docs/GOVERNMENT_READINESS_CHECKLIST.md",
        },
        "summary": _summary(),
        "components": components,
    }
    return report


_BADGE_COLORS = (
    (0.9, "#4c1"),      # brightgreen
    (0.8, "#97ca00"),   # green
    (0.7, "#a4a61d"),   # yellowgreen
    (0.6, "#dfb317"),   # yellow
    (0.5, "#fe7d37"),   # orange
    (0.0, "#e05d44"),   # red
)


def _badge_color(ratio: float) -> str:
    for threshold, color in _BADGE_COLORS:
        if ratio >= threshold:
            return color
    return _BADGE_COLORS[-1][1]


def _badge_svg(summary: dict) -> str:
    """Deterministic shields-style SVG for the gov-readiness non-blocking ratio.

    Stdlib-only and fully deterministic (no timestamps, no randomness) so the
    committed snapshot is stable across runs until the data changes.
    """
    ratio = round(summary["overall_non_blocking_ratio"], 3)
    label = "gov readiness"
    value = f"{ratio:.1%} non-blocking"
    color = _badge_color(ratio)

    def _width(text: str) -> int:
        # Approximate 11px Verdana metrics with padding; constant so output is stable.
        return int(round(6.6 * len(text))) + 20

    label_w = _width(label)
    value_w = _width(value)
    total_w = label_w + value_w
    label_cx = round(label_w / 2, 1)
    value_cx = round(label_w + value_w / 2, 1)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{total_w}" height="20" role="img" aria-label="{label}: {value}">
  <title>{label}: {value}</title>
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_w}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_w}" height="20" fill="#555"/>
    <rect x="{label_w}" width="{value_w}" height="20" fill="{color}"/>
    <rect width="{total_w}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" text-rendering="geometricPrecision" font-size="11">
    <text x="{label_cx}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{label_cx}" y="14">{label}</text>
    <text x="{value_cx}" y="15" fill="#010101" fill-opacity=".3">{value}</text>
    <text x="{value_cx}" y="14">{value}</text>
  </g>
</svg>
"""


def _badge_endpoint(summary: dict) -> dict:
    """shields.io endpoint-format JSON for a live README badge.

    The endpoint file is committed to the repo; the README points
    ``img.shields.io/endpoint`` at its raw URL. Color is derived from the
    same bands as the SVG badge, so the badge turns yellow/red automatically
    if the non-blocking ratio drops.
    """
    ratio = round(summary["overall_non_blocking_ratio"], 3)
    return {
        "schemaVersion": 1,
        "label": "gov readiness",
        "message": f"{ratio:.1%} non-blocking",
        "color": _badge_color(ratio),
        "cacheSeconds": 3600,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="AEON government-readiness report generator (stdlib-only).")
    ap.add_argument("--out", default="scripts/output/government_readiness.json")
    ap.add_argument(
        "--badge-out",
        default=None,
        help="Also write a shields-style SVG readiness badge to this path",
    )
    ap.add_argument(
        "--badge-endpoint-out",
        default=None,
        help="Also write a shields.io endpoint-format JSON badge to this path",
    )
    args = ap.parse_args()

    report = _build_report()
    payload = json.dumps(report, indent=2, sort_keys=True)
    report["sha256"] = hashlib.sha256(payload.encode()).hexdigest()
    payload = json.dumps(report, indent=2, sort_keys=True)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload + "\n")
    summary = report["summary"]
    print(
        f"wrote {out} ({len(payload)} bytes): {summary['total_items']} controls, "
        f"{summary['by_status']['BLOCKING']} blocking, "
        f"{summary['by_status']['PARTIAL']} partial, {summary['by_status']['GAP']} gap"
    )
    if args.badge_out:
        svg = _badge_svg(summary)
        badge = Path(args.badge_out)
        badge.parent.mkdir(parents=True, exist_ok=True)
        badge.write_text(svg)
        print(f"wrote {badge}: non-blocking {summary['overall_non_blocking_ratio']:.1%}")
    if args.badge_endpoint_out:
        endpoint = Path(args.badge_endpoint_out)
        endpoint.parent.mkdir(parents=True, exist_ok=True)
        endpoint.write_text(json.dumps(_badge_endpoint(summary), indent=2) + "\n")
        print(f"wrote {endpoint}: shields.io endpoint badge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
