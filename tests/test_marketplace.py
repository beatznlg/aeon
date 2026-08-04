"""Regression coverage for the AEON OS plugin marketplace.

Covers the catalog contract, workspace-scoped install lifecycle, entry-point
gating, config validation, tenant isolation, and route authorization.
"""

from __future__ import annotations

import uuid

from aeon_marketplace import (
    ALLOWED_PERMISSIONS,
    BUILTIN_PLUGIN_CATALOG,
    MarketplaceManager,
    validate_config,
    validate_manifest,
)


def _register(client, label: str) -> tuple[str, str]:
    """Create a test workspace owner and return (token, workspace_id)."""
    response = client.post(
        "/auth/register",
        json={
            "email": f"market-{label}-{uuid.uuid4().hex[:8]}@test.local",
            "password": "secure123",
            "name": f"Market {label}",
        },
    )
    assert response.status_code == 201, response.get_json()
    data = response.get_json()
    return data["token"], data["user"]["workspace_id"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── catalog contract ───────────────────────────────────────────────────────


def test_catalog_manifests_are_internally_valid() -> None:
    """Every built-in manifest must pass the same validation we would apply to a third party."""
    assert len(BUILTIN_PLUGIN_CATALOG) >= 10
    seen: set[str] = set()
    for manifest in BUILTIN_PLUGIN_CATALOG:
        result = validate_manifest(manifest.to_dict())
        assert result["ok"], f"{manifest.id}: {result.get('error')}"
        assert manifest.id not in seen
        seen.add(manifest.id)
        assert set(manifest.permissions) <= ALLOWED_PERMISSIONS
        assert manifest.entry_points


def test_catalog_covers_all_modules_and_sectors() -> None:
    """The catalog spans every module category and every industry vertical."""
    categories = {m.category for m in BUILTIN_PLUGIN_CATALOG}
    # Every AEON module category must be represented.
    for expected in ("automation", "ai", "data", "analytics", "security", "integration", "communication", "productivity", "devops", "sector"):
        assert expected in categories, f"missing catalog category: {expected}"
    # Every industry vertical must be represented by a sector plugin.
    sector_ids = {m.id for m in BUILTIN_PLUGIN_CATALOG if m.category == "sector"}
    # Keyword fragments map to the sector plugin ids in the catalog.
    for keyword in (
        "healthcare", "finance", "retail", "logistics", "manufacturing", "tourism",
        "utility", "heritage", "sme", "gov", "energy", "telecom",
        "agri", "cyber", "education", "safety", "realestate",
    ):
        assert any(keyword in sid for sid in sector_ids), f"missing sector plugin for: {keyword}"


def test_every_entry_point_has_runnable_handler() -> None:
    """Installing any plugin must yield fully callable entry points (no orphans)."""
    from aeon_marketplace import _run_builtin

    orphans: list[tuple[str, str]] = []
    for manifest in BUILTIN_PLUGIN_CATALOG:
        for entry in manifest.entry_points:
            result = _run_builtin(manifest, entry, {}, {})
            if not result.get("ok"):
                orphans.append((manifest.id, entry))
    assert orphans == [], f"entry points without handlers: {orphans}"


def test_catalog_endpoint_exposes_contract(client) -> None:
    token, _workspace_id = _register(client, "catalog")
    response = client.get("/marketplace/plugins", headers=_headers(token))

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert len(data["plugins"]) == len(BUILTIN_PLUGIN_CATALOG)
    assert data["summary"]["plugins"] == len(BUILTIN_PLUGIN_CATALOG)
    for plugin in data["plugins"]:
        assert plugin["installed"] is False
        assert plugin["id"]
        assert plugin["version"]
        assert plugin["entry_points"]


def test_plugin_detail_unknown_returns_404(client) -> None:
    token, _workspace_id = _register(client, "detail")
    response = client.get("/marketplace/plugins/not-a-plugin", headers=_headers(token))
    assert response.status_code == 404
    assert response.get_json()["error"] == "plugin not found"


# ── lifecycle ──────────────────────────────────────────────────────────────


def test_install_uninstall_lifecycle(client) -> None:
    token, _workspace_id = _register(client, "lifecycle")
    headers = _headers(token)

    install = client.post(
        "/marketplace/plugins/sentiment-analyzer/install",
        headers=headers,
        json={"config": {"locale": "es"}},
    )
    assert install.status_code == 201, install.get_json()
    assert install.get_json()["install"]["enabled"] is True
    assert install.get_json()["install"]["config"]["locale"] == "es"

    catalog = client.get("/marketplace/plugins", headers=headers).get_json()
    entry = next(p for p in catalog["plugins"] if p["id"] == "sentiment-analyzer")
    assert entry["installed"] is True and entry["enabled"] is True

    installed = client.get("/marketplace/installed", headers=headers).get_json()
    assert [p["plugin_id"] for p in installed["installed"]] == ["sentiment-analyzer"]

    uninstall = client.post("/marketplace/plugins/sentiment-analyzer/uninstall", headers=headers)
    assert uninstall.status_code == 200
    installed = client.get("/marketplace/installed", headers=headers).get_json()
    assert installed["installed"] == []


def test_double_install_and_unknown_plugin_rejected(client) -> None:
    token, _workspace_id = _register(client, "double")
    headers = _headers(token)

    first = client.post("/marketplace/plugins/scheduler/install", headers=headers, json={})
    assert first.status_code == 201

    second = client.post("/marketplace/plugins/scheduler/install", headers=headers, json={})
    assert second.status_code == 400
    assert "already installed" in second.get_json()["error"]

    unknown = client.post("/marketplace/plugins/nope/install", headers=headers, json={})
    assert unknown.status_code == 400
    assert unknown.get_json()["error"] == "plugin not found"


def test_config_validation_rejects_bad_and_unknown_keys(client) -> None:
    token, _workspace_id = _register(client, "config")
    headers = _headers(token)

    bad_type = client.post(
        "/marketplace/plugins/grid-monitor/install",
        headers=headers,
        json={"config": {"critical_threshold": "high"}},
    )
    assert bad_type.status_code == 400
    assert "critical_threshold" in bad_type.get_json()["error"]

    bad_key = client.post(
        "/marketplace/plugins/grid-monitor/install",
        headers=headers,
        json={"config": {"not_declared": 1}},
    )
    assert bad_key.status_code == 400
    assert "unknown config key" in bad_key.get_json()["error"]

    ok = client.post(
        "/marketplace/plugins/grid-monitor/install",
        headers=headers,
        json={"config": {"region": "east", "critical_threshold": 0.85}},
    )
    assert ok.status_code == 201
    assert ok.get_json()["install"]["config"] == {"region": "east", "critical_threshold": 0.85}

    update = client.post(
        "/marketplace/plugins/grid-monitor/config",
        headers=headers,
        json={"config": {"critical_threshold": 0.95}},
    )
    assert update.status_code == 200
    assert update.get_json()["install"]["config"]["critical_threshold"] == 0.95


# ── permissions & entry gating ─────────────────────────────────────────────


def test_run_entry_is_gated_on_install_and_enabled(client) -> None:
    token, _workspace_id = _register(client, "gating")
    headers = _headers(token)

    not_installed = client.post(
        "/marketplace/plugins/sentiment-analyzer/run", headers=headers, json={"entry": "analyze"}
    )
    assert not_installed.status_code == 404
    assert not_installed.get_json()["error"] == "plugin not installed"

    client.post("/marketplace/plugins/sentiment-analyzer/install", headers=headers, json={})

    unknown_entry = client.post(
        "/marketplace/plugins/sentiment-analyzer/run", headers=headers, json={"entry": "launch_missiles"}
    )
    assert unknown_entry.status_code == 400
    assert "unknown entry point" in unknown_entry.get_json()["error"]

    missing_entry = client.post("/marketplace/plugins/sentiment-analyzer/run", headers=headers, json={})
    assert missing_entry.status_code == 400
    assert missing_entry.get_json()["error"] == "entry required"

    client.post("/marketplace/plugins/sentiment-analyzer/disable", headers=headers)

    disabled = client.post(
        "/marketplace/plugins/sentiment-analyzer/run", headers=headers, json={"entry": "analyze"}
    )
    assert disabled.status_code == 403
    assert disabled.get_json()["error"] == "plugin disabled"

    client.post("/marketplace/plugins/sentiment-analyzer/enable", headers=headers)

    ok = client.post(
        "/marketplace/plugins/sentiment-analyzer/run",
        headers=headers,
        json={"entry": "analyze", "params": {"text": "AEON OS is great"}},
    )
    assert ok.status_code == 200
    body = ok.get_json()
    assert body["ok"] is True
    assert "summary" in body
    assert body["stats"]["words"] == 4


# ── tenant isolation & authorization ───────────────────────────────────────


def test_workspace_isolation_between_tenants(client) -> None:
    token_a, _ = _register(client, "iso-a")
    token_b, _ = _register(client, "iso-b")

    install = client.post("/marketplace/plugins/fraud-scoring/install", headers=_headers(token_a), json={})
    assert install.status_code == 201

    # Tenant B must not see or act on tenant A's installs.
    catalog_b = client.get("/marketplace/plugins", headers=_headers(token_b)).get_json()
    entry_b = next(p for p in catalog_b["plugins"] if p["id"] == "fraud-scoring")
    assert entry_b["installed"] is False

    run_b = client.post(
        "/marketplace/plugins/fraud-scoring/run", headers=_headers(token_b), json={"entry": "score"}
    )
    assert run_b.status_code == 404
    assert run_b.get_json()["error"] == "plugin not installed"

    disable_b = client.post("/marketplace/plugins/fraud-scoring/disable", headers=_headers(token_b))
    assert disable_b.status_code == 404


def test_agent_tools_endpoint_exposes_callable_plugins(client) -> None:
    """GET /marketplace/agent-tools mirrors kernel discovery for the workspace."""
    token, workspace_id = _register(client, "agent-tools")
    headers = _headers(token)

    # Empty workspace: no callable plugin tools.
    empty = client.get("/marketplace/agent-tools", headers=headers)
    assert empty.status_code == 200
    assert empty.get_json()["plugins"] == []
    assert empty.get_json()["count"] == 0

    install = client.post(
        "/marketplace/plugins/sentiment-analyzer/install",
        headers=headers,
        json={"config": {}},
    )
    assert install.status_code == 201

    data = client.get("/marketplace/agent-tools", headers=headers).get_json()
    assert data["ok"] is True
    assert data["workspace_id"] == workspace_id
    assert len(data["plugins"]) == 1
    tool = data["plugins"][0]
    assert tool["plugin_id"] == "sentiment-analyzer"
    assert set(tool["entry_points"]) == {"analyze", "trends"}
    assert "config" not in tool  # discovery never leaks config/credentials

    # Disabled plugins disappear from agent discovery.
    client.post("/marketplace/plugins/sentiment-analyzer/disable", headers=headers)
    after_disable = client.get("/marketplace/agent-tools", headers=headers).get_json()
    assert after_disable["plugins"] == []


def test_agent_tools_endpoint_isolated_between_tenants(client) -> None:
    token_a, workspace_a = _register(client, "agent-tools-iso-a")
    token_b, workspace_b = _register(client, "agent-tools-iso-b")

    install = client.post(
        "/marketplace/plugins/fraud-scoring/install",
        headers=_headers(token_a),
        json={"config": {}},
    )
    assert install.status_code == 201

    data_a = client.get("/marketplace/agent-tools", headers=_headers(token_a)).get_json()
    assert data_a["workspace_id"] == workspace_a
    assert [p["plugin_id"] for p in data_a["plugins"]] == ["fraud-scoring"]

    data_b = client.get("/marketplace/agent-tools", headers=_headers(token_b)).get_json()
    assert data_b["workspace_id"] == workspace_b
    assert data_b["plugins"] == []


def test_routes_require_authentication(client) -> None:
    assert client.get("/marketplace/plugins").status_code == 401
    assert client.get("/marketplace/installed").status_code == 401
    assert client.post("/marketplace/plugins/scheduler/install", json={}).status_code == 401
    assert client.post("/marketplace/plugins/scheduler/run", json={"entry": "suggest"}).status_code == 401


# ── manifest & config validation helpers ───────────────────────────────────


def test_validate_manifest_rejects_unknown_permissions_and_bad_ids() -> None:
    result = validate_manifest(
        {
            "id": "evil plugin",
            "name": "Evil",
            "version": "1.0",
            "description": "x",
            "category": "ai",
            "permissions": ["read", "root"],
            "entry_points": {"go": "do"},
        }
    )
    assert result["ok"] is False
    assert "id" in result["error"]
    assert "unknown permission: root" in result["error"]


def test_validate_manifest_accepts_a_valid_external_manifest() -> None:
    result = validate_manifest(
        {
            "id": "hello-world",
            "name": "Hello World",
            "version": "1.2.3",
            "description": "A friendly plugin.",
            "author": "Acme",
            "category": "productivity",
            "permissions": ["execute"],
            "entry_points": {"greet": "Say hello"},
            "config_schema": {"salutation": {"type": "string", "default": "Hi", "required": False}},
        }
    )
    assert result["ok"] is True, result.get("error")
    assert result["manifest"]["id"] == "hello-world"


def test_validate_config_fails_closed_on_undeclared_keys() -> None:
    schema = {"name": {"type": "string", "required": True}}
    assert validate_config(schema, {"name": "x"})["ok"] is True
    assert validate_config(schema, {"name": "x", "sneaky": 1})["ok"] is False
    assert validate_config(schema, {})["ok"] is False
    assert validate_config(schema, {"name": 42})["ok"] is False


# ── persistence ────────────────────────────────────────────────────────────


def test_install_state_persists_across_manager_reload(tmp_path) -> None:
    root = tmp_path / "state"
    manager = MarketplaceManager(root)
    assert manager.install("ws-1", "scheduler", {"working_hours": "08:00-16:00"})["ok"] is True

    reloaded = MarketplaceManager(root)
    installed = reloaded.list_installed("ws-1")
    assert [p["plugin_id"] for p in installed] == ["scheduler"]
    assert installed[0]["config"]["working_hours"] == "08:00-16:00"
    assert reloaded.list_installed("ws-2") == []

    catalog = reloaded.list_catalog(workspace_id="ws-1")
    scheduler = next(p for p in catalog if p["id"] == "scheduler")
    assert scheduler["installed"] is True
