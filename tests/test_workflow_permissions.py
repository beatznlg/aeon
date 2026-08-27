"""Regression coverage for GitHub Actions token permissions."""

from __future__ import annotations

from pathlib import Path


WORKFLOW_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"
READ_ONLY_WORKFLOWS = (
    "aeon-ci.yml",
    "docker-ci.yml",
    "quality-gate.yml",
    "railway-deploy.yml",
)


def test_ci_workflows_declare_read_only_default_permissions() -> None:
    """CI and deployment workflows must not inherit write-capable defaults."""
    expected = "permissions:\n  contents: read\n"
    for filename in READ_ONLY_WORKFLOWS:
        workflow = (WORKFLOW_DIR / filename).read_text(encoding="utf-8")
        assert expected in workflow, f"{filename} is missing read-only default permissions"
