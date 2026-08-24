// Minimal diagnostic endpoint: if this fails while static pages render,
// the Node function runtime itself is broken (not app code).
export const dynamic = "force-dynamic";

export async function GET() {
  return new Response(
    JSON.stringify({
      ok: true,
      node: process.version,
      platform: process.platform,
      hasAuthSecret: Boolean(process.env.AUTH_SECRET || process.env.NEXTAUTH_SECRET),
    }),
    { status: 200, headers: { "content-type": "application/json" } }
  );
}
