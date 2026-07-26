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
