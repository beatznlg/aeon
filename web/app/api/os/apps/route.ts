import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/auth";
import { APPS } from "@/lib/apps";

export const dynamic = "force-dynamic";

/**
 * The AEON app registry is served from the frontend catalog (web/lib/apps.ts),
 * but each workspace's installed set must survive server restarts and reboots.
 * Persist it as a JSON file per workspace (same pattern as web/lib/local-users.ts):
 * the path is resolved at request time so Vercel's output tracer cannot
 * statically lstat the file during the build.
 */
function storeFile(): string {
  const dir = process.env.AEON_LOCAL_DATA_DIR;
  const base = dir && dir.length > 0 ? dir : process.cwd();
  return base + "/.data/apps-" + "installed" + ".json";
}

interface InstalledStore {
  [workspaceId: string]: string[];
}

function loadStore(): InstalledStore {
  try {
    const fs = require("fs");
    const file = storeFile();
    if (!fs.existsSync(file)) return {};
    const parsed = JSON.parse(fs.readFileSync(file, "utf-8"));
    return parsed && typeof parsed === "object" ? (parsed as InstalledStore) : {};
  } catch {
    return {};
  }
}

function saveStore(store: InstalledStore): boolean {
  try {
    const fs = require("fs");
    const path = require("path");
    const file = storeFile();
    fs.mkdirSync(path.dirname(file), { recursive: true });
    fs.writeFileSync(file, JSON.stringify(store, null, 2), { encoding: "utf-8", mode: 0o600 });
    return true;
  } catch (err) {
    console.warn("[apps] failed to persist installed store:", err);
    return false;
  }
}

async function getWorkspaceId(): Promise<string> {
  try {
    const session = await auth();
    return ((session?.user as { workspaceId?: string } | undefined)?.workspaceId as string) || "default";
  } catch {
    return "default";
  }
}

export async function GET() {
  const workspaceId = await getWorkspaceId();
  const store = loadStore();
  const installed = store[workspaceId] || [];
  return NextResponse.json({ ok: true, apps: APPS, installed, workspaceId });
}

export async function POST(req: NextRequest) {
  const workspaceId = await getWorkspaceId();
  const body = await req.json().catch(() => ({}));
  const appId = String(body.appId || "").trim();
  const exists = APPS.some((a) => a.id === appId);
  if (!exists) {
    return NextResponse.json({ ok: false, error: "unknown app" }, { status: 400 });
  }
  const store = loadStore();
  const installed = store[workspaceId] || [];
  if (!installed.includes(appId)) {
    installed.push(appId);
    store[workspaceId] = installed;
    saveStore(store);
  }
  return NextResponse.json({ ok: true, appId, installed });
}

export async function DELETE(req: NextRequest) {
  const workspaceId = await getWorkspaceId();
  const body = await req.json().catch(() => ({}));
  const appId = String(body.appId || "").trim();
  const store = loadStore();
  const installed = (store[workspaceId] || []).filter((id) => id !== appId);
  store[workspaceId] = installed;
  saveStore(store);
  return NextResponse.json({ ok: true, appId, installed });
}
