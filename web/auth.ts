import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import bcrypt from "bcryptjs";
import { getSupabaseServerClient } from "@/lib/supabase";

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
const TRUST_HOST = process.env.VERCEL === "1" || process.env.AUTH_TRUST_HOST === "true" || process.env.NODE_ENV !== "production";

/**
 * Fallback admin user that works when Supabase is not configured.
 * This lets the project boot and the first admin log in immediately.
 */
const DEMO_EMAIL = "admin@demo.local";
const DEMO_PASSWORD = "demo123";

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
    };
  }
  // Built-in demo account fallback
  return {
    id: "demo-admin",
    email: DEMO_EMAIL,
    name: "Demo Admin",
    role: "ADMIN" as AeonRole,
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
              return {
                id: user.id,
                email: user.email,
                name: user.name,
                role: user.role as AeonRole,
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

        // ── AEON Flask backend bridge ─────────────────────────────────
        // Authenticates users that live in the Python backend's database
        // (self-service registrations and the one-click demo account).
        const flaskUser = await loginViaFlask(email, password);
        if (flaskUser) return flaskUser;

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
