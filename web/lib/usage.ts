/**
 * AEON OS Usage Metering
 *
 * Fire-and-forget logging of usage events. If AEON_PYTHON_URL is configured,
 * events are forwarded to the Python backend for persistence and billing.
 * Otherwise they are silently dropped (graceful degradation).
 */

import { pythonUrl } from "./kernel";

export interface UsagePayload {
  userId?: string;
  workspaceId?: string;
  action: string;
  module?: string;
  quantity?: number;
  cost?: number;
  metadata?: Record<string, any>;
}

export async function logUsage(payload: UsagePayload) {
  const url = pythonUrl();
  if (!url) {
    return;
  }

  try {
    await fetch(`${url}/usage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: payload.action,
        module: payload.module || "global",
        quantity: payload.quantity ?? 1,
        cost: payload.cost ?? 0,
        user_id: payload.userId,
        workspace_id: payload.workspaceId,
        metadata: payload.metadata ?? {},
      }),
    });
  } catch {
    // Usage logging must never break the caller.
  }
}
