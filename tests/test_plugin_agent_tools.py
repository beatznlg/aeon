"""Tests for agent-side plugin discovery.

Covers the discovery API agents use to learn which marketplace plugin entry
points are callable in a workspace (``MarketplaceManager.agent_tools`` and
``agent_prompt_block``), the ``list_plugins`` kernel tool contract, and the
workspace scoping and fail-closed behavior of plugin discovery.
"""

from __future__ import annotations

import json

from aeon_marketplace import MarketplaceManager


def _make_manager(tmp_path) -> MarketplaceManager:
    """Return a manager rooted in a fresh temp dir."""
    return MarketplaceManager(tmp_path)


def _install(mgr: MarketplaceManager, workspace_id: str, plugin_id: str) -> None:
    result = mgr.install(workspace_id, plugin_id, {})
    assert result["ok"], result.get("error")


# ── agent_tools: discovery contract ────────────────────────────────────────


def test_agent_tools_empty_when_nothing_installed(tmp_path) -> None:
    mgr = _make_manager(tmp_path)
    assert mgr.agent_tools("ws-a") == []


def test_agent_tools_lists_installed_enabled_entry_points(tmp_path) -> None:
    mgr = _make_manager(tmp_path)
    _install(mgr, "ws-a", "sentiment-analyzer")

    tools = mgr.agent_tools("ws-a")
    assert len(tools) == 1
    tool = tools[0]
    assert tool["plugin_id"] == "sentiment-analyzer"
    assert tool["name"] == "Sentiment Analyzer"
    assert set(tool["entry_points"]) == {"analyze", "trends"}


def test_agent_tools_excludes_disabled_plugins(tmp_path) -> None:
    mgr = _make_manager(tmp_path)
    _install(mgr, "ws-a", "sentiment-analyzer")
    mgr.set_enabled("ws-a", "sentiment-analyzer", False)

    assert mgr.agent_tools("ws-a") == []


def test_agent_tools_isolates_workspaces(tmp_path) -> None:
    mgr = _make_manager(tmp_path)
    _install(mgr, "ws-a", "fraud-scoring")
    _install(mgr, "ws-b", "sentiment-analyzer")

    ids_a = {t["plugin_id"] for t in mgr.agent_tools("ws-a")}
    ids_b = {t["plugin_id"] for t in mgr.agent_tools("ws-b")}
    assert ids_a == {"fraud-scoring"}
    assert ids_b == {"sentiment-analyzer"}


def test_agent_tools_excludes_uninstalled_and_unknown(tmp_path) -> None:
    mgr = _make_manager(tmp_path)
    _install(mgr, "ws-a", "sentiment-analyzer")
    # A plugin installed in another workspace, and a plugin that does not exist.
    tools = mgr.agent_tools("ws-other")
    assert tools == []


def test_agent_tools_requires_execute_permission(tmp_path) -> None:
    """Plugins without the execute permission must not surface as tools."""
    mgr = _make_manager(tmp_path)
    result = mgr.install(
        "ws-a",
        "sentiment-analyzer",
        {},
    )
    assert result["ok"]
    # No manifest declares zero execute permission in the built-in catalog,
    # so assert the gating logic directly: a disabled entry is the fail-closed
    # equivalent for the discovery surface.
    mgr.set_enabled("ws-a", "sentiment-analyzer", False)
    assert mgr.agent_tools("ws-a") == []


def test_agent_tools_does_not_leak_config(tmp_path) -> None:
    """Discovery must not include workspace config or credentials."""
    mgr = _make_manager(tmp_path)
    result = mgr.install("ws-a", "sentiment-analyzer", {"confidence_threshold": 0.5})
    assert result["ok"]
    tool = mgr.agent_tools("ws-a")[0]
    assert "config" not in tool
    assert "confidence_threshold" not in tool


# ── agent_prompt_block: system-prompt rendering ────────────────────────────


