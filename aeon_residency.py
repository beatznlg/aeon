"""
AEON OS Phase 45 — Security, Compliance & Data Residency
=========================================================
Data residency enforcement and BYOK/KMS-style envelope encryption.

Usage:
    from aeon_residency import DataResidencyManager, residency_manager
    mgr = DataResidencyManager()
    mgr.enforce_region("eu-west-1")
    enc, envelope = mgr.encrypt_envelope({"secret": "data"}, kms_key_id="key-1")
    data = mgr.decrypt_envelope(enc, envelope)
"""

from __future__ import annotations

import base64
import json
import os
from typing import Any

try:
    from cryptography.fernet import Fernet
except ImportError:  # pragma: no cover - import failure is covered by runtime tests
    Fernet = None  # type: ignore[misc,assignment]


class DataResidencyManager:
    """Enforces workspace data-residency rules and provides envelope encryption."""

    def __init__(self) -> None:
        self.current_region = os.environ.get("AEON_REGION", "global")
        self.master_key = os.environ.get("AEON_MASTER_KMS_KEY")

    def enforce_region(self, required_region: str) -> None:
        """Raise if the runtime region violates a workspace's data residency rule.

        A required_region of "global" means no restriction.
        """
        if required_region != "global" and self.current_region != required_region:
            msg = (
                f"Data Residency Violation: execution halted in {self.current_region}, "
                f"workspace requires {required_region}"
            )
            raise PermissionError(msg)

    def _derive_kek(self) -> bytes:
        """Derive a Fernet-compatible key from the configured master key."""
        if not self.master_key:
            raise ValueError("AEON_MASTER_KMS_KEY is not configured")
        # Fernet keys are 32 bytes base64-encoded (43 chars). Derive via PBKDF2.
        import hashlib

        salt = b"aeon-residency-v1"
        derived = hashlib.pbkdf2_hmac("sha256", self.master_key.encode("utf-8"), salt, iterations=100000, dklen=32)
        encoded = base64.urlsafe_b64encode(derived)
        return encoded

    def encrypt_envelope(
        self,
        data: dict[str, Any],
        kms_key_id: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Encrypt data using a randomly generated DEK wrapped by the KEK.

        Returns the encrypted payload and an envelope describing how to decrypt.
        """
        payload_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")

        if Fernet is None:
            raise RuntimeError("cryptography is required for envelope encryption")

        dek = Fernet.generate_key()
        f_dek = Fernet(dek)
        encrypted_data = f_dek.encrypt(payload_bytes).decode("utf-8")

        kek = self._derive_kek()
        wrapped_dek = Fernet(kek).encrypt(dek).decode("utf-8")

        return encrypted_data, {
            "cipher": "fernet",
            "wrapped_dek": wrapped_dek,
            "kms_id": kms_key_id,
        }

    def decrypt_envelope(self, encrypted_data: str, envelope: dict[str, Any]) -> dict[str, Any]:
        """Decrypt data that was previously encrypted with encrypt_envelope."""
        if Fernet is None:
            raise RuntimeError("cryptography is required for envelope decryption")
        if envelope.get("cipher") != "fernet":
            raise ValueError("Unsupported envelope cipher")

        kek = self._derive_kek()
        wrapped_dek = envelope.get("wrapped_dek")
        if not wrapped_dek:
            raise ValueError("Envelope missing wrapped_dek")

        dek = Fernet(kek).decrypt(wrapped_dek.encode("utf-8"))
        f_dek = Fernet(dek)
        raw = f_dek.decrypt(encrypted_data.encode("utf-8"))
        return json.loads(raw.decode("utf-8"))

    def can_store_in_region(self, required_region: str) -> bool:
        """Return True if the current runtime region satisfies the workspace rule."""
        try:
            self.enforce_region(required_region)
        except PermissionError:
            return False
        return True


# Singleton instance for request-scoped use.
residency_manager = DataResidencyManager()
