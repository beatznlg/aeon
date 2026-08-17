/**
 * AEON Flask JWT auth bridge.
 * Manages the Flask backend JWT token in localStorage,
 * bridging NextAuth frontend auth with Flask backend auth.
 */

const FLASK_TOKEN_KEY = "aeon_flask_token";
const FLASK_USER_KEY = "aeon_flask_user";

/**
 * Auth calls are proxied through a Next.js API route so the browser never has
 * to reach the Flask origin directly (which may be a private 127.0.0.1 address
 * or a CORS-restricted host in hosted/preview environments).
 */
const FLASK_AUTH_PROXY = "/api/auth/flask";

export interface FlaskUser {
  id: string;
  email: string;
  name?: string;
  role: string;
  workspace_id?: string;
}

export function getFlaskToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(FLASK_TOKEN_KEY);
}

export function getFlaskUser(): FlaskUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(FLASK_USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function storeFlaskSession(token: string, user: FlaskUser) {
  if (typeof window !== "undefined") {
    localStorage.setItem(FLASK_TOKEN_KEY, token);
    localStorage.setItem(FLASK_USER_KEY, JSON.stringify(user));
  }
}

export function clearFlaskSession() {
  if (typeof window !== "undefined") {
    localStorage.removeItem(FLASK_TOKEN_KEY);
    localStorage.removeItem(FLASK_USER_KEY);
  }
}

export async function loginToFlask(
  email: string,
  password: string
): Promise<{ token: string; user: FlaskUser } | null> {
  try {
    const res = await fetch(FLASK_AUTH_PROXY, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "login", email, password }),
    });
    const data = await res.json();
    if (data.ok && data.token) {
      return { token: data.token, user: data.user };
    }
    return null;
  } catch {
    return null;
  }
}

export async function registerToFlask(
  email: string,
  password: string,
  name?: string
): Promise<{ token: string; user: FlaskUser } | null> {
  try {
    const res = await fetch(FLASK_AUTH_PROXY, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "register",
        email,
        password,
        name: name || email.split("@")[0],
      }),
    });
    const data = await res.json();
    if (data.ok && data.token) {
      return { token: data.token, user: data.user };
    }
    return null;
  } catch {
    return null;
  }
}

export function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getFlaskToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}
