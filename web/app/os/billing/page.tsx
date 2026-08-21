"use client";

import { useEffect, useState, useCallback } from "react";
import { useSession } from "next-auth/react";
import { useTheme } from "@/components/ThemeProvider";
import { FadeIn, ScaleOnHover } from "@/components/animations";
import PageHeader from "@/components/ui/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import LoadingState from "@/components/ui/LoadingState";
import ErrorState from "@/components/ui/ErrorState";
import { isWorkspaceAdmin } from "@/lib/theme-config";

interface SubscriptionInfo {
  ok: boolean;
  subscription_id?: string;
  status?: string;
  plan?: string;
  current_period_end?: string;
  cancel_at_period_end?: boolean;
  simulated?: boolean;
  error?: string;
}

interface StripeConfig {
  ok: boolean;
  available: boolean;
  mode: "test" | "live" | null;
  prices_configured: boolean;
}

interface Plan {
  id: string;
  name: string;
  price: string;
  period: string;
  description: string;
  features: string[];
  highlight?: boolean;
  stripePlan: string;
}

const PLANS: Plan[] = [
  {
    id: "free",
    name: "Free",
    price: "$0",
    period: "forever",
    description: "Get started with core AEON capabilities.",
    features: [
      "1 workspace",
      "3 AI models (stub provider)",
      "Basic sector dashboards",
      "Community plugins",
      "Standard support",
    ],
    stripePlan: "free",
  },
  {
    id: "team",
    name: "Team",
    price: "$49",
    period: "/month",
    description: "Full platform access for growing teams.",
    features: [
      "Up to 10 workspaces",
      "All AI providers (OpenAI, Anthropic, etc.)",
      "All 16 industry sectors",
      "Workflow builder & automations",
      "Marketplace plugins",
      "Knowledge bases & RAG",
      "Priority support",
    ],
    highlight: true,
    stripePlan: "team",
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "$199",
    period: "/month",
    description: "Advanced governance, compliance, and scale.",
    features: [
      "Unlimited workspaces",
      "All Team features",
      "SSO / SCIM provisioning",
      "SIEM integration",
      "Disaster recovery & backup",
      "Custom compliance policies",
      "Audit export & retention",
      "Dedicated support & SLA",
    ],
    stripePlan: "enterprise",
  },
];

const STATUS_COLORS: Record<string, string> = {
  active: "bg-emerald-500/15 text-emerald-400",
  trialing: "bg-blue-500/15 text-blue-400",
  past_due: "bg-amber-500/15 text-amber-400",
  canceled: "bg-red-500/15 text-red-400",
  unpaid: "bg-red-500/15 text-red-400",
  incomplete: "bg-gray-500/15 text-gray-400",
};

