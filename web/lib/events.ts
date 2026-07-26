/**
 * In-memory event bus for real-time SSE delivery.
 * Persists across Next.js hot reloads via `globalThis`.
 * Works for single-instance deployments. For multi-instance,
 * swap this adapter for Redis Pub/Sub or Supabase Realtime.
 */

export interface AeonEvent {
  type:
    | "notification"
    | "notification_read"
    | "swarm_status"
    | "workflow_status"
    | "audit_log"
    | "workspace_activity"
    | "system";
  payload: Record<string, any>;
  user_id?: string;
  workspace_id?: string;
  timestamp: string;
}

interface Client {
  userId: string;
  controller: ReadableStreamDefaultController;
}

declare global {
  var __AEON_EVENT_BUS__: {
    clients: Map<string, Client>;
    broadcast: (event: AeonEvent) => void;
    addClient: (userId: string, controller: ReadableStreamDefaultController) => string;
    removeClient: (id: string) => void;
  } | undefined;
}

function createBus() {
  const clients = new Map<string, Client>();

  const broadcast = (event: AeonEvent) => {
    const data = `data: ${JSON.stringify(event)}\n\n`;
    const encoder = new TextEncoder();
    const bytes = encoder.encode(data);

    for (const [, client] of Array.from(clients.entries())) {
      // If user_id is specified, only send to that user's clients
      if (event.user_id && client.userId !== event.user_id) continue;

      // If workspace_id is specified but user_id isn't, we still send to all clients
      // because we don't have a workspace -> client mapping. The client UI can filter.
      try {
        client.controller.enqueue(bytes);
      } catch {
        // Client disconnected; cleanup happens on cancel
      }
    }
  };

  const addClient = (userId: string, controller: ReadableStreamDefaultController) => {
    const id = `${userId}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
    clients.set(id, { userId, controller });
    return id;
  };

  const removeClient = (id: string) => {
    clients.delete(id);
  };

  return { clients, broadcast, addClient, removeClient };
}

export function getEventBus() {
  if (!globalThis.__AEON_EVENT_BUS__) {
    globalThis.__AEON_EVENT_BUS__ = createBus();
  }
  return globalThis.__AEON_EVENT_BUS__;
}

export function broadcastEvent(event: AeonEvent) {
  getEventBus().broadcast(event);
}
