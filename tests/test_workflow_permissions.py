"""Regression coverage for GitHub Actions token permissions."""

from __future__ import annotations

from pathlib import Path


WORKFLOW_DIR = Path(__file__).resolve().parents[1] / ".github" / "workflows"
READ_ONLY_WORKFLOWS = (
    "aeon-ci.yml",
    "docker-ci.yml",
    "quality-gate.yml",
    "railway-deploy.yml",
    "vercel-deploy.yml",
)


def test_ci_workflows_declare_read_only_default_permissions() -> None:
    """CI and deployment workflows must not inherit write-capable defaults."""
    expected = "permissions:\n  contents: read\n"
    for filename in READ_ONLY_WORKFLOWS:
        workflow = (WORKFLOW_DIR / filename).read_text(encoding="utf-8")
        assert expected in workflow, f"{filename} is missing read-only default permissions"


def test_vercel_preview_job_has_only_the_permission_it_needs() -> None:
    """The preview job may comment on its PR, but must retain read-only checkout access."""
    workflow = (WORKFLOW_DIR / "vercel-deploy.yml").read_text(encoding="utf-8")
    preview_job = workflow.split("  deploy-preview:", 1)[1]
    preview_job = preview_job.split("    steps:", 1)[0]

    assert "    permissions:\n      contents: read\n      pull-requests: write\n" in preview_job
    assert "packages: write" not in preview_job
    assert "contents: write" not in preview_job
