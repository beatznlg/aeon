import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/lib/proxy";

export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  return proxyApiRequest(req, { backendPath: "/dashboard/stats" });
}
