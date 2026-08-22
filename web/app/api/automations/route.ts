import { NextRequest } from "next/server";
import { backendFetch } from "@/lib/backend-fetch";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  return backendFetch(req, "/automations");
}

export async function POST(req: NextRequest) {
  return backendFetch(req, "/automations", { method: "POST" });
}
