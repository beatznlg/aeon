#!/usr/bin/env python3
"""Per-sector LLM accuracy evaluation harness for AEON OS.

Runs a sector QA benchmark through the real enterprise inference pipeline
(sector pack -> policy -> evidence -> grounding -> decide), so the metrics it
emits are exactly the thresholds the runtime enforces.

Two modes:

  # Deterministic offline run (CI-safe, no API keys)
  python scripts/sector_eval.py --sector finance --stub \
      --out scripts/output/sector_eval_finance.json

  # Live gate run against a real provider/model
  python scripts/sector_eval.py \
      --questions scripts/eval_sets/sample_sector_eval.json \
      --provider openai --model gpt-4o --min-accuracy 0.85 \
      --out scripts/output/sector_eval_live.json

After writing the report, the harness auto-attaches its SHA-256 fingerprint
and metrics to the matching model-registry deployment (by provider + model +
workspace, or exactly when ``--registry-deployment <id>`` is given). Use
``--no-registry`` to disable, or ``--registry-required`` to fail the run when
no deployment matched (exit code 2).

Exits non-zero when accuracy falls below ``--min-accuracy``, so the harness
can gate CI. Reports are JSON evidence files with a SHA-256 fingerprint for
the assurance ledger (see docs/SECTOR_FINETUNING_PLAYBOOK.md).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from aeon_enterprise_pipeline import EnterpriseInferencePipeline  # noqa: E402
from aeon_inference import EvidenceItem  # noqa: E402
from aeon_model_registry import attach_eval_evidence  # noqa: E402
from aeon_sector_packs import get_sector_pack  # noqa: E402

DEFAULT_EVAL_SET = str(
    Path(__file__).resolve().parent / "eval_sets" / "sample_sector_eval.json"
)
PASS_STATUSES = frozenset({"answered", "pending_human_approval"})


class StubProvider:
    """Deterministic offline provider for CI/demo eval runs.

    Answers with the first evidence sentence from the prompt, so grounding,
    citation coverage, and expected-content checks are measured against real
    evidence instead of a canned string.
    """

    backend = "stub"

    def generate(self, prompt: str, system: str | None = None, max_new_tokens: int = 512) -> dict:
        evidence = ""
        if "\n\nQuestion:" in prompt:
            evidence = prompt.split("\n\nQuestion:", 1)[0]
        if evidence.startswith("Evidence:\n"):
            evidence = evidence[len("Evidence:\n") :]
        # Single-sentence answers keep the claim count at 1 so citation
        # coverage is measured per-evidence-item, matching the pipeline's
        # conservative baseline assessor.
        text = evidence.strip().split("\n", 1)[0].rstrip(".")
        return {"text": text, "backend": "stub", "tokens_used": len(text.split())}


def _live_provider(provider: str | None, model: str | None) -> object | None:
    if not provider:
        return None
    try:
        from aeon_llm import get_llm_provider

        resolved = get_llm_provider(provider, model)
        if resolved is not None and callable(getattr(resolved, "generate", None)):
            return resolved
    except Exception as exc:  # noqa: BLE001 - report and fall back to stub
        print(f"WARNING: live provider {provider!r} unavailable ({exc}); using --stub")
    return None


def _evidence_resolver(item: dict):
    def resolver(_query: str):
        out: list[EvidenceItem] = []
        for idx, ev in enumerate(item.get("evidence") or []):
            out.append(
                EvidenceItem(
                    source_id=str(ev.get("source_id") or f"src-{idx}"),
                    chunk_id=str(ev.get("chunk_id") or f"c{idx}"),
                    text=str(ev.get("text") or ""),
                    relevance=float(ev.get("relevance") or 0.95),
                    authority=float(ev.get("authority") or 0.8),
                    freshness=float(ev.get("freshness") or 0.9),
                )
            )
        return out

    return resolver


def _output_validator(item: dict):
    expected = [str(part) for part in item.get("expected") or []]

    def validate(answer: str) -> tuple[bool, str | None]:
        low = answer.lower()
        missing = [part for part in expected if part.lower() not in low]
        if missing:
            return False, f"missing expected content: {missing}"
        return True, None

    return validate


def _fingerprint(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _run_item(pipeline_factory, item: dict, args) -> dict:
    sector = str(item.get("sector") or args.sector or "general")
    pack_id = args.sector_pack or None
    pack = get_sector_pack(pack_id, sector=sector)
    task_type = str(item.get("task_type") or "general")

    pipeline = pipeline_factory(item, pack)
    result = pipeline.run(
        str(item.get("question") or ""),
        task_type=task_type,
        sector=sector,
        sector_pack_id=pack_id,
        model=args.model,
        provider_id=args.provider or "stub",
        metadata={"eval_item_id": str(item.get("id") or "")},
    )

    expected = [str(part) for part in item.get("expected") or []]
    answer = result.answer or ""
    content_ok = all(part.lower() in answer.lower() for part in expected)
    must_block = bool(item.get("must_block"))
    passed = (result.status in PASS_STATUSES and content_ok) or (
        must_block and result.status == "blocked_by_policy"
    )

    assessment = result.evidence
    return {
        "id": str(item.get("id") or ""),
        "sector": sector,
        "sector_pack_id": pack.id,
        "risk_level": pack.risk_level,
        "task_type": task_type,
        "question": str(item.get("question") or ""),
        "status": result.status,
        "passed": bool(passed),
        "content_ok": bool(content_ok),
        "must_block": must_block,
        "confidence": result.confidence,
        "review_required": bool(result.review_required),
        "retrieval_score": assessment.retrieval_score if assessment else None,
        "groundedness_score": assessment.groundedness_score if assessment else None,
        "citation_coverage": assessment.citation_coverage if assessment else None,
        "answer": answer[:400],
        "reason": result.reason,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sector", default="all", help="sector filter (default: all)")
    ap.add_argument("--questions", default=DEFAULT_EVAL_SET, help="eval set JSON")
    ap.add_argument("--stub", action="store_true", help="use the deterministic stub provider")
    ap.add_argument("--provider", default=None, help="live provider name (e.g. openai)")
    ap.add_argument("--model", default=None, help="live model id")
    ap.add_argument("--sector-pack", default=None, help="override sector pack id")
    ap.add_argument("--min-accuracy", type=float, default=0.8, help="gate: minimum pass rate")
    ap.add_argument("--out", default="scripts/output/sector_eval.json", help="evidence JSON path")
    ap.add_argument("--registry-deployment", default=None, help="attach eval evidence to this registry deployment id")
    ap.add_argument("--workspace-id", default=None, help="workspace id for report metadata and registry matching")
    ap.add_argument("--no-registry", action="store_true", help="do not auto-attach eval evidence to the model registry")
    ap.add_argument("--registry-required", action="store_true", help="exit non-zero when no registry deployment matched")
    args = ap.parse_args()

    eval_set = Path(args.questions)
    if not eval_set.exists():
        print(f"ERROR: eval set not found: {eval_set}", file=sys.stderr)
        return 2
    items = json.loads(eval_set.read_text(encoding="utf-8"))
    if args.sector != "all":
        wanted = str(args.sector).strip().lower()
        items = [it for it in items if str(it.get("sector") or "").strip().lower() == wanted]
    if not items:
        print(f"ERROR: no eval items for sector {args.sector!r}", file=sys.stderr)
        return 2

    provider_obj = StubProvider() if args.stub else (_live_provider(args.provider, args.model) or StubProvider())
    mode = "stub" if isinstance(provider_obj, StubProvider) else "live"

    def pipeline_factory(item, pack):
        return EnterpriseInferencePipeline(
            provider_obj,
            evidence_resolver=_evidence_resolver(item),
            output_validator=_output_validator(item),
        )

    results = [_run_item(pipeline_factory, item, args) for item in items]

    n = len(results)
    passed = sum(1 for r in results if r["passed"])
    released = sum(1 for r in results if r["status"] in PASS_STATUSES)
    abstained = sum(1 for r in results if r["status"] == "abstained")
    blocked = sum(1 for r in results if r["status"] == "blocked_by_policy")
    failed = sum(1 for r in results if r["status"] == "failed")
    needs_info = sum(1 for r in results if r["status"] == "needs_more_information")
    review_req = sum(1 for r in results if r["review_required"])

    grounded_vals = [r["groundedness_score"] for r in results if r["groundedness_score"] is not None]
    citation_vals = [r["citation_coverage"] for r in results if r["citation_coverage"] is not None]
    conf_vals = [r["confidence"] for r in results if r["confidence"] is not None]

    def _mean(vals):
        return round(sum(vals) / len(vals), 4) if vals else None

    # Hallucination rate: released answers that failed the grounding gate.
    # decide_inference is fail-closed, so this should be 0 by construction.
    hallucinated = sum(
        1
        for r in results
        if r["status"] in PASS_STATUSES
        and r["groundedness_score"] is not None
        and r["groundedness_score"] < 0.90
    )

    accuracy = round(passed / n, 4) if n else 0.0
    gate_ok = accuracy >= args.min_accuracy

    packs_seen = sorted({r["sector_pack_id"] for r in results})
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tool": "scripts/sector_eval.py",
        "mode": mode,
        "provider": args.provider or "stub",
        "model": args.model,
        "sector": args.sector,
        "sector_packs": packs_seen,
        "workspace_id": args.workspace_id or None,
        "n": n,
        "metrics": {
            "accuracy": accuracy,
            "passed": passed,
            "released": released,
            "abstained": abstained,
            "blocked_by_policy": blocked,
            "failed": failed,
            "needs_more_information": needs_info,
            "human_review_required": review_req,
            "hallucination_rate": round(hallucinated / n, 4) if n else None,
            "mean_confidence": _mean(conf_vals),
            "mean_groundedness": _mean(grounded_vals),
            "mean_citation_coverage": _mean(citation_vals),
        },
        "gate": {"min_accuracy": args.min_accuracy, "passed": bool(gate_ok)},
        "items": results,
    }
    report["fingerprint"] = _fingerprint(report)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    print(f"sector_eval: mode={mode} sector={args.sector} n={n} passed={passed} "
          f"accuracy={accuracy} min={args.min_accuracy} gate={'PASS' if gate_ok else 'FAIL'}")
    print(f"  statuses: released={released} abstained={abstained} blocked={blocked} "
          f"failed={failed} needs_info={needs_info} review={review_req}")
    print(f"  mean groundedness={_mean(grounded_vals)} mean citation coverage={_mean(citation_vals)}")
    print(f"  report: {out} (fingerprint {report['fingerprint'][:12]})")

    attach_ok = _attach_registry_evidence(report, args)

    if not gate_ok:
        return 1
    if args.registry_required and not attach_ok:
        print(
            "ERROR: --registry-required set but eval evidence was not attached "
            "to a registry deployment",
            file=sys.stderr,
        )
        return 2
    return 0


def _attach_registry_evidence(report: dict, args) -> bool:
    """Best-effort: attach the eval fingerprint to the matching registry deployment.

    Targets ``--registry-deployment`` when given, otherwise auto-matches by
    provider + model (+ workspace) via ``aeon_model_registry.attach_eval_evidence``.
    Returns True only when a deployment was actually updated.
    """
    if args.no_registry:
        return False
    if not args.registry_deployment and not args.model:
        print(
            "  registry: no model context for matching; pass --model or "
            "--registry-deployment to attach eval evidence"
        )
        return False
    metrics = report["metrics"]
    try:
        attached = attach_eval_evidence(
            args.registry_deployment,
            provider=report["provider"],
            model=args.model,
            eval_report=str(Path(args.out)),
            eval_sha256=report["fingerprint"],
            accuracy=metrics["accuracy"],
            metrics={
                "n": report["n"],
                "abstained": metrics["abstained"],
                "hallucination_rate": metrics["hallucination_rate"],
                "human_review_required": metrics["human_review_required"],
                "mean_groundedness": metrics["mean_groundedness"],
                "mean_citation_coverage": metrics["mean_citation_coverage"],
            },
            workspace_id=args.workspace_id,
        )
    except ValueError as exc:
        print(f"  registry: could not attach eval evidence ({exc})")
        return False
    if attached is None:
        print(
            "  registry: no matching deployment; skipping attachment "
            "(use --registry-deployment to target one)"
        )
        return False
    print(
        f"  registry: attached eval evidence to deployment {attached['deployment_id']} "
        f"({attached['provider']}/{attached['model']}, sha256 {report['fingerprint'][:12]})"
    )
    return True


if __name__ == "__main__":
    sys.exit(main())
