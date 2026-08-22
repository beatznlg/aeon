import { NextRequest } from "next/server";
import { proxySiemRequest } from "@/lib/siem-proxy";

export async function GET(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const params = await context.params;
  return proxySiemRequest(request, {
    backendPath: `/siem/integrations/${params.id}`,
  });
}

export async function PATCH(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const params = await context.params;
  return proxySiemRequest(request, {
    backendPath: `/siem/integrations/${params.id}`,
  });
}

export async function DELETE(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const params = await context.params;
  return proxySiemRequest(request, {
    backendPath: `/siem/integrations/${params.id}`,
  });
}
