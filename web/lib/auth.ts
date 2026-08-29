import { auth } from "@/auth";

export type AeonRole = "ADMIN" | "OPERATOR" | "VIEWER" | "OWNER" | "SUPER_ADMIN";

export interface AuthContext {
  id?: string;
  email?: string | null;
  role?: string;
  workspaceId?: string;
}

/** Platform admins: OWNER/SUPER_ADMIN are super-admin roles above ADMIN. */
const PLATFORM_ADMIN_ROLES = ["OWNER", "SUPER_ADMIN", "ADMIN"];

export function isAdminRole(role: string | null | undefined): boolean {
  if (!role) return false;
  return PLATFORM_ADMIN_ROLES.includes(role.toUpperCase());
}

export function getRole(session: any): AeonRole {
  const raw = (session?.user as any)?.role as string | undefined;
  if (!raw) return "VIEWER";
  const upper = raw.toUpperCase();
  return (
    (PLATFORM_ADMIN_ROLES.includes(upper) || upper === "OPERATOR" || upper === "VIEWER"
      ? upper
      : "VIEWER") as AeonRole
  );
}

export function isAdmin(session: any): boolean {
  return isAdminRole(getRole(session));
}

export function isOperator(session: any): boolean {
  return ["ADMIN", "OPERATOR"].includes(getRole(session)) || isAdminRole(getRole(session));
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
