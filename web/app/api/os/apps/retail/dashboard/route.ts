import { NextResponse } from "next/server";
import { spawn } from "child_process";

export const dynamic = "force-dynamic";

function runRetailDashboard(): Promise<string> {
  return new Promise((resolve, reject) => {
    const root = process.cwd();
    const script = `
import json, os
os.environ['AEON_OS_ROOT'] = '${root}/aeon_os_state'
from aeon_os import AeonOS
from aeon import _safe_run

aos = AeonOS()
aos.install_app('default-workspace', 'retail')

skus = ['SKU-001', 'SKU-042', 'SKU-099', 'SKU-107', 'SKU-215']
suppliers = ['Alpha Corp', 'Beta Logistics', 'Gamma Wholesale', 'Delta Distributors']

forecast = []
for sku in skus:
    ok, data = _safe_run('demand_forecast', {'sku': sku, 'horizon_days': 30}, '${root}/aeon_os_state')
    if ok:
        forecast.append(json.loads(data))

inventory = _safe_run('inventory_optimizer', {'skus': skus}, '${root}/aeon_os_state')
if inventory[0]:
    inventory = json.loads(inventory[1])

supplier_risks = []
for s in suppliers:
    ok, data = _safe_run('supplier_risk', {'supplier': s}, '${root}/aeon_os_state')
    if ok:
        supplier_risks.append(json.loads(data))

elasticity = _safe_run('price_elasticity', {'sku': 'SKU-001', 'price_change_pct': 10}, '${root}/aeon_os_state')
if elasticity[0]:
    elasticity = json.loads(elasticity[1])

personalizer = _safe_run('storefront_personalizer', {'segment': 'premium_shopper'}, '${root}/aeon_os_state')
if personalizer[0]:
    personalizer = json.loads(personalizer[1])

result = {
    'ok': True,
    'forecast': forecast,
    'inventory': inventory,
    'supplier_risks': supplier_risks,
    'price_elasticity': elasticity,
    'personalizer': personalizer,
}
print('___AEON_OS_RETAIL___' + json.dumps(result))
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
        return reject(new Error(stderr || "aeon os retail dashboard failed"));
      }
      resolve(stdout);
    });
    proc.on("error", reject);
  });
}

export async function GET() {
  try {
    const stdout = await runRetailDashboard();
    const marker = stdout.indexOf("___AEON_OS_RETAIL___");
    if (marker === -1) {
      return NextResponse.json({ ok: false, error: "no retail data from aeon os" }, { status: 500 });
    }
    const result = JSON.parse(stdout.slice(marker + "___AEON_OS_RETAIL___".length).split("\n")[0]);
    return NextResponse.json(result);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e.message || String(e) }, { status: 500 });
  }
}
