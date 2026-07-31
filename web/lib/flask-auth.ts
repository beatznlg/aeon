/**
 * AEON Flask JWT auth bridge.
 * Manages the Flask backend JWT token in localStorage,
 * bridging NextAuth frontend auth with Flask backend auth.
 */

const FLASK_TOKEN_KEY = "aeon_flask_token";
const FLASK_USER_KEY = "aeon_flask_user";
const AEON_URL = process.env.NEXT_PUBLIC_AEON_PYTHON_URL || "http://127.0.0.1:5000";

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
    const res = await fetch(`${AEON_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
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
    const res = await fetch(`${AEON_URL}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name: name || email.split("@")[0] }),
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
