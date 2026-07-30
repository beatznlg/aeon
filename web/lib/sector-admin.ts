/**
 * Sector Admin CRUD Service
 * =========================
 * API helpers for add/edit/delete operations on sector tool data.
 * Calls the Python backend POST/PATCH/DELETE endpoints via the Next.js proxy.
 *
 * All CRUD operations now emit toast notifications automatically.
 */

import { useToast } from "@/lib/toast";

/**
 * React hook that wraps CRUD operations with toast notifications.
 * Use this in your components instead of calling raw CRUD functions.
 */
export function useCrudWithToasts() {
  const { toast } = useToast();

  const create = async (
    sector: string,
    tool: string,
    item: Record<string, unknown>,
    label?: string,
  ) => {
    const result = await createToolItem(sector, tool, item);
    if (result.ok) {
      toast.success(`${label || tool} created`, "Item added successfully");
    } else {
      toast.error(`Failed to create ${label || tool}`, result.error);
    }
    return result;
  };

  const update = async (
    sector: string,
    tool: string,
    idField: string,
    idValue: string,
    updates: Record<string, unknown>,
    label?: string,
  ) => {
    const result = await updateToolItem(sector, tool, idField, idValue, updates);
    if (result.ok) {
      toast.success(`${label || tool} updated`, "Changes saved");
    } else {
      toast.error(`Failed to update ${label || tool}`, result.error);
    }
    return result;
  };

  const remove = async (
    sector: string,
    tool: string,
    idField: string,
    idValue: string,
    label?: string,
  ) => {
    const result = await deleteToolItem(sector, tool, idField, idValue);
    if (result.ok) {
      toast.success(`${label || tool} deleted`, "Item removed");
    } else {
      toast.error(`Failed to delete ${label || tool}`, result.error);
    }
    return result;
  };

  return { create, update, remove };
}


// ─── Types ───────────────────────────────────────────────────────────────────

export interface CrudResult {
  ok: boolean;
  error?: string;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

async function apiCall<T = Record<string, unknown>>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T & CrudResult> {
  try {
    const res = await fetch(`/api/sector/${path}`, {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json() as T;
    if (!res.ok) {
      return { ...(data as unknown as Record<string, unknown>), ok: false, error: (data as unknown as Record<string, unknown>)?.error || `HTTP ${res.status}` } as T & CrudResult;
    }
    return { ...data, ok: true } as T & CrudResult;
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : String(err);
    return { ok: false, error: message } as T & CrudResult;
  }
}

// ─── CRUD Operations ─────────────────────────────────────────────────────────

/**
 * Create a new item in a sector tool's data array (or replace object data).
 * POST /api/sector/:sector/:tool
 */
export async function createToolItem(
  sector: string,
  tool: string,
  item: Record<string, unknown>,
): Promise<CrudResult & { created?: Record<string, unknown> }> {
  return apiCall("POST", `${sector}/${tool}`, item);
}

/**
 * Update an existing item in a sector tool's data array.
 * PATCH /api/sector/:sector/:tool
 * The `idField` and `idValue` identify which item to patch.
 */
export async function updateToolItem(
  sector: string,
  tool: string,
  idField: string,
  idValue: string,
  updates: Record<string, unknown>,
): Promise<CrudResult> {
  // Include the ID field so the backend can find the item
  const body: Record<string, unknown> = { ...updates, [idField]: idValue };
  return apiCall("PATCH", `${sector}/${tool}`, body);
}

/**
 * Update multiple fields on an item in a tool's data array.
 * Accepts the full item to be replaced at the given index.
 * PATCH /api/sector/:sector/:tool with the full item object
 */
export async function replaceToolItem(
  sector: string,
  tool: string,
  fullItem: Record<string, unknown>,
): Promise<CrudResult> {
  return apiCall("PATCH", `${sector}/${tool}`, fullItem);
}

/**
 * Delete an item from a sector tool's data array.
 * DELETE /api/sector/:sector/:tool
 */
export async function deleteToolItem(
  sector: string,
  tool: string,
  idField: string,
  idValue: string,
): Promise<CrudResult> {
  return apiCall("DELETE", `${sector}/${tool}`, { [idField]: idValue });
}

/**
 * Fetch full tool data.
 * GET /api/sector/:sector/:tool
 */
export async function fetchToolData<T = unknown>(
  sector: string,
  tool: string,
): Promise<T & CrudResult> {
  return apiCall<T>("GET", `${sector}/${tool}`);
}
