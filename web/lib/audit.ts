import { getSupabaseServerClient } from "./supabase";

export interface AuditPayload {
  userId?: string;
  email?: string;
  action: string;
  module?: string;
  metadata?: Record<string, any>;
}

export async function logAudit(payload: AuditPayload) {
  const sb = getSupabaseServerClient();
  if (!sb) {
    console.log("[audit]", payload);
    return;
  }

  try {
    await sb.from("audit_logs").insert([
      {
        user_id: payload.userId,
        email: payload.email,
        action: payload.action,
        module: payload.module,
        metadata: payload.metadata ?? {},
        timestamp: new Date().toISOString(),
      },
    ]);
  } catch (err) {
    console.error("[audit] failed to write audit log:", err);
  }
}
