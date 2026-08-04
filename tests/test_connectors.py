"""Regression coverage for AEON OS integration connectors.

Covers the catalog/adapter consistency contract and the request construction
of the real connectors (Jira, Salesforce, ServiceNow, SendGrid, Twilio) with
network access monkeypatched out.
"""

from __future__ import annotations

import importlib.util
import os


# conftest stubs aeon_integrations for the server, so load the real module
# directly (mirrors the kernel-tool test pattern).
def _load_real_integrations():
    spec = importlib.util.spec_from_file_location(
        "aeon_integrations_real",
        os.path.join(os.path.dirname(__file__), "..", "aeon_integrations.py"),
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

_integrations = _load_real_integrations()
ADAPTER_MAP = _integrations.ADAPTER_MAP
INTEGRATION_CATALOG = _integrations.INTEGRATION_CATALOG
IntegrationConfig = _integrations.IntegrationConfig
get_adapter = _integrations.get_adapter


def _config(adapter_type: str, secrets: dict, options: dict | None = None) -> IntegrationConfig:
    return IntegrationConfig(
        id="test-1",
        name=adapter_type,
        type=adapter_type,
        base_url=secrets.get("base_url", ""),
        secrets=secrets,
        options=options or {},
    )


class _CapturedRequest:
    def __init__(self, url, headers=None, json=None, timeout=None):
        self.url = url
        self.headers = headers or {}
        self.json = json
        self.timeout = timeout


def _fake_request_factory(captured: list, status: int = 200):
    class _Resp:
        status_code = status

        def json(self):
            return {"ok": True, "captured": True}

    def _fake(method, url, headers=None, json=None, timeout=None):
        captured.append(_CapturedRequest(url, headers, json, timeout))
        return _Resp()

    return _fake


def test_catalog_maps_to_adapters() -> None:
    """Every catalog entry has a registered adapter and vice versa."""
    catalog_types = {entry["adapter_type"] for entry in INTEGRATION_CATALOG}
    adapter_types = set(ADAPTER_MAP)
    # Every catalog entry must be instantiable.
    for entry in INTEGRATION_CATALOG:
        assert entry["adapter_type"] in ADAPTER_MAP, f"missing adapter for {entry['id']}"
        assert entry["required_secrets"], f"catalog entry {entry['id']} needs required_secrets"
    # Every adapter type should appear in the catalog (no dead adapters).
    for adapter_type in adapter_types:
        assert adapter_type in catalog_types or adapter_type == "http", f"adapter {adapter_type} not in catalog"
    # The new real connectors are present.
    for expected in ("jira", "salesforce", "servicenow", "sendgrid", "twilio"):
        assert expected in catalog_types


def _patch_request(monkeypatch, captured: list):
    monkeypatch.setattr(_integrations.requests, "request", _fake_request_factory(captured))


def test_jira_adapter_basic_auth(monkeypatch) -> None:
    captured: list = []
    _patch_request(monkeypatch, captured)
    adapter = get_adapter(_config("jira", {"email": "ops@acme.io", "token": "atlassian-token"}))
    result = adapter.run("issue/JIRA-1")
    assert result["ok"] is True
    assert captured[0].url == "https://your-domain.atlassian.net/rest/api/3/issue/JIRA-1"
    auth = captured[0].headers["Authorization"]
    assert auth.startswith("Basic ")
    assert "atlassian-token" not in auth


def test_jira_adapter_requires_credentials(monkeypatch) -> None:
    adapter = get_adapter(_config("jira", {}))
    result = adapter.run()
    assert result["ok"] is False
    assert "email/token" in result["error"]


def test_salesforce_adapter_uses_instance_url(monkeypatch) -> None:
    captured: list = []
    _patch_request(monkeypatch, captured)
    adapter = get_adapter(_config("salesforce", {"instance_url": "https://acme.my.salesforce.com", "token": "sf-token"}))
    result = adapter.run("sobjects/Account")
    assert result["ok"] is True
    assert captured[0].url == "https://acme.my.salesforce.com/services/data/v62.0/sobjects/Account"
    assert captured[0].headers["Authorization"] == "Bearer sf-token"


def test_servicenow_adapter_table_api(monkeypatch) -> None:
    captured: list = []
    _patch_request(monkeypatch, captured)
    adapter = get_adapter(
        _config("servicenow", {"user": "admin", "password": "pw", "base_url": "https://acme.service-now.com"})
    )
    result = adapter.run("incident")
    assert result["ok"] is True
    assert captured[0].url.endswith("/api/now/table/incident")
    assert captured[0].headers["Authorization"].startswith("Basic ")


def test_sendgrid_adapter_sends_email(monkeypatch) -> None:
    captured: list = []
    _patch_request(monkeypatch, captured)
    adapter = get_adapter(
        _config("sendgrid", {"token": "sg-token"}, options={"from_email": "aeon@acme.io"})
    )
    result = adapter.run("", method="POST", payload={"to": "user@acme.io", "subject": "Hi", "text": "body"})
    assert result["ok"] is True
    assert captured[0].url == "https://api.sendgrid.com/v3/mail/send"
    assert captured[0].headers["Authorization"] == "Bearer sg-token"
    assert captured[0].json["from"]["email"] == "aeon@acme.io"
    assert captured[0].json["personalizations"][0]["to"][0]["email"] == "user@acme.io"


def test_sendgrid_adapter_requires_recipient(monkeypatch) -> None:
    adapter = get_adapter(_config("sendgrid", {"token": "sg-token"}, options={"from_email": "aeon@acme.io"}))
    result = adapter.run("", method="POST", payload={"to": ""})
    assert result["ok"] is False
    assert "from email" in result["error"]


def test_twilio_adapter_builds_message_url(monkeypatch) -> None:
    captured: list = []
    _patch_request(monkeypatch, captured)
    adapter = get_adapter(
        _config("twilio", {"account_sid": "AC123", "auth_token": "tw-token"}, options={"from_number": "+15005550006"})
    )
    result = adapter.run("", method="POST", payload={"to": "+15005551234", "text": "Alert"})
    assert result["ok"] is True
    assert captured[0].url == "https://api.twilio.com/2010-04-01/Accounts/AC123/Messages.json"
    assert captured[0].headers["Authorization"].startswith("Basic ")
    assert captured[0].json["To"] == "+15005551234"
    assert captured[0].json["Body"] == "Alert"


def test_twilio_adapter_requires_numbers(monkeypatch) -> None:
    adapter = get_adapter(_config("twilio", {"account_sid": "AC123", "auth_token": "tok"}))
    result = adapter.run("", method="POST", payload={"to": ""})
    assert result["ok"] is False
    assert "phone numbers" in result["error"]
