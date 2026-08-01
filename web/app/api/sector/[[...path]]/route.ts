import { NextRequest, NextResponse } from "next/server";
import { proxyApiRequest } from "@/lib/proxy";
import { generateSectorData } from "@/lib/sector-data-gen";

export const dynamic = "force-dynamic";

/**
 * Sector API Router
 * =================
 * Handles /api/sector/:sector/:tool requests.
 * 1. Tries to proxy to the Python backend first (/sectors/data/<sector>/<tool>)
 * 2. Falls back to generating time-varying local mock data (for live-updating charts)
 */
export async function GET(request: NextRequest, { params }: { params: { path?: string[] } }) {
  const path = params.path || [];
  const [sector, ...rest] = path;
  const tool = rest.join("-");

  // If we have a sector + tool, try Python backend first, then fallback to local generator
  if (sector && tool) {
    // Try to proxy to Python backend (/sectors/data/<sector>/<tool>)
    try {
      const backendPath = `/sectors/data/${path.join("/")}`;
      const proxyRes = await proxyApiRequest(request, { backendPath });
      if (proxyRes.ok) {
        return proxyRes;
      }
    } catch {
      // Proxy unavailable — use local generator
    }

    // Generate time-varying mock data for live-updating charts
    const data = generateSectorData({ sector, tool });
    // Add timestamp so clients can measure freshness
    const dataObj =
      typeof data === "object" && data !== null && !Array.isArray(data)
        ? (data as Record<string, unknown>)
        : {};
    return NextResponse.json({
      ...dataObj,
      _generatedAt: Date.now(),
      _source: "local-dynamic",
    });
  }

  // If no specific sector/tool, proxy to Python backend
  const backendPath = `/sectors/data/${path.join("/")}`;
  return proxyApiRequest(request, { backendPath });
}

export async function POST(request: NextRequest, { params }: { params: { path?: string[] } }) {
  const backendPath = `/sectors/data/${(params.path || []).join("/")}`;
  return proxyApiRequest(request, { backendPath });
}

export async function PATCH(request: NextRequest, { params }: { params: { path?: string[] } }) {
  const backendPath = `/sectors/data/${(params.path || []).join("/")}`;
  return proxyApiRequest(request, { backendPath });
}

export async function DELETE(request: NextRequest, { params }: { params: { path?: string[] } }) {
  const backendPath = `/sectors/data/${(params.path || []).join("/")}`;
  return proxyApiRequest(request, { backendPath });
}
