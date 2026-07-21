import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import { promisify } from "util";
import path from "path";

export const dynamic = "force-dynamic";

function runAeonOS(appId: string, query: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const root = process.cwd();
    const script = `
import json, os
os.environ['AEON_OS_ROOT'] = '${root}/aeon_os_state'
from aeon_os import AeonOS
aos = AeonOS()
aos.install_app('default-workspace', '${appId}')
result = aos.tick('default-workspace', '${appId}', ${JSON.stringify(query)})
print('___AEON_OS_RESULT___' + json.dumps(result))
`;
    const proc = spawn("python3", ["-c", script], {
      cwd: root,
      env: { ...process.env, AEON_OS_ROOT: `${root}/aeon_os_state` },
    });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d) => { stdout += d.toString(); });
    proc.stderr.on("data", (d) => { stderr += d.toString(); });
    proc.on("close", (code) => {
      if (code !== 0) {
        return reject(new Error(stderr || "aeon os process failed"));
      }
      resolve(stdout);
    });
    proc.on("error", reject);
  });
}

export async function POST(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const id = params.id;
  const body = await req.json().catch(() => ({}));
  const query = String(body.query || "").trim();
  if (!query) {
    return NextResponse.json({ ok: false, error: "missing query" }, { status: 400 });
  }
  try {
    const stdout = await runAeonOS(id, query);
    const marker = stdout.indexOf("___AEON_OS_RESULT___");
    if (marker === -1) {
      return NextResponse.json({ ok: false, error: "no result from aeon os" }, { status: 500 });
    }
    const result = JSON.parse(stdout.slice(marker + "___AEON_OS_RESULT___".length).split("\n")[0]);
    return NextResponse.json(result);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e.message || String(e) }, { status: 500 });
  }
}
