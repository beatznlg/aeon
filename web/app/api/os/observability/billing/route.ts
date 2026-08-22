import { NextRequest } from "next/server";
import { auth } from "@/auth";
import { backendFetch } from "@/lib/backend-fetch";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const session = await auth();
  const { searchParams } = new URL(req.url);
  const workspaceId =
    searchParams.get("workspace_id") ||
    ((session?.user as any)?.workspaceId as string) ||
    "default";

  return backendFetch(req, `/billing/${encodeURIComponent(workspaceId)}`);
}
