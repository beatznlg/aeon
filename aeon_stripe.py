"""
AEON OS Phase 5 — Stripe Payment Integration
=============================================
Real Stripe payment processing with subscription plans, checkout sessions,
billing portal, and webhook handling. Falls back gracefully to the simulated
billing system when STRIPE_API_KEY is not configured.

Env:
    STRIPE_API_KEY             Live/test secret key (sk_test_... or sk_live_...)
    STRIPE_WEBHOOK_SECRET      Webhook signing secret (whsec_...)
    STRIPE_PRICE_FREE          Price ID for the Free plan (optional)
    STRIPE_PRICE_TEAM          Price ID for the Team plan ($49/mo)
    STRIPE_PRICE_ENTERPRISE    Price ID for the Enterprise plan (custom)
    STRIPE_TAX_RATE            Optional default tax rate ID

Usage:
    from aeon_stripe import get_stripe_client
    client = get_stripe_client()
    if client.available:
        url = client.create_checkout_session("ws-1", "team", "https://...")
    else:
        # falls back to simulated billing
        ...
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("aeon_stripe")


# ── Stripe client wrapper ─────────────────────────────────────────────────


class StripeClient:
    """Thin Stripe wrapper with graceful fallback when the SDK/key is absent."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._stripe_dir = self.root / "stripe"
        self._stripe_dir.mkdir(parents=True, exist_ok=True)
        self._customers_file = self._stripe_dir / "customers.json"
        self._subscriptions_file = self._stripe_dir / "subscriptions.json"
        self._stripe = None
        self._available = False
        self._init_stripe()

    def _init_stripe(self):
        """Try to import and configure the Stripe SDK."""
        api_key = os.environ.get("STRIPE_API_KEY", "").strip()
        if not api_key:
            logger.info("STRIPE_API_KEY not set — falling back to simulated billing")
            return
        try:
            import stripe as _stripe_lib
            _stripe_lib.api_key = api_key
            self._stripe = _stripe_lib
            self._available = True
            logger.info("Stripe SDK initialized (mode: %s)", "test" if "sk_test_" in api_key else "live")
        except ImportError:
            logger.warning("stripe Python SDK not installed — falling back to simulated billing")

    @property
    def available(self) -> bool:
        return self._available and self._stripe is not None

    @property
    def stripe(self):
        if not self.available:
            raise RuntimeError("Stripe is not configured")
        return self._stripe

    def _workspace_access(self, workspace_id: str, required_role: str) -> bool:
        """Enforce workspace membership when called from an authenticated request.

        Stripe helpers are also usable as a standalone library, so calls outside
        Flask retain their existing behavior. HTTP calls must never be able to
        create or manage billing for another workspace.
        """
        try:
            from flask import has_request_context
            if not has_request_context():
                return True
            from aeon_auth import get_current_user_context, has_role
            context = get_current_user_context()
            if not context:
                return False
            if has_role(context.get("role"), "SUPER_ADMIN"):
                return True
            from aeon_db import get_db
            membership = get_db().get_membership(workspace_id, context.get("user_id"))
            return bool(membership and has_role(membership.role, required_role))
        except Exception:
            return False

    # ── Customer helpers ────────────────────────────────────────────────

    def _load_json(self, path: Path) -> dict[str, Any]:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:  #nosec B110
                pass
        return {}

    def _save_json(self, path: Path, data: dict[str, Any]):
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_or_create_customer(self, workspace_id: str, email: str = "", name: str = "") -> str | None:
        """Return Stripe Customer ID for a workspace, creating one if needed."""
        customers = self._load_json(self._customers_file)
        existing = customers.get(workspace_id)
        if existing:
            return existing.get("stripe_customer_id")

        if not self.available:
            return None

        try:
            customer = self.stripe.Customer.create(
                metadata={"workspace_id": workspace_id},
                email=email or None,
                name=name or None,
            )
            customers[workspace_id] = {
                "workspace_id": workspace_id,
                "stripe_customer_id": customer.id,
                "created_at": time.time(),
            }
            self._save_json(self._customers_file, customers)
            logger.info("Created Stripe customer %s for workspace %s", customer.id, workspace_id)
            return customer.id
        except Exception as e:
            logger.error("Failed to create Stripe customer: %s", e)
            return None

    def get_stripe_customer_id(self, workspace_id: str) -> str | None:
        customers = self._load_json(self._customers_file)
        existing = customers.get(workspace_id)
        return existing.get("stripe_customer_id") if existing else None

    # ── Subscription helpers ────────────────────────────────────────────

    def get_subscription_id(self, workspace_id: str) -> str | None:
        subs = self._load_json(self._subscriptions_file)
        entry = subs.get(workspace_id)
        return entry.get("subscription_id") if entry else None

    def _save_subscription(self, workspace_id: str, subscription_id: str, status: str, plan_id: str):
        subs = self._load_json(self._subscriptions_file)
        subs[workspace_id] = {
            "workspace_id": workspace_id,
            "subscription_id": subscription_id,
            "status": status,
            "plan_id": plan_id,
            "updated_at": time.time(),
        }
        self._save_json(self._subscriptions_file, subs)
        # Also sync to local billing calculator
        self._sync_to_billing(workspace_id, plan_id)

    def _sync_to_billing(self, workspace_id: str, plan_id: str):
        """Sync subscription status to the simulated billing system as fallback."""
        try:
            from aeon_usage import BillingCalculator
            calc = BillingCalculator(self.root)
            calc.set_plan(workspace_id, plan_id, credits=0.0)
        except Exception:  #nosec B110
            pass

    # ── Price ID resolution ─────────────────────────────────────────────

    def _price_id_for_plan(self, plan_id: str) -> str | None:
        """Map a plan ID to a Stripe Price ID from env vars."""
        mapping = {
            "free": "STRIPE_PRICE_FREE",
            "team": "STRIPE_PRICE_TEAM",
            "enterprise": "STRIPE_PRICE_ENTERPRISE",
        }
        env_key = mapping.get(plan_id)
        if not env_key:
            return None
        return os.environ.get(env_key, "").strip() or None

    # ── Checkout session ────────────────────────────────────────────────

    def create_checkout_session(
        self,
        workspace_id: str,
        plan_id: str,
        success_url: str,
        cancel_url: str,
        customer_email: str = "",
        customer_name: str = "",
    ) -> dict[str, Any]:
        """Create a Stripe Checkout Session for a subscription plan.

        Returns a dict with 'url' (redirect URL) or an error. Development/test
        environments may use the simulated fallback; production never does.
        """
        if not self._workspace_access(workspace_id, "ADMIN"):
            return {"ok": False, "error": "workspace admin required"}
        if not self.available:
            if os.environ.get("AEON_ENV", "development").lower() in {"production", "prod", "staging"}:
                return {
                    "ok": False,
                    "error": "Stripe billing is not configured for this environment",
                    "configured": False,
                }
            # Development/test fallback: simulate plan changes without charging.
            logger.info("Stripe unavailable — simulating plan upgrade for %s -> %s", workspace_id, plan_id)
            self._sync_to_billing(workspace_id, plan_id)
            return {"ok": True, "url": None, "simulated": True, "plan_id": plan_id}

        try:
            customer_id = self.get_or_create_customer(workspace_id, email=customer_email, name=customer_name)
            price_id = self._price_id_for_plan(plan_id)

            if not price_id:
                return {"ok": False, "error": f"No Stripe Price ID configured for plan '{plan_id}'"}

            session = self.stripe.checkout.Session.create(
                mode="subscription",
                customer=customer_id,
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "workspace_id": workspace_id,
                    "plan_id": plan_id,
                },
                subscription_data={"metadata": {"workspace_id": workspace_id, "plan_id": plan_id}},
            )

            logger.info("Checkout session %s created for workspace %s (plan: %s)", session.id, workspace_id, plan_id)
            return {"ok": True, "url": session.url, "session_id": session.id, "simulated": False}

        except Exception as e:
            logger.error("Checkout session failed: %s", e)
            return {"ok": False, "error": str(e)}

    # ── Billing portal ──────────────────────────────────────────────────

    def create_portal_session(
        self,
        workspace_id: str,
        return_url: str,
    ) -> dict[str, Any]:
        """Create a Stripe Billing Portal session for managing subscriptions.

        Returns a dict with 'url' (redirect URL) or an error. Development/test
        environments may use the simulated fallback; production never does.
        """
        if not self._workspace_access(workspace_id, "ADMIN"):
            return {"ok": False, "error": "workspace admin required"}
        if not self.available:
            if os.environ.get("AEON_ENV", "development").lower() in {"production", "prod", "staging"}:
                return {
                    "ok": False,
                    "error": "Stripe billing is not configured for this environment",
                    "configured": False,
                }
            return {"ok": True, "url": None, "simulated": True}

        try:
            customer_id = self.get_stripe_customer_id(workspace_id)
            if not customer_id:
                # Try to create one
                customer_id = self.get_or_create_customer(workspace_id)
                if not customer_id:
                    return {"ok": False, "error": "No Stripe customer found for this workspace"}

            session = self.stripe.billing_portal.Configuration.create(
                business_profile={"headline": "AEON OS Billing"},
                features={
                    "subscription_cancel": {"enabled": True},
                    "subscription_pause": {"enabled": True},
                    "customer_update": {"enabled": True, "allowed_updates": ["email", "address", "tax_id"]},
                    "invoice_history": {"enabled": True},
                    "payment_method_update": {"enabled": True},
                },
            )

            portal = self.stripe.billing_portal.Session.create(
                customer=customer_id,
                configuration=session.id if hasattr(session, 'id') else None,
                return_url=return_url,
            )

            logger.info("Portal session %s created for workspace %s", portal.id, workspace_id)
            return {"ok": True, "url": portal.url, "simulated": False}

        except Exception as e:
            logger.error("Portal session failed: %s", e)
            return {"ok": False, "error": str(e)}

    # ── Webhook handler ─────────────────────────────────────────────────

    def handle_webhook(self, raw_body: bytes, signature_header: str) -> dict[str, Any]:
        """Verify and process a Stripe webhook event.

        Returns {'ok': True, 'type': ..., 'handled': True/False}
        """
        if not self.available:
            return {"ok": False, "error": "Stripe not configured"}

        secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
        if not secret:
            return {"ok": False, "error": "STRIPE_WEBHOOK_SECRET not set"}

        try:
            event = self.stripe.Webhook.construct_event(
                payload=raw_body,
                sig_header=signature_header,
                secret=secret,
            )
        except Exception as e:
            logger.warning("Webhook signature verification failed: %s", e)
            return {"ok": False, "error": f"Webhook verification failed: {e}"}

        event_type = event.get("type", "unknown")
        data = event.get("data", {}).get("object", {})

        result = self._handle_event(event_type, data)
        return {"ok": True, "type": event_type, **result}

    def _handle_event(self, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
        """Route webhook events to the appropriate handler."""
        handlers = {
            "checkout.session.completed": self._handle_checkout_completed,
            "checkout.session.async_payment_succeeded": self._handle_checkout_completed,
            "customer.subscription.created": self._handle_subscription_updated,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.paid": self._handle_invoice_paid,
            "invoice.payment_failed": self._handle_invoice_failed,
        }
        handler = handlers.get(event_type)
        if handler:
            return handler(data)
        return {"handled": False, "reason": f"Unhandled event type: {event_type}"}

    def _handle_checkout_completed(self, data: dict[str, Any]) -> dict[str, Any]:
        """Handle checkout.session.completed — subscribe the workspace."""
        metadata = data.get("metadata", {})
        workspace_id = metadata.get("workspace_id")
        plan_id = metadata.get("plan_id", "team")
        subscription_id = data.get("subscription")
        customer_id = data.get("customer")

        if not workspace_id:
            return {"handled": False, "reason": "No workspace_id in metadata"}

        # Save customer mapping
        if customer_id:
            customers = self._load_json(self._customers_file)
            if workspace_id not in customers:
                customers[workspace_id] = {}
            customers[workspace_id]["stripe_customer_id"] = customer_id
            customers[workspace_id]["stripe_customer_email"] = data.get("customer_details", {}).get("email", "")
            self._save_json(self._customers_file, customers)

        # Save subscription
        if subscription_id:
            self._save_subscription(workspace_id, subscription_id, "active", plan_id)

        logger.info("Checkout completed: workspace=%s plan=%s sub=%s", workspace_id, plan_id, subscription_id)
        return {"handled": True, "workspace_id": workspace_id, "plan_id": plan_id}

    def _handle_subscription_updated(self, data: dict[str, Any]) -> dict[str, Any]:
        """Sync subscription status changes."""
        metadata = data.get("metadata", {})
        subscription_id = data.get("id")
        status = data.get("status", "unknown")
        items = data.get("items", {}).get("data", [])

        workspace_id = metadata.get("workspace_id")
        if not workspace_id:
            # Try to find by customer
            customer_id = data.get("customer")
            if customer_id:
                customers = self._load_json(self._customers_file)
                for ws_id, info in customers.items():
                    if info.get("stripe_customer_id") == customer_id:
                        workspace_id = ws_id
                        break

        if not workspace_id:
            return {"handled": False, "reason": "Could not resolve workspace"}

        # Extract plan_id from subscription items
        plan_id = metadata.get("plan_id", "team")
        for item in items:
            price = item.get("price", {})
            product_meta = price.get("product", {})
            if isinstance(product_meta, dict):
                pid = product_meta.get("metadata", {}).get("plan_id")
                if pid:
                    plan_id = pid

        status_map = {
            "active": "active",
            "past_due": "past_due",
            "canceled": "canceled",
            "unpaid": "unpaid",
            "trialing": "trialing",
            "incomplete": "incomplete",
            "incomplete_expired": "expired",
            "paused": "paused",
        }

        local_status = status_map.get(status, status)
        self._save_subscription(workspace_id, subscription_id, local_status, plan_id)

        logger.info("Subscription updated: workspace=%s plan=%s status=%s", workspace_id, plan_id, local_status)
        return {"handled": True, "workspace_id": workspace_id, "plan_id": plan_id, "status": local_status}

    def _handle_subscription_deleted(self, data: dict[str, Any]) -> dict[str, Any]:
        """Downgrade to free plan when subscription is deleted."""
        subscription_id = data.get("id")
        customer_id = data.get("customer")

        workspace_id = None
        customers = self._load_json(self._customers_file)
        for ws_id, info in customers.items():
            if info.get("stripe_customer_id") == customer_id:
                workspace_id = ws_id
                break

        if not workspace_id:
            return {"handled": False, "reason": "Could not resolve workspace"}

        self._save_subscription(workspace_id, subscription_id, "canceled", "free")
        # Remove from local subscriptions
        subs = self._load_json(self._subscriptions_file)
        if workspace_id in subs:
            del subs[workspace_id]
            self._save_json(self._subscriptions_file, subs)

        logger.info("Subscription deleted: workspace=%s (downgraded to free)", workspace_id)
        return {"handled": True, "workspace_id": workspace_id, "plan_id": "free"}

    def _handle_invoice_paid(self, data: dict[str, Any]) -> dict[str, Any]:
        """Handle successful invoice payments — could add credits or log."""
        data.get("subscription")
        amount_paid = data.get("amount_paid", 0) / 100.0  # cents -> dollars
        customer_id = data.get("customer")

        workspace_id = None
        customers = self._load_json(self._customers_file)
        for ws_id, info in customers.items():
            if info.get("stripe_customer_id") == customer_id:
                workspace_id = ws_id
                break

        if workspace_id:
            # Add credits equivalent to the payment
            try:
                from aeon_usage import BillingCalculator
                calc = BillingCalculator(self.root)
                calc.add_credits(workspace_id, amount_paid)
            except Exception:  #nosec B110
                pass

        logger.info("Invoice paid: customer=%s amount=%.2f", customer_id, amount_paid)
        return {"handled": True, "workspace_id": workspace_id, "amount": amount_paid}

    def _handle_invoice_failed(self, data: dict[str, Any]) -> dict[str, Any]:
        """Flag subscription as past_due when payment fails."""
        subscription_id = data.get("subscription")
        customer_id = data.get("customer")

        workspace_id = None
        customers = self._load_json(self._customers_file)
        for ws_id, info in customers.items():
            if info.get("stripe_customer_id") == customer_id:
                workspace_id = ws_id
                break

        if workspace_id and subscription_id:
            subs = self._load_json(self._subscriptions_file)
            if workspace_id in subs:
                subs[workspace_id]["status"] = "past_due"
                self._save_json(self._subscriptions_file, subs)

        logger.warning("Invoice payment failed: customer=%s sub=%s", customer_id, subscription_id)
        return {"handled": True, "workspace_id": workspace_id, "status": "past_due"}

    # ── Status helpers ──────────────────────────────────────────────────

    def get_subscription_status(self, workspace_id: str) -> dict[str, Any]:
        """Return the Stripe subscription status for a workspace.

        Returns a dict with plan_id, status, and subscription_id if found.
        Falls back to local billing system.
        """
        if not self._workspace_access(workspace_id, "VIEWER"):
            return {"ok": False, "error": "workspace access denied"}

        subs = self._load_json(self._subscriptions_file)
        entry = subs.get(workspace_id)

        if entry:
            return {
                "ok": True,
                "workspace_id": workspace_id,
                "plan_id": entry.get("plan_id", "free"),
                "status": entry.get("status", "active"),
                "subscription_id": entry.get("subscription_id"),
                "source": "stripe" if self.available else "local",
            }

        # Fallback: check local billing
        try:
            from aeon_usage import BillingCalculator
            calc = BillingCalculator(self.root)
            status = calc.workspace_status(workspace_id)
            return {
                "ok": True,
                "workspace_id": workspace_id,
                "plan_id": status.get("plan", {}).get("id", "free"),
                "status": "active",
                "source": "local",
            }
        except Exception:  #nosec B110
            pass

        return {
            "ok": True,
            "workspace_id": workspace_id,
            "plan_id": "free",
            "status": "active",
            "source": "default",
        }


# ── Singleton ──────────────────────────────────────────────────────────────

_stripe_client: StripeClient | None = None
_stripe_root: Path | None = None


def init_stripe(root: Path):
    """Initialize the Stripe client singleton (called once at server start)."""
    global _stripe_client, _stripe_root
    _stripe_root = Path(root)
    _stripe_client = StripeClient(_stripe_root)


def get_stripe_client() -> StripeClient:
    """Return the singleton StripeClient instance."""
    global _stripe_client
    if _stripe_client is None:
        root = _stripe_root or Path(os.environ.get("AEON_ROOT", "./aeon_state/server"))
        _stripe_client = StripeClient(root)
    return _stripe_client
