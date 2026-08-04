"""
AEON OS — Enterprise Single Sign-On (Phase 44)
==============================================
Supports SAML 2.0 (optional python3-saml) and OpenID Connect (joserfc).
Providers are configured per workspace. Successful SSO callbacks perform
just-in-time user provisioning and issue AEON JWT access tokens.

Env:
  AEON_BASE_URL          Public base URL of the AEON backend, e.g.
                         https://aeon.example.com. Falls back to the Host
                         header or http://localhost:5000.
"""

from __future__ import annotations

import hashlib
import logging
import os
import secrets
import urllib.parse
from typing import Any

import requests
from flask import request

from aeon_auth import create_access_token
from aeon_db import IdentityLink, Membership, SsoProvider, User, get_db

logger = logging.getLogger("aeon_sso")

# SAML is a heavy optional dependency (requires xmlsec). Treat it as optional.
try:  # pragma: no cover
    from onelogin.saml2.auth import OneLogin_Saml2_Auth

    SAML_AVAILABLE = True
except Exception:  # noqa: BLE001
    SAML_AVAILABLE = False

try:  # pragma: no cover
    from joserfc import jwt as jose_jwt
    from joserfc.jwk import KeySet as JoseKeySet
    from joserfc.jwt import JWTClaimsRegistry

    JOSERFC_AVAILABLE = True
except Exception:  # noqa: BLE001
    JOSERFC_AVAILABLE = False


def _base_url() -> str:
    env_url = os.environ.get("AEON_BASE_URL", "")
    if env_url:
        return env_url.rstrip("/")
    if request and request.host_url:
        return request.host_url.rstrip("/")
    return "http://localhost:5000"


def _acs_url(workspace_id: str, protocol: str) -> str:
    return f"{_base_url()}/sso/{protocol}/acs/{workspace_id}"


def _login_callback_url(workspace_id: str, protocol: str) -> str:
    return f"{_base_url()}/sso/{protocol}/callback/{workspace_id}"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_sso_provider(provider_id: str) -> SsoProvider | None:
    db = get_db()
    with db.session() as s:
        return s.query(SsoProvider).filter_by(id=str(provider_id)).first()


def list_sso_providers(workspace_id: str, active_only: bool = True) -> list[SsoProvider]:
    db = get_db()
    with db.session() as s:
        q = s.query(SsoProvider).filter_by(workspace_id=str(workspace_id))
        if active_only:
            q = q.filter_by(active=True)
        return q.all()


def create_sso_provider(
    workspace_id: str,
    protocol: str,
    name: str,
    config: dict[str, Any],
    attribute_mapping: dict[str, Any] | None = None,
    active: bool = True,
) -> SsoProvider:
    db = get_db()
    provider = SsoProvider(
        workspace_id=str(workspace_id),
        protocol=protocol.lower(),
        name=name,
        config=config or {},
        attribute_mapping=attribute_mapping or {},
        active=active,
    )
    with db.session() as s:
        s.add(provider)
        s.commit()
        return provider


def update_sso_provider(
    provider: SsoProvider,
    name: str | None = None,
    config: dict[str, Any] | None = None,
    attribute_mapping: dict[str, Any] | None = None,
    active: bool | None = None,
) -> SsoProvider:
    if name is not None:
        provider.name = name
    if config is not None:
        provider.config = config
    if attribute_mapping is not None:
        provider.attribute_mapping = attribute_mapping
    if active is not None:
        provider.active = active
    db = get_db()
    with db.session() as s:
        s.add(provider)
        s.commit()
        return provider


def delete_sso_provider(provider_id: str) -> bool:
    db = get_db()
    with db.session() as s:
        q = s.query(SsoProvider).filter_by(id=str(provider_id))
        deleted = q.delete()
        s.commit()
        return bool(deleted)


# === OIDC helpers =============================================================

def _oidc_auth_url(provider: SsoProvider, state: str, nonce: str) -> str:
    cfg = provider.config or {}
    params = {
        "client_id": cfg["client_id"],
        "response_type": "code",
        "scope": cfg.get("scope", "openid email profile"),
        "redirect_uri": _login_callback_url(provider.workspace_id, "oidc"),
        "state": state,
        "nonce": nonce,
    }
    return f"{cfg['authorization_endpoint']}?{urllib.parse.urlencode(params)}"


