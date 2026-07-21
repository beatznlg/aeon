import { NextResponse } from "next/server";
import { spawn } from "child_process";

export const dynamic = "force-dynamic";

const ROOT = process.cwd();

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
  health: `
import json, os
os.environ['AEON_OS_ROOT'] = '${ROOT}/aeon_os_state'
from aeon import _safe_run

symptoms_list = ['fever, cough, fatigue', 'chest pain, shortness of breath', 'headache, nausea']
patients = ['P-1001', 'P-1002', 'P-1003']
metrics = ['heart_rate', 'blood_pressure_sys', 'oxygen_sat']
drug_sets = ['aspirin, warfarin', 'lisinopril, potassium', 'metformin']
telehealth_cases = [('chest pain', 65), ('fever', 30), ('skin rash', 42)]

diagnostics = []
for s in symptoms_list:
    ok, data = _safe_run('diagnostic_analyzer', {'symptoms': s}, '${ROOT}/aeon_os_state')
    if ok: diagnostics.append(json.loads(data))

patient_vitals = []
for p in patients:
    for m in metrics:
        ok, data = _safe_run('health_monitor', {'patient_id': p, 'metric': m}, '${ROOT}/aeon_os_state')
        if ok: patient_vitals.append(json.loads(data))

drug_interactions = []
for ds in drug_sets:
    ok, data = _safe_run('drug_interaction_check', {'drugs': ds}, '${ROOT}/aeon_os_state')
    if ok: drug_interactions.append(json.loads(data))

telehealth = []
for s, a in telehealth_cases:
    ok, data = _safe_run('telehealth_triage', {'symptoms': s, 'age': a}, '${ROOT}/aeon_os_state')
    if ok: telehealth.append(json.loads(data))

result = {'ok': True, 'diagnostics': diagnostics, 'patient_vitals': patient_vitals, 'drug_interactions': drug_interactions, 'telehealth': telehealth}
print('___AEON_OS_DASHBOARD___' + json.dumps(result))
`,
  transport: `
import json, os
os.environ['AEON_OS_ROOT'] = '${ROOT}/aeon_os_state'
from aeon import _safe_run

zones = ['downtown', 'midtown', 'airport_corridor', 'suburb_east']
fleets = [(10, 3), (8, 2), (15, 3)]
routes = ['A,B,C,D,E', 'F,G,H,I,J', 'K,L,M,N,O']

traffic = []
for z in zones:
    ok, data = _safe_run('traffic_optimizer', {'zone': z}, '${ROOT}/aeon_os_state')
    if ok: traffic.append(json.loads(data))

fleet_data = []
for v, s in fleets:
    ok, data = _safe_run('fleet_scheduler', {'vehicles': v, 'shifts': s}, '${ROOT}/aeon_os_state')
    if ok: fleet_data.append(json.loads(data))

route_plan = []
for r in routes:
    ok, data = _safe_run('route_optimizer', {'stops': r}, '${ROOT}/aeon_os_state')
    if ok: route_plan.append(json.loads(data))

result = {'ok': True, 'traffic': traffic, 'fleet': fleet_data, 'route_plan': route_plan}
print('___AEON_OS_DASHBOARD___' + json.dumps(result))
`,
  finance: `
import json, os
os.environ['AEON_OS_ROOT'] = '${ROOT}/aeon_os_state'
from aeon import _safe_run

ok, risk_data_r = _safe_run('risk_assessment', {'asset': 'S&P 500', 'portfolio_value': 500000}, '${ROOT}/aeon_os_state')
risk_data = json.loads(risk_data_r[1]) if ok else None

payment_accounts = ['ACC-1234', 'ACC-5678', 'ACC-9012']
payments = []
for a in payment_accounts:
    ok, data = _safe_run('payment_analyzer', {'account_id': a, 'days': 30}, '${ROOT}/aeon_os_state')
    if ok: payments.append(json.loads(data))

ok, market_r = _safe_run('market_forecast', {'market': 'NASDAQ', 'horizon_days': 90}, '${ROOT}/aeon_os_state')
market_data = json.loads(market_r[1]) if ok else None

fraud_txns = [('TXN-5001', 5000, 'foreign'), ('TXN-5002', 35, 'local'), ('TXN-5003', 25000, 'unknown')]
fraud = []
for tid, amt, loc in fraud_txns:
    ok, data = _safe_run('fraud_detection', {'transaction_id': tid, 'amount': amt, 'location': loc}, '${ROOT}/aeon_os_state')
    if ok: fraud.append(json.loads(data))

credit_apps = [('APP-200', 75000, 15000, 5), ('APP-201', 45000, 25000, 2), ('APP-202', 120000, 10000, 8)]
credit = []
for aid, inc, debt, hist in credit_apps:
    ok, data = _safe_run('credit_scoring', {'applicant_id': aid, 'income': inc, 'debt': debt, 'history_years': hist}, '${ROOT}/aeon_os_state')
    if ok: credit.append(json.loads(data))

result = {'ok': True, 'risk_data': risk_data, 'payment_analysis': payments, 'market_data': market_data, 'fraud_cases': fraud, 'credit_applications': credit}
print('___AEON_OS_DASHBOARD___' + json.dumps(result))
`,
  cultural_heritage: `
import json, os
os.environ['AEON_OS_ROOT'] = '${ROOT}/aeon_os_state'
from aeon import _safe_run

venues = ['National Museum', 'Modern Art Gallery', 'History Center']
sites = ['Colosseum', 'Machu Picchu', 'Angkor Wat']
exhibitions = [('Modern Art', 80000), ('Ancient Egypt', 60000), ('Space Exploration', 45000)]
tour_sites = [('Louvre Museum', 'art'), ('British Museum', 'history'), ('Uffizi Gallery', 'architecture')]

visitor_data = []
for v in venues:
    ok, data = _safe_run('visitor_engagement', {'venue': v, 'visitor_count': 500}, '${ROOT}/aeon_os_state')
    if ok: visitor_data.append(json.loads(data))

heritage_sites = []
for s in sites:
    ok, data = _safe_run('cultural_heritage_guide', {'site': s}, '${ROOT}/aeon_os_state')
    if ok: heritage_sites.append(json.loads(data))

exhibition_data = []
for theme, budget in exhibitions:
    ok, data = _safe_run('exhibition_planner', {'theme': theme, 'budget': budget}, '${ROOT}/aeon_os_state')
    if ok: exhibition_data.append(json.loads(data))

virtual_tours = []
for site, interest in tour_sites:
    ok, data = _safe_run('virtual_tour_guide', {'site': site, 'interest': interest}, '${ROOT}/aeon_os_state')
    if ok: virtual_tours.append(json.loads(data))

result = {'ok': True, 'visitor_data': visitor_data, 'heritage_sites': heritage_sites, 'exhibitions': exhibition_data, 'virtual_tours': virtual_tours}
print('___AEON_OS_DASHBOARD___' + json.dumps(result))
`,
  utilities: `
import json, os
os.environ['AEON_OS_ROOT'] = '${ROOT}/aeon_os_state'
from aeon import _safe_run

resources = [('water', 1000, 850), ('electricity', 500, 480), ('natural_gas', 300, 320)]
services = ['waste_collection', 'street_lighting', 'public_transport']
districts = ['Zone A', 'Zone B', 'Zone C']
regions = ['North Grid', 'South Grid', 'East Grid']

resource_data = []
for r, d, s in resources:
    ok, data = _safe_run('resource_optimizer', {'resource': r, 'demand': d, 'supply': s}, '${ROOT}/aeon_os_state')
    if ok: resource_data.append(json.loads(data))

public_services = []
for sv in services:
    ok, data = _safe_run('public_service_monitor', {'service': sv, 'jurisdiction': 'Metro District'}, '${ROOT}/aeon_os_state')
    if ok: public_services.append(json.loads(data))

waste_data = []
for d in districts:
    ok, data = _safe_run('waste_management', {'district': d, 'period': 'monthly'}, '${ROOT}/aeon_os_state')
    if ok: waste_data.append(json.loads(data))

energy_grid = []
for r in regions:
    ok, data = _safe_run('energy_grid_monitor', {'region': r, 'time_of_day': 14}, '${ROOT}/aeon_os_state')
    if ok: energy_grid.append(json.loads(data))

result = {'ok': True, 'resource_data': resource_data, 'public_services': public_services, 'waste_data': waste_data, 'energy_grid': energy_grid}
print('___AEON_OS_DASHBOARD___' + json.dumps(result))
`,
  sme: `
import json, os
os.environ['AEON_OS_ROOT'] = '${ROOT}/aeon_os_state'
from aeon import _safe_run

processes = [('invoice_approval', 5), ('employee_onboarding', 3), ('report_generation', 2)]
doc_types = ['invoice', 'contract', 'receipt']
support_queries = [
    ('Where is my order?', 'standard'),
    ('I want a refund', 'premium'),
    ('My account is locked', 'standard'),
]
chains = ['SC-001', 'SC-002', 'SC-003']

workflow_data = []
for proc, emp in processes:
    ok, data = _safe_run('workflow_automator', {'process': proc, 'employees': emp}, '${ROOT}/aeon_os_state')
    if ok: workflow_data.append(json.loads(data))

document_queue = []
for dt in doc_types:
    ok, data = _safe_run('document_processor', {'document_type': dt}, '${ROOT}/aeon_os_state')
    if ok: document_queue.append(json.loads(data))

support_tickets = []
for q, tier in support_queries:
    ok, data = _safe_run('customer_support_bot', {'query': q, 'customer_tier': tier}, '${ROOT}/aeon_os_state')
    if ok: support_tickets.append(json.loads(data))

supply_chain = []
for c in chains:
    ok, data = _safe_run('supply_chain_analyzer', {'chain_id': c, 'depth': 3}, '${ROOT}/aeon_os_state')
    if ok: supply_chain.append(json.loads(data))

result = {'ok': True, 'workflow_data': workflow_data, 'document_queue': document_queue, 'support_tickets': support_tickets, 'supply_chain': supply_chain}
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
