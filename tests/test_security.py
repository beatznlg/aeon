"""Tests for AEON security PII/PHI detection and redaction (Phase 45)."""

from __future__ import annotations

from aeon_security import SecurityScanner, sanitize_metadata, scan_text


def test_pii_redaction_email():
    scanner = SecurityScanner(pii_enabled=True, phi_enabled=False)
    text = "Contact me at alice@example.com for details."
    redacted, findings = scanner.scan_and_redact(text)
    assert "[EMAIL_REDACTED]" in redacted
    assert "alice@example.com" not in redacted
    assert any(f["type"] == "EMAIL" for f in findings)


def test_phi_redaction_mrn():
    scanner = SecurityScanner(pii_enabled=False, phi_enabled=True)
    text = "Patient MRN #123456 needs follow-up."
    redacted, findings = scanner.scan_and_redact(text)
    assert "[MRN_REDACTED]" in redacted
    assert "123456" not in redacted
    assert any(f["type"] == "MRN" for f in findings)


def test_pii_and_phi_enabled():
    scanner = SecurityScanner(pii_enabled=True, phi_enabled=True)
    text = "User email is test@corp.com and MRN #123456"
    redacted, findings = scanner.scan_and_redact(text)
    assert "[EMAIL_REDACTED]" in redacted
    assert "[MRN_REDACTED]" in redacted
    assert len(findings) == 2


def test_pii_disabled():
    scanner = SecurityScanner(pii_enabled=False, phi_enabled=False)
    text = "Contact me at alice@example.com"
    redacted, findings = scanner.scan_and_redact(text)
    assert redacted == text
    assert findings == []


def test_sanitize_metadata_nested():
    metadata = {
        "note": "Email alice@example.com and phone 555-123-4567",
        "nested": {"ssn": "123-45-6789"},
        "list": ["token=abc1234567890123", {"email": "bob@example.com"}],
    }
    result = sanitize_metadata(metadata, pii_enabled=True, phi_enabled=False)
    assert "[EMAIL_REDACTED]" in result["note"]
    assert "[PHONE_REDACTED]" in result["note"]
    assert "[SSN_REDACTED]" in result["nested"]["ssn"]
    assert "[API_KEY_REDACTED]" in result["list"][0]
    assert "[EMAIL_REDACTED]" in result["list"][1]["email"]


def test_scan_text_helper():
    redacted, findings = scan_text("My email is foo@bar.com", pii_enabled=True, phi_enabled=False)
    assert "[EMAIL_REDACTED]" in redacted
    assert any(f["category"] == "PII" for f in findings)


def test_no_false_positives_on_empty():
    scanner = SecurityScanner(pii_enabled=True, phi_enabled=True)
    redacted, findings = scanner.scan_and_redact("")
    assert redacted == ""
    assert findings == []