export default function BillingPage() {
  const { data: session } = useSession();
  const { config } = useTheme();
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(null);
  const [stripeConfig, setStripeConfig] = useState<StripeConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);

  const workspaceId = (session?.user as any)?.workspace_id || "";
  const admin = isWorkspaceAdmin((session?.user as any)?.role);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const [subRes, configRes] = await Promise.all([
        workspaceId
          ? fetch(`/api/stripe/subscription/${workspaceId}`, {
              headers: { Authorization: `Bearer ${(session?.user as any)?.token || ""}` },
              cache: "no-store",
            }).then((r) => r.json())
          : Promise.resolve({ ok: false, error: "no workspace" }),
        fetch("/api/stripe/config", {
          headers: { Authorization: `Bearer ${(session?.user as any)?.token || ""}` },
          cache: "no-store",
        }).then((r) => r.json()),
      ]);

      setSubscription(subRes);
      setStripeConfig(configRes);
    } catch (e: any) {
      setError(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }, [workspaceId, session]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCheckout = async (planId: string) => {
    if (planId === "free") return;
    setCheckoutLoading(planId);
    try {
      const res = await fetch("/api/stripe/checkout", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${(session?.user as any)?.token || ""}`,
        },
        body: JSON.stringify({
          workspace_id: workspaceId,
          plan_id: planId,
          success_url: `${window.location.origin}/os/billing?upgraded=true`,
          cancel_url: `${window.location.origin}/os/billing`,
        }),
      });
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      } else if (data.simulated) {
        // Simulated mode — refresh to show updated state
        await fetchData();
      } else {
        setError(data.error || "Checkout failed");
      }
    } catch (e: any) {
      setError(e?.message || "Checkout failed");
    } finally {
      setCheckoutLoading(null);
    }
  };

  const handlePortal = async () => {
    setPortalLoading(true);
    try {
      const res = await fetch("/api/stripe/portal", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${(session?.user as any)?.token || ""}`,
        },
        body: JSON.stringify({
          workspace_id: workspaceId,
          return_url: `${window.location.origin}/os/billing`,
        }),
      });
      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      } else if (data.simulated) {
        // Simulated mode
        await fetchData();
      } else {
        setError(data.error || "Portal session failed");
      }
    } catch (e: any) {
      setError(e?.message || "Portal session failed");
    } finally {
      setPortalLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <LoadingState message="Loading billing..." />
      </div>
    );
  }

  if (error && !subscription) {
    return <ErrorState error={error} onRetry={fetchData} />;
  }

  const currentPlan = subscription?.plan || "free";
  const subStatus = subscription?.status || "none";
  const isActive = subStatus === "active" || subStatus === "trialing";
  const isSimulated = subscription?.simulated || false;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Billing & Subscription"
        subtitle="Manage your AEON OS plan and payment settings"
        backHref="/os"
      />

      {/* Stripe Configuration Warning */}
      {stripeConfig && !stripeConfig.available && (
        <FadeIn>
          <Card className="border-amber-500/30 bg-amber-500/5">
            <div className="flex items-start gap-3">
              <span className="text-xl">⚠️</span>
              <div>
                <p className="font-medium text-amber-400">Stripe Not Configured</p>
                <p className="mt-1 text-sm text-amber-400/70">
                  Billing is running in simulated mode. Set <code className="rounded bg-amber-400/10 px-1.5 py-0.5 text-xs">STRIPE_API_KEY</code> and{" "}
                  <code className="rounded bg-amber-400/10 px-1.5 py-0.5 text-xs">STRIPE_WEBHOOK_SECRET</code> to enable real payments.
                </p>
              </div>
            </div>
          </Card>
        </FadeIn>
      )}

      {/* Current Subscription */}
      {subscription?.ok && (
        <FadeIn>
          <Card title="Current Subscription">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-3">
                  <span className="text-lg font-semibold capitalize text-aeon-text-1">
                    {currentPlan} Plan
                  </span>
                  {subStatus !== "none" && (
                    <Badge className={STATUS_COLORS[subStatus] || "bg-gray-500/15 text-gray-400"}>
                      {subStatus.replace(/_/g, " ")}
                    </Badge>
                  )}
                  {isSimulated && (
                    <Badge className="bg-purple-500/15 text-purple-400">Simulated</Badge>
                  )}
                </div>
                {subscription.current_period_end && (
                  <p className="text-sm text-aeon-text-2">
                    {subscription.cancel_at_period_end
                      ? `Cancels on ${new Date(subscription.current_period_end).toLocaleDateString()}`
                      : `Renews on ${new Date(subscription.current_period_end).toLocaleDateString()}`}
                  </p>
                )}
              </div>
              {isActive && admin && (
                <Button
                  onClick={handlePortal}
                  disabled={portalLoading}
                  variant="secondary"
                  className="shrink-0"
                >
                  {portalLoading ? "Opening portal..." : "Manage Subscription"}
                </Button>
              )}
            </div>
          </Card>
        </FadeIn>
      )}

      {/* Plan Cards */}
      <FadeIn>
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-aeon-text-1">
            {currentPlan === "free" ? "Choose a Plan" : "Upgrade Your Plan"}
          </h2>
          <div className="grid gap-6 md:grid-cols-3">
            {PLANS.map((plan) => {
              const isCurrent = currentPlan === plan.id;
              const isUpgrade = PLANS.findIndex((p) => p.id === plan.id) > PLANS.findIndex((p) => p.id === currentPlan);
              const canAction = admin && !isCurrent && (plan.id === "free" ? false : isUpgrade || currentPlan === "free");

              return (
                <ScaleOnHover key={plan.id}>
                  <Card
                    className={`relative h-full ${
                      plan.highlight
                        ? "border-violet-500/40 ring-1 ring-violet-500/20"
                        : ""
                    } ${isCurrent ? "border-emerald-500/40 ring-1 ring-emerald-500/20" : ""}`}
                  >
                    {plan.highlight && !isCurrent && (
                      <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                        <Badge className="bg-violet-500 text-white">Most Popular</Badge>
                      </div>
                    )}
                    {isCurrent && (
                      <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                        <Badge className="bg-emerald-500 text-white">Current Plan</Badge>
                      </div>
                    )}

                    <div className="flex flex-col h-full">
                      <div className="mb-4">
                        <h3 className="text-xl font-bold text-aeon-text-1">{plan.name}</h3>
                        <div className="mt-2 flex items-baseline gap-1">
                          <span className="text-3xl font-bold text-aeon-text-1">{plan.price}</span>
                          <span className="text-sm text-aeon-text-2">{plan.period}</span>
                        </div>
                        <p className="mt-2 text-sm text-aeon-text-2">{plan.description}</p>
                      </div>

                      <ul className="mb-6 flex-1 space-y-2">
                        {plan.features.map((feature) => (
                          <li key={feature} className="flex items-start gap-2 text-sm text-aeon-text-2">
                            <span className="mt-0.5 text-emerald-400">✓</span>
                            {feature}
                          </li>
                        ))}
                      </ul>

                      <Button
                        onClick={() => handleCheckout(plan.stripePlan)}
                        disabled={!canAction || checkoutLoading !== null}
                        variant={plan.highlight && canAction ? "primary" : "secondary"}
                        className="w-full"
                      >
                        {isCurrent
                          ? "Current Plan"
                          : checkoutLoading === plan.stripePlan
                            ? "Redirecting..."
                            : plan.id === "free"
                              ? "Included"
                              : "Upgrade"}
                      </Button>
                    </div>
                  </Card>
                </ScaleOnHover>
              );
            })}
          </div>
        </div>
      </FadeIn>

      {/* Billing Info */}
      <FadeIn>
        <Card title="Billing Information">
          <div className="space-y-3 text-sm text-aeon-text-2">
            <div className="flex items-start gap-2">
              <span className="text-aeon-text-1">•</span>
              <p>All plans include a 14-day free trial for Team and Enterprise features.</p>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-aeon-text-1">•</span>
              <p>Payments are processed securely through Stripe. We never store your card details.</p>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-aeon-text-1">•</span>
              <p>Cancel anytime — your plan remains active until the end of the billing period.</p>
            </div>
            <div className="flex items-start gap-2">
              <span className="text-aeon-text-1">•</span>
              <p>
                Need a custom plan?{" "}
                <a href="mailto:sales@aeonos.com" className="text-violet-400 hover:underline">
                  Contact sales
                </a>
              </p>
            </div>
          </div>
        </Card>
      </FadeIn>
    </div>
  );
}
