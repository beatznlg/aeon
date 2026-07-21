import { NextResponse } from "next/server";
import { spawn } from "child_process";

export const dynamic = "force-dynamic";

const scripts: Record<string, string> = {
  retail: `
import json, os
os.environ['AEON_OS_ROOT'] = '${process.cwd()}/aeon_os_state'
from aeon_os import AeonOS
from aeon import _safe_run

aos = AeonOS()
aos.install_app('default-workspace', 'retail')

skus = ['SKU-001', 'SKU-042', 'SKU-099', 'SKU-107', 'SKU-215']
suppliers = ['Alpha Corp', 'Beta Logistics', 'Gamma Wholesale', 'Delta Distributors']

forecast = []
for sku in skus:
    ok, data = _safe_run('demand_forecast', {'sku': sku, 'horizon_days': 30}, '${process.cwd()}/aeon_os_state')
    if ok:
        forecast.append(json.loads(data))

inventory = _safe_run('inventory_optimizer', {'skus': skus}, '${process.cwd()}/aeon_os_state')
if inventory[0]:
    inventory = json.loads(inventory[1])

supplier_risks = []
for s in suppliers:
    ok, data = _safe_run('supplier_risk', {'supplier': s}, '${process.cwd()}/aeon_os_state')
    if ok:
        supplier_risks.append(json.loads(data))

elasticity = _safe_run('price_elasticity', {'sku': 'SKU-001', 'price_change_pct': 10}, '${process.cwd()}/aeon_os_state')
if elasticity[0]:
    elasticity = json.loads(elasticity[1])

personalizer = _safe_run('storefront_personalizer', {'segment': 'premium_shopper'}, '${process.cwd()}/aeon_os_state')
if personalizer[0]:
    personalizer = json.loads(personalizer[1])

result = {'ok': True, 'forecast': forecast, 'inventory': inventory, 'supplier_risks': supplier_risks, 'price_elasticity': elasticity, 'personalizer': personalizer}
print('___AEON_OS_DASHBOARD___' + json.dumps(result))
`,
  manufacturing: `
import json, os
os.environ['AEON_OS_ROOT'] = '${process.cwd()}/aeon_os_state'
from aeon import _safe_run

machines = ['CNC-01', 'CNC-02', 'CNC-03', 'CNC-04']
batches = ['B-998', 'B-999', 'B-1000']
routes = ['R-10', 'R-11', 'R-12']

maintenance = []
for m in machines:
    ok, data = _safe_run('predictive_maintenance', {'machine_id': m}, '${process.cwd()}/aeon_os_state')
    if ok:
        maintenance.append(json.loads(data))

qc = []
for b in batches:
    ok, data = _safe_run('qc_vision', {'batch_id': b}, '${process.cwd()}/aeon_os_state')
    if ok:
        qc.append(json.loads(data))

logistics = []
for r in routes:
    ok, data = _safe_run('smart_logistics', {'route_id': r}, '${process.cwd()}/aeon_os_state')
    if ok:
        logistics.append(json.loads(data))

result = {'ok': True, 'maintenance': maintenance, 'qc': qc, 'logistics': logistics}
print('___AEON_OS_DASHBOARD___' + json.dumps(result))
`,
  professional: `
import json, os
os.environ['AEON_OS_ROOT'] = '${process.cwd()}/aeon_os_state'
from aeon import _safe_run

docs = ['Vendor_NDA.pdf', 'Client_MSA.pdf', 'Employment_Contract.pdf']
invoices = ['INV-102', 'INV-103', 'INV-104']
datasets = ['user_dump.csv', 'transactions.csv']

legal = []
for d in docs:
    ok, data = _safe_run('legal_doc_parser', {'document_name': d}, '${process.cwd()}/aeon_os_state')
    if ok:
        legal.append(json.loads(data))

accounting = []
for i in invoices:
    ok, data = _safe_run('smart_accounting', {'invoice_id': i}, '${process.cwd()}/aeon_os_state')
    if ok:
        accounting.append(json.loads(data))

data_mgmt = []
for d in datasets:
    ok, data = _safe_run('data_manager', {'dataset_id': d}, '${process.cwd()}/aeon_os_state')
    if ok:
        data_mgmt.append(json.loads(data))

result = {'ok': True, 'legal': legal, 'accounting': accounting, 'data_management': data_mgmt}
print('___AEON_OS_DASHBOARD___' + json.dumps(result))
`,
  tourism: `
import json, os
os.environ['AEON_OS_ROOT'] = '${process.cwd()}/aeon_os_state'
from aeon import _safe_run

properties = ['Hotel-Central', 'Hotel-West', 'Hotel-Airport']
rooms = ['King Suite', 'Double Queen', 'Standard']
guests = [
    {'guest_id': 'G-445', 'request_summary': 'dining reservation'},
    {'guest_id': 'G-446', 'request_summary': 'housekeeping request'},
    {'guest_id': 'G-447', 'request_summary': 'transport to airport'},
]

bookings = []
for p in properties:
    ok, data = _safe_run('booking_optimizer', {'property_id': p}, '${process.cwd()}/aeon_os_state')
    if ok:
        bookings.append(json.loads(data))

pricing = []
for i, room in enumerate(rooms):
    ok, data = _safe_run('dynamic_pricing', {'room_type': room, 'offset_days': i * 7}, '${process.cwd()}/aeon_os_state')
    if ok:
        pricing.append(json.loads(data))

concierge = []
for g in guests:
    ok, data = _safe_run('automated_concierge', g, '${process.cwd()}/aeon_os_state')
    if ok:
        concierge.append(json.loads(data))

result = {'ok': True, 'bookings': bookings, 'pricing': pricing, 'concierge': concierge}
print('___AEON_OS_DASHBOARD___' + json.dumps(result))
`,
};

function runDashboard(appId: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const root = process.cwd();
    const script = scripts[appId];
    if (!script) {
      return resolve("");
    }
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
        return reject(new Error(stderr || `aeon os ${appId} dashboard failed`));
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
  if (!scripts[id]) {
    return NextResponse.json({ ok: false, error: "no dashboard for this app" }, { status: 404 });
  }
  try {
    const stdout = await runDashboard(id);
    const marker = stdout.indexOf("___AEON_OS_DASHBOARD___");
    if (marker === -1) {
      return NextResponse.json({ ok: false, error: "no dashboard data from aeon os" }, { status: 500 });
    }
    const result = JSON.parse(stdout.slice(marker + "___AEON_OS_DASHBOARD___".length).split("\n")[0]);
    return NextResponse.json(result);
  } catch (e: any) {
    return NextResponse.json({ ok: false, error: e.message || String(e) }, { status: 500 });
  }
}
