"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";

type BillingPlan = {
  id: string;
  name: string;
  limits: Record<string, number>;
  price_per_request: number;
  price_per_1k_tokens: number;
};

type BillingStatus = {
  workspace_id: string;
  plan: { id: string; name: string; limits: Record<string, number> };
  credits: number;
  usage: { requests: number; tokens: number; workflows: number; integrations: number };
  limits: Record<string, number>;
  estimated_cost: number;
  remaining_credits: number;
  quota_usage_pct: Record<string, number>;
};

type UsageSummary = {
  period_days: number;
  total_events: number;
  total_quantity: number;
  total_cost: number;
  by_action: Record<string, { quantity: number; cost: number; count: number }>;
  by_day: Record<string, { quantity: number; cost: number; count: number }>;
};

type StripeConfig = {
  available: boolean;
  mode: string | null;
  prices_configured: boolean;
};

const PLANS: {
  id: string;
  name: string;
  icon: string;
  color: string;
  price: string;
  features: string[];
}[] = [
  {
    id: "free",
    name: "Free",
    icon: "🌱",
    color: "#94a3b8",
    price: "$0/mo",
    features: [
      "1,000 requests/mo",
      "100K tokens",
      "10 workflows",
      "5 integrations",
      "Community support",
    ],
  },
  {
    id: "team",
    name: "Team",
    icon: "🚀",
    color: "#6366f1",
    price: "$49/mo",
    features: [
      "50,000 requests/mo",
      "5M tokens",
      "500 workflows",
      "50 integrations",
      "Priority support",
      "Team workspace",
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    icon: "🏢",
    color: "#f59e0b",
    price: "Custom",
    features: [
      "1M+ requests/mo",
      "100M+ tokens",
      "Unlimited workflows",
      "Unlimited integrations",
      "Dedicated support",
      "SLA guarantee",
      "Custom deployment",
    ],
  },
];

export default function BillingPage() {
  const { data: session } = useSession();
  const workspaceId = ((session?.user as any)?.workspaceId as string) || "default";

  const [billing, setBilling] = useState<BillingStatus | null>(null);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [stripeConfig, setStripeConfig] = useState<StripeConfig | null>(null);
  const [stripeSubStatus, setStripeSubStatus] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [upgrading, setUpgrading] = useState<string | null>(null);
  const [creditAmount, setCreditAmount] = useState("50");
  const [addingCredits, setAddingCredits] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [billingRes, usageRes, stripeRes, stripeSubRes] = await Promise.all([
        fetch(`/api/os/observability/billing?workspace_id=${workspaceId}`, { cache: "no-store" }),
        fetch(`/api/os/observability/usage?workspace_id=${workspaceId}`, { cache: "no-store" }),
        fetch(`/api/stripe/config`, { cache: "no-store" }),
        fetch(`/api/stripe/subscription/${workspaceId}`, { cache: "no-store" }),
      ]);
      const billingData = await billingRes.json();
      const usageData = await usageRes.json();
      const stripeData = await stripeRes.json();
      const stripeSubData = await stripeSubRes.json();

      if (billingData.ok) setBilling(billingData.billing);
      if (usageData.ok) setUsage(usageData.summary);
      if (stripeData.ok) setStripeConfig(stripeData);
      if (stripeSubData.ok) setStripeSubStatus(stripeSubData.status || "");
    } catch {
      // silent fallback
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const upgradeViaStripe = async (planId: string) => {
    setUpgrading(planId);
    setMessage(null);
    try {
      const res = await fetch(`/api/stripe/checkout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workspace_id: workspaceId,
          plan_id: planId,
          success_url: `${window.location.origin}/os/billing?upgrade=success`,
          cancel_url: `${window.location.origin}/os/billing?upgrade=cancel`,
        }),
      });
      const data = await res.json();

      if (data.simulated) {
        // Fallback: Stripe not configured — use simulated billing
        const simRes = await fetch(`/api/os/observability/billing/${workspaceId}/plan`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plan_id: planId }),
        });
        const simData = await simRes.json();
        if (simData.ok) {
          setBilling(simData.billing);
          setMessage({ ok: true, text: `Upgraded to ${simData.billing.plan.name}! (simulated)` });
        } else {
          setMessage({ ok: false, text: simData.error || "Upgrade failed" });
        }
      } else if (data.ok && data.url) {
        // Real Stripe checkout — redirect
        window.location.href = data.url;
      } else {
        setMessage({ ok: false, text: data.error || "Checkout failed" });
      }
    } catch (e: any) {
      setMessage({ ok: false, text: e?.message || "Network error" });
    } finally {
      setUpgrading(null);
    }
  };

  const openBillingPortal = async () => {
    setMessage(null);
    try {
      const res = await fetch(`/api/stripe/portal`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workspace_id: workspaceId,
          return_url: `${window.location.origin}/os/billing`,
        }),
      });
      const data = await res.json();
      if (data.ok && data.url) {
        window.location.href = data.url;
      } else if (data.simulated) {
        setMessage({
          ok: true,
          text: "Portal not available — Stripe not configured. Use simulated upgrade instead.",
        });
      } else {
        setMessage({ ok: false, text: data.error || "Portal failed" });
      }
    } catch (e: any) {
      setMessage({ ok: false, text: e?.message || "Network error" });
    }
  };

  const addCredits = async () => {
    const amount = parseFloat(creditAmount);
    if (isNaN(amount) || amount <= 0) return;
    setAddingCredits(true);
    setMessage(null);
    try {
      const res = await fetch(`/api/os/observability/billing/${workspaceId}/credits`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ amount }),
      });
      const data = await res.json();
      if (data.ok) {
        setBilling(data.billing);
        setMessage({ ok: true, text: `$${amount} credits added!` });
      } else {
        setMessage({ ok: false, text: data.error || "Failed to add credits" });
      }
    } catch (e: any) {
      setMessage({ ok: false, text: e?.message || "Network error" });
    } finally {
      setAddingCredits(false);
    }
  };

  const currentPlanId = billing?.plan?.id || "free";
  const stripeActive = stripeConfig?.available ?? false;
  const stripeMode = stripeConfig?.mode ?? null;

  const actionCounts = billing?.usage || { requests: 0, tokens: 0, workflows: 0, integrations: 0 };
  const usageLabels: Record<string, string> = {
    requests: "API Requests",
    tokens: "Token Usage",
    workflows: "Workflow Runs",
    integrations: "Integration Calls",
  };

  if (loading) {
    return (
      <div className="os-page">
        <div style={{ padding: 40, textAlign: "center", color: "var(--fg-mute)" }}>
          Loading billing data…
        </div>
      </div>
    );
  }

  return (
    <div className="os-page">
      <header className="os-header">
        <div>
          <h1>💰 Billing & Plans</h1>
          <p className="dashboard-subtitle">
            Manage your subscription, payment method, and usage credits
          </p>
        </div>
      </header>

      {message && (
        <div className={`module-alert ${message.ok ? "" : "danger"}`} style={{ marginBottom: 20 }}>
          {message.text}
        </div>
      )}

      {/* ── Stripe Status Banner ── */}
      {stripeActive && (
        <div className="stripe-banner">
          <span className="stripe-banner-icon">⚡</span>
          <span>
            Stripe {stripeMode === "test" ? "test mode" : "live"} is active.
            {stripeSubStatus === "active"
              ? " You have an active subscription."
              : " Use checkout to subscribe."}
          </span>
          {stripeSubStatus === "active" && (
            <button className="btn btn-sm stripe-portal-btn" onClick={openBillingPortal}>
              Manage in Stripe →
            </button>
          )}
        </div>
      )}
      {!stripeActive && (
        <div className="stripe-banner simulated" style={{ marginBottom: 20 }}>
          <span className="stripe-banner-icon">🔄</span>
          <span>
            Simulated billing active. Set <code>STRIPE_API_KEY</code> in your environment to enable
            real payment processing.
          </span>
        </div>
      )}

      {/* ── Current Plan Status ── */}
      <section className="billing-status-bar">
        <div className="billing-status-item">
          <span className="billing-status-label">Current Plan</span>
          <span
            className="billing-status-value"
            style={{ color: PLANS.find((p) => p.id === currentPlanId)?.color }}
          >
            {PLANS.find((p) => p.id === currentPlanId)?.icon} {billing?.plan?.name || "Free"}
          </span>
        </div>
        <div className="billing-status-item">
          <span className="billing-status-label">Credits</span>
          <span className="billing-status-value">${(billing?.credits ?? 0).toFixed(2)}</span>
        </div>
        <div className="billing-status-item">
          <span className="billing-status-label">Est. Monthly Cost</span>
          <span className="billing-status-value">${(billing?.estimated_cost ?? 0).toFixed(2)}</span>
        </div>
        <div className="billing-status-item">
          <span className="billing-status-label">Remaining</span>
          <span
            className="billing-status-value"
            style={{ color: (billing?.remaining_credits ?? 0) > 0 ? "#22c55e" : "#ef4444" }}
          >
            ${(billing?.remaining_credits ?? 0).toFixed(2)}
          </span>
        </div>
        <div className="billing-status-item">
          <span className="billing-status-label">Payment</span>
          <span
            className="billing-status-value"
            style={{ fontSize: "0.8rem", color: stripeActive ? "#22c55e" : "#94a3b8" }}
          >
            {stripeActive ? "Stripe" : "Simulated"}
          </span>
        </div>
      </section>

      {/* ── Plan Comparison ── */}
      <section className="billing-plans-section">
        <h2 className="billing-section-title">Choose Your Plan</h2>
        <div className="billing-plans">
          {PLANS.map((plan) => {
            const isCurrent = plan.id === currentPlanId;
            return (
              <div
                key={plan.id}
                className={`billing-plan-card ${isCurrent ? "current" : ""}`}
                style={{ borderColor: isCurrent ? plan.color : "var(--border)" }}
              >
                {isCurrent && (
                  <div className="billing-plan-badge" style={{ background: plan.color }}>
                    CURRENT
                  </div>
                )}
                <div className="billing-plan-icon" style={{ fontSize: "2.5rem" }}>
                  {plan.icon}
                </div>
                <h3 className="billing-plan-name">{plan.name}</h3>
                <div className="billing-plan-price">{plan.price}</div>
                <ul className="billing-plan-features">
                  {plan.features.map((f, i) => (
                    <li key={i} className="billing-plan-feature">
                      <span className="billing-plan-check">✓</span> {f}
                    </li>
                  ))}
                </ul>
                {isCurrent && stripeSubStatus === "active" ? (
                  <button
                    className="btn btn-secondary"
                    onClick={openBillingPortal}
                    style={{ width: "100%", marginTop: "auto" }}
                  >
                    Manage Subscription
                  </button>
                ) : (
                  <button
                    className={`btn ${isCurrent ? "btn-secondary" : "btn-primary"}`}
                    onClick={() => upgradeViaStripe(plan.id)}
                    disabled={isCurrent || upgrading === plan.id}
                    style={{ width: "100%", marginTop: "auto" }}
                  >
                    {isCurrent
                      ? "Current Plan"
                      : upgrading === plan.id
                        ? "Processing..."
                        : plan.id === "free"
                          ? "Downgrade"
                          : "Subscribe"}
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </section>

      {/* ── Quota Usage ── */}
      {billing?.quota_usage_pct && Object.keys(billing.quota_usage_pct).length > 0 && (
        <section className="billing-section">
          <h2 className="billing-section-title">Resource Usage</h2>
          <div className="billing-quota-grid">
            {Object.entries(billing.quota_usage_pct).map(([key, pct]) => {
              const used = (actionCounts as any)[key] ?? 0;
              const limit = billing.limits[key] ?? 1;
              return (
                <div key={key} className="billing-quota-card">
                  <div className="billing-quota-header">
                    <span className="billing-quota-label">{usageLabels[key] || key}</span>
                    <span className="billing-quota-numbers">
                      {used.toLocaleString()} / {limit.toLocaleString()}
                    </span>
                  </div>
                  <div className="billing-quota-bar-bg">
                    <div
                      className="billing-quota-bar-fill"
                      style={{
                        width: `${Math.min(100, pct)}%`,
                        background: pct > 90 ? "#ef4444" : pct > 70 ? "#f59e0b" : "#6366f1",
                      }}
                    />
                  </div>
                  <div className="billing-quota-pct">{pct.toFixed(1)}% used</div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Add Credits ── */}
      <section className="billing-section">
        <h2 className="billing-section-title">Add Credits</h2>
        <p style={{ color: "var(--fg-soft)", marginBottom: 16, fontSize: "0.85rem" }}>
          {stripeActive
            ? "Add credits to your account. Credits are deducted before overage billing."
            : "Add simulated credits to cover usage costs."}
        </p>
        <div className="billing-credit-form">
          <div className="billing-credit-presets">
            {[10, 25, 50, 100, 500].map((amt) => (
              <button
                key={amt}
                className={`btn btn-sm ${parseFloat(creditAmount) === amt ? "btn-primary" : ""}`}
                onClick={() => setCreditAmount(String(amt))}
              >
                ${amt}
              </button>
            ))}
          </div>
          <div className="billing-credit-input-row">
            <span style={{ color: "var(--fg-soft)", fontWeight: 600 }}>$</span>
            <input
              className="os-input"
              type="number"
              min={1}
              step={1}
              value={creditAmount}
              onChange={(e) => setCreditAmount(e.target.value)}
              style={{ width: 120, textAlign: "center" }}
            />
            <button className="btn btn-primary" onClick={addCredits} disabled={addingCredits}>
              {addingCredits ? "Adding..." : "Add Credits"}
            </button>
          </div>
        </div>
      </section>

      {/* ── Recent Activity ── */}
      {usage && usage.total_events > 0 && (
        <section className="billing-section">
          <h2 className="billing-section-title">Recent Activity</h2>
          <div className="billing-activity-list">
            {Object.entries(usage.by_action || {})
              .slice(0, 8)
              .map(([action, data]) => (
                <div key={action} className="billing-activity-item">
                  <div className="billing-activity-info">
                    <span className="billing-activity-action">{action}</span>
                    <span className="billing-activity-count">{data.count} calls</span>
                  </div>
                  <div className="billing-activity-cost">${data.cost.toFixed(4)}</div>
                </div>
              ))}
          </div>
        </section>
      )}
    </div>
  );
}
