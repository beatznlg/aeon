"""Billing authorization and production-safety regression tests."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path


def _register(client, label: str) -> tuple[str, str]:
    response = client.post(
        "/auth/register",
        json={
            "email": f"billing-{label}-{uuid.uuid4().hex[:8]}@test.local",
            "password": "secure123",
            "name": f"Billing {label}",
        },
    )
    assert response.status_code == 201, response.get_json()
    payload = response.get_json()
    return payload["token"], payload["user"]["workspace_id"]


def _load_real_stripe_module():
    path = Path(__file__).resolve().parents[1] / "aeon_stripe.py"
    spec = importlib.util.spec_from_file_location("aeon_stripe_regression", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_stripe_helpers_enforce_workspace_membership(client, tmp_path):
    token, own_workspace = _register(client, "owner")
    _other_token, other_workspace = _register(client, "other")
    stripe_module = _load_real_stripe_module()
    stripe_client = stripe_module.StripeClient(tmp_path)

    import aeon_server

    with aeon_server.app.test_request_context(
        "/stripe/checkout",
        headers={"Authorization": f"Bearer {token}"},
    ):
        assert stripe_client._workspace_access(own_workspace, "ADMIN") is True
        assert stripe_client._workspace_access(other_workspace, "ADMIN") is False
        assert stripe_client.get_subscription_status(other_workspace)["error"] == "workspace access denied"


def test_stripe_does_not_simulate_paid_checkout_in_production(client, tmp_path, monkeypatch):
    _token, workspace_id = _register(client, "production")
    stripe_module = _load_real_stripe_module()
    stripe_client = stripe_module.StripeClient(tmp_path)
    monkeypatch.setenv("AEON_ENV", "production")

    import aeon_server

    with aeon_server.app.test_request_context(
        "/stripe/checkout",
        headers={"Authorization": f"Bearer {_token}"},
    ):
        result = stripe_client.create_checkout_session(
            workspace_id=workspace_id,
            plan_id="team",
            success_url="https://example.test/success",
            cancel_url="https://example.test/cancel",
        )

    assert result["ok"] is False
    assert result["configured"] is False
    assert "not configured" in result["error"]


def test_billing_and_usage_routes_reject_foreign_workspace(client):
    token, _own_workspace = _register(client, "route-owner")
    _other_token, other_workspace = _register(client, "route-other")
    headers = {"Authorization": f"Bearer {token}"}

    checkout = client.post(
        "/stripe/checkout",
        headers=headers,
        json={"workspace_id": other_workspace, "plan_id": "team"},
    )
    assert checkout.status_code == 403

    portal = client.post(
        "/stripe/portal",
        headers=headers,
        json={"workspace_id": other_workspace},
    )
    assert portal.status_code == 403

    subscription = client.get(
        f"/stripe/subscription/{other_workspace}",
        headers=headers,
    )
    assert subscription.status_code == 403

    usage = client.get(
        f"/usage/summary?workspace_id={other_workspace}",
        headers=headers,
    )
    assert usage.status_code == 403

    recorded = client.post(
        "/usage",
        headers=headers,
        json={"workspace_id": other_workspace, "action": "chat"},
    )
    assert recorded.status_code == 403