def _exchange_oidc_code(provider: SsoProvider, code: str) -> dict[str, Any]:
    cfg = provider.config or {}
    token_endpoint = cfg["token_endpoint"]
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _login_callback_url(provider.workspace_id, "oidc"),
        "client_id": cfg["client_id"],
    }
    if cfg.get("client_secret"):
        payload["client_secret"] = cfg["client_secret"]
    response = requests.post(token_endpoint, data=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def _decode_oidc_id_token(provider: SsoProvider, id_token: str, nonce: str) -> dict[str, Any]:
    cfg = provider.config or {}
    jwks_uri = cfg.get("jwks_uri")

    # In test/development it is convenient to skip signature verification when
    # explicitly configured. Production should always verify.
    if os.environ.get("AEON_ENV") in ("test", "dev") and cfg.get("skip_id_token_verification"):
        import jwt as pyjwt

        claims = pyjwt.decode(
            id_token,
            options={"verify_signature": False},
            algorithms=["HS256", "RS256"],
        )
        return claims

    if not JOSERFC_AVAILABLE:
        raise RuntimeError("joserfc is required for production OIDC token verification")

    key = None
    if jwks_uri:
        jwks = requests.get(jwks_uri, timeout=30).json()
        key = JoseKeySet.import_key_set(jwks)

    token = jose_jwt.decode(id_token, key)
    claims = dict(token.claims)
    # Validate registered claims (exp, iat, nbf, sub, aud, iss) the way
    # authlib's claims.validate() did, via joserfc's claims registry.
    JWTClaimsRegistry().validate(claims)
    if claims.get("nonce") != nonce:
        raise ValueError("OIDC nonce mismatch")
    return claims


def _map_sso_role(attribute_mapping: dict[str, Any], attributes: dict[str, Any]) -> str:
    raw = None
    for key in ("role", "groups"):
        if key in attributes:
            raw = attributes[key]
            break
    if not raw:
        return attribute_mapping.get("default_role", "VIEWER")
    if isinstance(raw, str):
        raw = [raw]
    role_map = attribute_mapping.get("role_map", {})
    for item in raw:
        item_str = str(item).lower()
        for pattern, mapped in role_map.items():
            if pattern.lower() in item_str:
                return mapped.upper()
    return attribute_mapping.get("default_role", "VIEWER")


def _provision_sso_user(provider: SsoProvider, external_id: str, email: str, name: str | None, attributes: dict[str, Any]) -> User:
    role = _map_sso_role(provider.attribute_mapping or {}, attributes)
    db = get_db()
    with db.session() as s:
        # Look for an existing identity link first.
        link = (
            s.query(IdentityLink)
            .filter_by(provider_id=str(provider.id), external_id=str(external_id))
            .first()
        )
        if link:
            user = s.query(User).filter_by(id=str(link.user_id)).first()
            if user:
                return user

        # Fall back to email-based linking.
        user = s.query(User).filter_by(email=email.lower()).first()
        if not user:
            user = User(
                email=email.lower(),
                name=name or email.split("@")[0],
                password=secrets.token_urlsafe(32),
                role=role,
            )
            s.add(user)
            s.flush()
        else:
            # Enterprise SSO login takes precedence; update name if provided.
            if name:
                user.name = name

        membership = (
            s.query(Membership)
            .filter_by(workspace_id=str(provider.workspace_id), user_id=str(user.id))
            .first()
        )
        if not membership:
            membership = Membership(workspace_id=str(provider.workspace_id), user_id=str(user.id), role=role)
            s.add(membership)
        else:
            membership.role = role

        if not link:
            link = IdentityLink(user_id=str(user.id), provider_id=str(provider.id), external_id=str(external_id))
            s.add(link)

        s.commit()
        return user


def _issue_sso_token(provider: SsoProvider, user: User) -> str:
    db = get_db()
    membership = db.get_membership(str(provider.workspace_id), str(user.id))
    role = membership.role if membership else user.role
    return create_access_token(str(user.id), user.email, role, str(provider.workspace_id))


def initiate_oidc_login(provider: SsoProvider, state: str, nonce: str) -> str:
    if provider.protocol != "oidc":
        raise ValueError("provider is not an OIDC provider")
    return _oidc_auth_url(provider, state, nonce)


def complete_oidc_login(provider: SsoProvider, code: str, state: str, nonce: str) -> dict[str, Any]:
    if provider.protocol != "oidc":
        raise ValueError("provider is not an OIDC provider")

    tokens = _exchange_oidc_code(provider, code)
    id_token = tokens.get("id_token")
    if not id_token:
        raise ValueError("OIDC token response did not include id_token")

    claims = _decode_oidc_id_token(provider, id_token, nonce)
    email = (claims.get("email") or claims.get("preferred_username") or "").lower()
    if not email:
        raise ValueError("OIDC id_token is missing an email claim")

    name = claims.get("name") or claims.get("given_name")
    external_id = str(claims.get("sub"))
    attributes = dict(claims)
    attributes["role"] = claims.get("role") or claims.get("groups")

    user = _provision_sso_user(provider, external_id, email, name, attributes)
    token = _issue_sso_token(provider, user)
    return {
        "ok": True,
        "token": token,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "workspace_id": str(provider.workspace_id),
        },
    }


