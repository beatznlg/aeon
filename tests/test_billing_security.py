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


def test_usage_summary_requires_explicit_workspace_context(client):
    token, own_workspace = _register(client, "route-missing-workspace")
    response = client.get(
        "/usage/summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "workspace_id required"
    assert own_workspace


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

    batched = client.post(
        "/usage",
        headers=headers,
        json=[
            {"workspace_id": _own_workspace, "action": "chat"},
            {"workspace_id": other_workspace, "action": "chat"},
        ],
    )
    assert batched.status_code == 403


_EVENT_CAPTURE = {}


def _make_fake_stripe(event: dict):
    _EVENT_CAPTURE["event"] = event

    class FakeWebhook:
        _event = event

        @staticmethod
        def construct_event(payload, sig_header, secret):
            return _EVENT_CAPTURE["event"]

    class FakeStripe:
        Webhook = FakeWebhook

    return FakeStripe()


def test_webhook_duplicate_event_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    stripe_module = _load_real_stripe_module()
    stripe_client = stripe_module.StripeClient(tmp_path)
    stripe_client._stripe = _make_fake_stripe(
        {"id": "evt_test_123", "type": "invoice.paid", "data": {"object": {"id": "in_1"}}}
    )
    stripe_client._available = True

    calls = {"n": 0}

    def fake_handler(event_type, data):
        calls["n"] += 1
        return {"handled": True, "workspace_id": "ws-1", "plan_id": "team"}

    stripe_client._handle_event = fake_handler

    first = stripe_client.handle_webhook(b"{}", "t=1,v1=sig")
    assert first["ok"] is True
    assert first["handled"] is True
    assert first.get("duplicate") is not True

    second = stripe_client.handle_webhook(b"{}", "t=1,v1=sig")
    assert second["ok"] is True
    assert second.get("duplicate") is True
    assert second["handled"] is False

    # The side-effect handler ran exactly once across both deliveries.
    assert calls["n"] == 1

    # The queryable delivery log records a processed + a duplicate entry,
    # newest first, with no secret material.
    deliveries = stripe_client.list_webhook_deliveries()
    assert [d["event_id"] for d in deliveries] == ["evt_test_123", "evt_test_123"]
    assert [d["status"] for d in deliveries] == ["duplicate", "processed"]
    assert all("sig" not in (d.get("detail") or "") for d in deliveries)


def test_webhook_different_event_id_is_processed(tmp_path, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    stripe_module = _load_real_stripe_module()
    stripe_client = stripe_module.StripeClient(tmp_path)

    stripe_client._stripe = _make_fake_stripe(
        {"id": "evt_test_456", "type": "invoice.paid", "data": {"object": {"id": "in_2"}}}
    )
    stripe_client._available = True
    calls = {"n": 0}

    def fake_handler(event_type, data):
        calls["n"] += 1
        return {"handled": True, "workspace_id": "ws-1", "plan_id": "team"}

    stripe_client._handle_event = fake_handler
    first = stripe_client.handle_webhook(b"{}", "t=1,v1=sig")
    assert first["ok"] is True and first["handled"] is True

    # A different event id is a distinct, non-duplicate event.
    stripe_client._stripe = _make_fake_stripe(
        {"id": "evt_test_789", "type": "customer.subscription.deleted", "data": {"object": {}}}
    )
    second = stripe_client.handle_webhook(b"{}", "t=1,v1=sig")
    assert second["ok"] is True
    assert second.get("duplicate") is not True
    assert calls["n"] == 2
