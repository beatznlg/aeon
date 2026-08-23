/**
 * Offline-capable user store (server-only).
 *
 * AEON's identity layer normally authenticates against the Flask backend or
 * Supabase. When neither is reachable (e.g. a frontend-only preview session),
 * registration and login still need to work for a fully functional demo. This
 * module persists users to a local JSON file on the server's filesystem so the
 * credentials flow (register → sign in → session) works end to end.
 *
 * Security notes:
 * - Passwords are stored as bcrypt hashes only — never plaintext.
 * - The file lives outside the public web root (web/.data/aeon-users.json).
 * - This is a demo/offline fallback. When Supabase or the Flask backend is
 *   configured and reachable, those remain authoritative and this store is
 *   only consulted as a last resort.
 */

import bcrypt from "bcryptjs";
import fs from "fs";
import path from "path";

export type LocalRole = "ADMIN" | "OPERATOR" | "VIEWER";

export interface LocalUser {
  id: string;
  email: string;
  name: string;
  passwordHash: string;
  role: LocalRole;
  workspaceId: string;
  createdAt: string;
}

export type LocalUserPublic = Omit<LocalUser, "passwordHash">;

const DATA_DIR = path.resolve(process.cwd(), ".data");
const USERS_FILE = path.join(DATA_DIR, "aeon-users.json");

function normalizeEmail(email: string): string {
  return String(email || "").trim().toLowerCase();
}

function loadUsers(): LocalUser[] {
  try {
    if (!fs.existsSync(USERS_FILE)) return [];
    const raw = fs.readFileSync(USERS_FILE, "utf-8");
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as LocalUser[]) : [];
  } catch {
    // Corrupt or unreadable store — treat as empty rather than crash.
    return [];
  }
}

function saveUsers(users: LocalUser[]): boolean {
  try {
    fs.mkdirSync(DATA_DIR, { recursive: true });
    fs.writeFileSync(USERS_FILE, JSON.stringify(users, null, 2), {
      encoding: "utf-8",
      mode: 0o600,
    });
    return true;
  } catch (err) {
    console.warn("[local-users] failed to persist user store:", err);
    return false;
  }
}

function toPublic(user: LocalUser): LocalUserPublic {
  return {
    id: user.id,
    email: user.email,
    name: user.name,
    role: user.role,
    workspaceId: user.workspaceId,
    createdAt: user.createdAt,
  };
}

export function findLocalUser(email: string): LocalUserPublic | null {
  const normalized = normalizeEmail(email);
  if (!normalized) return null;
  const user = loadUsers().find((u) => u.email === normalized);
  return user ? toPublic(user) : null;
}

/**
 * Verify credentials against the local store.
 * Returns the public user on success, null on unknown email or wrong password.
 */
export function verifyLocalUser(
  email: string,
  password: string
): LocalUserPublic | null {
  const normalized = normalizeEmail(email);
  if (!normalized || !password) return null;
  const user = loadUsers().find((u) => u.email === normalized);
  if (!user) return null;
  try {
    return bcrypt.compareSync(password, user.passwordHash) ? toPublic(user) : null;
  } catch {
    return null;
  }
}

/**
 * Create a user in the local store.
 * Returns the public user, or null if the email is already registered.
 */
export function createLocalUser(
  email: string,
  password: string,
  name?: string
): LocalUserPublic | null {
  const normalized = normalizeEmail(email);
  if (!normalized || !password || password.length < 6) return null;
  const users = loadUsers();
  if (users.some((u) => u.email === normalized)) return null;

  const id = `user_${crypto.randomUUID()}`;
  const user: LocalUser = {
    id,
    email: normalized,
    name: (name || "").trim() || normalized.split("@")[0],
    passwordHash: bcrypt.hashSync(password, 10),
    role: "ADMIN",
    workspaceId: `ws_${crypto.randomUUID()}`,
    createdAt: new Date().toISOString(),
  };
  users.push(user);
  if (!saveUsers(users)) return null;
  return toPublic(user);
}
