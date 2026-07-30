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
        { id: "health", label: "Health Command", icon: "🏥", enabled: false },
        { id: "finance", label: "Finance Command", icon: "", enabled: true },
        { id: "retail", label: "Commerce Command", icon: "📦", enabled: false },
        { id: "transport", label: "Transport Command", icon: "🚚", enabled: false },
        { id: "manufacturing", label: "Factory Command", icon: "🏭", enabled: true },
        { id: "tourism", label: "Hospitality Command", icon: "🏨", enabled: false },
        { id: "cultural_heritage", label: "Cultural Command", icon: "️", enabled: false },
        { id: "professional", label: "Professional Hub", icon: "📋", enabled: true },
        { id: "utilities", label: "Utilities Command", icon: "⚡", enabled: false },
        { id: "sme", label: "SME Business Suite", icon: "🏢", enabled: false },
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

    return NextResponse.json({
      ok: true,
      email: DEMO_EMAIL,
      password: DEMO_PASSWORD,
      workspaceId,
      seed: seedData,
    });
  } catch (err: any) {
    return NextResponse.json({ ok: false, error: err.message || "Demo seed failed" }, { status: 500 });
  }
}
