import { NextRequest, NextResponse } from "next/server";

const AEON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

const DEMO_EMAIL = "admin@demo.local";
const DEMO_PASSWORD = "demo123";
const DEMO_NAME = "Demo Admin";

interface AuthResponse {
  ok?: boolean;
  token?: string;
  user?: {
    id?: string;
    email?: string;
    role?: string;
    workspace_id?: string;
  };
  error?: string;
}

async function registerOrLogin(): Promise<AuthResponse> {
  try {
    // Try register first (idempotent if user exists).
    let res = await fetch(`${AEON_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: DEMO_EMAIL,
        password: DEMO_PASSWORD,
        name: DEMO_NAME,
      }),
    });
    let data = (await res.json()) as AuthResponse;

    // If the user already exists, fall back to login.
    if (!data.ok) {
      res = await fetch(`${AEON_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: DEMO_EMAIL,
          password: DEMO_PASSWORD,
        }),
      });
      data = (await res.json()) as AuthResponse;
    }

    return data;
  } catch (err: any) {
    return {
      ok: false,
      error:
        "AEON backend unreachable — is the Python server running? Start it with `npm run dev:full` from web/, or set AEON_PYTHON_URL.",
    };
  }
}

export async function POST(_req: NextRequest) {
  try {
    const auth = await registerOrLogin();
    if (!auth.ok || !auth.token || !auth.user?.workspace_id) {
      return NextResponse.json(
        { ok: false, error: auth.error || "Could not create or authenticate demo user" },
        { status: 500 }
      );
    }

    const workspaceId = auth.user.workspace_id;

    // Apply a polished demo company branding.
    const branding = {
      companyName: "NexGen Industries",
      productName: "NexGen Command",
      tagline: "AI-Powered Enterprise Operations",
      primaryColor: "#0ea5e9",
      logoUrl: "",
      modules: [
        { id: "dashboard", label: "Dashboard", icon: "◈", enabled: true },
        { id: "chat", label: "Chat", icon: "💬", enabled: true },
        { id: "os", label: "OS Modules", icon: "⊞", enabled: true },
        { id: "automations", label: "Automations", icon: "🤖", enabled: true },
        { id: "swarms", label: "Swarms", icon: "🐝", enabled: true },
        { id: "llm", label: "LLM Brain", icon: "⚡", enabled: true },
        { id: "apiKeys", label: "API Keys", icon: "🔑", enabled: true },
        { id: "observability", label: "Observability", icon: "📊", enabled: true },
        { id: "monitoring", label: "Monitoring", icon: "📈", enabled: true },
        { id: "knowledge", label: "Knowledge", icon: "📚", enabled: true },
        { id: "ragChat", label: "RAG Chat", icon: "🧠", enabled: true },
        { id: "aiStudio", label: "AI Studio", icon: "", enabled: true },
        { id: "notifications", label: "Notifications", icon: "🔔", enabled: true },
        { id: "activity", label: "Activity", icon: "⚡", enabled: true },
        { id: "security", label: "Security & Ops", icon: "🛡️", enabled: true },
        { id: "anomalies", label: "Anomalies", icon: "🔍", enabled: true },
        { id: "incidents", label: "Incidents", icon: "🚨", enabled: true },
        { id: "dr", label: "Disaster Recovery", icon: "🛡️", enabled: true },
        { id: "integrations", label: "API Gateway & Integrations", icon: "🔗", enabled: true },
        { id: "governance", label: "Governance", icon: "🛡️", enabled: true },
        { id: "cybersecurity", label: "Security Command", icon: "🛡️", enabled: true },
        { id: "health", label: "Health Command", icon: "🏥", enabled: true },
        { id: "finance", label: "Finance Command", icon: "", enabled: true },
        { id: "retail", label: "Commerce Command", icon: "📦", enabled: true },
        { id: "transport", label: "Transport Command", icon: "🚚", enabled: true },
        { id: "manufacturing", label: "Factory Command", icon: "🏭", enabled: true },
        { id: "tourism", label: "Hospitality Command", icon: "🏨", enabled: true },
        { id: "cultural_heritage", label: "Cultural Command", icon: "🏛️", enabled: true },
        { id: "professional", label: "Professional Hub", icon: "📋", enabled: true },
        { id: "utilities", label: "Utilities Command", icon: "⚡", enabled: true },
        { id: "sme", label: "SME Business Suite", icon: "🏢", enabled: true },
        { id: "telecom", label: "Telecom Command", icon: "📡", enabled: true },
        { id: "agriculture", label: "AgriTech Command", icon: "🌾", enabled: true },
        { id: "education", label: "Education Command", icon: "🎓", enabled: true },
        { id: "public_safety", label: "Public Safety Command", icon: "🚔", enabled: true },
        { id: "real_estate", label: "Real Estate Command", icon: "🏠", enabled: true },
      ],
    };

    await fetch(`${AEON_URL}/workspaces/${encodeURIComponent(workspaceId)}/branding`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${auth.token}`,
      },
      body: JSON.stringify(branding),
    });

    // Seed the workspace with realistic demo data.
    const seedRes = await fetch(`${AEON_URL}/workspaces/${encodeURIComponent(workspaceId)}/seed`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${auth.token}`,
      },
    });
    let seedData = {};
    try {
      seedData = (await seedRes.json()) as Record<string, unknown>;
    } catch {
      seedData = { ok: false, error: "Could not parse seed response" };
    }

    // Best-effort Supabase-backed demo records (automation rules + approvals).
    // These tables require Supabase to be configured; failures are ignored so
    // the demo still works for the modules backed by the local database.
    const authHeaders = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${auth.token}`,
    };

    const demoRules = [
      {
        name: "Escalate critical incidents to on-call",
        event_type: "incident.critical",
        actions: [
          {
            type: "webhook",
            config: { url: "https://hooks.example.com/oncall", method: "POST" },
          },
          {
            type: "wait_for_event",
            config: { event: "incident.acknowledged", timeout: 300 },
          },
        ],
        enabled: true,
        approval_required: false,
        schedule_type: "event",
        cooldown_minutes: 5,
      },
      {
        name: "Nightly SIEM log aggregation",
        event_type: "schedule",
        actions: [
          {
            type: "workflow",
            config: { workflow: "siem-export", params: { batch: 500 } },
          },
        ],
        enabled: true,
        approval_required: false,
        schedule_type: "cron",
        cron_expression: "0 2 * * *",
        cooldown_minutes: 0,
      },
    ];

    for (const rule of demoRules) {
      try {
        await fetch(`${AEON_URL}/automations`, {
          method: "POST",
          headers: authHeaders,
          body: JSON.stringify(rule),
        });
      } catch {
        // Supabase not configured — skip.
      }
    }

    try {
      await fetch(`${AEON_URL}/approvals`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({
          event_type: "workflow_status",
          event_payload: {
            workflow: "Nightly SIEM log aggregation",
            reason: "First demo run requires human approval",
          },
          action_type: "workflow",
          action_config: { workflow: "siem-export" },
        }),
      });
    } catch {
      // Supabase not configured — skip.
    }

    return NextResponse.json({
      ok: true,
      email: DEMO_EMAIL,
      password: DEMO_PASSWORD,
      workspaceId,
      seed: seedData,
    });
  } catch (err: any) {
    return NextResponse.json(
      { ok: false, error: err.message || "Demo seed failed" },
      { status: 500 }
    );
  }
}
