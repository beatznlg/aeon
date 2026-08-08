#!/usr/bin/env python3
"""Prepare a scripted, pre-verified AEON OS demo environment.

Seeds the exact state the DEMO_RUNBOOK describes: a dev-mode admin login,
sector workspaces with distinct per-workspace LLM preferences and operating
profiles, approved + activated model-registry deployments, and per-sector
stub evals whose fingerprints are auto-attached to the matching deployment.

Everything is idempotent: re-running converges (existing workspaces and
deployments are reused, evals are regenerated with the deterministic stub).

Usage:
    python scripts/prepare_demo.py
    python scripts/prepare_demo.py --root /var/aeon --admin-password '...' --no-evals
    python scripts/prepare_demo.py --out scripts/output/demo_ready.json

Writes a verification report (default scripts/output/demo_ready.json) with
workspace ids, active deployments, eval accuracy, and a report SHA-256.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEMO_ADMIN_ID = "admin-fallback"  # matches aeon_auth._FallbackAdmin.id

# slug -> (name, sector, model, org_type, data_classification, frameworks)
DEMO_WORKSPACES: tuple[tuple[str, str, str, str, str, str, tuple[str, ...]], ...] = (
    ("acme-health", "Acme Health - Provider", "health", "demo-health-llm", "healthcare", "confidential", ("HIPAA",)),
    ("acme-finance", "Acme Finance - Banking", "finance", "demo-finance-llm", "enterprise", "confidential", ("PCI-DSS",)),
    ("gov-city", "CityGov Services", "government", "demo-gov-llm", "government", "restricted", ("NIST-800-53", "FEDRAMP")),
    ("acme-manufacturing", "Acme Manufacturing", "manufacturing", "demo-mfg-llm", "enterprise", "internal", ("NIST-CSF",)),
)

ADAPTER_VERSION = "demo-adapter-1"
PROVIDER = "stub"  # zero-key demo; every workspace gets a distinct model id


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _configure_env(args: argparse.Namespace) -> dict[str, str]:
    """Set the environment the demo server will boot with, then return it."""
    os.environ.setdefault("AEON_ENV", "development")
    os.environ.setdefault("AEON_ROOT", str(args.root))
    os.environ.setdefault("AEON_ADMIN_EMAIL", args.admin_email)
    os.environ.setdefault("AEON_DATABASE_URL", args.database_url)
    os.environ.setdefault("NEXTAUTH_SECRET", "demo-secret-0123456789abcdef0123456789abcdef")
    os.environ["ADMIN_EMAIL"] = args.admin_email
    os.environ["ADMIN_PASSWORD_HASH"] = args.admin_password_hash
    return os.environ.copy()


def _ensure_admin(db: Any, email: str, password_hash: str) -> str:
    """Create or update the dev-mode admin user; returns its id."""
    existing = db.get_user_by_email(email)
    if existing:
        # Align the DB row with the fallback-admin identity so the dev login
        # token (user id "admin-fallback") resolves memberships.
        if str(existing.id) == DEMO_ADMIN_ID:
            return DEMO_ADMIN_ID
        return str(existing.id)
    from aeon_db import DEFAULT_TENANT_ID, User

    with db.session() as s:
        s.add(
            User(
                id=DEMO_ADMIN_ID,
                email=email,
                name="Demo Administrator",
                password=password_hash,
                role="ADMIN",
                tenant_id=DEFAULT_TENANT_ID,
            )
        )
        s.commit()
    return DEMO_ADMIN_ID


def _ensure_workspace(db: Any, admin_id: str, slug: str, name: str, model: str) -> dict[str, Any]:
    """Create (or reuse) a workspace, its admin membership, and LLM preference."""
    from aeon_db import DEFAULT_TENANT_ID, Membership, Workspace, update_workspace_llm_preference

    workspace = db.get_workspace_by_slug(slug)
    if workspace is None:
        workspace = Workspace(
            id=str(uuid.uuid4()),
            tenant_id=DEFAULT_TENANT_ID,
            slug=slug,
            name=name,
            plan="enterprise",
            llm_provider=PROVIDER,
            llm_model=model,
        )
        with db.session() as s:
            s.add(workspace)
            s.commit()

    workspace_id = str(workspace.id)
    with db.session() as s:
        membership = db.get_membership(workspace_id, admin_id)
        if membership is None:
            s.add(Membership(workspace_id=workspace_id, user_id=admin_id, role="ADMIN"))
            s.commit()

    try:
        update_workspace_llm_preference(workspace_id, provider=PROVIDER, model=model)
    except ValueError:
        pass  # workspace vanished concurrently; next run converges
    return {"id": workspace_id, "slug": slug, "name": name, "provider": PROVIDER, "model": model}


def _set_operating_profile(root: Path, workspace_id: str, sector: str, org_type: str, classification: str, frameworks: tuple[str, ...]) -> dict[str, Any] | None:
    """Apply a sector-aligned operating profile; never fatal if unknown values are rejected."""
    try:
        from aeon_operating_profiles import get_operating_profile_manager, recommend_profiles

        manager = get_operating_profile_manager(root)
        candidates = recommend_profiles(sector=sector)
        if not candidates:
            return None
        profile_id = str(candidates[0]["id"])
        return manager.set(
            workspace_id,
            profile_id=profile_id,
            sector=sector,
            organization_type=org_type,
            deployment_mode="cloud",
            data_classification=classification,
            compliance_frameworks=frameworks,
        ).to_dict()
    except Exception as exc:  # nosec B110 - profiles are demo metadata
        return {"skipped": str(exc)[:120]}


def _sector_pack_id(sector: str) -> str | None:
    try:
        from aeon_sector_packs import SECTOR_PACKS

        for pack in SECTOR_PACKS:
            if pack.sector.lower() == sector.lower():
                return pack.id
    except Exception:  # nosec B110
        return None
    return None


def _ensure_deployment(workspace_id: str, sector: str, model: str) -> dict[str, Any] | None:
    """Register -> approve -> activate one deployment per workspace (idempotent)."""
    from aeon_model_registry import (
        activate_deployment,
        approve_deployment,
        list_deployments,
        register_deployment,
    )

    existing = list_deployments(workspace_id=workspace_id, provider=PROVIDER, model=model)
    for record in existing:
        if record.get("status") in ("registered", "approved", "active"):
            if record.get("status") != "active":
                try:
                    approve_deployment(record["deployment_id"], os.environ.get("ADMIN_EMAIL", "admin@aeon.local"), workspace_id=workspace_id)
                    activate_deployment(record["deployment_id"], os.environ.get("ADMIN_EMAIL", "admin@aeon.local"), workspace_id=workspace_id)
                except Exception:  # nosec B110 - converges on next run
                    pass
            return record

    pack_id = _sector_pack_id(sector)
    record = register_deployment(
        provider=PROVIDER,
        model=model,
        workspace_id=workspace_id,
        adapter_version=ADAPTER_VERSION,
        base_model=model,
        sector_pack_id=pack_id,
        rollback_plan="Revert to the general-business base model and re-run sector eval",
        notes="Seeded by scripts/prepare_demo.py",
    )
    approve_deployment(
        record["deployment_id"],
        os.environ.get("ADMIN_EMAIL", "admin@aeon.local"),
        workspace_id=workspace_id,
        note="Demo seed approval",
    )
    return activate_deployment(
        record["deployment_id"],
        os.environ.get("ADMIN_EMAIL", "admin@aeon.local"),
        workspace_id=workspace_id,
    )


def _run_sector_eval(sector: str, model: str, workspace_id: str, out_dir: Path, env: dict[str, str]) -> dict[str, Any]:
    """Run the deterministic stub eval and auto-attach its fingerprint."""
    out = out_dir / f"sector_eval_{workspace_id[:8]}_{sector}.json"
    cmd = [
        sys.executable,
        "scripts/sector_eval.py",
        "--sector", sector,
        "--stub",
        "--model", model,
        "--workspace-id", workspace_id,
        "--registry-required",
        "--out", str(out),
    ]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=300)
    report: dict[str, Any] = {"ok": proc.returncode == 0, "exit": proc.returncode, "out": str(out)}
    if proc.returncode == 0:
        try:
            data = json.loads(out.read_text())
            report["accuracy"] = (data.get("metrics") or {}).get("accuracy")
            report["items"] = data.get("n")
        except Exception:  # nosec B110
            report["note"] = "eval report unreadable"
    else:
        report["stderr_tail"] = (proc.stderr or proc.stdout or "").strip()[-300:]
    return report


def _verify(root: Path, workspaces: list[dict[str, Any]], evals: list[dict[str, Any]]) -> dict[str, Any]:
    """Gather the evidence the briefing needs and return the report payload."""
    from aeon_model_registry import get_active_deployments

    ws_summary = []
    for ws in workspaces:
        deployments = get_active_deployments(workspace_id=ws["id"])
        ws_summary.append({**ws, "active_deployments": deployments})

    ledger = root / "assurance_ledger.jsonl"
    ledger_records = sum(1 for _ in ledger.open()) if ledger.exists() else 0

    return {
        "generated_at": _now_iso(),
        "admin": {"email": os.environ.get("ADMIN_EMAIL", ""), "demo_password": os.environ.get("AEON_ADMIN_PASSWORD", "")},
        "root": str(root),
        "workspaces": ws_summary,
        "evals": evals,
        "assurance_ledger_records": ledger_records,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed a scripted, pre-verified AEON OS demo environment.")
    ap.add_argument("--root", default="./aeon_state/server", help="AEON_ROOT state dir (default: ./aeon_state/server)")
    ap.add_argument("--database-url", default="", help="AEON_DATABASE_URL override (default: sqlite aeon_state/aeon.db)")
    ap.add_argument("--admin-email", default="admin@demo.local", help="demo admin email (default: admin@demo.local)")
    ap.add_argument("--admin-password", default="demo-admin-password", help="demo admin password (default: demo-admin-password)")
    ap.add_argument("--out", default="scripts/output/demo_ready.json", help="verification report path")
    ap.add_argument("--no-evals", action="store_true", help="skip per-sector eval generation")
    args = ap.parse_args()

    from werkzeug.security import generate_password_hash

    args.root = Path(args.root).resolve()
    args.admin_password_hash = generate_password_hash(args.admin_password)

    os.environ.setdefault("AEON_ADMIN_PASSWORD", args.admin_password)
    env = _configure_env(args)

    # DB must be created before the app modules are imported.
    from aeon_db import get_db, init_db

    init_db()
    db = get_db()
    db.ensure_default_tenant()
    db.ensure_default_workspace()

    admin_id = _ensure_admin(db, args.admin_email, args.admin_password_hash)

    workspaces: list[dict[str, Any]] = []
    for slug, name, sector, model, org_type, classification, frameworks in DEMO_WORKSPACES:
        ws = _ensure_workspace(db, admin_id, slug, name, model)
        ws["sector"] = sector
        ws["operating_profile"] = _set_operating_profile(args.root, ws["id"], sector, org_type, classification, frameworks)
        deployment = _ensure_deployment(ws["id"], sector, model)
        ws["deployment_id"] = (deployment or {}).get("deployment_id")
        workspaces.append(ws)

    evals: list[dict[str, Any]] = []
    if not args.no_evals:
        out_dir = REPO_ROOT / "scripts" / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        for ws in workspaces:
            if not ws.get("deployment_id"):
                continue
            result = _run_sector_eval(ws["sector"], ws["model"], ws["id"], out_dir, env)
            result["workspace"] = ws["slug"]
            result["sector"] = ws["sector"]
            evals.append(result)

    report = _verify(args.root, workspaces, evals)
    report["sha256"] = hashlib.sha256(json.dumps(report, sort_keys=True).encode("utf-8")).hexdigest()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(f"wrote {out_path.resolve()}")

    print("\n=== AEON OS demo environment ready ===")
    print(f"admin login : {args.admin_email} / {args.admin_password}  (dev-mode fallback)")
    print(f"aeon root   : {args.root}")
    print(f"ledger      : {report['assurance_ledger_records']} assurance record(s)")
    for ws in workspaces:
        dep = "active" if ws.get("deployment_id") else "missing"
        eval_ok = next((e for e in evals if e.get("workspace") == ws["slug"]), None)
        acc = f"acc={eval_ok.get('accuracy')}" if eval_ok and eval_ok.get("ok") else ("no eval" if args.no_evals else "eval FAILED")
        print(f"  {ws['slug']:<20} {ws['id'][:8]}  provider={ws['provider']:<4} model={ws['model']:<18} deployment={dep:<6} {acc}")

    failed = [e for e in evals if not e.get("ok")]
    if failed:
        print(f"\nWARNING: {len(failed)} eval(s) failed; see stderr in the report.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
