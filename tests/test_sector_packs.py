import uuid

from aeon_sector_packs import get_sector_pack, list_sector_packs, task_allowed


def _register(client, label: str) -> tuple[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": f"packs-{label}-{uuid.uuid4().hex[:8]}@test.local",
            "password": "secure123",
            "name": f"Packs {label}",
        },
    )
    assert response.status_code == 201, response.get_json()
    data = response.get_json()
    return data["token"], data["user"]["workspace_id"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_sector_packs_route_returns_catalog(client):
    token, _workspace_id = _register(client, "route")

    response = client.get("/sector-packs", headers=_headers(token))

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    ids = {pack["id"] for pack in data["packs"]}
    assert "general-business" in ids
    assert "telecom-operator" in ids
    assert "agriculture-producer" in ids
    assert "education-institution" in ids
    assert "public-safety-agency" in ids
    assert "real-estate-portfolio" in ids
    # Every pack exposes its inference policy and approved model tags.
    telecom = next(pack for pack in data["packs"] if pack["id"] == "telecom-operator")
    assert telecom["inference_policy"]["require_grounding"] is True
    assert "private" in telecom["approved_model_tags"]


def test_sector_packs_include_regulated_and_secure_defaults():
    packs = list_sector_packs()
    ids = {pack["id"] for pack in packs}
    assert "healthcare-us-provider" in ids
    assert "government-public-sector" in ids
    assert "defense-secure" in ids
    assert "critical-infrastructure" in ids
    assert "telecom-operator" in ids
    assert "agriculture-producer" in ids
    assert "education-institution" in ids
    assert "public-safety-agency" in ids
    assert "real-estate-portfolio" in ids


def test_new_sector_packs_resolve_by_registry_sector_id():
    assert get_sector_pack(sector="telecom").id == "telecom-operator"
    assert get_sector_pack(sector="agriculture").id == "agriculture-producer"
    assert get_sector_pack(sector="education").id == "education-institution"
    assert get_sector_pack(sector="public_safety").id == "public-safety-agency"
    assert get_sector_pack(sector="real_estate").id == "real-estate-portfolio"


def test_every_registry_sector_resolves_to_a_sector_pack():
    from aeon_sectors import list_sector_catalog

    registry = {sector["id"] for sector in list_sector_catalog()}
    resolved = {sector: get_sector_pack(sector=sector).id for sector in sorted(registry)}

    # Exhaustive expectation: every sector in the tenant sector registry must
    # resolve through the inference pipeline's pack lookup — either to its
    # dedicated pack or to the general fallback. Adding a registry sector
    # without a pack (or renaming a pack's sector) fails this suite.
    assert resolved == {
        "agriculture": "agriculture-producer",
        "cybersecurity": "general-business",
        "education": "education-institution",
        "finance": "financial-services-global",
        "health": "healthcare-us-provider",
        "heritage": "general-business",
        "manufacturing": "manufacturing-enterprise",
        "public_safety": "public-safety-agency",
        "real_estate": "real-estate-portfolio",
        "retail": "general-business",
        "sme": "general-business",
        "telecom": "telecom-operator",
        "tourism": "general-business",
        "transport": "general-business",
        "utilities": "critical-infrastructure",
        "professional": "general-business",
    }

    # Every pack must reference a registry sector or a documented profile-level
    # sector (general / government / defense are not tenant data sectors). This
    # guards against a pack whose sector id would never resolve.
    pack_sectors = {pack["sector"] for pack in list_sector_packs()}
    assert pack_sectors <= registry | {"general", "government", "defense"}

    # Resolution is stable across repeated lookups.
    assert get_sector_pack(sector="telecom").id == resolved["telecom"]
    assert get_sector_pack(sector="heritage").id == resolved["heritage"]


def test_new_sector_packs_ground_outputs_and_block_autonomous_actions():
    telecom = get_sector_pack(sector="telecom")
    assert telecom.inference_policy.require_grounding is True
    assert telecom.inference_policy.require_citations is True
    assert task_allowed(telecom, "fault_triage") is True
    assert task_allowed(telecom, "autonomous_network_change") is False

    public_safety = get_sector_pack(sector="public_safety")
    assert public_safety.inference_policy.risk_level == "critical"
    assert public_safety.inference_policy.require_human_review is True
    assert task_allowed(public_safety, "dispatch_suggestion") is True
    assert task_allowed(public_safety, "autonomous_dispatch_authorization") is False

    education = get_sector_pack(sector="education")
    assert task_allowed(education, "at_risk_analysis") is True
    assert task_allowed(education, "autonomous_grade_change") is False

    real_estate = get_sector_pack(sector="real_estate")
    assert task_allowed(real_estate, "valuation_analysis") is True
    assert task_allowed(real_estate, "autonomous_acquisition") is False


def test_healthcare_pack_requires_grounding_and_review():
    pack = get_sector_pack("healthcare-us-provider")
    assert pack.inference_policy.require_grounding is True
    assert pack.inference_policy.require_human_review is True
    assert task_allowed(pack, "retrieval_qa") is True
    assert task_allowed(pack, "autonomous_diagnosis") is False


def test_sector_fallback_is_general_and_unknown_id_is_rejected():
    assert get_sector_pack(sector="unknown").id == "general-business"
    try:
        get_sector_pack("does-not-exist")
    except ValueError as exc:
        assert "unknown sector pack" in str(exc)
    else:
        raise AssertionError("unknown pack should be rejected")
