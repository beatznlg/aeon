from aeon_sector_packs import get_sector_pack, list_sector_packs, task_allowed


def test_sector_packs_include_regulated_and_secure_defaults():
    packs = list_sector_packs()
    ids = {pack["id"] for pack in packs}
    assert "healthcare-us-provider" in ids
    assert "government-public-sector" in ids
    assert "defense-secure" in ids
    assert "critical-infrastructure" in ids


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
