"""
AEON OS Phase 45 — Security, Compliance & Data Residency
=========================================================
PII/PHI detection and redaction utilities.

Usage:
    from aeon_security import SecurityScanner
    scanner = SecurityScanner(pii_enabled=True, phi_enabled=True)
    redacted, findings = scanner.scan_and_redact(text)
"""

from __future__ import annotations

import re
from typing import Any

# Extended regex patterns for generic PII and medical PHI.
# These are intentionally conservative; they catch common patterns without
# relying on heavy NLP libraries, keeping AEON dependency-light.
SECURITY_PATTERNS: dict[str, dict[str, re.Pattern[str]]] = {
    "PII": {
        "EMAIL": re.compile(r"[\w\.-]+@[\w\.-]+\.\w+"),
        "CREDIT_CARD": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
        "SSN": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "PHONE": re.compile(r"\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
        "IBAN": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
        "API_KEY": re.compile(r"\b(?:api[_-]?key|token)\s*[:=]\s*[\w-]{16,}\b", re.IGNORECASE),
    },
    "PHI": {
        "MRN": re.compile(r"\bMRN\s*#?\s*\d{6,10}\b", re.IGNORECASE),
        "ICD10": re.compile(r"\b[A-TV-Z][0-9][0-9AB]\.?[0-9A-TV-Z]{0,4}\b"),
        "NPI": re.compile(r"\b\d{10}\b"),
    },
}


class SecurityScanner:
    """Detect and redact PII/PHI in text payloads."""

    def __init__(self, *, pii_enabled: bool = True, phi_enabled: bool = False):
        self.pii_enabled = pii_enabled
        self.phi_enabled = phi_enabled

    def _patterns(self) -> dict[str, re.Pattern[str]]:
        """Return the enabled pattern dictionaries merged together."""
        merged: dict[str, re.Pattern[str]] = {}
        if self.pii_enabled:
            merged.update(SECURITY_PATTERNS["PII"])
        if self.phi_enabled:
            merged.update(SECURITY_PATTERNS["PHI"])
        return merged

    def scan(self, text: str) -> list[dict[str, Any]]:
        """Return a list of PII/PHI findings without redacting."""
        findings: list[dict[str, Any]] = []
        if not text:
            return findings

        for category, patterns in SECURITY_PATTERNS.items():
            if category == "PII" and not self.pii_enabled:
                continue
            if category == "PHI" and not self.phi_enabled:
                continue
            for label, pattern in patterns.items():
                for match in pattern.finditer(text):
                    findings.append({
                        "category": category,
                        "type": label,
                        "match": match.group(0),
                        "start": match.start(),
                        "end": match.end(),
                    })
        return findings

    def scan_and_redact(self, text: str) -> tuple[str, list[dict[str, Any]]]:
        """Redact enabled PII/PHI patterns and return the cleaned text plus findings."""
        findings = self.scan(text)
        redacted = text
        if not redacted:
            return redacted, findings

        for category, patterns in SECURITY_PATTERNS.items():
            if category == "PII" and not self.pii_enabled:
                continue
            if category == "PHI" and not self.phi_enabled:
                continue
            for label, pattern in patterns.items():
                redacted = pattern.sub(f"[{label}_REDACTED]", redacted)

        return redacted, findings

    def redact(self, text: str) -> str:
        """Convenience method that returns only the redacted text."""
        return self.scan_and_redact(text)[0]


def sanitize_metadata(metadata: dict[str, Any], *, pii_enabled: bool = True, phi_enabled: bool = False) -> dict[str, Any]:
    """Recursively sanitize a metadata dict, redacting PII/PHI in string values."""
    if not isinstance(metadata, dict):
        return metadata

    scanner = SecurityScanner(pii_enabled=pii_enabled, phi_enabled=phi_enabled)
    cleaned: dict[str, Any] = {}
    for key, value in metadata.items():
        if isinstance(value, str):
            cleaned[key] = scanner.redact(value)
        elif isinstance(value, dict):
            cleaned[key] = sanitize_metadata(value, pii_enabled=pii_enabled, phi_enabled=phi_enabled)
        elif isinstance(value, list):
            cleaned[key] = [
                scanner.redact(v) if isinstance(v, str) else (sanitize_metadata(v, pii_enabled=pii_enabled, phi_enabled=phi_enabled) if isinstance(v, dict) else v)
                for v in value
            ]
        else:
            cleaned[key] = value
    return cleaned


def scan_text(text: str, *, pii_enabled: bool = True, phi_enabled: bool = False) -> tuple[str, list[dict[str, Any]]]:
    """Top-level helper for one-off PII/PHI scanning and redaction."""
    return SecurityScanner(pii_enabled=pii_enabled, phi_enabled=phi_enabled).scan_and_redact(text)
