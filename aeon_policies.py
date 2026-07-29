"""
AEON OS Phase 41 — Automation Policy Enforcement
==================================================
Workspace-level policy engine that evaluates automation rules against
configurable constraints. Policies can block an operation or require
human approval before a rule is activated.

Usage:
    from aeon_policies import evaluate_automation_policy, PolicyEffect
    allowed, effect, violations = evaluate_automation_policy(workspace_id, rule_data)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from aeon_db import (
    AutomationPolicy,
    list_automation_policies,
)


class PolicyEffect:
    """Enumeration-ish constants for policy effects."""

    BLOCK = "block"
    REQUIRE_APPROVAL = "require_approval"


@dataclass
class PolicyViolation:
    """A single policy violation returned by the evaluation engine."""

    policy_id: str | None
    policy_name: str | None
    effect: str
    message: str
    rule: str | None = None


@dataclass
class PolicyResult:
    """Result of evaluating a rule against all workspace policies."""

    allowed: bool = True
    effect: str = "allow"
    violations: list[PolicyViolation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "effect": self.effect,
            "violations": [
                {
                    "policy_id": v.policy_id,
                    "policy_name": v.policy_name,
                    "effect": v.effect,
                    "message": v.message,
                    "rule": v.rule,
                }
                for v in self.violations
            ],
        }


def _rule_action_types(rule: dict[str, Any]) -> set[str]:
    """Return all action types used in a rule definition."""
    types: set[str] = set()
    actions = rule.get("actions") or []
    if isinstance(actions, list):
        for step in actions:
            if not isinstance(step, dict):
                continue
            step_type = step.get("type") or step.get("action_type")
            if step_type:
                types.add(step_type)
    if not types and rule.get("action_type"):
        types.add(rule["action_type"])
    return types


def _rule_event_types(rule: dict[str, Any]) -> set[str]:
    """Return event types referenced by a rule definition."""
    event_type = rule.get("event_type")
    types: set[str] = set()
    if event_type:
        types.add(str(event_type))
    return types


def _matches_pattern(value: str, pattern: str) -> bool:
    """Check whether a value matches a glob-like or regex pattern."""
    if not pattern:
        return False
    if pattern == "*":
        return True
    if pattern.startswith("/") and pattern.endswith("/"):
        try:
            return bool(re.search(pattern[1:-1], value))
        except re.error:
            return False
    # Convert glob wildcards to regex.
    regex = "^" + pattern.replace(".", r"\.").replace("*", ".*").replace("?", ".") + "$"
    try:
        return bool(re.match(regex, value))
    except re.error:
        return False


def _evaluate_single_policy(rule: dict[str, Any], policy: AutomationPolicy) -> list[PolicyViolation]:
    """Evaluate a single policy against a rule. Returns zero or more violations."""
    violations: list[PolicyViolation] = []
    if not policy.enabled:
        return violations

    config = policy.rules or {}
    blocked_actions = set(config.get("blocked_actions", []) or [])
    allowed_actions = config.get("allowed_actions")
    blocked_events = set(config.get("blocked_events", []) or [])
    allowed_events = config.get("allowed_events")
    require_condition = config.get("require_condition", False)
    name_pattern = config.get("name_pattern")
    name_blacklist = set(config.get("name_blacklist", []) or [])
    max_actions = config.get("max_actions")

    action_types = _rule_action_types(rule)
    event_types = _rule_event_types(rule)

    # Blocked action types
    for action_type in action_types:
        if action_type in blocked_actions:
            violations.append(
                PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    effect=policy.effect,
                    message=f"Action type '{action_type}' is blocked by policy",
                    rule="blocked_actions",
                )
            )

    # Allowed action types (whitelist)
    if isinstance(allowed_actions, list) and allowed_actions:
        for action_type in action_types:
            if action_type not in allowed_actions:
                violations.append(
                    PolicyViolation(
                        policy_id=policy.id,
                        policy_name=policy.name,
                        effect=policy.effect,
                        message=f"Action type '{action_type}' is not in the allowed actions list",
                        rule="allowed_actions",
                    )
                )

    # Blocked event types
    for event_type in event_types:
        if event_type in blocked_events:
            violations.append(
                PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    effect=policy.effect,
                    message=f"Event type '{event_type}' is blocked by policy",
                    rule="blocked_events",
                )
            )

    # Allowed event types (whitelist)
    if isinstance(allowed_events, list) and allowed_events:
        for event_type in event_types:
            if event_type not in allowed_events:
                violations.append(
                    PolicyViolation(
                        policy_id=policy.id,
                        policy_name=policy.name,
                        effect=policy.effect,
                        message=f"Event type '{event_type}' is not in the allowed events list",
                        rule="allowed_events",
                    )
                )

    # Require a non-trivial condition
    if require_condition:
        condition = rule.get("condition") or {}
        if not condition or (isinstance(condition, dict) and not condition.get("operator") and not condition.get("field")):
            violations.append(
                PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    effect=policy.effect,
                    message="A condition is required by policy",
                    rule="require_condition",
                )
            )

    # Naming convention
    if name_pattern:
        name = (rule.get("name") or "").strip()
        if not _matches_pattern(name, name_pattern):
            violations.append(
                PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    effect=policy.effect,
                    message=f"Rule name does not match required pattern '{name_pattern}'",
                    rule="name_pattern",
                )
            )

    # Name blacklist
    name = (rule.get("name") or "").strip()
    if name in name_blacklist:
        violations.append(
            PolicyViolation(
                policy_id=policy.id,
                policy_name=policy.name,
                effect=policy.effect,
                message=f"Rule name '{name}' is blacklisted by policy",
                rule="name_blacklist",
            )
        )

    # Max actions
    if isinstance(max_actions, int) and max_actions >= 0:
        actions = rule.get("actions") or []
        if isinstance(actions, list) and len(actions) > max_actions:
            violations.append(
                PolicyViolation(
                    policy_id=policy.id,
                    policy_name=policy.name,
                    effect=policy.effect,
                    message=f"Rule has {len(actions)} actions; maximum allowed is {max_actions}",
                    rule="max_actions",
                )
            )

    return violations


def evaluate_automation_policy(
    workspace_id: str,
    rule: dict[str, Any],
    *,
    exclude_policy_id: str | None = None,
) -> PolicyResult:
    """Evaluate a rule against all enabled policies in a workspace.

    Returns a PolicyResult. If any policy with effect 'block' is violated,
    the operation is blocked. If only 'require_approval' policies are
    violated, the rule must go through approval before activation.
    """
    policies = list_automation_policies(workspace_id, enabled_only=True)
    all_violations: list[PolicyViolation] = []

    for policy in policies:
        if exclude_policy_id and policy.id == exclude_policy_id:
            continue
        all_violations.extend(_evaluate_single_policy(rule, policy))

    if not all_violations:
        return PolicyResult(allowed=True, effect="allow", violations=[])

    # Determine aggregate effect: block wins over require_approval.
    block_violations = [v for v in all_violations if v.effect == PolicyEffect.BLOCK]
    require_violations = [v for v in all_violations if v.effect == PolicyEffect.REQUIRE_APPROVAL]

    if block_violations:
        return PolicyResult(
            allowed=False,
            effect=PolicyEffect.BLOCK,
            violations=block_violations + require_violations,
        )

    if require_violations:
        return PolicyResult(
            allowed=False,
            effect=PolicyEffect.REQUIRE_APPROVAL,
            violations=require_violations,
        )

    return PolicyResult(allowed=True, effect="allow", violations=[])


def check_automation_limit(current_count: int, max_rules: int) -> bool:
    """Return True if current automation count is below the policy limit."""
    return current_count < max_rules


__all__ = [
    "PolicyEffect",
    "PolicyResult",
    "PolicyViolation",
    "evaluate_automation_policy",
    "check_automation_limit",
]
