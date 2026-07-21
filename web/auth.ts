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
}

/**
 * Fallback admin user that works when Supabase is not configured.
 * This lets the project boot and the first admin log in immediately.
 */
function getFallbackAdmin(): AeonUser | null {
  const email = process.env.ADMIN_EMAIL;
  const password = process.env.ADMIN_PASSWORD;
  if (!email || !password) return null;
  return {
    id: "admin-fallback",
    email,
    name: "Administrator",
    role: "ADMIN" as AeonRole,
  };
}

export const { handlers, auth, signIn, signOut } = NextAuth({
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
        if (fallback?.email === email) {
          const fallbackPassword = process.env.ADMIN_PASSWORD || "";
          const ok = await bcrypt.compare(password, fallbackPassword);
          if (!ok) return null;
          return fallback;
        }

        // ── Supabase-backed user lookup ───────────────────────────────
        const sb = getSupabaseServerClient();
        if (!sb) {
          console.warn("[auth] Supabase not configured; only fallback admin is available");
          return null;
        }

        const { data: user, error } = await sb
          .from("users")
          .select("id, email, name, password, role")
          .eq("email", email)
          .single();

        if (error || !user?.password) {
          console.error("[auth] user lookup failed:", error?.message);
          return null;
        }

        const isValid = await bcrypt.compare(password, String(user.password));
        if (!isValid) return null;

        return {
          id: user.id,
          email: user.email,
          name: user.name,
          role: user.role as AeonRole,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.id = user.id;
        token.role = (user as AeonUser).role;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.id as string;
        session.user.role = token.role as string;
      }
      return session;
    },
  },
});
