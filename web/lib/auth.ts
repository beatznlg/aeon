import { auth } from "@/auth";

export type AeonRole = "ADMIN" | "OPERATOR" | "VIEWER";

export interface AuthContext {
  id?: string;
  email?: string | null;
  role?: string;
  workspaceId?: string;
}

export function getRole(session: any): AeonRole {
  return ((session?.user as any)?.role as AeonRole) || "VIEWER";
}

export function isAdmin(session: any): boolean {
  return getRole(session) === "ADMIN";
}

export function isOperator(session: any): boolean {
  return ["ADMIN", "OPERATOR"].includes(getRole(session));
}

export function requireAuth(session: any): AuthContext {
  if (!session?.user) {
    throw new Error("unauthorized");
  }
  return {
    id: (session.user as any).id as string,
    email: session.user.email,
    role: (session.user as any).role as string,
    workspaceId: (session.user as any).workspaceId as string | undefined,
  };
}

export function requireRole(session: any, allowed: AeonRole[]): AuthContext {
  const ctx = requireAuth(session);
  if (!allowed.includes(getRole(session))) {
    throw new Error("forbidden");
  }
  return ctx;
}

export async function currentSession(): Promise<AuthContext | null> {
  const s = await auth();
  if (!s?.user) return null;
  return {
    id: (s.user as any).id as string,
    email: s.user.email,
    role: (s.user as any).role as string,
    workspaceId: (s.user as any).workspaceId as string | undefined,
  };
}
