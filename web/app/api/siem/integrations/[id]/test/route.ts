import { NextRequest } from "next/server";
import { proxySiemRequest } from "@/lib/siem-proxy";

export async function POST(request: NextRequest, context: { params: Promise<{ id: string }> }) {
  const params = await context.params;
  return proxySiemRequest(request, {
    backendPath: `/siem/integrations/${params.id}/test`,
  });
}
