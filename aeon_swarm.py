"""
AEON OS Phase 14 — Advanced Agent Orchestration (Swarm Kernel)
================================================================
Multi-agent swarm coordination with role-based task allocation,
inter-agent message bus, reflection, and safe autonomous evolution hooks.

The module is intentionally dependency-light: it reuses the existing
ReflectiveAgent from ``aeon.py`` and the AeonOS orchestrator from
``aeon_os.py``.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SwarmMessage:
    """A single message on the swarm message bus."""

    sender: str
    recipient: str
    content: str
    msg_type: str = "chat"  # chat, task, review, evolution
    timestamp: float = field(default_factory=time.time)
    swarm_id: str = ""


@dataclass
class SwarmTask:
    """A task created by the planner and executed by an agent."""

    id: str
    description: str
    required_role: str
    dependencies: list[str] = field(default_factory=list)
    assigned_to: str | None = None
    status: str = "open"  # open, running, done, failed
    result: Any = None
    output: str = ""


@dataclass
class SwarmAgent:
    """A swarm participant wrapping an app_id, a ReflectiveAgent, and inboxes."""

    app_id: str
    role: str
    agent: Any = None
    inbox: list[SwarmMessage] = field(default_factory=list)
    outbox: list[SwarmMessage] = field(default_factory=list)

    def receive(self, msg: SwarmMessage) -> None:
        self.inbox.append(msg)

    def send(self, msg: SwarmMessage) -> None:
        self.outbox.append(msg)


class SwarmManager:
    """Coordinate multiple ReflectiveAgents for a shared task.

    The execution model is role-based:
      * planner  - breaks the prompt into SwarmTasks
      * executor - carries out assigned tasks
      * reviewer - reflects on outputs and can request corrective tasks
      * summarizer - synthesizes outputs into a final answer

    Inter-agent communication happens through a lightweight message bus
    (``broadcast`` / ``inbox``).  Evolution suggestions are extracted from
    reviewer output but are never auto-executed; they are returned for a
    human or an explicit CodeEvolver call to act on.
    """

    DEFAULT_ROLES = ("planner", "executor", "reviewer", "summarizer")

    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else Path(".")
        self.swarm_dir = self.root / "swarms"
        self.swarm_dir.mkdir(parents=True, exist_ok=True)
        self._running: dict[str, dict[str, Any]] = {}
        self._messages: dict[str, list[SwarmMessage]] = {}
        self._tasks: dict[str, list[SwarmTask]] = {}

    @staticmethod
    def _new_swarm_id() -> str:
        return str(uuid.uuid4())[:8]

    def _plan_tasks(self, prompt: str, roles: list[str]) -> list[SwarmTask]:
        """Heuristic planner: one task per unique role.

        In the future this can call the active LLM provider to produce a
        structured plan.  Keeping it deterministic avoids heavy deps in tests.
        """
        tasks: list[SwarmTask] = []
        for idx, role in enumerate(dict.fromkeys(roles)):
            tasks.append(
                SwarmTask(
                    id=f"task-{idx}-{role}",
                    description=f"{role}: contribute to \"{prompt[:120]}\"",
                    required_role=role,
                )
            )
        return tasks

    def broadcast(self, swarm_id: str, msg: SwarmMessage) -> None:
        """Deliver a message to every agent's inbox in the swarm."""
        messages = self._messages.setdefault(swarm_id, [])
        messages.append(msg)

    def coordinate(
        self,
        app_ids: list[str],
        prompt: str,
        os_orchestrator: Any,
        roles: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Run a complete swarm cycle: plan, execute, reflect, summarize.

        Args:
            app_ids: list of app/agent identifiers participating in the swarm.
            prompt: the shared task description.
            os_orchestrator: an AeonOS instance used to retrieve agents.
            roles: optional mapping of app_id -> role.  Missing entries receive
                   a role round-robin from DEFAULT_ROLES.

        Returns:
            A dictionary with the swarm_id, task results, reflection, summary,
            and any evolution suggestions.
        """
        if not app_ids:
            return {"ok": False, "error": "app_ids required"}
        if not prompt or not prompt.strip():
            return {"ok": False, "error": "prompt required"}

        swarm_id = self._new_swarm_id()
        self._messages[swarm_id] = []

        # Assign roles
        role_map = roles or {}
        for i, app_id in enumerate(app_ids):
            if app_id not in role_map:
                role_map[app_id] = self.DEFAULT_ROLES[i % len(self.DEFAULT_ROLES)]

        # Initialize agents
        agents: dict[str, SwarmAgent] = {}
        for app_id in app_ids:
            try:
                # Use the default workspace for swarm demos.
                reflective_agent = os_orchestrator._agent_for("default")
            except Exception as exc:  # pragma: no cover - best effort fallback
                reflective_agent = None
            agents[app_id] = SwarmAgent(
                app_id=app_id,
                role=role_map.get(app_id, "executor"),
                agent=reflective_agent,
            )

        # Planning phase
        unique_roles = list(dict.fromkeys(role_map.values()))
        tasks = self._plan_tasks(prompt, unique_roles)
        self._tasks[swarm_id] = tasks

        # Broadcast plan to all agents
        self.broadcast(
            swarm_id,
            SwarmMessage(
                sender="swarm",
                recipient="*",
                content=f"plan: {len(tasks)} tasks for prompt: {prompt[:200]}",
                msg_type="task",
                swarm_id=swarm_id,
            ),
        )

        # Execution phase
        results: dict[str, Any] = {}
        for task in tasks:
            # Capability match: find an agent whose role fits the task.
            candidate = next(
                (app_id for app_id in app_ids if agents[app_id].role == task.required_role),
                app_ids[0],
            )
            task.assigned_to = candidate
            task.status = "running"
            try:
                reflective_agent = agents[candidate].agent
                if reflective_agent is None:
                    raise RuntimeError(f"agent {candidate} not available")
                query = (
                    f"[{task.required_role.upper()}] {task.description}\n\n"
                    f"Original prompt: {prompt}"
                )
                result = reflective_agent.act(query)
                task.result = result
                task.output = (
                    result.get("answer", str(result))
                    if isinstance(result, dict)
                    else str(result)
                )
                task.status = "done"
                results[task.id] = {"ok": True, "output": task.output}
            except Exception as exc:
                task.status = "failed"
                results[task.id] = {"ok": False, "error": str(exc)}

        # Reflection phase
        reflection: dict[str, Any] = {"agent": None, "answer": ""}
        reviewer_id = next(
            (app_id for app_id in app_ids if agents[app_id].role == "reviewer"),
            None,
        )
        if reviewer_id:
            review_input = (
                f"Review the following outputs for prompt: {prompt}\n\n"
                + "\n".join(f"{t.id}: {t.output}" for t in tasks)
            )
            try:
                reflection_result = agents[reviewer_id].agent.act(review_input)
                reflection = {
                    "agent": reviewer_id,
                    "answer": (
                        reflection_result.get("answer", str(reflection_result))
                        if isinstance(reflection_result, dict)
                        else str(reflection_result)
                    ),
                }
            except Exception as exc:
                reflection = {"agent": reviewer_id, "answer": "", "error": str(exc)}

        # Summarization phase
        summary = ""
        summarizer_id = next(
            (app_id for app_id in app_ids if agents[app_id].role == "summarizer"),
            app_ids[0],
            # fallback to first agent if no summarizer assigned
        )
        try:
            summary_input = (
                f"Summarize the following outputs for prompt: {prompt}\n\n"
                + "\n".join(f"{t.id}: {t.output}" for t in tasks)
            )
            summary_result = agents[summarizer_id].agent.act(summary_input)
            summary = (
                summary_result.get("answer", str(summary_result))
                if isinstance(summary_result, dict)
                else str(summary_result)
            )
        except Exception as exc:
            summary = f"summary failed: {exc}"

        # Safe autonomous evolution hook: parse any JSON suggestions from review.
        evolution_suggestions: list[dict[str, Any]] = []
        if reviewer_id:
            evolution_suggestions = self._extract_evolution_suggestions(reflection.get("answer", ""))

        self._running[swarm_id] = {
            "prompt": prompt,
            "app_ids": app_ids,
            "roles": role_map,
            "status": "done",
            "started": time.time(),
        }

        return {
            "ok": True,
            "swarm_id": swarm_id,
            "prompt": prompt,
            "agents": app_ids,
            "roles": role_map,
            "tasks": [
                {
                    "id": t.id,
                    "description": t.description,
                    "status": t.status,
                    "assigned_to": t.assigned_to,
                    "output": t.output,
                }
                for t in tasks
            ],
            "results": results,
            "reflection": reflection,
            "summary": summary,
            "evolution_suggestions": evolution_suggestions,
        }

    @staticmethod
    def _extract_evolution_suggestions(text: str) -> list[dict[str, Any]]:
        """Look for JSON blocks containing tool_improvement suggestions.

        Suggestions are returned, not executed, so the loop stays safe and
        bounded.  A human or an explicit ``CodeEvolver`` call must act on them.
        """
        suggestions: list[dict[str, Any]] = []
        if not text:
            return suggestions
        # Try to find JSON blocks like {"tool_improvement": {...}}
        for start_marker in ("```json", "```"):
            if start_marker in text:
                block = text.split(start_marker, 1)[-1].split("```", 1)[0]
                try:
                    data = json.loads(block.strip())
                    if isinstance(data, dict) and "tool_improvement" in data:
                        suggestions.append(data["tool_improvement"])
                except Exception:  # nosec B110 - malformed JSON is ignored
                    pass
        # Also try the whole text as JSON
        try:
            data = json.loads(text.strip())
            if isinstance(data, dict) and "tool_improvement" in data:
                suggestions.append(data["tool_improvement"])
        except Exception:  # nosec B110
            pass
        return suggestions

    def status(self, swarm_id: str | None = None) -> dict[str, Any]:
        if swarm_id:
            running = self._running.get(swarm_id)
            return {
                "ok": True,
                "swarm_id": swarm_id,
                "running": running,
                "message_count": len(self._messages.get(swarm_id, [])),
                "task_count": len(self._tasks.get(swarm_id, [])),
            }
        return {"ok": True, "running": self._running}

    def messages(self, swarm_id: str) -> list[dict[str, Any]]:
        return [
            {
                "sender": m.sender,
                "recipient": m.recipient,
                "content": m.content,
                "msg_type": m.msg_type,
                "timestamp": m.timestamp,
            }
            for m in self._messages.get(swarm_id, [])
        ]
