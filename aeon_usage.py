"""
AEON OS Phase 5 — Observability, Billing & Usage Metering
==========================================================
Lightweight usage tracking, billing calculator, and system health collector.

Usage:
    from aeon_usage import UsageMeter, BillingCalculator, HealthCollector
    meter = UsageMeter(root)
    meter.record_event(UsageEvent(...))
    summary = meter.get_summary(workspace_id="ws-1", days=30)

    billing = BillingCalculator(root)
    status = billing.workspace_status("ws-1")

    health = HealthCollector(root)
    status = health.snapshot()
"""

import json
import secrets as _secrets
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# === models ===================================================================

@dataclass
class UsageEvent:
    id: str
    timestamp: float
    user_id: str | None
    workspace_id: str | None
    action: str
    module: str
    quantity: float
    cost: float
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "action": self.action,
            "module": self.module,
            "quantity": self.quantity,
            "cost": self.cost,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UsageEvent":
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            user_id=data.get("user_id"),
            workspace_id=data.get("workspace_id"),
            action=data.get("action", "unknown"),
            module=data.get("module", "global"),
            quantity=float(data.get("quantity", 1)),
            cost=float(data.get("cost", 0)),
            metadata=data.get("metadata", {}),
        )


@dataclass
class BillingPlan:
    id: str
    name: str
    limits: dict[str, float]
    price_per_request: float
    price_per_1k_tokens: float


# === helpers ==================================================================

def _generate_id() -> str:
    return _secrets.token_urlsafe(8)


def _now() -> float:
    return time.time()


# === usage meter ==============================================================

