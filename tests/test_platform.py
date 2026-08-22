"""Tests for the AEON Platform Foundation (modules, connectors, tenants, universal model)."""

from __future__ import annotations

import pytest

from aeon_platform import (
    CONNECTOR_CATALOG,
    CONNECTOR_CONTRACT,
    INDUSTRY_PACKS,
    MODULE_CATALOG,
    TenantConfigManager,
    connector_health,
    list_connectors,
    list_industry_packs,
    list_modules,
    list_universal_entities,
    normalize_entity,
)


@pytest.fixture()
def manager(tmp_path):
    return TenantConfigManager(tmp_path)


def test_module_catalog_is_universal_and_grouped():
    ids = [m["id"] for m in MODULE_CATALOG]
    assert "identity" in ids
    assert "projects" in ids
    assert "risk-engine" in ids
    categories = {m["category"] for m in MODULE_CATALOG}
    assert categories == {"core", "business", "ai"}
    # Every core module is required; nothing else is.
    for module in MODULE_CATALOG:
        if module["category"] == "core":
            assert module["required"] is True
        else:
            assert module["required"] is False


def test_connector_catalog_implements_universal_contract():
    for connector in CONNECTOR_CATALOG:
        assert set(connector["capabilities"]) <= set(CONNECTOR_CONTRACT)
        assert connector["required_secrets"]
    ids = {c["id"] for c in CONNECTOR_CATALOG}
    for expected in ("sage", "microsoft365", "indigo", "xero", "sap", "salesforce"):
        assert expected in ids


def test_new_tenant_defaults_to_universal_core(manager):
    effective = manager.effective("brand_new_tenant")
    assert effective["modules"] == [m["id"] for m in MODULE_CATALOG if m["category"] == "core"]
    assert effective["connectors"] == []
    assert effective["industry"] == "core"
    assert effective["pack"]["id"] == "core"


def test_engineering_pack_applies_modules_and_connectors(manager):
    out = manager.set("ag_group", company="AG Group", industry="engineering-construction", currency="EUR", country="MT")
    assert out["company"] == "AG Group"
    assert out["currency"] == "EUR"
    assert out["country"] == "MT"
    assert out["pack"]["name"] == "Engineering & Construction"
    assert "projects" in out["modules"]
    assert "risk-engine" in out["modules"]
    assert set(out["connectors"]) == {"sage", "microsoft365", "indigo"}


def test_restaurant_tenant_different_config_same_platform(manager):
    out = manager.set("restaurant_xyz", company="Restaurant XYZ", industry="restaurant")
    assert "inventory" in out["modules"]
    assert "sales" in out["modules"]
    assert set(out["connectors"]) == {"xero", "microsoft365", "pos"}


def test_unknown_module_and_connector_rejected(manager):
    with pytest.raises(ValueError, match="unknown modules"):
        manager.set("t1", modules=["finance", "not-a-module"])
    with pytest.raises(ValueError, match="unknown connectors"):
        manager.set("t1", connectors=["not-a-connector"])
    with pytest.raises(ValueError, match="unknown industry pack"):
        manager.set("t1", industry="not-an-industry")


def test_tenant_config_persists_across_manager_instances(tmp_path):
    first = TenantConfigManager(tmp_path)
    first.set("ag_group", company="AG Group", industry="engineering-construction")
    second = TenantConfigManager(tmp_path)
    effective = second.effective("ag_group")
    assert effective["company"] == "AG Group"
    assert "projects" in effective["modules"]


def test_universal_normalization_sage_and_xero_to_same_entity():
    sage = normalize_entity("invoice", {"invoice_number": "INV-001", "total_amount": 1200.5, "date": "2026-08-01", "status": "paid"}, "sage")
    xero = normalize_entity("invoice", {"number": "INV-001", "total": 1200.5, "issued_at": "2026-08-01", "status": "paid"}, "xero")
    assert sage["number"] == xero["number"] == "INV-001"
    assert sage["total"] == xero["total"] == 1200.5
    assert sage["issued_at"] == xero["issued_at"] == "2026-08-01"
    assert sage["_source"] == "sage"
    assert xero["_source"] == "xero"


def test_universal_normalization_unknown_entity_rejected():
    with pytest.raises(ValueError, match="unknown universal entity"):
        normalize_entity("spaceship", {}, "x")


def test_connector_health_reports_contract(manager):
    result = connector_health("sage")
    assert result["status"] == "operational"
    assert set(result["contract"]) == set(CONNECTOR_CONTRACT)
    with pytest.raises(ValueError, match="unknown connector"):
        connector_health("nope")


def test_build_tenant_context_prompt(manager):
    manager.set("ag_group", company="AG Group", industry="engineering-construction", currency="EUR", country="MT")
    from aeon_platform import build_tenant_context_prompt

    # Point the process-wide manager at the temp store for the prompt builder.
    import aeon_platform

    original = aeon_platform.get_tenant_config_manager
    aeon_platform.get_tenant_config_manager = lambda root=None: manager
    try:
        prompt = build_tenant_context_prompt("ag_group")
    finally:
        aeon_platform.get_tenant_config_manager = original
    assert "Company: AG Group" in prompt
    assert "Engineering & Construction" in prompt
    assert "Currency: EUR" in prompt
    assert "Country: MT" in prompt
    assert "projects" in prompt
    assert "Sage" in prompt
    assert "Microsoft 365" in prompt
    assert "Indigo" in prompt


def test_build_tenant_context_prompt_generic_for_unknown_tenant(manager):
    from aeon_platform import build_tenant_context_prompt

    import aeon_platform

    original = aeon_platform.get_tenant_config_manager
    aeon_platform.get_tenant_config_manager = lambda root=None: manager
    try:
        prompt = build_tenant_context_prompt("")
    finally:
        aeon_platform.get_tenant_config_manager = original
    # Unknown tenants still get a generic context so chat never loses grounding.
    assert "an AEON tenant" in prompt
    assert "Enabled modules:" in prompt


def test_catalog_listing_functions():
    modules = list_modules()
    assert len(modules) == len(MODULE_CATALOG)
    assert all("enabled" in m for m in modules)
    connectors = list_connectors()
    assert len(connectors) == len(CONNECTOR_CATALOG)
    packs = list_industry_packs()
    assert len(packs) == len(INDUSTRY_PACKS)
    entities = list_universal_entities()
    assert len(entities) >= 25
    assert {e["id"] for e in entities} >= {"invoice", "project", "person", "risk"}
