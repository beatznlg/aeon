import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import { getSupabaseServerClient } from "@/lib/supabase";

const DEMO_EMAIL = "admin@demo.local";
const DEMO_PASSWORD = "demo123";
const DEMO_NAME = "Demo Admin";

/**
 * Demo seed route — works standalone without the Flask backend.
 *
 * Strategy (in priority order):
 * 1. Supabase: upsert demo user + workspace directly
 * 2. Fallback admin: return credentials matching ADMIN_EMAIL / ADMIN_PASSWORD
 *    env vars (already handled by auth.ts)
 * 3. Flask bridge: fall back to the old Flask register/login if reachable
 */
async function seedDemoUser() {
  // ── Try Supabase first ────────────────────────────────────────────
  const sb = getSupabaseServerClient();
  if (sb) {
    try {
      // Check if demo user already exists
      const { data: existing } = await sb
        .from("users")
        .select("id, email")
        .eq("email", DEMO_EMAIL)
        .single();

      if (existing) {
        return { ok: true, email: DEMO_EMAIL, password: DEMO_PASSWORD, source: "supabase-existing" };
      }

      // Create demo user with bcrypt hash
      const passwordHash = await bcrypt.hash(DEMO_PASSWORD, 10);
      const userId = crypto.randomUUID();

      const { error: insertError } = await sb.from("users").upsert(
        {
          id: userId,
          email: DEMO_EMAIL,
          name: DEMO_NAME,
          password: passwordHash,
          role: "ADMIN",
        },
        { onConflict: "email" }
      );

      if (insertError) {
        console.warn("[demo] Supabase user insert failed:", insertError.message);
      }

      // Create workspace
      const workspaceId = crypto.randomUUID();
      await sb.from("workspaces").upsert(
        {
          id: workspaceId,
          name: "Demo Workspace",
          slug: "demo",
          plan: "team",
          created_by: userId,
        },
        { onConflict: "id" }
      );

      // Create membership
      await sb.from("memberships").upsert(
        {
          user_id: userId,
          workspace_id: workspaceId,
          role: "ADMIN",
        },
        { onConflict: "user_id,workspace_id" }
      );

      return { ok: true, email: DEMO_EMAIL, password: DEMO_PASSWORD, source: "supabase-created" };
    } catch (err: any) {
      console.warn("[demo] Supabase seed failed, trying fallback:", err.message);
    }
  }

  // ── Try Flask backend (legacy) ────────────────────────────────────
  const AEON_URL = (process.env.AEON_PYTHON_URL || "").replace(/\/$/, "");
  if (AEON_URL) {
    try {
      let res = await fetch(`${AEON_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: DEMO_EMAIL, password: DEMO_PASSWORD, name: DEMO_NAME }),
      });
      let data = await res.json();
      if (!data.ok) {
        res = await fetch(`${AEON_URL}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: DEMO_EMAIL, password: DEMO_PASSWORD }),
        });
        data = await res.json();
      }
      if (data.ok) return { ok: true, email: DEMO_EMAIL, password: DEMO_PASSWORD, source: "flask" };
    } catch {
      // Flask not reachable — fall through
    }
  }

  // ── Return demo credentials — auth.ts fallback admin handles this ─
  return { ok: true, email: DEMO_EMAIL, password: DEMO_PASSWORD, source: "fallback" };
}

export async function POST(_req: NextRequest) {
  try {
    const result = await seedDemoUser();
    if (!result.ok) {
      return NextResponse.json({ ok: false, error: "Could not create demo user" }, { status: 500 });
    }
    return NextResponse.json({
      ok: true,
      email: result.email,
      password: result.password,
    });
  } catch (err: any) {
    return NextResponse.json({ ok: false, error: err.message || "Demo seed failed" }, { status: 500 });
  }
}
