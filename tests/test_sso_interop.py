"""IdP interoperability harness (simulated Entra/Okta-style OIDC flow).

Mocks the discovery, token-exchange, and JWKS endpoints and drives the real
``aeon_sso.complete_oidc_login`` verification and provisioning pipeline.
Real-tenant interop evidence (Entra ID, Okta, Google, Keycloak, ADFS/PIV-CAC)
is captured manually per ``docs/security/IDP_INTEROP_MATRIX.md``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import types

import pytest

_SECRET = b"interop-test-secret"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _sign_hmac(data: str, secret: bytes = _SECRET) -> str:
    return _b64url(hmac.new(secret, data.encode("ascii"), hashlib.sha256).digest())


def _make_id_token(*, nonce: str, secret: bytes = _SECRET) -> str:
    header = {"alg": "HS256", "typ": "JWT", "kid": "k1"}
    claims = {
        "iss": "https://idp.test",
        "sub": "user-001",
        "email": "gov@entra.test",
        "nonce": nonce,
        "exp": int(time.time()) + 3600,
    }
    h = _b64url(json.dumps(header, separators=(",", ":")).encode("ascii"))
    c = _b64url(json.dumps(claims, separators=(",", ":")).encode("ascii"))
    signing_input = f"{h}.{c}"
    return f"{signing_input}.{_sign_hmac(signing_input, secret)}"


def _jwks_dict() -> dict:
    return {"keys": [{"kty": "oct", "alg": "HS256", "kid": "k1", "k": _b64url(_SECRET)}]}


def _provider() -> types.SimpleNamespace:
    return types.SimpleNamespace(
        protocol="oidc",
        id="prov-entra",
        workspace_id="ws-entra",
        config={
            "client_id": "aeon-client",
            "client_secret": "secret",
            "token_endpoint": "https://login.microsoftonline.com/tenant/oauth2/v2.0/token",
            "jwks_uri": "https://login.microsoftonline.com/tenant/discovery/v2.0/keys",
        },
        attribute_mapping={},
    )


def _patch_endpoints(monkeypatch, id_token: str) -> dict:
    import aeon_sso

    provider = _provider()

    def fake_post(url, **kwargs):
        assert url == provider.config["token_endpoint"]
        return types.SimpleNamespace(json=lambda: {"id_token": id_token, "access_token": "at-1"}, raise_for_status=lambda: None)

    def fake_get(uri, timeout=30):
        assert uri == provider.config["jwks_uri"]
        return types.SimpleNamespace(json=lambda: _jwks_dict(), raise_for_status=lambda: None)

    monkeypatch.setattr(aeon_sso.requests, "post", fake_post)
    monkeypatch.setattr(aeon_sso.requests, "get", fake_get)
    return provider


def test_oidc_full_flow_entra_style(monkeypatch):
    """Valid id_token + JWKS -> claims verified -> user provisioned -> token issued."""
    import aeon_sso
    from aeon_sso import complete_oidc_login

    provider = _patch_endpoints(monkeypatch, _make_id_token(nonce="nonce-abc"))
    provisioned = {}

    def fake_provision(p, external_id, email, name, attributes):
        provisioned.update({"external_id": external_id, "email": email, "name": name})
        return types.SimpleNamespace(id="user-1", email=email, name=name, role="VIEWER")

    monkeypatch.setattr(aeon_sso, "_provision_sso_user", fake_provision)
    monkeypatch.setattr(aeon_sso, "_issue_sso_token", lambda p, u: "jwt-issued")

    result = complete_oidc_login(provider, "code-x", "state-x", "nonce-abc")
    assert result["ok"] is True
    assert result["token"] == "jwt-issued"
    assert provisioned["external_id"] == "user-001"
    assert provisioned["email"] == "gov@entra.test"
    assert result["user"]["workspace_id"] == "ws-entra"


def test_oidc_flow_rejects_nonce_mismatch(monkeypatch):
    from aeon_sso import complete_oidc_login

    provider = _patch_endpoints(monkeypatch, _make_id_token(nonce="nonce-abc"))
    with pytest.raises(ValueError, match="nonce mismatch"):
        complete_oidc_login(provider, "code-x", "state-x", "wrong-nonce")


def test_oidc_flow_requires_id_token(monkeypatch):
    import aeon_sso
    from aeon_sso import complete_oidc_login

    provider = _provider()

    def fake_post(url, **kwargs):
        return types.SimpleNamespace(json=lambda: {"access_token": "at-1"}, raise_for_status=lambda: None)

    monkeypatch.setattr(aeon_sso.requests, "post", fake_post)
    with pytest.raises(ValueError, match="did not include id_token"):
        complete_oidc_login(provider, "code-x", "state-x", "nonce-abc")
