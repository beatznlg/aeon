/**
 * AEON Kernel Proxy
 *
 * If `AEON_PYTHON_URL` is configured, chat / tick requests are forwarded to the
 * Python ReflectiveAgent kernel. Otherwise the caller falls back to the
 * existing TypeScript implementation.
 */

export interface KernelResponse<T = unknown> {
  ok: boolean;
  data?: T;
  error?: string;
  backend?: string;
}

export function pythonUrl(): string | undefined {
  return process.env.AEON_PYTHON_URL;
}

export async function kernelChat(
  query: string,
  system?: string,
): Promise<KernelResponse<{ answer: string; backend: string }> | null> {
  const url = pythonUrl();
  if (!url) return null;

  const res = await fetch(`${url}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, system }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`AEON kernel chat failed (${res.status}): ${text}`);
  }

  const json = (await res.json()) as {
    ok: boolean;
    data?: { answer?: string; backend?: string };
    error?: string;
  };
  if (!json.ok) {
    throw new Error(json.error || "AEON kernel returned ok=false");
  }

  return {
    ok: true,
    data: {
      answer: json.data?.answer ?? "",
      backend: json.data?.backend ?? "aeon_python",
    },
  };
}

export async function kernelAppChat(
  appId: string,
  query: string,
  system?: string,
): Promise<KernelResponse<{ answer: string; backend: string }> | null> {
  const url = pythonUrl();
  if (!url) return null;

  const res = await fetch(`${url}/apps/${encodeURIComponent(appId)}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, system }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`AEON kernel app chat failed (${res.status}): ${text}`);
  }

  const json = (await res.json()) as {
    ok: boolean;
    data?: { answer?: string; backend?: string };
    error?: string;
  };
  if (!json.ok) {
    throw new Error(json.error || "AEON kernel returned ok=false");
  }

  return {
    ok: true,
    data: {
      answer: json.data?.answer ?? "",
      backend: json.data?.backend ?? "aeon_python",
    },
  };
}

export async function kernelTick(
  appId: string,
  query: string,
  asyncMode = false,
): Promise<KernelResponse<unknown> | null> {
  const url = pythonUrl();
  if (!url) return null;

  const res = await fetch(`${url}/apps/${encodeURIComponent(appId)}/tick`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, async: asyncMode }),
  });

  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`AEON kernel tick failed (${res.status}): ${text}`);
  }

  return (await res.json()) as KernelResponse<unknown>;
}
