#!/usr/bin/env python3
"""Build a one-page A4 sales brief PDF for AEON OS.

Reuses the pure-stdlib PDF writer from build_aeon_presentation.py (same
slide/PDF machinery, retargeted to an A4 portrait page). The brief is a
company/government-facing one-pager: positioning, platform capabilities,
sector-adaptive intelligence, trust evidence, and honest pilot framing.

Run:  python3 scripts/build_sales_brief.py
Out:  docs/AEON_OS_Sales_Brief.pdf
"""
from __future__ import annotations

from pathlib import Path

import build_aeon_presentation as pres

# A4 portrait, points.
W, H = 595, 842

# Retarget the shared writer classes to this page size. The Slide/Pdf classes
# resolve the module-level W/H globals at call time, so this is sufficient.
pres.W, pres.H = W, H

OUT = Path(__file__).resolve().parents[1] / "docs" / "AEON_OS_Sales_Brief.pdf"

BG = pres.BG
PANEL = pres.PANEL
PANEL_2 = pres.PANEL_2
TEXT = pres.TEXT
MUTED = pres.MUTED
CYAN = pres.CYAN
BLUE = pres.BLUE
ORANGE = pres.ORANGE
GREEN = pres.GREEN

MARGIN = 42
CONTENT_W = W - 2 * MARGIN  # 511
FOOTER_Y = 30  # bottom-up: footer line sits 30pt above the page bottom


class BriefPage(pres.Slide):
    """Single A4 portrait page with a clean header band (no slide beacon)."""

    def __init__(self) -> None:
        self.number = 1
        self.ops: list[str] = []
        self.rect(0, 0, W, H, BG)
        # Top accent rule: the one consistent visual signature.
        self.rect(0, H - 6, W, 6, CYAN)

    def section(self, title: str, top: float) -> None:
        self.text(title, MARGIN, top, 14.5, TEXT, "F2")
        self.rect(MARGIN, H - top - 5, 150, 3, CYAN)

    def footer(self, label: str) -> None:
        self.line(MARGIN, FOOTER_Y, W - MARGIN, FOOTER_Y, (36, 54, 80), 0.8)
        self.text(label, MARGIN, H - 27, 9, MUTED)
        self.text("1", W - MARGIN - 14, H - 27, 9, CYAN, "F2")


def add_header(page: BriefPage) -> None:
    page.text("AEON OS", MARGIN, 20, 30, TEXT, "F2")
    page.text(
        "Advanced Evolutionary Orchestrator Network - open-source AI agent platform",
        MARGIN,
        58,
        11.5,
        CYAN,
    )
    page.text("SALES BRIEF - COMPANY & GOVERNMENT", W - MARGIN - 205, 22, 10.5, ORANGE, "F2")
    page.text("v3.0  |  github.com/beatznlg/aeon", W - MARGIN - 205, 42, 10, MUTED)
    page.line(MARGIN, H - 84, W - MARGIN, H - 84, (36, 54, 80), 0.8)


def add_positioning(page: BriefPage) -> None:
    page.block(
        "AEON OS is an open-source AI orchestration platform: multi-tenant workspaces, a governed "
        "agent kernel, RAG knowledge bases, automations with human approvals, and evidence-backed "
        "governance - deployable self-hosted, on-prem, or air-gapped.",
        MARGIN,
        94,
        CONTENT_W,
        11,
        TEXT,
        leading=15,
    )


CAPABILITY_CARDS: list[tuple[str, list[str], tuple[int, int, int]]] = [
    ("Multi-tenant workspaces", ["Workspaces, memberships, RBAC", "Viewer / Operator / Admin roles", "Tenant-isolated LLM providers"], CYAN),
    ("Agent kernel", ["Reflective agents + memory", "Safe, validated tool runner", "Swarms & automations"], BLUE),
    ("LLM routing & tuning", ["10+ providers, incl. local", "Ollama / vLLM / LM Studio", "Fine-tuning playbook"], ORANGE),
    ("RAG & grounding", ["Hybrid retrieval", "Grounding & citation gates", "Per-sector policies"], GREEN),
    ("Governance & audit", ["Hash-chained audit ledger", "PII / PHI redaction", "Human-in-the-loop"], CYAN),
    ("Deployment", ["Self-hosted or on-prem", "Air-gapped capable", "No SaaS lock-in"], BLUE),
]


def add_capabilities(page: BriefPage) -> None:
    page.section("Platform capabilities", 150)
    card_w = (CONTENT_W - 2 * 14) / 3
    xs = [MARGIN, MARGIN + card_w + 14, MARGIN + 2 * (card_w + 14)]
    for row in range(2):
        top = 170 + row * (118 + 16)
        for col in range(3):
            title, body, accent = CAPABILITY_CARDS[row * 3 + col]
            page.card(xs[col], top, card_w, 118, title, body, accent, size=9)


def add_sector_strip(page: BriefPage) -> None:
    page.section("Sector-adaptive intelligence", 436)
    page.card(
        MARGIN,
        456,
        CONTENT_W,
        70,
        "Seven policy-gated sector packs",
        "Health, finance, government, defense, critical infrastructure, manufacturing, utilities - "
        "each with its own inference policy (grounding, citations, human review), a fine-tuning "
        "playbook, and automated per-sector accuracy gates.",
        GREEN,
        size=10,
    )


TRUST_BULLETS = [
    "Measured quality gate in CI: 414 tests, Bandit 0 High, pip-audit clean; SBOM + DR-drill evidence artifacts per run.",
    "Enforced grounding gates (retrieval >= 0.78, groundedness >= 0.90, citations 1.0) with hash-chained audit and assurance ledgers.",
    "Threat model (prompt injection, tenant isolation, SSRF, exfiltration); IdP interop matrix (Entra ID, Okta, PIV/CAC); formal IR / access-review / retention policies.",
    "Model registry records provider, adapter version, and eval fingerprint (SHA-256) for every approved deployment.",
]


def add_trust(page: BriefPage) -> None:
    page.section("Trust & readiness evidence", 540)
    page.card(
        MARGIN,
        560,
        CONTENT_W,
        112,
        "Verified engineering evidence - pilot-grade today",
        TRUST_BULLETS,
        CYAN,
        size=9.5,
    )


def add_pilot_framing(page: BriefPage) -> None:
    page.card(
        MARGIN,
        688,
        CONTENT_W,
        92,
        "Pilot-ready - never self-certified",
        "AEON ships engineering readiness evidence and deployment controls, not self-issued "
        "certifications. FedRAMP, SOC 2, HIPAA, PCI, and CJIS require independent audits and "
        "agency agreements. AEON is built for the pilots and controlled assessments that lead there.",
        ORANGE,
        size=10,
    )


def main() -> None:
    page = BriefPage()
    add_header(page)
    add_positioning(page)
    add_capabilities(page)
    add_sector_strip(page)
    add_trust(page)
    add_pilot_framing(page)
    page.footer("AEON OS | sales brief | github.com/beatznlg/aeon | August 2026")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = pres.Pdf().build([page])
    OUT.write_bytes(pdf)
    print(f"wrote {OUT} ({len(pdf)} bytes, 1 page)")


if __name__ == "__main__":
    main()
