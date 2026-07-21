"""
AEON OS Phase 4 — Multi-Agent Swarms & Visual Workflows
=======================================================
This module is imported for side-effects: it patches the AeonOS class with
workflow and swarm helpers without modifying aeon_os.py directly.

Usage:
    import aeon_workflows  # patches AeonOS on import
    from aeon_os import AeonOS

    os = AeonOS()
    os.save_workflow(...)
    os.run_workflow(workflow_id)
    os.run_swarm(["cybersecurity", "finance"], "assess risk")
"""

import os
import json
import time
import hashlib
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field

from aeon_os import AeonOS, OS_ROOT


@dataclass
class WorkflowNode:
    """A single step in a workflow, backed by one AEON module/app."""
    id: str
    app_id: str
    prompt: str
    x: float = 0.0
    y: float = 0.0


@dataclass
class WorkflowEdge:
    """Connection between two workflow nodes."""
    source: str
    target: str
    condition: str = "always"


@dataclass
class WorkflowDefinition:
    """Serializable workflow (nodes + edges) for cross-module automation."""
    id: str
    name: str
    description: str
    nodes: List[WorkflowNode]
    edges: List[WorkflowEdge]
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "nodes": [
                {"id": n.id, "app_id": n.app_id, "prompt": n.prompt, "x": n.x, "y": n.y}
                for n in self.nodes
            ],
            "edges": [
                {"source": e.source, "target": e.target, "condition": e.condition}
                for e in self.edges
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowDefinition":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            nodes=[WorkflowNode(**n) for n in data.get("nodes", [])],
            edges=[WorkflowEdge(**e) for e in data.get("edges", [])],
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


class WorkflowEngine:
    """Persist and run cross-module workflows on top of AeonOS."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.workflow_dir = self.root / "workflows"
        self.workflow_dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, workflow_id: str) -> Path:
        safe_id = hashlib.sha256(workflow_id.encode()).hexdigest()[:16]
        return self.workflow_dir / f"{safe_id}.json"

    def save(self, workflow: WorkflowDefinition) -> None:
        workflow.updated_at = time.time()
        self._path_for(workflow.id).write_text(json.dumps(workflow.to_dict(), indent=2))

    def load(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        path = self._path_for(workflow_id)
        if not path.exists():
            return None
        try:
            return WorkflowDefinition.from_dict(json.loads(path.read_text()))
        except Exception:
            return None

    def list_workflows(self) -> List[Dict[str, Any]]:
        workflows = []
        for path in self.workflow_dir.glob("*.json"):
            try:
                wf = WorkflowDefinition.from_dict(json.loads(path.read_text()))
                workflows.append(wf.to_dict())
            except Exception:
                pass
        return workflows

    def delete(self, workflow_id: str) -> bool:
        path = self._path_for(workflow_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def run(self, workflow_id: str, os_orchestrator: AeonOS, initial_input: str = "") -> Dict[str, Any]:
        workflow = self.load(workflow_id)
        if workflow is None:
            return {"ok": False, "error": "workflow not found"}
        node_map = {n.id: n for n in workflow.nodes}
        if not node_map:
            return {"ok": False, "error": "workflow has no nodes"}

        adjacency: Dict[str, List[str]] = {n.id: [] for n in workflow.nodes}
        for edge in workflow.edges:
            adjacency.setdefault(edge.source, []).append(edge.target)

        ordered_ids = [workflow.nodes[0].id]
        visited: set = set()
        results: List[Dict[str, Any]] = []
        current_input = initial_input

        while ordered_ids:
            node_id = ordered_ids.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)
            node = node_map.get(node_id)
            if not node:
                continue

            prompt = node.prompt
            if current_input:
                prompt = f"Context from previous step: {current_input}\n\n{prompt}"

            try:
                tick_result = os_orchestrator.tick("default", node.app_id, prompt)
                output = tick_result.get("data", tick_result) if isinstance(tick_result, dict) else tick_result
                current_input = str(output)[:500]
                results.append({
                    "node_id": node_id,
                    "app_id": node.app_id,
                    "ok": True,
                    "output": output,
                })
                for next_id in adjacency.get(node_id, []):
                    if next_id not in visited and next_id not in ordered_ids:
                        ordered_ids.append(next_id)
            except Exception as e:
                results.append({
                    "node_id": node_id,
                    "app_id": node.app_id,
                    "ok": False,
                    "error": str(e),
                })
                break

        return {"ok": True, "workflow_id": workflow_id, "results": results}


class SwarmManager:
    """Coordinate multiple ReflectiveAgents (one per module) for a shared task."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.swarm_dir = self.root / "swarms"
        self.swarm_dir.mkdir(parents=True, exist_ok=True)
        self._running: Dict[str, Dict[str, Any]] = {}

    def coordinate(self, app_ids: List[str], prompt: str, os_orchestrator: AeonOS) -> Dict[str, Any]:
        results: Dict[str, Any] = {}
        for app_id in app_ids:
            try:
                tick_result = os_orchestrator.tick("default", app_id, prompt)
                output = tick_result.get("data", tick_result) if isinstance(tick_result, dict) else tick_result
                results[app_id] = {"ok": True, "output": output}
            except Exception as e:
                results[app_id] = {"ok": False, "error": str(e)}
        return {"ok": True, "prompt": prompt, "agents": app_ids, "results": results}

    def status(self) -> Dict[str, Any]:
        return {"ok": True, "running": self._running}


def _patch_aeon_os() -> None:
    """Attach workflow/swarm helpers to AeonOS at import time."""
    original_init = AeonOS.__init__

    def new_init(self, root: Path = OS_ROOT):
        original_init(self, root)
        self.workflow_engine = WorkflowEngine(self.root)
        self.swarm_manager = SwarmManager(self.root)

    AeonOS.__init__ = new_init  # type: ignore

    def save_workflow(self, workflow: WorkflowDefinition) -> None:
        self.workflow_engine.save(workflow)

    def get_workflow(self, workflow_id: str) -> Optional[WorkflowDefinition]:
        return self.workflow_engine.load(workflow_id)

    def list_workflows(self) -> List[Dict[str, Any]]:
        return self.workflow_engine.list_workflows()

    def delete_workflow(self, workflow_id: str) -> bool:
        return self.workflow_engine.delete(workflow_id)

    def run_workflow(self, workflow_id: str, initial_input: str = "") -> Dict[str, Any]:
        return self.workflow_engine.run(workflow_id, self, initial_input)

    def run_swarm(self, app_ids: List[str], prompt: str) -> Dict[str, Any]:
        return self.swarm_manager.coordinate(app_ids, prompt, self)

    AeonOS.save_workflow = save_workflow  # type: ignore
    AeonOS.get_workflow = get_workflow  # type: ignore
    AeonOS.list_workflows = list_workflows  # type: ignore
    AeonOS.delete_workflow = delete_workflow  # type: ignore
    AeonOS.run_workflow = run_workflow  # type: ignore
    AeonOS.run_swarm = run_swarm  # type: ignore


_patch_aeon_os()
