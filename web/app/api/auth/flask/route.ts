import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import { getSupabaseServerClient } from "@/lib/supabase";
import { createLocalUser, verifyLocalUser } from "@/lib/local-users";

const AEON_PYTHON_URL = process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000";

/**
 * Server-side proxy for the AEON Python backend auth endpoints.
 *
 * The browser must not call the Flask origin directly (it is often a private
 * 127.0.0.1 address or a CORS-restricted host), so the login page and the
 * flask-auth helpers route login/register through this Next.js route instead.
 *
 * Body: { action: "login" | "register", email, password, name? }
 *
 * Fallback order when the backend is unreachable:
 *   1. Supabase — durable multi-tenant user store (production path; the
 *      serverless filesystem is read-only, so this is what keeps registrations
 *      alive on the deployed site).
 *   2. Local file store (web/lib/local-users.ts) — offline/demo fallback that
 *      only persists where the server filesystem is writable.
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const action = body?.action === "register" ? "register" : "login";
    const email = String(body?.email || "").trim().toLowerCase();
    const password = String(body?.password || "");
    const name = body?.name ? String(body.name).trim() : undefined;

    if (!email || !password) {
      return NextResponse.json(
        { ok: false, error: "MISSING_CREDENTIALS" },
        { status: 400 }
      );
    }

    // ── Try the Flask backend first ──────────────────────────────────
    let backendStatus = 0;
    try {
      const res = await fetch(`${AEON_PYTHON_URL}/auth/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, name }),
        // Don't let a hanging backend stall the login page for long.
        signal: AbortSignal.timeout(4000),
      });
      backendStatus = res.status;
      const data = await res.json();
      // When registration succeeds on the Flask backend, also save the user
      // locally so they can log in even if the backend later becomes
      // unreachable (e.g. the container restarts or crashes).  This is a
      // write-through cache — the authoritative store remains PostgreSQL.
      if (action === "register" && data?.ok) {
        try {
          createLocalUser(email, password, name);
        } catch {
          // Best-effort: local store failure must not block registration.
        }
      }
      // Forward the backend's response verbatim (including errors like
      // EMAIL_TAKEN / INVALID_CREDENTIALS) — do not double-register.
      return NextResponse.json(data, { status: res.status });
    } catch {
      // Backend unreachable — fall through to Supabase / local store.
    }

    // Backend answered but is broken (5xx without a usable body) — treat like
    // unreachable and fall through to Supabase / local store so registration
    // and login survive a wedged backend restart. 4xx responses above were
    // real validation or auth errors and were already returned verbatim.
    if (backendStatus < 500) {
      return NextResponse.json(
        { ok: false, error: "INVALID_CREDENTIALS" },
        { status: 401 }
      );
    }

    // ── Supabase (durable, production) ───────────────────────────────
    const sb = getSupabaseServerClient();
    if (sb) {
      if (action === "register") {
        const { data: existing } = await sb
          .from("users")
          .select("id")
          .eq("email", email)
          .maybeSingle();
        if (existing) {
          return NextResponse.json(
            { ok: false, error: "EMAIL_TAKEN" },
            { status: 409 }
          );
        }
        const passwordHash = await bcrypt.hash(password, 10);
        const userId = `user_${crypto.randomUUID()}`;
        const workspaceId = `ws_${crypto.randomUUID()}`;
        const displayName = name || email.split("@")[0];

        const { error: insertError } = await sb.from("users").insert({
          id: userId,
          email,
          name: displayName,
          password: passwordHash,
          role: "ADMIN",
        });
        if (insertError) {
          console.warn("[auth] Supabase user insert failed:", insertError.message);
          return NextResponse.json(
            { ok: false, error: "REGISTRATION_FAILED" },
            { status: 500 }
          );
        }

        // Personal workspace + membership so the user can run the setup wizard.
        await sb.from("workspaces").insert({
          id: workspaceId,
          name: `${displayName}'s Workspace`,
          slug: email.split("@")[0].toLowerCase().replace(/[^a-z0-9-]/g, "-"),
          plan: "team",
          created_by: userId,
        });
        await sb.from("memberships").insert({
          user_id: userId,
          workspace_id: workspaceId,
          role: "ADMIN",
        });

        return NextResponse.json(
          {
            ok: true,
            token: `sb-${userId}`,
            user: {
              id: userId,
              email,
              name: displayName,
              role: "ADMIN",
              workspace_id: workspaceId,
            },
          },
          { status: 200 }
        );
      }

      // login — verify against the Supabase users table
      const { data: user, error } = await sb
        .from("users")
        .select("id, email, name, password, role")
        .eq("email", email)
        .maybeSingle();
      if (!error && user?.password) {
        const isValid = await bcrypt.compare(password, String(user.password));
        if (isValid) {
          const { data: membership } = await sb
            .from("memberships")
            .select("workspace_id, role")
            .eq("user_id", user.id)
            .limit(1)
            .maybeSingle();
          return NextResponse.json(
            {
              ok: true,
              token: `sb-${user.id}`,
              user: {
                id: user.id,
                email: user.email,
                name: user.name,
                role: (membership?.role as string) || user.role || "ADMIN",
                workspace_id: membership?.workspace_id,
              },
            },
            { status: 200 }
          );
        }
        return NextResponse.json(
          { ok: false, error: "INVALID_CREDENTIALS" },
          { status: 401 }
        );
      }
    }

    // ── Offline fallback (no backend, no Supabase) ───────────────────
    if (action === "register") {
      const user = createLocalUser(email, password, name);
      if (!user) {
        return NextResponse.json(
          { ok: false, error: "EMAIL_TAKEN" },
          { status: 409 }
        );
      }
      return NextResponse.json(
        {
          ok: true,
          token: `local-${user.id}`,
          user: {
            id: user.id,
            email: user.email,
            name: user.name,
            role: user.role,
            workspace_id: user.workspaceId,
          },
        },
        { status: 200 }
      );
    }

    const user = verifyLocalUser(email, password);
    if (!user) {
      return NextResponse.json(
        { ok: false, error: "INVALID_CREDENTIALS" },
        { status: 401 }
      );
    }
    return NextResponse.json(
      {
        ok: true,
        token: `local-${user.id}`,
        user: {
          id: user.id,
          email: user.email,
          name: user.name,
          role: user.role,
          workspace_id: user.workspaceId,
        },
      },
      { status: 200 }
    );
  } catch {
    return NextResponse.json(
      {
        ok: false,
        error:
          "AEON backend unreachable — is the Python server running? Start it with `npm run dev:full` from web/, or set AEON_PYTHON_URL.",
      },
      { status: 502 }
    );
  }
}
