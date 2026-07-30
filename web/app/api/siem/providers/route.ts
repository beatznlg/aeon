import { NextRequest } from "next/server";
import { proxySiemRequest } from "@/lib/siem-proxy";

export async function GET(request: NextRequest) {
  return proxySiemRequest(request, { backendPath: "/siem/providers" });
}
