"""
AEON Notification Helper
========================
Writes in-app notifications to the Supabase `notifications` table using the
service-role key (bypasses RLS so the backend can notify any user).

This module is used by aeon_server.py to auto-create notifications when key
events happen: swarms complete / fail, workflows run, API keys are
created / revoked, users register, billing events fire, etc.

Usage:
    from aeon_notify import notify

    notify(
        user_id="uuid",
        type="swarm_completed",
        title="Risk Assessment Complete",
        body="...",
        icon="🐝",
        link="/swarm/abc123",
        workspace_id="uuid",
    )

The call is fire-and-forget — a failure to reach Supabase is logged and
swallowed so it never interrupts the primary request flow.
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger("aeon_notify")


def broadcast_event(
    type: str,
    payload: dict[str, Any],
    user_id: str | None = None,
    workspace_id: str | None = None,
) -> bool:
    """Broadcast an event to the Next.js real-time SSE hub.

    This is fire-and-forget: failures are logged but not raised so that the
    primary request flow is never interrupted. The webhook is authenticated
    with a shared internal secret (``AEON_INTERNAL_SECRET``).
    """
    web_url = os.environ.get("AEON_WEB_URL")
    secret = os.environ.get("AEON_INTERNAL_SECRET")
    if not web_url or not secret:
        logger.debug("Broadcasting not configured — skipping event %r", type)
        return False

    try:
        import requests

        url = web_url.rstrip("/") + "/api/events/broadcast"
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
            json={
                "type": type,
                "payload": payload,
                "user_id": user_id,
                "workspace_id": workspace_id,
            },
            timeout=5,
        )
        response.raise_for_status()
        logger.debug("Broadcasted event %s → %s", type, user_id[:8] if user_id else "*")
        return True
    except Exception as exc:
        logger.warning("Failed to broadcast event %r: %s", type, exc)
        return False

_NOTIFICATION_TYPES = frozenset({
    "swarm_completed",
    "swarm_failed",
    "workflow_completed",
    "workflow_failed",
    "api_key_created",
    "api_key_revoked",
    "api_key_rotated",
    "welcome",
    "plan_changed",
    "credits_added",
    "subscription_updated",
    "subscription_canceled",
    "invoice_due",
    "integration_error",
    "system_alert",
})


def _ensure_icon(notif_type: str) -> str:
    """Return a suitable default emoji for the notification type."""
    return {
        "swarm_completed": "🐝",
        "swarm_failed": "⚠️",
        "workflow_completed": "⚡",
        "workflow_failed": "❌",
        "api_key_created": "🔑",
        "api_key_revoked": "🗑️",
        "api_key_rotated": "🔄",
        "welcome": "👋",
        "plan_changed": "⭐",
        "credits_added": "💰",
        "subscription_updated": "📋",
        "subscription_canceled": "🚫",
        "invoice_due": "🧾",
        "integration_error": "🔌",
        "system_alert": "🔔",
    }.get(notif_type, "🔔")


def notify(
    user_id: str,
    type: str,
    title: str,
    body: str | None = None,
    icon: str | None = None,
    link: str | None = None,
    workspace_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Create a notification for *user_id* about *type*.

    This is a fire-and-forget helper.  Returns ``True`` on success,
    ``False`` on failure (logged but not raised).

    Parameters
    ----------
    user_id:
        UUID of the user to notify.
    type:
        Event type (see ``_NOTIFICATION_TYPES``).
    title:
        Short human-readable title.
    body:
        Optional longer description.
    icon:
        Emoji icon.  Auto-derived from *type* when omitted.
    link:
        Optional relative URL to link to.
    workspace_id:
        Optional workspace context.
    metadata:
        Optional JSON-serialisable dict with extra context.
    """
    if type not in _NOTIFICATION_TYPES:
        logger.warning("Unknown notification type %r — inserting anyway", type)

    # Resolve Supabase credentials
    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        logger.debug("Supabase not configured — skipping notification %r", type)
        return False

    payload = {
        "user_id": user_id,
        "type": type,
        "title": title,
        "body": body or "",
        "icon": icon or _ensure_icon(type),
        "link": link or "",
        "workspace_id": workspace_id,
        "metadata": json.dumps(metadata or {}),
        "read": False,
        "created_at": "now",
    }

    try:
        import requests

        r = requests.post(
            f"{supabase_url}/rest/v1/notifications",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=payload,
            timeout=5,
        )
        r.raise_for_status()
        logger.debug("Notification sent: %s → %s (%s)", type, user_id[:8], title[:50])
        return True
    except Exception as exc:
        logger.warning("Failed to send notification %r: %s", type, exc)
        return False


# ── Activity feed logging ────────────────────────────────────────────────────

def log_activity(
    type: str,
    payload: dict[str, Any],
    user_id: str | None = None,
    workspace_id: str | None = None,
) -> bool:
    """Persist an activity event to Supabase and broadcast it in real time.

    This is fire-and-forget: failures are logged but not raised so that the
    primary request flow is never interrupted.
    """
    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    # Always attempt to broadcast the live event, even if persistence is unavailable.
    if supabase_url and service_key:
        try:
            import requests

            r = requests.post(
                f"{supabase_url}/rest/v1/activity_events",
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json={
                    "type": type,
                    "payload": json.dumps(payload or {}),
                    "user_id": user_id,
                    "workspace_id": workspace_id,
                },
                timeout=5,
            )
            r.raise_for_status()
            logger.debug("Activity logged: %s → %s", type, user_id[:8] if user_id else "*")
        except Exception as exc:
            logger.warning("Failed to persist activity %r: %s", type, exc)

    # Broadcast via the Next.js real-time hub when configured.
    broadcast_event(type, payload, user_id, workspace_id)

    # Evaluate event-driven automation rules (Phase 18).
    try:
        from aeon_automations import evaluate_automations

        evaluate_automations(type, payload, user_id, workspace_id)
    except Exception as exc:
        logger.debug("Automation evaluation skipped for %s: %s", type, exc)

    return True
