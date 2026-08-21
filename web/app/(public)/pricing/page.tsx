"use client";

import Link from "next/link";
import { useState } from "react";

/* ── Plan data ───────────────────────────────────────────────────────────── */

interface Plan {
  id: string;
  name: string;
  price: string;
  period: string;
  description: string;
  highlight?: boolean;
  cta: string;
  href: string;
  features: { text: string; included: boolean }[];
}

const PLANS: Plan[] = [
  {
    id: "free",
    name: "Free",
    price: "$0",
    period: "forever",
    description: "Start exploring AEON with core capabilities at zero cost.",
    cta: "Get Started Free",
    href: "/login?callbackUrl=/os",
    features: [
      { text: "1 workspace", included: true },
      { text: "3 AI models (stub provider)", included: true },
      { text: "Basic sector dashboards", included: true },
      { text: "Community plugins", included: true },
      { text: "Standard support", included: true },
      { text: "Workflow builder", included: false },
      { text: "Knowledge bases & RAG", included: false },
      { text: "SSO / SCIM", included: false },
      { text: "SIEM integration", included: false },
      { text: "Disaster recovery", included: false },
    ],
  },
  {
    id: "team",
    name: "Team",
    price: "$49",
    period: "/month",
    description: "Full platform access for growing teams and departments.",
    highlight: true,
    cta: "Start 14-Day Trial",
    href: "/login?callbackUrl=/os/billing",
    features: [
      { text: "Up to 10 workspaces", included: true },
      { text: "All AI providers (OpenAI, Anthropic, etc.)", included: true },
      { text: "All 16 industry sectors", included: true },
      { text: "Workflow builder & automations", included: true },
      { text: "Marketplace plugins", included: true },
      { text: "Knowledge bases & RAG", included: true },
      { text: "Priority support", included: true },
      { text: "SSO / SCIM", included: false },
      { text: "SIEM integration", included: false },
      { text: "Disaster recovery", included: false },
    ],
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: "$199",
    period: "/month",
    description: "Advanced governance, compliance, and scale for large organizations.",
    cta: "Contact Sales",
    href: "mailto:sales@aeonos.com",
    features: [
      { text: "Unlimited workspaces", included: true },
      { text: "All Team features", included: true },
      { text: "SSO / SCIM provisioning", included: true },
      { text: "SIEM integration", included: true },
      { text: "Disaster recovery & backup", included: true },
      { text: "Custom compliance policies", included: true },
      { text: "Audit export & retention", included: true },
      { text: "Dedicated support & SLA", included: true },
      { text: "On-premise deployment option", included: true },
      { text: "Custom sector packs", included: true },
    ],
  },
];

/* ── FAQ data ────────────────────────────────────────────────────────────── */

const FAQ = [
  {
    q: "What is included in the free plan?",
    a: "The free plan gives you one workspace with access to basic sector dashboards and community plugins. It uses the stub AI provider so you can explore the platform without any API keys.",
  },
  {
    q: "Can I try Team or Enterprise before committing?",
    a: "Yes. Both Team and Enterprise include a 14-day free trial with full feature access. No credit card required to start.",
  },
  {
    q: "How does billing work?",
    a: "We use Stripe for secure payment processing. You can upgrade, downgrade, or cancel anytime from your billing settings. Plans renew monthly.",
  },
  {
    q: "What AI providers are supported?",
    a: "AEON supports OpenAI, Anthropic, Google, Mistral, HuggingFace, Ollama, vLLM, and custom providers. The Team and Enterprise plans include access to all providers.",
  },
  {
    q: "Is my data secure?",
    a: "Yes. AEON is built with enterprise security: workspace isolation, RBAC, tamper-evident audit logs, encrypted at rest, and SOC 2 readiness controls. We never train on your data.",
  },
  {
    q: "Do you offer volume or annual discounts?",
    a: "Yes. Contact our sales team for annual billing discounts and custom enterprise pricing for large deployments.",
  },
];

/* ── Component ───────────────────────────────────────────────────────────── */

