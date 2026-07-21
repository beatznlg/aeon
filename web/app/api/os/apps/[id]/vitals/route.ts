import { NextResponse } from "next/server";
import { spawn } from "child_process";

export const dynamic = "force-dynamic";

function runVitals(appId: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const root = process.cwd();
    const script = `
import json, os
os.environ['AEON_OS_ROOT'] = '${root}/aeon_os_state'
from aeon_os import AeonOS
aos = AeonOS()
aos.install_app('default-workspace', '${appId}')
result = aos.vitals('default-workspace')
print('___AEON_OS_VITALS___' + json.dumps(result))
`;
    const proc = require("child_process").spawn("python3", ["-c", script], {
      cwd: root,
      env: { ...process.env, AEON_OS_ROOT: `${root}/aeon_os_state` },
    });
    let stdout = "";
    let stderr = "";
    proc.stdout.on("data", (d: Buffer) => { stdout += d.toString(); });
    proc.stderr.on("data", (d: Buffer) => { stderr += d.toString(); });
    proc.on("close", (code: number) => {
      if (code !== 0) {
        return reject(new Error(stderr || "aeon os vitals failed"));
      }
      resolve(stdout);
    });
    proc.on("error", reject);
  });
}

export async function GET(
  _req: Request,
  { params }: { params: { id: string } }
) {
  const id = params.id;
  try {
    const stdout = await runVitals(id);
    const marker = stdout.indexOf("___AEON_OS_VITALS___");
    if (marker === -1) {
      return NextResponse.json({ ok: false, error: "no vitals from aeon os" }, { status: 500 });
    }
    const result = JSON.parse(stdout.slice(marker + "___AEON_OS_VITALS___".length).split("\n")[0]);
    return NextResponse.json(result);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e.message || String(e) }, { status: 500 });
  }
}
