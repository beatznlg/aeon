#!/usr/bin/env python3
"""Build a printable one-page demo agenda PDF for AEON OS.

Reuses the pure-stdlib PDF writer from build_aeon_presentation.py (same
slide/PDF machinery, retargeted to A4 portrait) so the agenda can be
regenerated anywhere without extra dependencies. Maps the DEMO_RUNBOOK's
15-minute arc to the workspaces seeded by scripts/prepare_demo.py
(acme-health, acme-finance, gov-city, acme-manufacturing).

Run:  python3 scripts/build_demo_agenda.py
Out:  docs/AEON_OS_Demo_Agenda.pdf
"""
from __future__ import annotations

from pathlib import Path

import build_aeon_presentation as pres

# A4 portrait, points.
W, H = 595, 842
pres.W, pres.H = W, H

OUT = Path(__file__).resolve().parents[1] / "docs" / "AEON_OS_Demo_Agenda.pdf"

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


class AgendaPage(pres.Slide):
    """Single A4 portrait page with a clean header band (no slide beacon)."""

    def __init__(self) -> None:
        self.number = 1
        self.ops: list[str] = []
        self.rect(0, 0, W, H, BG)
        self.rect(0, H - 6, W, 6, CYAN)

    def section(self, title: str, top: float) -> None:
        self.text(title, MARGIN, top, 14.5, TEXT, "F2")
        self.rect(MARGIN, H - top - 5, 150, 3, CYAN)

    def footer(self, label: str) -> None:
        self.line(MARGIN, 30, W - MARGIN, 30, (36, 54, 80), 0.8)
        self.text(label, MARGIN, H - 27, 9, MUTED)
        self.text("1", W - MARGIN - 14, H - 27, 9, CYAN, "F2")


def add_header(page: AgendaPage) -> None:
    page.text("AEON OS", MARGIN, 20, 30, TEXT, "F2")
    page.text("Demo Agenda - 15-Minute Briefing", MARGIN, 58, 13.5, CYAN, "F2")
    page.text("COMPANY & GOVERNMENT", W - MARGIN - 170, 26, 10.5, ORANGE, "F2")
    page.text("v3.0  |  github.com/beatznlg/aeon", W - MARGIN - 170, 44, 9.5, MUTED)
    page.line(MARGIN, H - 84, W - MARGIN, H - 84, (36, 54, 80), 0.8)


# (start, end, title, detail)
ARC: list[tuple[str, str, str, str]] = [
    ("0:00", "0:30", "Landing & login", "Dashboard: workspaces, automations, approvals, capabilities. Login admin@demo.local / demo-admin-password."),
    ("0:30", "3:00", "Multi-tenant LLM control", "Open /llm; switch provider and model per workspace. Two tenants run different models with zero cross-talk (provider isolation)."),
    ("3:00", "5:00", "RAG & grounding", "acme-health: ask a grounded question, show citations and the enforcement gates (retrieval >= 0.78, groundedness >= 0.90, citations 1.0)."),
    ("5:00", "7:00", "Workflows & automations", "acme-manufacturing: run a workflow, trigger an automation, show execution history and metrics."),
    ("7:00", "9:00", "Human-in-the-loop", "acme-finance: show a pending approval, approve it, watch the deferred action execute."),
    ("9:00", "11:00", "Marketplace + MCP", "Install a plugin, connect an MCP server, invoke a tool from chat."),
    ("11:00", "13:00", "Governance", "gov-city: compliance profile, /ready gate, audit-chain integrity check, SSO/SCIM config (redacted)."),
    ("13:00", "15:00", "Evidence & pilot framing", "Model registry with eval fingerprints, SBOM, DR drill. State honestly: pilot-ready, not certified."),
]


def add_arc(page: AgendaPage) -> None:
    page.section("The 15-minute arc", 96)
    y = 116
    page.rect(MARGIN, H - 420, CONTENT_W, 296, PANEL, PANEL_2, 1)
    for start, end, title, detail in ARC:
        page.text(f"{start}-{end}", MARGIN + 16, y + 2, 9.5, CYAN, "F2")
        page.text(title, MARGIN + 92, y + 2, 10.5, TEXT, "F2")
        lines = pres.wrap(detail, 330, 9)
        for i, line in enumerate(lines[:2]):
            page.text(line, MARGIN + 92, y + 19 + i * 12, 9, MUTED)
        y += 34
    page.text("Run it live, or scroll to any step on request - the demo is fully scripted and idempotent.", MARGIN + 16, 400, 9.5, ORANGE, "F1")


SECTORS: list[tuple[str, str, str, tuple[int, int, int]]] = [
    ("acme-health", "Healthcare", "Diagnostics demo - mandatory human review + BAA profile declaration. Demo data, not clinical advice.", CYAN),
    ("acme-finance", "Banking", "Fraud/risk scoring with human approval gates. No autonomous lending or credit decisions.", BLUE),
    ("gov-city", "Government", "RBAC, SSO, immutable audit, readiness gate. CJIS/FedRAMP require agency processes.", GREEN),
    ("acme-manufacturing", "Manufacturing", "Maintenance/logistics automation with the condition engine (run_if, thresholds).", ORANGE),
]


def add_sectors(page: AgendaPage) -> None:
    page.section("Sector scenarios - the four seeded workspaces", 432)
    card_w = (CONTENT_W - 14) / 2
    for i, (slug, sector, detail, accent) in enumerate(SECTORS):
        col = i % 2
        row = i // 2
        x = MARGIN + col * (card_w + 14)
        top = 452 + row * 104
        page.rect(x, H - top - 96, card_w, 96, PANEL, PANEL_2, 1)
        page.rect(x, H - top - 4, card_w, 4, accent)
        page.text(f"{slug}  |  {sector}", x + 14, top + 14, 10.5, TEXT, "F2")
        lines = pres.wrap(detail, int(card_w - 28), 8.5)
        yy = top + 36
        for line in lines[:4]:
            page.text(line, x + 14, yy, 8.5, MUTED)
            yy += 12


def add_prep(page: AgendaPage) -> None:
    page.section("Before the briefing (5 minutes)", 664)
    page.rect(MARGIN, H - 684 - 64, CONTENT_W, 64, PANEL, PANEL_2, 1)
    page.rect(MARGIN, H - 684 - 4, CONTENT_W, 4, GREEN)
    page.block(
        [
            "python3 scripts/prepare_demo.py   # idempotent; re-run the morning of the demo",
            "Evidence at hand: scripts/output/demo_ready.json, sbom.json, dr_report.json, government_readiness.json",
            "Never claim certification (FedRAMP/HIPAA/PCI/CJIS/SOC 2) - pilot-ready framing only (docs/COMPLIANCE_READINESS.md).",
        ],
        MARGIN + 16,
        706,
        CONTENT_W - 32,
        9.5,
        TEXT,
        leading=15,
    )


def main() -> None:
    page = AgendaPage()
    add_header(page)
    add_arc(page)
    add_sectors(page)
    add_prep(page)
    page.footer("AEON OS | demo agenda | github.com/beatznlg/aeon | August 2026")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = pres.Pdf().build([page])
    OUT.write_bytes(pdf)
    print(f"wrote {OUT} ({len(pdf)} bytes, 1 page)")


if __name__ == "__main__":
    main()
