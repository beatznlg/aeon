import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const q = String(body.query || "").trim();
  const limit = Math.min(5, Math.max(1, Number(body.limit || 5)));
  if (!q) {
    return NextResponse.json({ ok: false, error: "empty query", items: [] });
  }

  const headers: Record<string, string> = {
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "AEON-Web-UI/1.0",
  };
  const token = process.env.GH_TOKEN || process.env.GITHUB_TOKEN;
  if (token) headers["Authorization"] = "Bearer " + token;

  try {
    const r = await fetch(
      `https://api.github.com/search/code?q=${encodeURIComponent(q)}&per_page=${limit}`,
      { headers, cache: "no-store" },
    );
    if (r.status !== 200) {
      return NextResponse.json({
        ok: false, error: "HTTP " + r.status, items: [], snippet: (await r.text()).slice(0, 160),
      });
    }
    const j = await r.json();
    const items = (j.items || []).slice(0, limit).map((it: any) => ({
      name: it.name,
      path: it.path,
      html_url: it.html_url,
      repo: it.repository?.full_name,
    }));
    return NextResponse.json({ ok: true, total: j.total_count || 0, items });
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e?.message || String(e), items: [] });
  }
}
