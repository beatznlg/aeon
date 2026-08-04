"""Regression tests for AEON CORS origin handling."""

from __future__ import annotations


def test_wildcard_cors_does_not_reflect_request_origin(client, monkeypatch):
    monkeypatch.setenv("AEON_CORS_ALLOWED_ORIGINS", "*")
    monkeypatch.delenv("AEON_CORS_ALLOW_CREDENTIALS", raising=False)

    response = client.get("/live", headers={"Origin": "https://untrusted.example"})

    assert response.status_code == 200
    assert response.headers["Access-Control-Allow-Origin"] == "*"
    assert "Access-Control-Allow-Credentials" not in response.headers


def test_credentialed_cors_requires_explicit_allowlist(client, monkeypatch):
    monkeypatch.setenv("AEON_CORS_ALLOWED_ORIGINS", "*")
    monkeypatch.setenv("AEON_CORS_ALLOW_CREDENTIALS", "true")

    response = client.get("/live", headers={"Origin": "https://untrusted.example"})

    assert response.status_code == 200
    assert "Access-Control-Allow-Origin" not in response.headers
    assert "Access-Control-Allow-Credentials" not in response.headers


def test_explicit_credentialed_cors_allows_only_configured_origin(client, monkeypatch):
    monkeypatch.setenv("AEON_CORS_ALLOWED_ORIGINS", "https://app.example")
    monkeypatch.setenv("AEON_CORS_ALLOW_CREDENTIALS", "true")

    allowed = client.get("/live", headers={"Origin": "https://app.example"})
    denied = client.get("/live", headers={"Origin": "https://untrusted.example"})

    assert allowed.headers["Access-Control-Allow-Origin"] == "https://app.example"
    assert allowed.headers["Access-Control-Allow-Credentials"] == "true"
    assert "Access-Control-Allow-Origin" not in denied.headers
