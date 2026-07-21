import { NextResponse } from "next/server";
import { auth } from "@/auth";
import { requireRole } from "@/lib/auth";
import { testConnector, queryConnector, CONNECTORS, ConnectorConfig } from "@/lib/connectors";

export const dynamic = "force-dynamic";

/**
 * GET /api/connectors
 * Returns the catalog of available connector definitions.
 * Requires authentication.
 */
export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
  }

  const catalog = Object.values(CONNECTORS).map((c) => ({
    id: c.id,
    name: c.name,
    type: c.type,
    description: c.description,
    requiredSecrets: c.requiredSecrets,
    optionalSecrets: c.optionalSecrets,
  }));

  return NextResponse.json({ ok: true, catalog });
}

/**
 * POST /api/connectors
 * Body: { action: "test" | "query", config: ConnectorConfig, sql?: string }
 * Tests or queries a connector. Restricted to OPERATOR/ADMIN.
 */
export async function POST(req: Request) {
  try {
    const session = await auth();
    requireRole(session, ["ADMIN", "OPERATOR"]);

    const body = (await req.json().catch(() => ({}))) as {
      action?: "test" | "query";
      config?: ConnectorConfig;
      sql?: string;
    };

    const { action = "test", config, sql } = body;

    if (!config) {
      return NextResponse.json({ ok: false, error: "missing config" }, { status: 400 });
    }

    let result;
    if (action === "query") {
      if (!sql) {
        return NextResponse.json({ ok: false, error: "missing sql" }, { status: 400 });
      }
      result = await queryConnector(config, sql);
    } else {
      result = await testConnector(config);
    }

    return NextResponse.json(result);
  } catch (err: any) {
    const status = err?.message === "unauthorized" ? 401 : err?.message === "forbidden" ? 403 : 500;
    return NextResponse.json({ ok: false, error: err?.message || String(err) }, { status });
  }
}