export default function PricingPage() {
  const [openFaq, setOpenFaq] = useState<number | null>(null);

  return (
    <div className="min-h-screen">
      {/* ── Nav ─────────────────────────────────────────────────────────── */}
      <nav className="border-b border-white/5 bg-aeon-bg-0/80 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link href="/" className="flex items-center gap-2 text-lg font-bold text-white">
            <span className="text-xl">⬡</span> AEON OS
          </Link>
          <div className="flex items-center gap-6 text-sm text-white/60">
            <Link href="/" className="hover:text-white transition-colors">
              Home
            </Link>
            <Link href="/pricing" className="text-white">
              Pricing
            </Link>
            <Link
              href="/login"
              className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 transition-colors"
            >
              Sign In
            </Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ────────────────────────────────────────────────────────── */}
      <section className="px-6 pb-16 pt-20 text-center">
        <div className="mx-auto max-w-3xl">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-violet-500/20 bg-violet-500/10 px-4 py-1.5 text-xs font-medium text-violet-300">
            <span className="h-1.5 w-1.5 rounded-full bg-violet-400 animate-pulse" />
            Now with 16 industry sectors
          </div>
          <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl">
            Simple, transparent pricing
          </h1>
          <p className="mt-5 text-lg text-white/60">
            Start free. Scale with your team. Enterprise-grade AI governance at every tier.
          </p>
        </div>
      </section>

      {/* ── Plan cards ──────────────────────────────────────────────────── */}
      <section className="mx-auto max-w-6xl px-6 pb-24">
        <div className="grid gap-8 lg:grid-cols-3">
          {PLANS.map((plan) => (
            <div
              key={plan.id}
              className={`relative flex flex-col rounded-2xl border p-8 transition-all ${
                plan.highlight
                  ? "border-violet-500/40 bg-gradient-to-b from-violet-500/10 to-transparent shadow-lg shadow-violet-500/10"
                  : "border-white/10 bg-white/[0.02]"
              }`}
            >
              {plan.highlight && (
                <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
                  <span className="rounded-full bg-violet-600 px-4 py-1 text-xs font-semibold text-white">
                    Most Popular
                  </span>
                </div>
              )}

              <div className="mb-6">
                <h3 className="text-xl font-bold text-white">{plan.name}</h3>
                <p className="mt-2 text-sm text-white/50">{plan.description}</p>
                <div className="mt-4 flex items-baseline gap-1">
                  <span className="text-4xl font-bold text-white">{plan.price}</span>
                  <span className="text-sm text-white/40">{plan.period}</span>
                </div>
              </div>

              <ul className="mb-8 flex-1 space-y-3">
                {plan.features.map((f) => (
                  <li
                    key={f.text}
                    className={`flex items-start gap-2.5 text-sm ${
                      f.included ? "text-white/80" : "text-white/30"
                    }`}
                  >
                    <span className={`mt-0.5 ${f.included ? "text-emerald-400" : "text-white/20"}`}>
                      {f.included ? "✓" : "—"}
                    </span>
                    {f.text}
                  </li>
                ))}
              </ul>

              <Link
                href={plan.href}
                className={`block w-full rounded-xl py-3 text-center text-sm font-semibold transition-colors ${
                  plan.highlight
                    ? "bg-violet-600 text-white hover:bg-violet-500"
                    : "border border-white/10 bg-white/5 text-white hover:bg-white/10"
                }`}
              >
                {plan.cta}
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* ── Feature comparison ──────────────────────────────────────────── */}
      <section className="border-t border-white/5 bg-white/[0.01] px-6 py-20">
        <div className="mx-auto max-w-4xl">
          <h2 className="text-center text-2xl font-bold text-white">Compare plans</h2>
          <p className="mt-2 text-center text-sm text-white/50">
            Every plan includes core AEON security and governance features.
          </p>

          <div className="mt-10 overflow-hidden rounded-xl border border-white/10">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/10 text-left text-xs uppercase tracking-wider text-white/40">
                  <th className="px-6 py-4">Feature</th>
                  <th className="px-6 py-4 text-center">Free</th>
                  <th className="px-6 py-4 text-center">Team</th>
                  <th className="px-6 py-4 text-center">Enterprise</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {[
                  ["Workspaces", "1", "Up to 10", "Unlimited"],
                  ["AI Providers", "Stub only", "All providers", "All providers + custom"],
                  ["Industry Sectors", "Basic", "All 16", "All 16 + custom packs"],
                  ["Automations", "—", "✓", "✓"],
                  ["Knowledge Bases (RAG)", "—", "✓", "✓"],
                  ["Marketplace Plugins", "Community", "Full access", "Full access + custom"],
                  ["SSO / SCIM", "—", "—", "✓"],
                  ["SIEM Integration", "—", "—", "✓"],
                  ["Disaster Recovery", "—", "—", "✓"],
                  ["Compliance Policies", "—", "—", "Custom"],
                  ["Audit Export", "—", "—", "✓"],
                  ["Support", "Community", "Priority", "Dedicated SLA"],
                  ["Workspace Isolation", "✓", "✓", "✓"],
                  ["Tamper-Evident Audit", "✓", "✓", "✓"],
                  ["RBAC", "✓", "✓", "✓"],
                ].map(([feature, free, team, enterprise]) => (
                  <tr key={feature} className="text-white/70">
                    <td className="px-6 py-3 font-medium text-white/90">{feature}</td>
                    <td className="px-6 py-3 text-center text-white/50">{free}</td>
                    <td className="px-6 py-3 text-center text-white/70">{team}</td>
                    <td className="px-6 py-3 text-center text-white/70">{enterprise}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── FAQ ─────────────────────────────────────────────────────────── */}
      <section className="px-6 py-20">
        <div className="mx-auto max-w-2xl">
          <h2 className="text-center text-2xl font-bold text-white">
            Frequently asked questions
          </h2>
          <div className="mt-10 space-y-3">
            {FAQ.map((item, i) => (
              <div
                key={i}
                className="overflow-hidden rounded-xl border border-white/10 bg-white/[0.02]"
              >
                <button
                  onClick={() => setOpenFaq(openFaq === i ? null : i)}
                  className="flex w-full items-center justify-between px-6 py-4 text-left text-sm font-medium text-white/90 hover:bg-white/[0.03] transition-colors"
                >
                  {item.q}
                  <span
                    className={`ml-4 text-white/40 transition-transform ${
                      openFaq === i ? "rotate-180" : ""
                    }`}
                  >
                    ▾
                  </span>
                </button>
                {openFaq === i && (
                  <div className="px-6 pb-4 text-sm leading-relaxed text-white/50">
                    {item.a}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ─────────────────────────────────────────────────────────── */}
      <section className="border-t border-white/5 px-6 py-20">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-2xl font-bold text-white">
            Ready to transform your AI operations?
          </h2>
          <p className="mt-3 text-white/50">
            Start your free trial today. No credit card required.
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-4 sm:flex-row">
            <Link
              href="/login?callbackUrl=/os"
              className="rounded-xl bg-violet-600 px-8 py-3 text-sm font-semibold text-white hover:bg-violet-500 transition-colors"
            >
              Get Started Free
            </Link>
            <Link
              href="mailto:sales@aeonos.com"
              className="rounded-xl border border-white/10 bg-white/5 px-8 py-3 text-sm font-semibold text-white hover:bg-white/10 transition-colors"
            >
              Talk to Sales
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────────────────────── */}
      <footer className="border-t border-white/5 px-6 py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 text-xs text-white/30 sm:flex-row">
          <span>© 2026 AEON OS. All rights reserved.</span>
          <div className="flex gap-6">
            <Link href="/" className="hover:text-white/60 transition-colors">
              Home
            </Link>
            <Link href="/pricing" className="hover:text-white/60 transition-colors">
              Pricing
            </Link>
            <a href="mailto:support@aeonos.com" className="hover:text-white/60 transition-colors">
              Support
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