class UsageMeter:
    """Append-only usage event store with simple aggregation."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.usage_dir = self.root / "usage"
        self.usage_dir.mkdir(parents=True, exist_ok=True)
        self.events_file = self.usage_dir / "events.jsonl"

    def record_event(
        self,
        *,
        action: str,
        module: str = "global",
        quantity: float = 1.0,
        cost: float = 0.0,
        user_id: str | None = None,
        workspace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UsageEvent:
        event = UsageEvent(
            id=_generate_id(),
            timestamp=_now(),
            user_id=user_id,
            workspace_id=workspace_id,
            action=action,
            module=module,
            quantity=float(quantity),
            cost=float(cost),
            metadata=metadata or {},
        )
        with self.events_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        return event

    def iter_events(self, workspace_id: str | None = None, days: int = 30):
        if not self.events_file.exists():
            return
        cutoff = _now() - (days * 24 * 60 * 60)
        with self.events_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if data.get("timestamp", 0) < cutoff:
                        continue
                    if workspace_id and data.get("workspace_id") != workspace_id:
                        continue
                    yield UsageEvent.from_dict(data)
                except Exception:  #nosec B112
                    continue

    def get_summary(
        self,
        workspace_id: str | None = None,
        days: int = 30,
    ) -> dict[str, Any]:
        total_quantity = 0.0
        total_cost = 0.0
        by_action: dict[str, dict[str, float]] = defaultdict(lambda: {"quantity": 0.0, "cost": 0.0, "count": 0})
        by_module: dict[str, dict[str, float]] = defaultdict(lambda: {"quantity": 0.0, "cost": 0.0, "count": 0})
        by_day: dict[str, dict[str, float]] = defaultdict(lambda: {"quantity": 0.0, "cost": 0.0, "count": 0})
        total_count = 0

        for event in self.iter_events(workspace_id=workspace_id, days=days):
            total_quantity += event.quantity
            total_cost += event.cost
            total_count += 1

            by_action[event.action]["quantity"] += event.quantity
            by_action[event.action]["cost"] += event.cost
            by_action[event.action]["count"] += 1

            by_module[event.module]["quantity"] += event.quantity
            by_module[event.module]["cost"] += event.cost
            by_module[event.module]["count"] += 1

            day = time.strftime("%Y-%m-%d", time.localtime(event.timestamp))
            by_day[day]["quantity"] += event.quantity
            by_day[day]["cost"] += event.cost
            by_day[day]["count"] += 1

        return {
            "period_days": days,
            "workspace_id": workspace_id,
            "total_events": total_count,
            "total_quantity": total_quantity,
            "total_cost": round(total_cost, 6),
            "by_action": {k: {a: round(b, 6) if isinstance(b, float) else b for a, b in v.items()} for k, v in by_action.items()},
            "by_module": {k: {a: round(b, 6) if isinstance(b, float) else b for a, b in v.items()} for k, v in by_module.items()},
            "by_day": {k: {a: round(b, 6) if isinstance(b, float) else b for a, b in v.items()} for k, v in sorted(by_day.items())},
        }


# === billing calculator =======================================================

DEFAULT_PLANS = {
    "free": BillingPlan(
        id="free",
        name="Free",
        limits={"requests": 1000, "tokens": 100_000, "workflows": 10, "integrations": 5},
        price_per_request=0.0,
        price_per_1k_tokens=0.0,
    ),
    "team": BillingPlan(
        id="team",
        name="Team",
        limits={"requests": 50_000, "tokens": 5_000_000, "workflows": 500, "integrations": 50},
        price_per_request=0.001,
        price_per_1k_tokens=0.02,
    ),
    "enterprise": BillingPlan(
        id="enterprise",
        name="Enterprise",
        limits={"requests": 1_000_000, "tokens": 100_000_000, "workflows": 100_000, "integrations": 10_000},
        price_per_request=0.0005,
        price_per_1k_tokens=0.01,
    ),
}


class BillingCalculator:
    """Compute workspace usage against plan quotas."""

    def __init__(self, root: Path, meter: UsageMeter | None = None):
        self.root = Path(root)
        self.billing_dir = self.root / "billing"
        self.billing_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.billing_dir / "workspaces.json"
        self.meter = meter or UsageMeter(root)
        self.plans = DEFAULT_PLANS

    def _load_state(self) -> dict[str, Any]:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:  #nosec B110
                pass
        return {}

    def _save_state(self, state: dict[str, Any]) -> None:
        self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def get_plan(self, plan_id: str) -> BillingPlan:
        return self.plans.get(plan_id, self.plans["free"])

    def set_plan(self, workspace_id: str, plan_id: str, credits: float = 0.0):
        state = self._load_state()
        state[workspace_id] = {
            "workspace_id": workspace_id,
            "plan_id": plan_id,
            "credits": float(credits),
            "updated_at": _now(),
        }
        self._save_state(state)

    def add_credits(self, workspace_id: str, amount: float):
        state = self._load_state()
        if workspace_id not in state:
            state[workspace_id] = {"workspace_id": workspace_id, "plan_id": "free", "credits": 0.0}
        state[workspace_id]["credits"] = state[workspace_id].get("credits", 0.0) + float(amount)
        state[workspace_id]["updated_at"] = _now()
        self._save_state(state)

    def workspace_status(self, workspace_id: str, days: int = 30) -> dict[str, Any]:
        state = self._load_state()
        ws = state.get(workspace_id, {"workspace_id": workspace_id, "plan_id": "free", "credits": 0.0})
        plan = self.get_plan(ws.get("plan_id", "free"))
        summary = self.meter.get_summary(workspace_id=workspace_id, days=days)

        requests_used = summary["by_action"].get("chat", {}).get("count", 0) + summary["total_events"]
        tokens_used = summary["total_quantity"]
        workflows_used = summary["by_action"].get("workflow_run", {}).get("count", 0)
        integrations_used = summary["by_action"].get("integration_call", {}).get("count", 0)

        estimated_cost = (
            requests_used * plan.price_per_request
            + (tokens_used / 1000) * plan.price_per_1k_tokens
        )

        return {
            "workspace_id": workspace_id,
            "plan": {"id": plan.id, "name": plan.name, "limits": plan.limits},
            "credits": round(ws.get("credits", 0.0), 6),
            "usage": {
                "requests": requests_used,
                "tokens": tokens_used,
                "workflows": workflows_used,
                "integrations": integrations_used,
            },
            "limits": plan.limits,
            "estimated_cost": round(estimated_cost, 6),
            "remaining_credits": round(max(0, ws.get("credits", 0.0) - estimated_cost), 6),
            "quota_usage_pct": {
                k: round(min(100, (requests_used / v) * 100), 2) if k == "requests" else
                   round(min(100, (tokens_used / v) * 100), 2) if k == "tokens" else
                   round(min(100, (workflows_used / v) * 100), 2) if k == "workflows" else
                   round(min(100, (integrations_used / v) * 100), 2)
                for k, v in plan.limits.items()
            },
        }


# === health collector =========================================================

class HealthCollector:
    """Collect system health from the AEON kernel and integrations."""

    def __init__(self, root: Path):
        self.root = Path(root)

    def snapshot(
        self,
        agent_vitals: list[dict[str, Any]] | None = None,
        queue_size: int = 0,
        integrations: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "timestamp": _now(),
            "kernel": {"status": "ok", "backend": "aeon_python_kernel"},
            "agents": agent_vitals or [],
            "queue": {"size": queue_size, "status": "healthy" if queue_size < 100 else "congested"},
            "integrations": integrations or [],
            "storage": self._storage_status(),
        }

    def _storage_status(self) -> dict[str, Any]:
        try:
            usage_dir = self.root / "usage"
            events_file = usage_dir / "events.jsonl"
            size_bytes = events_file.stat().st_size if events_file.exists() else 0
            return {
                "usage_events_bytes": size_bytes,
                "usage_events_mb": round(size_bytes / (1024 * 1024), 4),
            }
        except Exception as e:
            return {"error": str(e)}
