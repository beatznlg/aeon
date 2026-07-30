"""
AEON OS Phase 46 — AI-powered Anomaly Detection
================================================
Lightweight, dependency-free anomaly detection for automation executions,
chat metrics, and audit streams.

The ``AnomalyDetector`` class uses statistical detectors (z-score, IQR,
rolling mean) plus an optional LLM summary hook. Detected anomalies are
persisted to the local database and fed to the incident-response layer.
"""

import logging
import math
import threading
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from aeon_db import add_audit_log, create_anomaly, get_db, list_automation_executions

logger = logging.getLogger("aeon_anomalies")

# Severity thresholds
_SEVERITY_WARNING = "warning"
_SEVERITY_CRITICAL = "critical"


# === Statistics helpers (stdlib only) ========================================

def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = _mean(values)
    variance = sum((x - m) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance)


def _zscore(value: float, mean: float, stdev: float) -> float:
    if stdev == 0:
        return 0.0
    return (value - mean) / stdev


def _iqr_bounds(values: list[float]) -> tuple[float, float]:
    """Return lower and upper bounds using the IQR rule."""
    if len(values) < 4:
        return (0.0, float("inf"))
    sorted_values = sorted(values)
    n = len(sorted_values)
    q1 = sorted_values[n // 4] if n % 4 == 0 else sorted_values[n // 4]
    q3_idx = 3 * n // 4
    q3 = sorted_values[q3_idx] if q3_idx < n else sorted_values[-1]
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return lower, upper


# === Anomaly detector =========================================================

class AnomalyDetector:
    """Detect anomalies in automation, chat, and audit data for a workspace."""

    def __init__(self, workspace_id: str):
        self.workspace_id = str(workspace_id)

    # --- public API ----------------------------------------------------------

    def detect(self) -> list[dict[str, Any]]:
        """Run all detectors and return/persist the anomalies found."""
        anomalies: list[dict[str, Any]] = []
        anomalies.extend(self.detect_automation_anomalies())
        anomalies.extend(self.detect_audit_volume_anomaly())

        persisted: list[dict[str, Any]] = []
        for anomaly in anomalies:
            try:
                record = create_anomaly(
                    workspace_id=self.workspace_id,
                    anomaly_type=anomaly["anomaly_type"],
                    severity=anomaly["severity"],
                    title=anomaly["title"],
                    description=anomaly.get("description"),
                    score=float(anomaly.get("score", 0.0)),
                    source_rule_id=anomaly.get("source_rule_id"),
                    source_metric=anomaly.get("source_metric"),
                    metadata=anomaly.get("metadata", {}),
                )
                anomaly["id"] = record.id
                anomaly["created_at"] = record.created_at.isoformat() if record.created_at else None
                persisted.append(anomaly)

                # Forward to SIEM integrations (best-effort).
                try:
                    from aeon_siem import forward_anomaly_event
                    forward_anomaly_event(self.workspace_id, str(record.id), anomaly)
                except Exception:
                    pass

                # Trigger incident-response runbooks for non-info anomalies.
                if anomaly["severity"] in (_SEVERITY_WARNING, _SEVERITY_CRITICAL):
                    from aeon_incidents import handle_anomaly

                    try:
                        handle_anomaly(record)
                    except Exception as exc:  # pragma: no cover - must not break detection
                        logger.warning("Incident handling failed for anomaly %s: %s", record.id, exc)
            except Exception as exc:
                logger.warning("Failed to persist anomaly: %s", exc)

        # Emit an audit event for the detection run.
        try:
            add_audit_log(
                action="ANOMALY_DETECTION_RUN",
                module="anomalies",
                user_id=None,
                workspace_id=self.workspace_id,
                email=None,
                metadata={"anomalies_found": len(persisted)},
            )
        except Exception:
            pass

        return persisted

    def detect_automation_anomalies(self) -> list[dict[str, Any]]:
        """Detect spikes in automation failure rate per rule and workspace-wide."""
        anomalies: list[dict[str, Any]] = []
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        executions = list_automation_executions(self.workspace_id, since=since)
        if len(executions) < 5:
            return anomalies

        # Per-rule failure rates in the last hour.
        rule_failures: dict[str, list[int]] = defaultdict(list)
        for execution in executions:
            rule_id = execution.get("rule_id") or "unknown"
            status = execution.get("status") or ""
            failed = 1.0 if str(status).lower() in {"failed", "error", "throttled"} else 0.0
            rule_failures[rule_id].append(failed)

        for rule_id, failures in rule_failures.items():
            if len(failures) < 5:
                continue
            rate = sum(failures) / len(failures)
            # Spike: failure rate exceeds 50 % and there are at least 5 runs.
            if rate >= 0.5:
                score = min(rate * 100.0, 100.0)
                severity = _SEVERITY_CRITICAL if rate >= 0.8 else _SEVERITY_WARNING
                anomalies.append({
                    "anomaly_type": "automation_failure_spike",
                    "severity": severity,
                    "title": f"Automation failure rate spike for rule {rule_id}",
                    "description": (
                        f"Rule '{rule_id}' failed {rate:.0%} of its executions "
                        f"in the last 24 hours ({sum(failures)} failures out of {len(failures)} runs)."
                    ),
                    "score": score,
                    "source_rule_id": rule_id,
                    "source_metric": "failure_rate",
                    "metadata": {
                        "rule_id": rule_id,
                        "failure_rate": rate,
                        "runs": len(failures),
                        "failures": sum(failures),
                    },
                })

        # Workspace-wide execution count drop/spike using z-score over hourly buckets.
        hourly_counts: dict[str, int] = defaultdict(int)
        for execution in executions:
            created = execution.get("created_at")
            if not created:
                continue
            try:
                if isinstance(created, str):
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                else:
                    created_dt = created
                bucket = created_dt.replace(minute=0, second=0, microsecond=0).isoformat()
                hourly_counts[bucket] += 1
            except Exception:
                continue

        counts = list(hourly_counts.values())
        mean_count = _mean(counts)
        stdev_count = _stdev(counts)
        z_score_anomalies: list[dict[str, Any]] = []
        if len(hourly_counts) >= 3:
            for bucket, count in hourly_counts.items():
                z = _zscore(count, mean_count, stdev_count)
                if abs(z) >= 2.0:
                    z_score_anomalies.append({
                        "anomaly_type": "automation_volume_spike" if z > 0 else "automation_volume_drop",
                        "severity": _SEVERITY_WARNING,
                        "title": "Automation execution volume anomaly",
                        "description": (
                            f"Execution count in hour {bucket} ({count}) deviates "
                            f"{z:.2f} standard deviations from the 24-hour mean."
                        ),
                        "score": min(abs(z) * 25.0, 100.0),
                        "source_metric": "execution_count",
                        "metadata": {"hour": bucket, "count": count, "z_score": z},
                    })
        anomalies.extend(z_score_anomalies)

        # Threshold-based fallback catches high absolute spikes that do not yet
        # exceed the z-score threshold (e.g., only a few hourly buckets exist).
        if not z_score_anomalies:
            for bucket, count in hourly_counts.items():
                if mean_count > 0 and count >= max(20, mean_count * 3.0):
                    anomalies.append({
                        "anomaly_type": "automation_volume_spike",
                        "severity": _SEVERITY_WARNING,
                        "title": "Automation execution volume spike",
                        "description": (
                            f"Execution count in hour {bucket} ({count}) is more than "
                            f"3x the mean ({mean_count:.1f}) for the period."
                        ),
                        "score": min((count / max(mean_count, 1.0)) * 25.0, 100.0),
                        "source_metric": "execution_count",
                        "metadata": {"hour": bucket, "count": count, "mean": mean_count},
                    })

        return anomalies

    def detect_audit_volume_anomaly(self) -> list[dict[str, Any]]:
        """Detect unusual spikes in audit log volume for the workspace."""
        try:
            from aeon_db import AuditLog

            since = datetime.now(timezone.utc) - timedelta(hours=24)
            db = get_db()
            with db.session() as s:
                rows = (
                    s.query(AuditLog)
                    .filter(AuditLog.workspace_id == self.workspace_id)
                    .filter(AuditLog.timestamp >= since)
                    .all()
                )
            if len(rows) < 10:
                return []

            hourly: dict[str, int] = defaultdict(int)
            for row in rows:
                ts = row.timestamp
                if not ts:
                    continue
                bucket = ts.replace(minute=0, second=0, microsecond=0).isoformat()
                hourly[bucket] += 1

            if len(hourly) < 3:
                return []

            counts = list(hourly.values())
            mean_count = _mean(counts)
            stdev_count = _stdev(counts)
            anomalies: list[dict[str, Any]] = []
            for bucket, count in hourly.items():
                z = _zscore(count, mean_count, stdev_count)
                if z >= 2.5:
                    anomalies.append({
                        "anomaly_type": "audit_volume_spike",
                        "severity": _SEVERITY_WARNING,
                        "title": "Audit log volume spike",
                        "description": (
                            f"Audit log count in hour {bucket} ({count}) is {z:.2f} "
                            f"standard deviations above the 24-hour mean."
                        ),
                        "score": min(abs(z) * 25.0, 100.0),
                        "source_metric": "audit_log_count",
                        "metadata": {"hour": bucket, "count": count, "z_score": z},
                    })
            # Also detect threshold-based spikes when z-score is not yet high enough.
            if not anomalies:
                for bucket, count in hourly.items():
                    if mean_count > 0 and count >= max(30, mean_count * 3.0):
                        anomalies.append({
                            "anomaly_type": "audit_volume_spike",
                            "severity": _SEVERITY_WARNING,
                            "title": "Audit log volume spike",
                            "description": (
                                f"Audit log count in hour {bucket} ({count}) is more than "
                                f"3x the mean ({mean_count:.1f}) for the period."
                            ),
                            "score": min((count / max(mean_count, 1.0)) * 25.0, 100.0),
                            "source_metric": "audit_log_count",
                            "metadata": {"hour": bucket, "count": count, "mean": mean_count},
                        })
            return anomalies
        except Exception as exc:
            logger.debug("Audit volume anomaly detection skipped: %s", exc)
            return []

    def summarize_with_llm(self, anomalies: list[dict[str, Any]]) -> str:
        """Return a short LLM-generated summary of the given anomalies."""
        if not anomalies:
            return "No anomalies detected."
        try:
            from aeon_llm import get_llm_provider

            provider = get_llm_provider()
            if not provider:
                raise ImportError
            summary = []
            for a in anomalies:
                summary.append(f"- {a.get('title')} ({a.get('severity')}): {a.get('description')}")
            prompt = (
                "Summarize the following workspace anomalies in one concise sentence, "
                "then list the top action item:\n" + "\n".join(summary)
            )
            response = provider.generate(prompt)
            if response and response.get("text"):
                return str(response["text"])
        except Exception as exc:
            logger.debug("LLM anomaly summary unavailable: %s", exc)

        # Fallback deterministic summary.
        return "Anomalies detected: " + ", ".join(a.get("title", "unknown") for a in anomalies)


def trigger_detection(workspace_id: str) -> list[dict[str, Any]]:
    """Run anomaly detection for a workspace and return detected anomalies."""
    return AnomalyDetector(workspace_id).detect()


def background_detect(workspace_id: str | None) -> None:
    """Run anomaly detection in the background (non-blocking)."""
    if not workspace_id:
        return
    thread = threading.Thread(target=trigger_detection, args=(str(workspace_id),), daemon=True)
    thread.start()
