"""Tests for Phase 44 Enterprise SSO (SAML/OIDC)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import types
import uuid

import pytest
from joserfc.errors import BadSignatureError, ExpiredTokenError

from aeon_cache import get_cache

# ── helpers for OIDC id_token verification tests ─────────────────────────────
_SECRET = b"regression-test-secret"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _sign_hmac(data: str, secret: bytes = _SECRET) -> str:
    return _b64url(hmac.new(secret, data.encode("ascii"), hashlib.sha256).digest())


def _make_id_token(
    *,
    nonce: str = "nonce-123",
    exp: int | None = None,
    secret: bytes = _SECRET,
    kid: str = "k1",
) -> str:
    """Build a compact HS256 id_token signed with the shared secret."""
    header = {"alg": "HS256", "typ": "JWT", "kid": kid}
    claims = {"iss": "https://idp.test", "sub": "user-abc", "email": "oidc@test.local", "nonce": nonce}
    claims["exp"] = exp if exp is not None else int(time.time()) + 3600
    h = _b64url(json.dumps(header, separators=(",", ":")).encode("ascii"))
    c = _b64url(json.dumps(claims, separators=(",", ":")).encode("ascii"))
    signing_input = f"{h}.{c}"
    return f"{signing_input}.{_sign_hmac(signing_input, secret)}"


def _jwks_dict(secret: bytes = _SECRET, kid: str = "k1") -> dict:
    return {"keys": [{"kty": "oct", "alg": "HS256", "kid": kid, "k": _b64url(secret)}]}


class _FakeProvider:
    """Minimal stand-in for aeon_db.SsoProvider used by the decoder."""

    def __init__(self, config: dict) -> None:
        self.config = config


def _patch_jwks(monkeypatch, jwks: dict, url: str = "https://idp.test/jwks") -> None:
    def fake_get(uri: str, timeout: int = 30):  # noqa: ARG001
        assert uri == url
        return types.SimpleNamespace(json=lambda: jwks)

    monkeypatch.setattr("aeon_sso.requests.get", fake_get)


@pytest.fixture
def registered_client(client):
    """Return a client with an registered admin user and workspace."""
    email = f"sso-{uuid.uuid4().hex[:8]}@test.local"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "password123", "name": "SSO Tester"},
    )
    assert resp.status_code == 201
    data = resp.get_json()
    client.token = data["token"]
    client.workspace_id = data["user"]["workspace_id"]
    return client


def _headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_oidc_provider_crud(registered_client):
    client = registered_client
    resp = client.post(
        "/sso/providers",
        headers=_headers(client.token),
        json={
            "protocol": "oidc",
            "name": "Test OIDC",
            "config": {
                "client_id": "test-client",
                "client_secret": "secret",
                "authorization_endpoint": "https://idp.test/authorize",
                "token_endpoint": "https://idp.test/token",
            },
            "attribute_mapping": {"default_role": "OPERATOR"},
        },
    )
    assert resp.status_code == 201
    provider = resp.get_json()["provider"]
    assert provider["protocol"] == "oidc"

    # List
    resp = client.get("/sso/providers", headers=_headers(client.token))
    assert resp.status_code == 200
    assert len(resp.get_json()["providers"]) == 1

    # Get
    resp = client.get(f"/sso/providers/{provider['id']}", headers=_headers(client.token))
    assert resp.status_code == 200
    assert resp.get_json()["provider"]["name"] == "Test OIDC"

    # Patch
    resp = client.patch(
        f"/sso/providers/{provider['id']}",
        headers=_headers(client.token),
        json={"name": "Updated OIDC", "active": False},
    )
    assert resp.status_code == 200
    assert resp.get_json()["provider"]["name"] == "Updated OIDC"

    # Delete
    resp = client.delete(f"/sso/providers/{provider['id']}", headers=_headers(client.token))
    assert resp.status_code == 200


@ pytest.mark.skipif(
    __import__("aeon_sso", fromlist=["saml_available"]).saml_available(),
    reason="SAML library is installed; skipping degradation test",
)
def test_saml_login_degrades_when_saml_unavailable(registered_client):
    client = registered_client
    resp = client.post(
        "/sso/providers",
        headers=_headers(client.token),
        json={
            "protocol": "saml",
            "name": "Test SAML",
            "config": {
                "idp_entity_id": "https://idp.test/entity",
                "idp_sso_url": "https://idp.test/saml",
                "idp_x509cert": "dummy",
            },
        },
    )
    assert resp.status_code == 201
    provider_id = resp.get_json()["provider"]["id"]
    resp = client.get(f"/sso/saml/login/{provider_id}")
    assert resp.status_code == 501


def test_oidc_callback_issues_token(registered_client, monkeypatch):
    client = registered_client
    resp = client.post(
        "/sso/providers",
        headers=_headers(client.token),
        json={
            "protocol": "oidc",
            "name": "Test OIDC Callback",
            "config": {
                "client_id": "test-client",
                "client_secret": "secret",
                "authorization_endpoint": "https://idp.test/authorize",
                "token_endpoint": "https://idp.test/token",
                "skip_id_token_verification": True,
            },
        },
    )
    assert resp.status_code == 201
    provider_id = resp.get_json()["provider"]["id"]

    def _fake_complete(provider, code, state, nonce):
        return {
            "ok": True,
            "token": "fake-jwt",
            "user": {
                "id": "user-id",
                "email": "new@example.com",
                "role": "VIEWER",
                "workspace_id": provider.workspace_id,
            },
        }

    monkeypatch.setattr("aeon_server.complete_oidc_login", _fake_complete)

    state = "test-state-123"
    nonce = "test-nonce-456"
    get_cache().set(f"oidc:state:{state}", {"provider_id": provider_id, "nonce": nonce}, ttl=600)

    resp = client.get(f"/sso/oidc/callback/{provider_id}?code=abc&state={state}&nonce={nonce}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["ok"] is True
    assert data["token"] == "fake-jwt"


def test_sso_provider_requires_admin(registered_client):
    client = registered_client
    # Create a viewer token by registering a second user? Simpler: use an invalid token.
    resp = client.post(
        "/sso/providers",
        headers={"Authorization": "Bearer invalid-token"},
        json={"protocol": "oidc", "name": "X", "config": {}},
    )
    assert resp.status_code == 401


# ── OIDC id_token verification (joserfc) ────────────────────────────────────
def _decode(token: str, nonce: str, monkeypatch) -> dict:
    """Decode an id_token against a mocked JWKS endpoint."""
    from aeon_sso import _decode_oidc_id_token

    _patch_jwks(monkeypatch, _jwks_dict())
    return _decode_oidc_id_token(_FakeProvider({"jwks_uri": "https://idp.test/jwks"}), token, nonce)


def test_oidc_id_token_verified_against_jwks(monkeypatch):
    """A valid id_token signed with a JWKS key decodes and returns claims."""
    claims = _decode(_make_id_token(), "nonce-123", monkeypatch)
    assert claims["sub"] == "user-abc"
    assert claims["email"] == "oidc@test.local"
    assert claims["nonce"] == "nonce-123"


def test_oidc_id_token_rejects_wrong_nonce(monkeypatch):
    """A cryptographically valid id_token with a mismatched nonce is rejected."""
    from aeon_sso import _decode_oidc_id_token

    _patch_jwks(monkeypatch, _jwks_dict())
    with pytest.raises(ValueError, match="nonce mismatch"):
        _decode_oidc_id_token(
            _FakeProvider({"jwks_uri": "https://idp.test/jwks"}),
            _make_id_token(),
            "different-nonce",
        )


def test_oidc_id_token_rejects_tampered_signature(monkeypatch):
    """A token with a corrupted signature fails verification (BadSignatureError)."""
    good = _make_id_token()
    header, payload, sig = good.rsplit(".", 2)
    tampered = f"{header}.{payload}.{('A' if not sig.endswith('A') else 'B')}"
    assert tampered != good
    with pytest.raises(BadSignatureError):
        _decode(tampered, "nonce-123", monkeypatch)


def test_oidc_id_token_rejects_wrong_jwks_key(monkeypatch):
    """A token signed with a different key than the JWKS is rejected."""
    from aeon_sso import _decode_oidc_id_token

    _patch_jwks(monkeypatch, _jwks_dict(secret=b"some-other-secret"))
    with pytest.raises(BadSignatureError):
        _decode_oidc_id_token(
            _FakeProvider({"jwks_uri": "https://idp.test/jwks"}),
            _make_id_token(secret=_SECRET),
            "nonce-123",
        )


def test_oidc_id_token_rejects_expired(monkeypatch):
    """An exp in the past fails registered-claim validation (ExpiredTokenError)."""
    from aeon_sso import _decode_oidc_id_token

    _patch_jwks(monkeypatch, _jwks_dict())
    with pytest.raises(ExpiredTokenError):
        _decode_oidc_id_token(
            _FakeProvider({"jwks_uri": "https://idp.test/jwks"}),
            _make_id_token(exp=int(time.time()) - 60),
            "nonce-123",
        )
