"""
AEON OS Phase 49 — Enterprise Observability & SIEM Integration
==============================================================
Forward AEON audit, anomaly, incident, and DLP events to enterprise SIEM
endpoints (Splunk HEC, Datadog, Elastic, QRadar, Azure Sentinel, generic
webhook).  The exporter runs asynchronously in a background thread so callers
remain responsive.

Usage:
    from aeon_siem import SiemExporter
    exporter = SiemExporter(workspace_id)
    exporter.export_event("audit", { ... })      # fire-and-forget
    exporter.export_event("anomaly", { ... })    # fire-and-forget
    exporter.send_test_event(integration_id)     # synchronous-ish
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests

from aeon_db import (
    SiemIntegration,
    create_siem_export_log,
    get_siem_integration,
    list_siem_integrations,
    update_siem_export_log_status,
)

logger = logging.getLogger("aeon_siem")

# Singleton background thread / queue shared across the process.
_export_queue: queue.Queue["_ExportJob"] = queue.Queue()
_worker_thread: threading.Thread | None = None
_worker_lock = threading.Lock()

_ALLOWED_PROVIDERS = frozenset({
    "splunk",
    "datadog",
    "elastic",
    "webhook",
    "qradar",
    "sentinel",
})


@dataclass
class _ExportJob:
    integration_id: str
    workspace_id: str
    event_type: str
    event_id: str | None
    payload: dict[str, Any]
    retry_count: int = 0
    extra_log: dict[str, Any] = field(default_factory=dict)


class SiemExporter:
    """Asynchronous SIEM exporter for a workspace.

    Events are enqueued and sent by a background worker with retry/backoff.
    Each delivery is recorded in ``SiemExportLog`` for visibility.
    """

    def __init__(self, workspace_id: str) -> None:
        self.workspace_id = str(workspace_id)
        _ensure_worker()

    def export_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        event_id: str | None = None,
    ) -> None:
        """Enqueue an event for all enabled SIEM integrations that subscribe to it."""
        integrations = list_siem_integrations(self.workspace_id, enabled_only=True)
        if not integrations:
            return

        for integration in integrations:
            if not _wants_event(integration, event_type, payload):
                continue
            job = _ExportJob(
                integration_id=integration.id,
                workspace_id=self.workspace_id,
                event_type=event_type,
                event_id=event_id,
                payload=payload,
            )
            _export_queue.put(job)

    def send_test_event(self, integration_id: str) -> dict[str, Any]:
        """Send a test event synchronously through a specific integration.

        Returns a dict with ``ok``, ``status``, and optional ``error``.
        """
        integration = get_siem_integration(integration_id, workspace_id=self.workspace_id)
        if not integration:
            return {"ok": False, "error": "integration not found"}

        test_payload = _format_payload(integration.provider, "test", {
            "message": "AEON SIEM test event",
            "integration_id": integration.id,
            "provider": integration.provider,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        result = _deliver(integration, test_payload)
        _record_log(integration, "test", None, result)
        return result


def _ensure_worker() -> None:
    """Start the background delivery worker if it isn't already running."""
    global _worker_thread
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
        _worker_thread.start()


def _worker_loop() -> None:
    """Background thread: dequeue jobs and attempt delivery."""
    while True:
        try:
            job = _export_queue.get(timeout=1)
        except queue.Empty:
            continue
        try:
            _process_job(job)
        except Exception as exc:  # pragma: no cover
            logger.exception("SIEM worker failed to process job: %s", exc)


def _process_job(job: _ExportJob) -> None:
    integration = get_siem_integration(job.integration_id, workspace_id=job.workspace_id)
    if not integration:
        logger.warning("SIEM integration %s no longer exists; dropping event", job.integration_id)
        return
    if not integration.enabled:
        return

    payload = _format_payload(integration.provider, job.event_type, job.payload)
    result = _deliver(integration, payload)
    _record_log(integration, job.event_type, job.event_id, result)

    # Retry on transient failures with exponential backoff.
    if not result.get("ok") and job.retry_count < 3:
        result["retry_count"] = job.retry_count + 1
        time.sleep(2 ** job.retry_count)
        _export_queue.put(
            _ExportJob(
                integration_id=job.integration_id,
                workspace_id=job.workspace_id,
                event_type=job.event_type,
                event_id=job.event_id,
                payload=job.payload,
                retry_count=job.retry_count + 1,
            )
        )


def _wants_event(integration: SiemIntegration, event_type: str, payload: dict[str, Any]) -> bool:
    """Return True if the integration subscribes to this event type/severity."""
    filters = integration.event_filters or []
    if filters and event_type not in filters:
        return False

    log_level = integration.log_level or "all"
    if log_level == "all":
        return True

    # Map severity to level.  Lower is more severe.
    severity_map = {"info": 3, "warning": 2, "critical": 1}
    level_map = {"all": 4, "warning": 2, "critical": 1}
    severity = (payload or {}).get("severity", "info").lower()
    event_level = severity_map.get(severity, 3)
    threshold = level_map.get(log_level, 4)
    return event_level <= threshold


