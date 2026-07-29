"""Tests for AEON data residency and encryption (Phase 45)."""

from __future__ import annotations

import json
import os

import pytest

from aeon_residency import DataResidencyManager


@pytest.fixture
def clean_region(monkeypatch):
    """Reset the region and master key environment for each test."""
    monkeypatch.setenv("AEON_REGION", "us-east-1")
    monkeypatch.setenv("AEON_MASTER_KMS_KEY", "test-master-key")
    return DataResidencyManager()


def test_residency_allows_matching_region(clean_region: DataResidencyManager):
    clean_region.enforce_region("us-east-1")
    assert clean_region.can_store_in_region("us-east-1") is True


def test_residency_blocks_mismatched_region(clean_region: DataResidencyManager):
    with pytest.raises(PermissionError):
        clean_region.enforce_region("eu-west-1")
    assert clean_region.can_store_in_region("eu-west-1") is False


def test_residency_global_is_unrestricted(clean_region: DataResidencyManager):
    clean_region.enforce_region("global")
    assert clean_region.can_store_in_region("global") is True


def test_envelope_encryption_round_trip(clean_region: DataResidencyManager):
    payload = {"secret": "data", "id": 1}
    encrypted, envelope = clean_region.encrypt_envelope(payload, kms_key_id="key-1")

    assert envelope["cipher"] == "fernet"
    assert envelope["kms_id"] == "key-1"
    assert "wrapped_dek" in envelope
    assert encrypted != json.dumps(payload)

    decrypted = clean_region.decrypt_envelope(encrypted, envelope)
    assert decrypted["secret"] == "data"
    assert decrypted["id"] == 1


def test_envelope_encryption_no_kms_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("AEON_MASTER_KMS_KEY", raising=False)
    monkeypatch.setenv("AEON_REGION", "us-east-1")
    mgr = DataResidencyManager()

    with pytest.raises(ValueError):
        mgr.encrypt_envelope({"secret": "data"})


def test_base64_fallback_when_cryptography_missing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(os.environ, "AEON_MASTER_KMS_KEY", "test-master-key")
    # Simulate cryptography not being available
    import aeon_residency as residency

    monkeypatch.setattr(residency, "Fernet", None)
    mgr = DataResidencyManager()

    payload = {"secret": "data"}
    encrypted, envelope = mgr.encrypt_envelope(payload, kms_key_id="key-1")
    assert envelope["cipher"] == "base64"

    decrypted = mgr.decrypt_envelope(encrypted, envelope)
    assert decrypted == payload
