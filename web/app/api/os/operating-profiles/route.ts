import { NextRequest, NextResponse } from "next/server";
import { backendFetch } from "@/lib/backend-fetch";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const query = req.nextUrl.searchParams.toString();
  return backendFetch(req, query ? `/operating-profiles?${query}` : "/operating-profiles");
}

export async function PUT(req: NextRequest) {
  return backendFetch(req, "/workspace/operating-profile", { method: "PUT" });
}
