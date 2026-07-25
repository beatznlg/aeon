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
    """A single step in a workflow, backed by one AEON module/app or integration."""
    id: str
    app_id: str
    prompt: str
    x: float = 0.0
    y: float = 0.0
    type: str = "agent"  # 'agent' or 'integration'
    integration_id: Optional[str] = None
    endpoint: str = ""
    method: str = "GET"
    payload: str = ""
    provider: Optional[str] = None  # LLM provider override per node


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
    provider: Optional[str] = None  # Default LLM provider for the whole workflow
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "provider": self.provider,
            "nodes": [
                {
                    "id": n.id,
                    "app_id": n.app_id,
                    "prompt": n.prompt,
                    "x": n.x,
                    "y": n.y,
                    "type": n.type,
                    "integration_id": n.integration_id,
                    "endpoint": n.endpoint,
                    "method": n.method,
                    "payload": n.payload,
                    "provider": n.provider,
                }
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
        raw_nodes = data.get("nodes", [])
        nodes = []
        for n in raw_nodes:
            nodes.append(
                WorkflowNode(
                    id=n["id"],
                    app_id=n.get("app_id", ""),
                    prompt=n.get("prompt", ""),
                    x=n.get("x", 0.0),
                    y=n.get("y", 0.0),
                    type=n.get("type", "agent"),
                    integration_id=n.get("integration_id"),
                    endpoint=n.get("endpoint", ""),
                    method=n.get("method", "GET"),
                    payload=n.get("payload", ""),
                    provider=n.get("provider"),
                )
            )
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            nodes=nodes,
            edges=[WorkflowEdge(**e) for e in data.get("edges", [])],
            provider=data.get("provider"),
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

    def run(self, workflow_id: str, os_orchestrator: AeonOS,
            initial_input: str = "", workspace_id: str = None) -> Dict[str, Any]:
        """
        Execute a workflow with workspace-scoped agents and per-node provider overrides.
        workspace_id: If provided, uses workspace-scoped agents from Phase 2a.
        """
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

        # Integration manager may be attached to the orchestrator by aeon_server.
        integration_manager = getattr(os_orchestrator, "integration_manager", None)

        # Resolve the effective provider: node-level > workflow-level > env default
        default_provider = workflow.provider or os.environ.get("AEON_LLM_PROVIDER")

        wsid = workspace_id or "default"

        while ordered_ids:
            node_id = ordered_ids.pop(0)
            if node_id in visited:
                continue
            visited.add(node_id)
            node = node_map.get(node_id)
            if not node:
                continue

            node_type = getattr(node, "type", "agent")
            effective_provider = node.provider or default_provider
            t0 = time.time()

            try:
                if node_type == "integration":
                    if integration_manager is None:
                        raise RuntimeError("integration_manager not attached to AeonOS")
                    if not node.integration_id:
                        raise ValueError("integration node missing integration_id")
                    parsed_payload: Optional[Any] = None
                    if node.payload:
                        payload_str = node.payload.replace("{input}", current_input)
                        try:
                            parsed_payload = json.loads(payload_str)
                        except Exception:
                            parsed_payload = payload_str
                    output = integration_manager.run(
                        node.integration_id,
                        endpoint=node.endpoint or "",
                        method=node.method or "GET",
                        payload=parsed_payload,
                    )
                    current_input = str(output.get("data", output))[:500]
                    node_label = node.integration_id
                else:
                    prompt = node.prompt
                    if current_input:
                        prompt = f"Context from previous step: {current_input}\n\n{prompt}"

                    # Apply provider override if specified
                    if effective_provider:
                        from aeon_llm import get_llm_provider
                        import aeon as _aeon
                        _aeon.QW = get_llm_provider(effective_provider)
                        os.environ["AEON_LLM_PROVIDER"] = effective_provider

                    # Use workspace-scoped agent if workspace_id provided
                    if wsid and wsid != "default":
                        # Create/use a workspace-scoped agent key
                        tick_result = os_orchestrator.tick(wsid, node.app_id, prompt)
                    else:
                        tick_result = os_orchestrator.tick("default", node.app_id, prompt)

                    output = tick_result.get("data", tick_result) if isinstance(tick_result, dict) else tick_result
                    current_input = str(output)[:500]
                    node_label = node.app_id

                elapsed = round(time.time() - t0, 3)
                results.append({
                    "node_id": node_id,
                    "app_id": node_label,
                    "type": node_type,
                    "ok": True,
                    "provider": effective_provider,
                    "latency_s": elapsed,
                    "output": output,
                })
                for next_id in adjacency.get(node_id, []):
                    if next_id not in visited and next_id not in ordered_ids:
                        ordered_ids.append(next_id)
            except Exception as e:
                elapsed = round(time.time() - t0, 3)
                results.append({
                    "node_id": node_id,
                    "app_id": node.integration_id if node_type == "integration" else node.app_id,
                    "type": node_type,
                    "ok": False,
                    "provider": effective_provider,
                    "latency_s": elapsed,
                    "error": str(e),
                })
                break

        # Compute summary
        total_nodes = len(results)
        ok_nodes = sum(1 for r in results if r.get("ok"))
        total_latency = sum(r.get("latency_s", 0) for r in results)

        return {
            "ok": True,
            "workflow_id": workflow_id,
            "workspace_id": wsid,
            "provider": default_provider,
            "summary": {
                "total_nodes": total_nodes,
                "ok_nodes": ok_nodes,
                "failed_nodes": total_nodes - ok_nodes,
                "total_latency_s": round(total_latency, 3),
            },
            "results": results,
        }


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
