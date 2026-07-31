"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSession } from "next-auth/react";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Select from "@/components/ui/Select";
import Badge from "@/components/ui/Badge";
import PageHeader from "@/components/ui/PageHeader";
import LoadingState from "@/components/ui/LoadingState";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import { getAuthHeaders } from "@/lib/flask-auth";

type Provider = { id: string; name: string; docs: string };
type Integration = {
  id: string;
  provider: string;
  name: string;
  endpoint_url: string;
  auth_type: string;
  custom_headers: Record<string, string>;
  event_filters: string[];
  log_level: string;
  batch_size: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};
type ExportLog = {
  id: string;
  event_type: string;
  status: string;
  http_status?: number;
  response_text?: string;
  created_at: string;
};

const EVENT_TYPES = ["audit", "anomaly", "incident", "dlp"];
const LOG_LEVELS = ["all", "warning", "critical"];
const AUTH_TYPES = ["token", "basic", "custom"];

export default function SiemPage() {
  const { data: session } = useSession();
  const workspaceId = ((session?.user as any)?.workspaceId as string) || "default";

  const [providers, setProviders] = useState<Provider[]>([]);
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [logs, setLogs] = useState<ExportLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Integration | null>(null);
  const [testing, setTesting] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  const emptyForm: Omit<Integration, "id" | "created_at" | "updated_at"> = {
    provider: "webhook",
    name: "",
    endpoint_url: "",
    auth_type: "token",
    custom_headers: {},
    event_filters: ["audit", "anomaly", "incident", "dlp"],
    log_level: "all",
    batch_size: 100,
    enabled: true,
  };
  const [form, setForm] = useState(emptyForm);

  const fetchAll = async () => {
    try {
      setLoading(true);
      setError(null);
      const [pRes, iRes, lRes] = await Promise.all([
        fetch("/api/siem/providers", { cache: "no-store", headers: getAuthHeaders() }),
        fetch("/api/siem/integrations", { cache: "no-store", headers: getAuthHeaders() }),
        fetch("/api/siem/export-logs?limit=50", { cache: "no-store", headers: getAuthHeaders() }),
      ]);
      const pData = await pRes.json();
      const iData = await iRes.json();
      const lData = await lRes.json();
      if (pData.ok) setProviders(pData.providers || []);
      if (iData.ok) setIntegrations(iData.integrations || []);
      if (lData.ok) setLogs(lData.logs || []);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const providerOptions = useMemo(() => {
    return providers.length
      ? providers.map((p) => ({ value: p.id, label: p.name }))
      : [
          { value: "splunk", label: "Splunk HEC" },
          { value: "datadog", label: "Datadog Logs" },
          { value: "elastic", label: "Elastic" },
          { value: "qradar", label: "IBM QRadar" },
          { value: "sentinel", label: "Microsoft Sentinel" },
          { value: "webhook", label: "Generic Webhook" },
        ];
  }, [providers]);

  const logLevelOptions = LOG_LEVELS.map((l) => ({ value: l, label: l }));
  const authOptions = AUTH_TYPES.map((a) => ({ value: a, label: a }));

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const url = editing ? `/api/siem/integrations/${editing.id}` : "/api/siem/integrations";
    const method = editing ? "PATCH" : "POST";
    try {
      const res = await fetch(url, {
        method,
        headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "save failed");
      setFormOpen(false);
      setEditing(null);
      setForm(emptyForm);
      await fetchAll();
    } catch (e) {
      setError(String(e));
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this SIEM integration?")) return;
    try {
      const res = await fetch(`/api/siem/integrations/${id}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "delete failed");
      await fetchAll();
    } catch (e) {
      setError(String(e));
    }
  };

  const handleTest = async (id: string) => {
    setTesting(id);
    setTestResult(null);
    try {
      const res = await fetch(`/api/siem/integrations/${id}/test`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      setTestResult({ ok: !!data.ok, message: data.error || "Test event delivered" });
    } catch (e) {
      setTestResult({ ok: false, message: String(e) });
    } finally {
      setTesting(null);
    }
  };

  const startEdit = (i: Integration) => {
    setEditing(i);
    setForm({
      provider: i.provider,
      name: i.name,
      endpoint_url: i.endpoint_url,
      auth_type: i.auth_type,
      custom_headers: i.custom_headers || {},
      event_filters: i.event_filters || [],
      log_level: i.log_level,
      batch_size: i.batch_size,
      enabled: i.enabled,
    });
    setFormOpen(true);
  };

  const startCreate = () => {
    setEditing(null);
    setForm(emptyForm);
    setFormOpen(true);
  };

  const toggleEvent = (event: string) => {
    setForm((f) => {
      const filters = f.event_filters.includes(event)
        ? f.event_filters.filter((e) => e !== event)
        : [...f.event_filters, event];
      return { ...f, event_filters: filters };
    });
  };

  return (
    <div className="aeon-page">
      <PageHeader
        title="SIEM Integrations"
        subtitle="Stream AEON audit, anomaly, incident, and DLP events to your enterprise SIEM"
        backHref="/os"
        actions={
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-aeon-fg-mute md:inline">
              Workspace: <code>{workspaceId}</code>
            </span>
            <Button onClick={startCreate}>+ Add destination</Button>
          </div>
        }
      />

      {error && (
        <div className="mb-6">
          <ErrorState error={error} onRetry={fetchAll} />
        </div>
      )}
      {testResult && (
        <div
          className={`mb-6 rounded-aeon border p-4 text-sm ${
            testResult.ok
              ? "border-aeon-success/30 bg-aeon-success-soft text-aeon-success"
              : "border-aeon-danger/30 bg-aeon-danger-soft text-aeon-danger"
          }`}
        >
          {testResult.ok ? "✅" : "❌"} {testResult.message}
        </div>
      )}

      {formOpen && (
        <Card title={editing ? "Edit SIEM integration" : "New SIEM integration"} className="mb-6">
          <form onSubmit={handleSave} className="flex flex-col gap-5">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
              <Input
                label="Name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                required
              />
              <Select
                label="Provider"
                options={providerOptions}
                value={form.provider}
                onChange={(e) => setForm({ ...form, provider: e.target.value })}
              />
              <Input
                label="Endpoint URL"
                value={form.endpoint_url}
                onChange={(e) => setForm({ ...form, endpoint_url: e.target.value })}
                required
              />
              <Select
                label="Log level"
                options={logLevelOptions}
                value={form.log_level}
                onChange={(e) => setForm({ ...form, log_level: e.target.value })}
              />
              <Input
                label="Batch size"
                type="number"
                min={1}
                max={1000}
                value={form.batch_size}
                onChange={(e) => setForm({ ...form, batch_size: Number(e.target.value) })}
              />
              <Select
                label="Auth type"
                options={authOptions}
                value={form.auth_type}
                onChange={(e) => setForm({ ...form, auth_type: e.target.value })}
              />
            </div>

            <div>
              <label className="aeon-label">Event filters</label>
              <div className="flex flex-wrap gap-4">
                {EVENT_TYPES.map((event) => (
                  <label
                    key={event}
                    className="flex cursor-pointer items-center gap-2 text-sm text-aeon-fg-soft"
                  >
                    <input
                      type="checkbox"
                      checked={form.event_filters.includes(event)}
                      onChange={() => toggleEvent(event)}
                      className="h-4 w-4 rounded border-aeon-border bg-aeon-bg text-aeon-primary focus:ring-aeon-primary"
                    />
                    <span className="capitalize">{event}</span>
                  </label>
                ))}
              </div>
            </div>

            <label className="flex cursor-pointer items-center gap-2 text-sm text-aeon-fg-soft">
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                className="h-4 w-4 rounded border-aeon-border bg-aeon-bg text-aeon-primary focus:ring-aeon-primary"
              />
              Enabled
            </label>

            <div className="flex gap-3">
              <Button type="submit" variant="primary">
                {editing ? "Save changes" : "Create integration"}
              </Button>
              <Button variant="secondary" onClick={() => setFormOpen(false)}>
                Cancel
              </Button>
            </div>
          </form>
        </Card>
      )}

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card
          title="Configured destinations"
          action={
            !formOpen && (
              <Button size="sm" onClick={startCreate}>
                + Add
              </Button>
            )
          }
        >
          {loading ? (
            <LoadingState />
          ) : integrations.length === 0 ? (
            <EmptyState
              title="No SIEM integrations yet"
              description="Add a destination to start forwarding events."
            />
          ) : (
            <div className="flex flex-col gap-3">
              {integrations.map((i) => (
                <div
                  key={i.id}
                  className="rounded-aeon-sm border border-aeon-border bg-aeon-bg p-4"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="text-base font-semibold text-aeon-fg">{i.name}</div>
                      <div className="mt-1 text-xs capitalize text-aeon-fg-mute">
                        {i.provider} · {i.event_filters.join(", ")}
                      </div>
                      <div className="mt-1 break-all text-xs text-aeon-fg-mute">
                        {i.endpoint_url}
                      </div>
                    </div>
                    <Badge variant={i.enabled ? "success" : "neutral"}>
                      {i.enabled ? "enabled" : "disabled"}
                    </Badge>
                  </div>
                  <div className="mt-3 flex gap-2">
                    <Button size="sm" onClick={() => handleTest(i.id)} loading={testing === i.id}>
                      Test
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => startEdit(i)}>
                      Edit
                    </Button>
                    <Button size="sm" variant="danger" onClick={() => handleDelete(i.id)}>
                      Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Recent export logs">
          {logs.length === 0 ? (
            <EmptyState title="No export attempts yet" />
          ) : (
            <div className="flex max-h-[500px] flex-col gap-2 overflow-auto pr-1">
              {logs.map((log) => (
                <div
                  key={log.id}
                  className="flex items-center justify-between rounded-aeon-sm border border-aeon-border bg-aeon-bg p-3"
                >
                  <div>
                    <div className="text-sm font-semibold uppercase text-aeon-fg-soft">
                      {log.event_type}
                    </div>
                    <div className="text-xs text-aeon-fg-mute">
                      {new Date(log.created_at).toLocaleString()}
                    </div>
                    {log.response_text && (
                      <div className="mt-1 text-xs text-aeon-fg-mute">{log.response_text}</div>
                    )}
                  </div>
                  <Badge variant={log.status === "delivered" ? "success" : "danger"}>
                    {log.status} {log.http_status ? `· ${log.http_status}` : ""}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </Card>
      </section>
    </div>
  );
}