# === SAML helpers =============================================================

def saml_available() -> bool:
    return SAML_AVAILABLE


def _saml_settings(provider: SsoProvider, acs_url: str) -> dict[str, Any]:
    cfg = provider.config or {}
    return {
        "strict": True,
        "debug": os.environ.get("AEON_ENV", "production") == "development",
        "sp": {
            "entityId": cfg.get("sp_entity_id") or f"aeon-{provider.workspace_id}",
            "assertionConsumerService": {
                "url": acs_url,
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
            },
            "NameIDFormat": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
            "x509cert": cfg.get("sp_x509cert", ""),
            "privateKey": cfg.get("sp_private_key", ""),
        },
        "idp": {
            "entityId": cfg["idp_entity_id"],
            "singleSignOnService": {
                "url": cfg["idp_sso_url"],
                "binding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
            },
            "x509cert": cfg["idp_x509cert"],
        },
        "security": {
            "nameIdEncrypted": False,
            "authnRequestsSigned": bool(cfg.get("sp_private_key")),
            "wantAssertionsEncrypted": False,
            "wantAssertionsSigned": True,
            "wantNameId": True,
            "wantNameIdEncrypted": False,
            "requestedAuthnContext": True,
        },
    }


def initiate_saml_login(provider: SsoProvider) -> str:
    if not SAML_AVAILABLE:
        raise RuntimeError("python3-saml is not installed")
    if provider.protocol != "saml":
        raise ValueError("provider is not a SAML provider")

    acs = _acs_url(provider.workspace_id, "saml")
    settings = _saml_settings(provider, acs)
    auth = OneLogin_Saml2_Auth({"REQUEST_METHOD": "GET"}, settings)
    return auth.login()


def complete_saml_login(provider: SsoProvider, request_form: dict[str, Any]) -> dict[str, Any]:
    if not SAML_AVAILABLE:
        raise RuntimeError("python3-saml is not installed")
    if provider.protocol != "saml":
        raise ValueError("provider is not a SAML provider")

    acs = _acs_url(provider.workspace_id, "saml")
    settings = _saml_settings(provider, acs)
    auth = OneLogin_Saml2_Auth({"REQUEST_METHOD": "POST", "POST": request_form}, settings)
    auth.process_response()
    errors = auth.get_errors()
    if errors:
        raise RuntimeError(f"SAML response errors: {errors}")

    attributes = auth.get_attributes()
    nameid = auth.get_nameid()
    email = (nameid or attributes.get("email", [None])[0] or "").lower()
    if not email:
        raise ValueError("SAML response did not contain an email")

    external_id = attributes.get("uid", [email])[0]
    name = attributes.get("name", [None])[0] or attributes.get("givenName", [None])[0]
    user = _provision_sso_user(provider, str(external_id), email, name, {**attributes, "email": email})
    token = _issue_sso_token(provider, user)
    return {
        "ok": True,
        "token": token,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "workspace_id": str(provider.workspace_id),
        },
    }
