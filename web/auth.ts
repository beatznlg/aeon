import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
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
const AUTH_SECRET = process.env.AUTH_SECRET || process.env.NEXTAUTH_SECRET || "";
const TRUST_HOST = process.env.AUTH_TRUST_HOST !== "false";
const DEMO_ENABLED = process.env.AEON_DEMO_ENABLED === "true" || process.env.NODE_ENV !== "production";
const DEMO_EMAIL = process.env.AEON_DEMO_EMAIL || "admin@demo.local";
const DEMO_PASSWORD = process.env.AEON_DEMO_PASSWORD || "demo123";
const DEMO_WORKSPACE_ID = process.env.AEON_DEMO_WORKSPACE_ID || "demo-workspace";

if (process.env.NODE_ENV === "production" && AUTH_SECRET.length < 32) {
  throw new Error("AUTH_SECRET/NEXTAUTH_SECRET must be at least 32 characters in production");
}

async function loginViaFlask(email: string, password: string): Promise<AeonUser | null> {
  try {
    const res = await fetch(`${AEON_PYTHON_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
      signal: AbortSignal.timeout(4000),
      cache: "no-store",
    });
    if (!res.ok) return null;
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
  ...(AUTH_SECRET ? { secret: AUTH_SECRET } : {}),
  trustHost: TRUST_HOST,
  session: { strategy: "jwt" },
  pages: { signIn: "/login" },
  providers: [
    Credentials({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const email = String(credentials?.email || "").trim().toLowerCase();
        const password = String(credentials?.password || "");
        if (!email || !password) return null;

        // Oracle production source of truth: Flask + PostgreSQL.
        const flaskUser = await loginViaFlask(email, password);
        if (flaskUser) return flaskUser;

        // Demo is an explicit opt-in in production and uses configurable credentials.
        if (DEMO_ENABLED && email === DEMO_EMAIL && password === DEMO_PASSWORD) {
          return {
            id: "admin-fallback",
            email: DEMO_EMAIL,
            name: "Demo Admin",
            role: "ADMIN",
            workspaceId: DEMO_WORKSPACE_ID,
          };
        }

        // Development/offline bootstrap only.
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
