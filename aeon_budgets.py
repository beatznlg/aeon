"""
AEON OS Phase 42 — Automation Cost & Budget Controls
======================================================
Workspace-level budget engine that limits automation executions by period
(workspace-wide or per-rule). Budgets can either block a run or warn
without stopping it.

Usage:
    from aeon_budgets import check_automation_budget, BudgetResult
    result = check_automation_budget(workspace_id, rule_id)
    if not result.allowed:
        # block the run
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from aeon_db import count_automation_executions, list_automation_budgets


class BudgetAction:
    """Enumeration-ish constants for budget actions."""

    BLOCK = "block"
    WARN = "warn"


@dataclass
class BudgetResult:
    """Result of checking automation budgets before a run."""

    allowed: bool = True
    warnings: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "warnings": self.warnings,
            "blocks": self.blocks,
        }


def _period_start(period: str, now: datetime) -> datetime | None:
    """Return the start of the budget window for a given period."""
    if period == "hour":
        return now - timedelta(hours=1)
    if period == "day":
        return now - timedelta(days=1)
    if period == "month":
        return now - timedelta(days=30)
    if period == "total":
        return None
    return now - timedelta(hours=1)


def check_automation_budget(
    workspace_id: str,
    rule_id: str | None = None,
) -> BudgetResult:
    """Check enabled automation budgets before executing a rule.

    Workspace-level budgets (rule_id is None) apply to every run in the
    workspace. Per-rule budgets apply only when the run targets that rule.
    """
    budgets = list_automation_budgets(str(workspace_id), enabled_only=True)
    warnings: list[str] = []
    blocks: list[str] = []

    now = datetime.now(timezone.utc)

    for budget in budgets:
        # Per-rule budgets only apply to that specific rule
        if budget.rule_id and budget.rule_id != str(rule_id):
            continue

        since = _period_start(budget.period, now)
        count = count_automation_executions(
            str(workspace_id),
            rule_id=budget.rule_id,
            since=since,
        )

        if count >= budget.limit_value:
            scope = f"rule {budget.rule_id}" if budget.rule_id else "workspace"
            message = (
                f"Automation budget exceeded: {budget.name} "
                f"({scope} {budget.period} limit {budget.limit_value}, used {count})"
            )
            if budget.action == BudgetAction.WARN:
                warnings.append(message)
            else:
                blocks.append(message)

    return BudgetResult(allowed=len(blocks) == 0, warnings=warnings, blocks=blocks)


__all__ = [
    "BudgetAction",
    "BudgetResult",
    "check_automation_budget",
]
