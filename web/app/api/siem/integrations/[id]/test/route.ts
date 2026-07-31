import { NextRequest } from "next/server";
import { proxySiemRequest } from "@/lib/siem-proxy";

export async function POST(request: NextRequest, { params }: { params: { id: string } }) {
  return proxySiemRequest(request, {
    backendPath: `/siem/integrations/${params.id}/test`,
  });
}
