"use client";

import { useEffect, useState } from "react";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import Badge from "@/components/ui/Badge";
import PageHeader from "@/components/ui/PageHeader";
import LoadingState from "@/components/ui/LoadingState";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import { getAuthHeaders } from "@/lib/flask-auth";

type BackupPolicy = {
  id: string;
  name: string;
  schedule: string;
  retention_days: number;
  target: string;
  encryption_enabled: boolean;
  enabled: boolean;
  last_run_at?: string;
  next_run_at?: string;
};

type BackupJob = {
  id: string;
  policy_id?: string;
  status: string;
  started_at?: string;
  completed_at?: string;
  size_bytes?: number;
  error_message?: string;
  created_at: string;
};

type RestoreJob = {
  id: string;
  backup_job_id: string;
  status: string;
  created_at: string;
};

type DRPlan = {
  id: string;
  name: string;
  rto_minutes: number;
  rpo_minutes: number;
  target_region: string;
  enabled: boolean;
  last_drill_at?: string;
};

type DRDrill = {
  id: string;
  plan_id: string;
  status: string;
  score?: number;
  created_at: string;
};

export default function DRPageClient() {
  const [policies, setPolicies] = useState<BackupPolicy[]>([]);
  const [jobs, setJobs] = useState<BackupJob[]>([]);
  const [restores, setRestores] = useState<RestoreJob[]>([]);
  const [plans, setPlans] = useState<DRPlan[]>([]);
  const [drills, setDrills] = useState<DRDrill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [policyForm, setPolicyForm] = useState({
    name: "",
    schedule: "0 2 * * *",
    retention_days: 30,
    target: "local",
    encryption_enabled: true,
    enabled: true,
  });

  const [planForm, setPlanForm] = useState({
    name: "",
    rto_minutes: 60,
    rpo_minutes: 60,
    target_region: "primary",
    failover_regions: "",
    enabled: true,
  });

  const fetchAll = async () => {
    try {
      setLoading(true);
      setError(null);
      const [pRes, jRes, rRes, plRes, dRes] = await Promise.all(
        [
          fetch("/api/dr/policies", { cache: "no-store", headers: getAuthHeaders() }),
          fetch("/api/dr/backups?limit=50", { cache: "no-store", headers: getAuthHeaders() }),
          fetch("/api/dr/restores?limit=50", { cache: "no-store", headers: getAuthHeaders() }),
          fetch("/api/dr/plans", { cache: "no-store", headers: getAuthHeaders() }),
          fetch("/api/dr/drills?limit=50", { cache: "no-store", headers: getAuthHeaders() }),
        ].map((p) => p)
      );
      const pData = await pRes.json();
      const jData = await jRes.json();
      const rData = await rRes.json();
      const plData = await plRes.json();
      const dData = await dRes.json();
      if (pData.ok) setPolicies(pData.policies || []);
      if (jData.ok) setJobs(jData.jobs || []);
      if (rData.ok) setRestores(rData.restores || []);
      if (plData.ok) setPlans(plData.plans || []);
      if (dData.ok) setDrills(dData.drills || []);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
  }, []);

  const createPolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch("/api/dr/policies", {
        method: "POST",
        headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(policyForm),
      });
      const data = await res.json();
      if (data.ok) {
        setPolicyForm({
          name: "",
          schedule: "0 2 * * *",
          retention_days: 30,
          target: "local",
          encryption_enabled: true,
          enabled: true,
        });
        await fetchAll();
      } else {
        setError(data.error || "failed to create policy");
      }
    } catch (e) {
      setError(String(e));
    }
  };

  const runPolicy = async (id: string) => {
    try {
      const res = await fetch(`/api/dr/policies/${id}/run`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (data.ok) await fetchAll();
      else setError(data.error || "run failed");
    } catch (e) {
      setError(String(e));
    }
  };

  const applyRetention = async (id: string) => {
    try {
      const res = await fetch(`/api/dr/policies/${id}/retention`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (data.ok) await fetchAll();
      else setError(data.error || "retention failed");
    } catch (e) {
      setError(String(e));
    }
  };

  const deletePolicy = async (id: string) => {
    if (!confirm("Delete this backup policy?")) return;
    try {
      const res = await fetch(`/api/dr/policies/${id}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (data.ok) await fetchAll();
      else setError(data.error || "delete failed");
    } catch (e) {
      setError(String(e));
    }
  };

  const restoreBackup = async (id: string) => {
    if (!confirm("Restore this backup?")) return;
    try {
      const res = await fetch(`/api/dr/backups/${id}/restore`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (data.ok) await fetchAll();
      else setError(data.error || "restore failed");
    } catch (e) {
      setError(String(e));
    }
  };

  const createPlan = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        ...planForm,
        failover_regions: planForm.failover_regions
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      };
      const res = await fetch("/api/dr/plans", {
        method: "POST",
        headers: { ...getAuthHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (data.ok) {
        setPlanForm({
          name: "",
          rto_minutes: 60,
          rpo_minutes: 60,
          target_region: "primary",
          failover_regions: "",
          enabled: true,
        });
        await fetchAll();
      } else {
        setError(data.error || "failed to create plan");
      }
    } catch (e) {
      setError(String(e));
    }
  };

  const runDrill = async (id: string) => {
    try {
      const res = await fetch(`/api/dr/plans/${id}/drill`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (data.ok) await fetchAll();
      else setError(data.error || "drill failed");
    } catch (e) {
      setError(String(e));
    }
  };

  const deletePlan = async (id: string) => {
    if (!confirm("Delete this DR plan?")) return;
    try {
      const res = await fetch(`/api/dr/plans/${id}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (data.ok) await fetchAll();
      else setError(data.error || "delete failed");
    } catch (e) {
      setError(String(e));
    }
  };

  const runScheduledBackups = async () => {
    try {
      const res = await fetch("/api/dr/scheduled/run", {
        method: "POST",
        headers: getAuthHeaders(),
      });
      const data = await res.json();
      if (data.ok) await fetchAll();
      else setError(data.error || "scheduled run failed");
    } catch (e) {
      setError(String(e));
    }
  };

  const statusVariant = (status: string) => {
    if (status === "completed" || status === "resolved" || status === "success") return "success";
    if (status === "failed" || status === "error") return "danger";
    return "warning";
  };

  return (
    <div className="aeon-page">
      <PageHeader
        title="Disaster Recovery"
        subtitle="Backup policies, restore jobs, and DR drills"
        backHref="/os"
        actions={
          <Button onClick={runScheduledBackups}>Run Scheduled Backups</Button>
        }
      />

      {error && (
        <div className="mb-6">
          <ErrorState error={error} onRetry={fetchAll} />
        </div>
      )}

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-2 xl:grid-cols-3">
        <Card title="Backup Policies">
          <form onSubmit={createPolicy} className="mb-4 flex flex-col gap-3">
            <Input
              placeholder="Policy name"
              value={policyForm.name}
              onChange={(e) => setPolicyForm({ ...policyForm, name: e.target.value })}
              required
            />
            <div className="grid grid-cols-2 gap-3">
              <Input
                placeholder="Schedule (cron)"
                value={policyForm.schedule}
                onChange={(e) => setPolicyForm({ ...policyForm, schedule: e.target.value })}
              />
              <Input
                type="number"
                placeholder="Retention (days)"
                value={policyForm.retention_days}
                onChange={(e) =>
                  setPolicyForm({ ...policyForm, retention_days: Number(e.target.value) })
                }
              />
            </div>
            <Button type="submit" variant="primary">
              Add Policy
            </Button>
          </form>
          {loading ? (
            <LoadingState />
          ) : policies.length === 0 ? (
            <EmptyState title="No backup policies" />
          ) : (
            <div className="flex max-h-[400px] flex-col gap-2 overflow-auto pr-1">
              {policies.map((p) => (
                <div
                  key={p.id}
                  className="rounded-aeon-sm border border-aeon-border bg-aeon-bg p-3"
                >
                  <div className="font-medium text-aeon-fg">{p.name}</div>
                  <div className="text-xs text-aeon-fg-mute">
                    {p.schedule} · {p.retention_days} days · {p.target}
                  </div>
                  <div className="mt-2 flex gap-2">
                    <Button size="sm" onClick={() => runPolicy(p.id)}>
                      Run
                    </Button>
                    <Button size="sm" variant="secondary" onClick={() => applyRetention(p.id)}>
                      Retention
                    </Button>
                    <Button size="sm" variant="danger" onClick={() => deletePolicy(p.id)}>
                      Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Recent Backup Jobs">
          {jobs.length === 0 ? (
            <EmptyState title="No backup jobs yet" />
          ) : (
            <div className="flex max-h-[400px] flex-col gap-2 overflow-auto pr-1">
              {jobs.map((j) => (
                <div
                  key={j.id}
                  className="rounded-aeon-sm border border-aeon-border bg-aeon-bg p-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs text-aeon-fg-soft">
                      #{j.id.slice(0, 8)}
                    </span>
                    <Badge variant={statusVariant(j.status)}>{j.status}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-aeon-fg-mute">
                    {new Date(j.created_at).toLocaleString()}
                    {j.size_bytes ? ` · ${(j.size_bytes / 1024 / 1024).toFixed(2)} MB` : ""}
                  </div>
                  {j.error_message && (
                    <div className="mt-1 text-xs text-aeon-danger">{j.error_message}</div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="DR Plans">
          <form onSubmit={createPlan} className="mb-4 flex flex-col gap-3">
            <Input
              placeholder="Plan name"
              value={planForm.name}
              onChange={(e) => setPlanForm({ ...planForm, name: e.target.value })}
              required
            />
            <div className="grid grid-cols-2 gap-3">
              <Input
                type="number"
                placeholder="RTO (min)"
                value={planForm.rto_minutes}
                onChange={(e) =>
                  setPlanForm({ ...planForm, rto_minutes: Number(e.target.value) })
                }
              />
              <Input
                type="number"
                placeholder="RPO (min)"
                value={planForm.rpo_minutes}
                onChange={(e) =>
                  setPlanForm({ ...planForm, rpo_minutes: Number(e.target.value) })
                }
              />
            </div>
            <Input
              placeholder="Failover regions (comma-separated)"
              value={planForm.failover_regions}
              onChange={(e) =>
                setPlanForm({ ...planForm, failover_regions: e.target.value })
              }
            />
            <Button type="submit" variant="primary">
              Add Plan
            </Button>
          </form>
          {plans.length === 0 ? (
            <EmptyState title="No DR plans" />
          ) : (
            <div className="flex max-h-[400px] flex-col gap-2 overflow-auto pr-1">
              {plans.map((pl) => (
                <div
                  key={pl.id}
                  className="rounded-aeon-sm border border-aeon-border bg-aeon-bg p-3"
                >
                  <div className="font-medium text-aeon-fg">{pl.name}</div>
                  <div className="text-xs text-aeon-fg-mute">
                    RTO {pl.rto_minutes}m · RPO {pl.rpo_minutes}m · {pl.target_region}
                  </div>
                  <div className="mt-2 flex gap-2">
                    <Button size="sm" onClick={() => runDrill(pl.id)}>
                      Run Drill
                    </Button>
                    <Button size="sm" variant="danger" onClick={() => deletePlan(pl.id)}>
                      Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Restore Jobs">
          {restores.length === 0 ? (
            <EmptyState title="No restore jobs" />
          ) : (
            <div className="flex max-h-[400px] flex-col gap-2 overflow-auto pr-1">
              {restores.map((r) => (
                <div
                  key={r.id}
                  className="rounded-aeon-sm border border-aeon-border bg-aeon-bg p-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-aeon-fg-soft">
                      Restore #{r.id.slice(0, 8)}
                    </span>
                    <Badge variant={statusVariant(r.status)}>{r.status}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-aeon-fg-mute">
                    {new Date(r.created_at).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card title="Recent Drills">
          {drills.length === 0 ? (
            <EmptyState title="No drills yet" />
          ) : (
            <div className="flex max-h-[400px] flex-col gap-2 overflow-auto pr-1">
              {drills.map((d) => (
                <div
                  key={d.id}
                  className="rounded-aeon-sm border border-aeon-border bg-aeon-bg p-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-aeon-fg-soft">
                      Drill #{d.id.slice(0, 8)}
                    </span>
                    <Badge variant={statusVariant(d.status)}>{d.status}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-aeon-fg-mute">
                    {new Date(d.created_at).toLocaleString()} · Score {d.score ?? "n/a"}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </section>
    </div>
  );
}
