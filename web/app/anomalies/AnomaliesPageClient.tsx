"use client";

import { useEffect, useState, useCallback } from "react";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Select from "@/components/ui/Select";
import Badge from "@/components/ui/Badge";
import PageHeader from "@/components/ui/PageHeader";
import LoadingState from "@/components/ui/LoadingState";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import { getAuthHeaders } from "@/lib/flask-auth";

type Anomaly = {
  id: string;
  anomaly_type: string;
  severity: string;
  title: string;
  description?: string;
  score?: number;
  source_rule_id?: string;
  source_metric?: string;
  metadata?: Record<string, any>;
  dismissed: boolean;
  created_at: string;
};

const severityOptions = [
  { value: "", label: "All severities" },
  { value: "critical", label: "Critical" },
  { value: "warning", label: "Warning" },
  { value: "info", label: "Info" },
];

export default function AnomaliesPageClient() {
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [severityFilter, setSeverityFilter] = useState<string>("");

  const fetchAnomalies = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const url = new URL("/api/anomalies", window.location.origin);
      url.searchParams.set("limit", "100");
      if (severityFilter) url.searchParams.set("severity", severityFilter);
      const res = await fetch(url.toString(), {
        cache: "no-store",
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (data.ok) setAnomalies(data.anomalies || []);
      else setError(data.error || "failed to load anomalies");
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [severityFilter]);

  useEffect(() => {
    fetchAnomalies();
  }, [fetchAnomalies]);

  const runDetection = async () => {
    try {
      setDetecting(true);
      setError(null);
      const res = await fetch("/api/anomalies/detect", {
        method: "POST",
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (data.ok) {
        await fetchAnomalies();
      } else {
        setError(data.error || "detection failed");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setDetecting(false);
    }
  };

  const dismiss = async (id: string) => {
    if (!confirm("Dismiss this anomaly as a false positive?")) return;
    try {
      const res = await fetch(`/api/anomalies/${id}/dismiss`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (data.ok) {
        setAnomalies((prev) => prev.map((a) => (a.id === id ? { ...a, dismissed: true } : a)));
      } else {
        setError(data.error || "dismiss failed");
      }
    } catch (e) {
      setError(String(e));
    }
  };

  const severityVariant = (severity: string) => {
    switch (severity) {
      case "critical":
        return "danger";
      case "warning":
        return "warning";
      default:
        return "info";
    }
  };

  return (
    <div className="aeon-page">
      <PageHeader
        title="Anomalies"
        subtitle="AI-powered anomaly detection and triage"
        backHref="/os"
        actions={
          <Button onClick={runDetection} loading={detecting}>
            Run Detection
          </Button>
        }
      />

      {error && (
        <div className="mb-6">
          <ErrorState error={error} onRetry={fetchAnomalies} />
        </div>
      )}

      <Card
        title="Detected anomalies"
        action={
          <div className="w-44">
            <Select
              label=""
              options={severityOptions}
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
            />
          </div>
        }
      >
        {loading ? (
          <LoadingState message="Scanning for anomalies…" />
        ) : anomalies.length === 0 ? (
          <EmptyState
            title="No anomalies detected"
            description="Run detection to scan for outliers in your data."
          />
        ) : (
          <div className="flex flex-col gap-3">
            {anomalies.map((a) => (
              <div
                key={a.id}
                className={`flex flex-col gap-3 rounded-aeon-sm border border-aeon-border bg-aeon-bg p-4 transition-opacity ${
                  a.dismissed ? "opacity-60" : ""
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-base font-semibold text-aeon-fg">{a.title}</div>
                    <div className="mt-1 text-xs text-aeon-fg-mute">
                      {a.anomaly_type} · score {a.score ?? "n/a"} ·{" "}
                      {new Date(a.created_at).toLocaleString()}
                    </div>
                    {a.description && (
                      <p className="mt-2 text-sm text-aeon-fg-soft">{a.description}</p>
                    )}
                  </div>
                  <Badge variant={severityVariant(a.severity)}>{a.severity}</Badge>
                </div>
                <div className="flex items-center gap-2">
                  {!a.dismissed ? (
                    <Button variant="secondary" size="sm" onClick={() => dismiss(a.id)}>
                      Dismiss
                    </Button>
                  ) : (
                    <span className="text-xs text-aeon-fg-mute">Dismissed</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