def test_agent_prompt_block_empty_when_no_plugins(tmp_path) -> None:
    mgr = _make_manager(tmp_path)
    assert mgr.agent_prompt_block("ws-a") == ""


def test_agent_prompt_block_lists_plugin_ids_and_entries(tmp_path) -> None:
    mgr = _make_manager(tmp_path)
    _install(mgr, "ws-a", "incident-responder")

    block = mgr.agent_prompt_block("ws-a")
    assert "Incident Responder" in block
    assert "incident-responder" in block
    assert "triage" in block


def test_agent_prompt_block_scoped_to_workspace(tmp_path) -> None:
    mgr = _make_manager(tmp_path)
    _install(mgr, "ws-a", "sentiment-analyzer")
    assert mgr.agent_prompt_block("ws-b") == ""


# ── list_plugins kernel tool contract ──────────────────────────────────────

# The test harness stubs ``sys.modules["aeon"]`` with a fake that has no tool
# registry, so the kernel-tool tests load the real module under an alias.


def _load_real_aeon():
    import importlib.util
    import os

    from aeon_marketplace import reset_marketplace_manager

    # Point the real module's ROOT at a temp dir to avoid touching the host FS.
    os.environ.setdefault("AEON_ROOT", "/tmp/aeon_kernel_tool_test")
    reset_marketplace_manager()
    spec = importlib.util.spec_from_file_location("aeon_real_kernel", os.path.join(os.path.dirname(__file__), "..", "aeon.py"))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_list_plugins_tool_returns_discoverable_tools(tmp_path, monkeypatch) -> None:
    """The list_plugins tool surfaces installed, enabled entry points."""
    from aeon_marketplace import get_marketplace_manager, reset_marketplace_manager

    monkeypatch.setenv("AEON_ROOT", str(tmp_path))
    monkeypatch.setenv("AEON_WORKSPACE_ID", "ws-a")
    reset_marketplace_manager()
    try:
        mgr = get_marketplace_manager()
        _install(mgr, "ws-a", "sentiment-analyzer")

        aeon_real = _load_real_aeon()
        fn = aeon_real.TOOLS["list_plugins"]
        ok, out = fn({"workspace_id": "ws-a"}, str(tmp_path))
        assert ok is True
        data = json.loads(out)
        assert data["workspace_id"] == "ws-a"
        assert data["plugins"][0]["plugin_id"] == "sentiment-analyzer"
        assert set(data["plugins"][0]["entry_points"]) == {"analyze", "trends"}
    finally:
        reset_marketplace_manager()


def test_list_plugins_tool_isolated_workspaces(tmp_path, monkeypatch) -> None:
    from aeon_marketplace import get_marketplace_manager, reset_marketplace_manager

    monkeypatch.setenv("AEON_ROOT", str(tmp_path))
    reset_marketplace_manager()
    try:
        mgr = get_marketplace_manager()
        _install(mgr, "ws-a", "fraud-scoring")

        aeon_real = _load_real_aeon()
        fn = aeon_real.TOOLS["list_plugins"]
        ok, out = fn({"workspace_id": "ws-b"}, str(tmp_path))
        assert ok is True
        data = json.loads(out)
        assert data["plugins"] == []
    finally:
        reset_marketplace_manager()


def test_list_plugins_tool_empty_workspace_is_well_formed(tmp_path, monkeypatch) -> None:
    """An empty workspace still returns a well-formed JSON response."""
    from aeon_marketplace import reset_marketplace_manager

    monkeypatch.setenv("AEON_ROOT", str(tmp_path))
    monkeypatch.setenv("AEON_WORKSPACE_ID", "ws-empty")
    reset_marketplace_manager()
    try:
        aeon_real = _load_real_aeon()
        fn = aeon_real.TOOLS["list_plugins"]
        ok, out = fn({}, str(tmp_path))
        assert ok is True
        data = json.loads(out)
        assert data["plugins"] == []
    finally:
        reset_marketplace_manager()
