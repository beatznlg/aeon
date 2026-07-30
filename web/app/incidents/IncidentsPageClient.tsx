"use client";

import { useEffect, useState } from "react";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Select from "@/components/ui/Select";
import Badge from "@/components/ui/Badge";
import Tabs from "@/components/ui/Tabs";
import PageHeader from "@/components/ui/PageHeader";
import LoadingState from "@/components/ui/LoadingState";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import { getAuthHeaders } from "@/lib/flask-auth";

type Incident = {
  id: string;
  title: string;
  severity: string;
  status: string;
  root_cause_anomaly_id?: string;
  runbook_id?: string;
  assignee_user_id?: string;
  created_at: string;
  updated_at: string;
};

type Runbook = {
  id: string;
  name: string;
  description?: string;
  triggers: any[];
  actions: any[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

const SEVERITIES = ["info", "warning", "critical"];
const STATUSES = ["open", "acknowledged", "resolved", "closed"];

const severityOptions = [
  { value: "info", label: "Info" },
  { value: "warning", label: "Warning" },
  { value: "critical", label: "Critical" },
];

const statusOptions = STATUSES.map((s) => ({ value: s, label: s }));

export default function IncidentsPageClient() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [runbooks, setRunbooks] = useState<Runbook[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"incidents" | "runbooks">("incidents");

  const [incidentForm, setIncidentForm] = useState({ title: "", severity: "warning", status: "open" });
  const [runbookForm, setRunbookForm] = useState({
    name: "",
    description: "",
    triggers: "",
    actions: "",
  });
  const [editingRunbook, setEditingRunbook] = useState<Runbook | null>(null);

  const fetchAll = async () => {
    try {
      setLoading(true);
      setError(null);
      const [iRes, rRes] = await Promise.all([
        fetch("/api/incidents?limit=100", { cache: "no-store", headers: getAuthHeaders() }),
        fetch("/api/runbooks", { cache: "no-store", headers: getAuthHeaders() }),
      ]);
      const iData = await iRes.json();
      const rData = await rRes.json();
      if (iData.ok) setIncidents(iData.incidents || []);
      if (rData.ok) setRunbooks(rData.runbooks || []);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const createIncident = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch("/api/incidents", {
        method: "POST",
        headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(incidentForm),
      });
      const data = await res.json();
      if (data.ok) {
        setIncidentForm({ title: "", severity: "warning", status: "open" });
        await fetchAll();
      } else {
        setError(data.error || "failed to create incident");
      }
    } catch (e) {
      setError(String(e));
    }
  };

  const updateIncident = async (id: string, status: string) => {
    try {
      const res = await fetch(`/api/incidents/${id}`, {
        method: "PATCH",
        headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      const data = await res.json();
      if (data.ok) {
        setIncidents((prev) => prev.map((i) => (i.id === id ? { ...i, status } : i)));
      } else {
        setError(data.error || "failed to update incident");
      }
    } catch (e) {
      setError(String(e));
    }
  };

  const saveRunbook = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        name: runbookForm.name,
        description: runbookForm.description,
        triggers: JSON.parse(runbookForm.triggers || "[]"),
        actions: JSON.parse(runbookForm.actions || "[]"),
        enabled: true,
      };
      const url = editingRunbook ? `/api/runbooks/${editingRunbook.id}` : "/api/runbooks";
      const method = editingRunbook ? "PATCH" : "POST";
      const res = await fetch(url, {
        method,
        headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.ok) {
        setRunbookForm({ name: "", description: "", triggers: "", actions: "" });
        setEditingRunbook(null);
        await fetchAll();
      } else {
        setError(data.error || "failed to save runbook");
      }
    } catch (e) {
      setError(String(e));
    }
  };

  const deleteRunbook = async (id: string) => {
    if (!confirm("Delete this runbook?")) return;
    try {
      const res = await fetch(`/api/runbooks/${id}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (data.ok) {
        await fetchAll();
      } else {
        setError(data.error || "failed to delete runbook");
      }
    } catch (e) {
      setError(String(e));
    }
  };

  const startEditRunbook = (rb: Runbook) => {
    setEditingRunbook(rb);
    setRunbookForm({
      name: rb.name,
      description: rb.description || "",
      triggers: JSON.stringify(rb.triggers || [], null, 2),
      actions: JSON.stringify(rb.actions || [], null, 2),
    });
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

  const statusVariant = (status: string) => {
    switch (status) {
      case "open":
        return "danger";
      case "resolved":
        return "success";
      case "acknowledged":
        return "warning";
      default:
        return "neutral";
    }
  };

  return (
    <div className="aeon-page">
      <PageHeader
        title="Incidents"
        subtitle="Incident triage and automated response runbooks"
        backHref="/os"
      />

      {error && (
        <div className="mb-6">
          <ErrorState error={error} onRetry={fetchAll} />
        </div>
      )}

      <Tabs
        tabs={[
          { id: "incidents", label: "Incidents" },
          { id: "runbooks", label: "Runbooks" },
        ]}
        active={activeTab}
        onChange={(id) => setActiveTab(id as "incidents" | "runbooks")}
        className="mb-6"
      />

      {activeTab === "incidents" && (
        <>
          <Card title="Create incident">
            <form onSubmit={createIncident} className="flex flex-wrap items-end gap-3">
              <div className="min-w-[200px] flex-1">
                <Input
                  label="Title"
                  value={incidentForm.title}
                  onChange={(e) => setIncidentForm({ ...incidentForm, title: e.target.value })}
                  required
                />
              </div>
              <div className="w-40">
                <Select
                  label="Severity"
                  options={severityOptions}
                  value={incidentForm.severity}
                  onChange={(e) => setIncidentForm({ ...incidentForm, severity: e.target.value })}
                />
              </div>
              <div className="w-40">
                <Select
                  label="Status"
                  options={statusOptions}
                  value={incidentForm.status}
                  onChange={(e) => setIncidentForm({ ...incidentForm, status: e.target.value })}
                />
              </div>
              <Button type="submit">Create</Button>
            </form>
          </Card>

          <Card title="Active incidents" className="mt-6">
            {loading ? (
              <LoadingState />
            ) : incidents.length === 0 ? (
              <EmptyState title="No incidents yet" description="Create an incident or trigger one from an anomaly." />
            ) : (
              <div className="flex flex-col gap-3">
                {incidents.map((i) => (
                  <div
                    key={i.id}
                    className="flex flex-col gap-3 rounded-aeon-sm border border-aeon-border bg-aeon-bg p-4"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <div className="text-base font-semibold text-aeon-fg">{i.title}</div>
                        <div className="mt-1 text-xs text-aeon-fg-mute">
                          {new Date(i.created_at).toLocaleString()} · updated{" "}
                          {new Date(i.updated_at).toLocaleString()}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant={severityVariant(i.severity)}>{i.severity}</Badge>
                        <Badge variant={statusVariant(i.status)}>{i.status}</Badge>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-aeon-fg-mute">Status:</span>
                      <Select
                        label=""
                        options={statusOptions}
                        value={i.status}
                        onChange={(e) => updateIncident(i.id, e.target.value)}
                        className="w-40"
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </>
      )}

      {activeTab === "runbooks" && (
        <>
          <Card title={editingRunbook ? "Edit runbook" : "Create runbook"}>
            <form onSubmit={saveRunbook} className="flex flex-col gap-4">
              <Input
                placeholder="Name"
                value={runbookForm.name}
                onChange={(e) => setRunbookForm({ ...runbookForm, name: e.target.value })}
                required
              />
              <Input
                placeholder="Description"
                value={runbookForm.description}
                onChange={(e) => setRunbookForm({ ...runbookForm, description: e.target.value })}
              />
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <textarea
                  className="aeon-input min-h-[120px] font-mono text-xs"
                  placeholder='Triggers (JSON array) e.g. [{"anomaly_type":"*","severity":"critical"}]'
                  value={runbookForm.triggers}
                  onChange={(e) => setRunbookForm({ ...runbookForm, triggers: e.target.value })}
                  rows={4}
                />
                <textarea
                  className="aeon-input min-h-[120px] font-mono text-xs"
                  placeholder='Actions (JSON array) e.g. [{"type":"notify","target":"admins"}]'
                  value={runbookForm.actions}
                  onChange={(e) => setRunbookForm({ ...runbookForm, actions: e.target.value })}
                  rows={4}
                />
              </div>
              <div className="flex gap-3">
                <Button type="submit" variant="primary">
                  {editingRunbook ? "Save changes" : "Create runbook"}
                </Button>
                {editingRunbook && (
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setEditingRunbook(null);
                      setRunbookForm({ name: "", description: "", triggers: "", actions: "" });
                    }}
                  >
                    Cancel
                  </Button>
                )}
              </div>
            </form>
          </Card>

          <Card title="Runbooks" className="mt-6">
            {runbooks.length === 0 ? (
              <EmptyState title="No runbooks yet" description="Create a runbook to automate incident response." />
            ) : (
              <div className="flex flex-col gap-3">
                {runbooks.map((rb) => (
                  <div
                    key={rb.id}
                    className="flex flex-col gap-2 rounded-aeon-sm border border-aeon-border bg-aeon-bg p-4"
                  >
                    <div className="text-base font-semibold text-aeon-fg">{rb.name}</div>
                    <div className="text-xs text-aeon-fg-mute">
                      {rb.description || "No description"} · {rb.triggers?.length || 0} triggers ·{" "}
                      {rb.actions?.length || 0} actions
                    </div>
                    <div className="flex gap-2">
                      <Button size="sm" onClick={() => startEditRunbook(rb)}>
                        Edit
                      </Button>
                      <Button size="sm" variant="danger" onClick={() => deleteRunbook(rb.id)}>
                        Delete
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
