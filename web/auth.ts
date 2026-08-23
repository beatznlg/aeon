import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import bcrypt from "bcryptjs";
import { getSupabaseServerClient } from "@/lib/supabase";
import { verifyLocalUser } from "@/lib/local-users";

export type AeonRole = "ADMIN" | "OPERATOR" | "VIEWER";

interface AeonUser {
  id: string;
  email: string;
  name?: string | null;
  role: AeonRole;
  workspaceId?: string;
}

const AEON_PYTHON_URL = (process.env.AEON_PYTHON_URL || "http://127.0.0.1:5000").replace(/\/$/, "");
// Always provide a fallback so NextAuth boots without explicit configuration.
// In production, override with a strong random value via AUTH_SECRET.
const AUTH_SECRET = process.env.AUTH_SECRET || process.env.NEXTAUTH_SECRET || "aeon-dev-fallback-do-not-use-in-production";
// NextAuth refuses to run on unknown hosts in production unless explicitly
// trusted. Managed hosts (Vercel, Freebuff hosting) all pass the real public
// URL in the request, so default to trusted and only opt out explicitly via
// AUTH_TRUST_HOST=false.
const TRUST_HOST =
  process.env.VERCEL === "1" ||
  process.env.AUTH_TRUST_HOST === "true" ||
  process.env.AUTH_TRUST_HOST === "1" ||
  process.env.AUTH_TRUST_HOST !== "false";

/**
 * Fallback admin user that works when Supabase is not configured.
 * This lets the project boot and the first admin log in immediately.
 */
const DEMO_EMAIL = "admin@demo.local";
const DEMO_PASSWORD = "demo123";
const DEMO_WORKSPACE_ID = "demo-workspace";

function getFallbackAdmin(): AeonUser | null {
  // Always allow the built-in demo account so users can try AEON without
  // configuring any environment variables. Production admin credentials
  // are handled separately via ADMIN_EMAIL / ADMIN_PASSWORD_HASH.
  if (process.env.ADMIN_EMAIL) {
    return {
      id: "admin-fallback",
      email: process.env.ADMIN_EMAIL,
      name: "Administrator",
      role: "ADMIN" as AeonRole,
      workspaceId: DEMO_WORKSPACE_ID,
    };
  }
  // Built-in demo account fallback. The id matches the Flask backend's
  // platform admin (aeon_auth._FallbackAdmin.id) so the proxy's X-User-Id
  // header grants workspace-scoped access when the backend is running but
  // the demo user has not been registered there yet.
  return {
    id: "admin-fallback",
    email: DEMO_EMAIL,
    name: "Demo Admin",
    role: "ADMIN" as AeonRole,
    workspaceId: DEMO_WORKSPACE_ID,
  };
}

async function verifyFallbackPassword(password: string): Promise<boolean> {
  // Built-in demo account
  if (password === DEMO_PASSWORD) return true;

  const configuredPassword = process.env.ADMIN_PASSWORD;
  if (!configuredPassword) return false;
  return password === configuredPassword;
}

/**
 * Authenticate against the AEON Flask backend.
 *
 * The frontend identity layer (NextAuth/Supabase) and the Python backend keep
 * users in separate stores, so a user registered through the backend (e.g. the
 * one-click demo account or the "Create Account" tab) is invisible to NextAuth.
 * This bridge lets those backend users sign in through the normal NextAuth
 * credentials flow while Supabase users and the env fallback admin still work.
 */
async function loginViaFlask(email: string, password: string): Promise<AeonUser | null> {
  try {
    const res = await fetch(`${AEON_PYTHON_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
      // Don't let a half-up backend stall the login flow.
      signal: AbortSignal.timeout(4000),
    });
    const data = await res.json();
    if (!data?.ok || !data?.user?.id) return null;
    return {
      id: String(data.user.id),
      email: String(data.user.email),
      name: data.user.name || null,
      role: (data.user.role as AeonRole) || "VIEWER",
      workspaceId: data.user.workspace_id,
    };
  } catch {
    return null;
  }
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  secret: AUTH_SECRET,
  trustHost: TRUST_HOST,
  session: { strategy: "jwt" },
  pages: {
    signIn: "/login",
  },
  providers: [
    Credentials({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) return null;

        const email = credentials.email as string;
        const password = credentials.password as string;

        // ── AEON Flask backend bridge ─────────────────────────────────
        // Authenticate first against the Python backend so users registered
        // there (self-service signups and the seeded demo account) use their
        // real workspace + membership instead of the frontend fallback.
        const flaskUser = await loginViaFlask(email, password);
        if (flaskUser) return flaskUser;

        // ── Fallback admin (no Supabase required) ─────────────────────
        const fallback = getFallbackAdmin();
        if (fallback && (fallback.email === email || email === DEMO_EMAIL)) {
          const ok = await verifyFallbackPassword(password);
          if (!ok) return null;
          return { ...fallback, email };
        }

        // ── Supabase-backed user lookup ───────────────────────────────
        const sb = getSupabaseServerClient();
        if (sb) {
          const { data: user, error } = await sb
            .from("users")
            .select("id, email, name, password, role")
            .eq("email", email)
            .single();

          if (!error && user?.password) {
            const isValid = await bcrypt.compare(password, String(user.password));
            if (isValid) {
              let workspaceId: string | undefined;
              let workspaceRole = user.role as AeonRole;
              try {
                const { data: membership } = await sb
                  .from("memberships")
                  .select("workspace_id, role")
                  .eq("user_id", user.id)
                  .limit(1)
                  .maybeSingle();
                workspaceId = membership?.workspace_id;
                workspaceRole = (membership?.role as AeonRole) || workspaceRole;
              } catch {
                // Older Supabase schemas may not expose memberships; keep the
                // authenticated user role and let the setup gate explain the gap.
              }
              return {
                id: user.id,
                email: user.email,
                name: user.name,
                role: workspaceRole,
                workspaceId,
              };
            }
            // Known Supabase user with a wrong password — do not fall through
            // to the backend with the same credentials.
            return null;
          }
          // Supabase configured but this user isn't there → try the backend.
        } else {
          console.warn("[auth] Supabase not configured; falling back to AEON backend");
        }

        // ── Offline local user store ──────────────────────────────────
        // Lets users registered while the backend was unreachable (see
        // /api/auth/flask fallback) sign in even in frontend-only sessions.
        const localUser = verifyLocalUser(email, password);
        if (localUser) {
          return {
            id: localUser.id,
            email: localUser.email,
            name: localUser.name,
            role: localUser.role as AeonRole,
            workspaceId: localUser.workspaceId,
          };
        }

        return null;
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id;
        token.role = (user as AeonUser).role;
        token.workspaceId = (user as AeonUser).workspaceId;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.id as string;
        session.user.role = token.role as string;
        session.user.workspaceId = token.workspaceId as string | undefined;
      }
      return session;
    },
  },
});
