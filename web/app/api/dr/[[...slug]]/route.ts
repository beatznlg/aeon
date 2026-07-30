import { NextRequest } from "next/server";
import { proxyApiRequest } from "@/lib/proxy";

function getBackendPath(req: NextRequest): string {
  return req.nextUrl.pathname.replace(/^\/api/, "");
}

export async function GET(req: NextRequest) {
  return proxyApiRequest(req, { backendPath: getBackendPath(req) });
}

export async function POST(req: NextRequest) {
  return proxyApiRequest(req, { backendPath: getBackendPath(req) });
}

export async function PATCH(req: NextRequest) {
  return proxyApiRequest(req, { backendPath: getBackendPath(req) });
}

export async function DELETE(req: NextRequest) {
  return proxyApiRequest(req, { backendPath: getBackendPath(req) });
}