def _format_payload(provider: str, event_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """Wrap event data in a provider-friendly envelope."""
    timestamp = datetime.now(timezone.utc).isoformat()
    base = {
        "aeon_event_type": event_type,
        "aeon_timestamp": timestamp,
        "source": "aeon-os",
        **data,
    }
    if provider == "splunk":
        return {"event": base, "sourcetype": "aeon:os", "time": time.time()}
    if provider == "datadog":
        return {"title": f"AEON {event_type}", "text": base, "date": timestamp, "tags": [f"aeon:{event_type}"]}
    if provider == "elastic":
        return base
    if provider == "qradar":
        return {"events": [base]}
    if provider == "sentinel":
        return {"Event": base}
    return base


def _deliver(integration: SiemIntegration, payload: dict[str, Any]) -> dict[str, Any]:
    """Attempt to POST the payload to the configured endpoint."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    headers.update(integration.custom_headers or {})

    auth_type = integration.auth_type or "token"
    if auth_type == "token":
        if integration.api_token_hash:
            # The token itself is not stored; this path only works when a token
            # is provided via the test endpoint or the integration object has
            # been temporarily hydrated.  In normal operation we expect the
            # caller to pass a bearer token through custom_headers.
            pass
    elif auth_type == "basic" and integration.username and integration.password_hash:
        import base64

        # Basic auth is intentionally not supported from stored password hash.
        return {"ok": False, "error": "basic auth requires runtime credential injection"}

    url = integration.endpoint_url
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if 200 <= resp.status_code < 300:
            return {"ok": True, "http_status": resp.status_code, "response": resp.text[:500]}
        return {"ok": False, "http_status": resp.status_code, "error": resp.text[:500]}
    except requests.exceptions.RequestException as exc:
        return {"ok": False, "error": str(exc)}


def _record_log(
    integration: SiemIntegration,
    event_type: str,
    event_id: str | None,
    result: dict[str, Any],
) -> None:
    """Persist a delivery attempt record."""
    try:
        status = "delivered" if result.get("ok") else "failed"
        create_siem_export_log(
            workspace_id=integration.workspace_id,
            integration_id=integration.id,
            event_type=event_type,
            event_id=event_id,
            status=status,
            http_status=result.get("http_status"),
            response_text=result.get("error") or result.get("response"),
        )
    except Exception as exc:  # pragma: no cover
        logger.exception("Failed to record SIEM export log: %s", exc)


def forward_audit_log_event(workspace_id: str, action: str, metadata: dict[str, Any]) -> None:
    """Convenience hook called after an audit log entry is created."""
    exporter = SiemExporter(workspace_id)
    exporter.export_event(
        "audit",
        {"action": action, "metadata": metadata},
    )


def forward_anomaly_event(workspace_id: str, anomaly_id: str, anomaly_data: dict[str, Any]) -> None:
    """Convenience hook called when a new anomaly is detected."""
    exporter = SiemExporter(workspace_id)
    exporter.export_event(
        "anomaly",
        anomaly_data,
        event_id=anomaly_id,
    )


def forward_incident_event(workspace_id: str, incident_id: str, incident_data: dict[str, Any]) -> None:
    """Convenience hook called when a new incident is created."""
    exporter = SiemExporter(workspace_id)
    exporter.export_event(
        "incident",
        incident_data,
        event_id=incident_id,
    )


def forward_dlp_event(workspace_id: str, event_id: str | None, dlp_data: dict[str, Any]) -> None:
    """Convenience hook called when a DLP guardrail blocks or flags content."""
    exporter = SiemExporter(workspace_id)
    exporter.export_event(
        "dlp",
        dlp_data,
        event_id=event_id,
    )


def list_supported_providers() -> list[dict[str, str]]:
    """Return the list of supported SIEM providers and their documentation."""
    return [
        {
            "id": "splunk",
            "name": "Splunk HEC",
            "docs": "https://docs.splunk.com/Documentation/Splunk/latest/Data/HECExamples",
        },
        {
            "id": "datadog",
            "name": "Datadog Logs",
            "docs": "https://docs.datadoghq.com/api/latest/logs/",
        },
        {
            "id": "elastic",
            "name": "Elastic (Elasticsearch)",
            "docs": "https://www.elastic.co/guide/en/elasticsearch/reference/current/docs-index_.html",
        },
        {
            "id": "qradar",
            "name": "IBM QRadar",
            "docs": "https://www.ibm.com/docs/en/qradar-on-cloud",
        },
        {
            "id": "sentinel",
            "name": "Microsoft Sentinel",
            "docs": "https://learn.microsoft.com/azure/sentinel/",
        },
        {
            "id": "webhook",
            "name": "Generic Webhook",
            "docs": "",
        },
    ]
