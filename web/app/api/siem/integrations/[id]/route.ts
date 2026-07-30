import { NextRequest } from "next/server";
import { proxySiemRequest } from "@/lib/siem-proxy";

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  return proxySiemRequest(request, {
    backendPath: `/siem/integrations/${params.id}`,
  });
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  return proxySiemRequest(request, {
    backendPath: `/siem/integrations/${params.id}`,
  });
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  return proxySiemRequest(request, {
    backendPath: `/siem/integrations/${params.id}`,
  });
}
