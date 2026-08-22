import Link from "next/link";
import AeonLogo from "@/components/AeonLogo";
import "../showcase.css";

const SECTORS = [
  {
    icon: "🏥",
    title: "Healthcare",
    tag: "UNIFY CARE. IMPROVE OUTCOMES.",
    metrics: [
      { label: "Patient Score", value: "78", trend: "+12%" },
      { label: "Care Plan", value: "92%", trend: "On track" },
      { label: "Readmission", value: "Low", trend: "-18%" },
    ],
    tags: ["EHR / EMR", "Lab Systems", "Imaging", "Pharmacy", "Wearables", "Billing", "Patient Portal"],
    quote: "360° patient view, AI-powered clinical insights and workflow automation — HIPAA, GDPR and SOC 2 ready.",
  },
  {
    icon: "🏗️",
    title: "Construction",
    tag: "PLAN. BUILD. MONITOR. DELIVER.",
    metrics: [
      { label: "Projects", value: "24", trend: "+14.2%" },
      { label: "Total Budget", value: "$128.6M", trend: "+8.3%" },
      { label: "CPI", value: "1.08", trend: "On target" },
    ],
    tags: ["BIM & CAD", "IoT Sensors", "Drones", "ERP & Finance", "GIS & Mapping", "Mobile Apps"],
    quote: "AI scheduling, real-time cost control, site monitoring and subcontractor management from concept to handover.",
  },
  {
    icon: "🏛️",
    title: "Government",
    tag: "SECURE. COMPLIANT. TRUSTED.",
    metrics: [
      { label: "Security Score", value: "92", trend: "+12%" },
      { label: "Threats (24h)", value: "128", trend: "-18%" },
      { label: "Systems", value: "1,248", trend: "Active" },
    ],
    tags: ["Public Safety", "Defense & Intel", "Citizen Services", "Smart Cities", "Data Privacy"],
    quote: "Zero-trust architecture, AI threat detection and real-time monitoring — FISMA, NIST 800-53, ISO 27001 and FedRAMP.",
  },
  {
    icon: "🏭",
    title: "Smart Factories",
    tag: "UNIFY. AUTOMATE. OPTIMIZE.",
    metrics: [
      { label: "OEE", value: "85.6%", trend: "+8.4%" },
      { label: "Downtime", value: "2.45%", trend: "-18.3%" },
      { label: "Quality", value: "98.3%", trend: "+4.6%" },
    ],
    tags: ["PLC & SCADA", "IIoT Sensors", "MES & ERP", "Robots", "CMMS", "Historians"],
    quote: "Predictive maintenance, energy monitoring and AI-driven quality control across every machine and line.",
  },
  {
    icon: "🎬",
    title: "Marketing & Media",
    tag: "CREATE. COLLABORATE. CONVERT.",
    metrics: [
      { label: "Impressions", value: "2.45M", trend: "+25%" },
      { label: "Engagement", value: "7.62%", trend: "+12%" },
      { label: "ROI", value: "340%", trend: "+16%" },
    ],
    tags: ["Content AI", "Video Editing AI", "Campaign Intelligence", "Social Scheduler", "Media Library"],
    quote: "AI content generation, auto-editing, brand consistency and multi-platform publishing in one creative OS.",
  },
  {
    icon: "🚇",
    title: "Transportation",
    tag: "CONNECT CITIZENS. OPTIMIZE MOBILITY.",
    metrics: [
      { label: "Traffic Index", value: "87", trend: "+12%" },
      { label: "Transit On-Time", value: "92.6%", trend: "+8%" },
      { label: "CO₂ Saved", value: "1,245t", trend: "+18%" },
    ],
    tags: ["Traffic Signals", "Toll Systems", "CCTV & Sensors", "Fleet Management", "Open Data"],
    quote: "Live traffic maps, predictive congestion insights and multi-agency coordination for smarter, greener cities.",
  },
  {
    icon: "🍽️",
    title: "Hospitality",
    tag: "EVERY EXPERIENCE. LIMITLESS POSSIBILITIES.",
    metrics: [
      { label: "Revenue", value: "€24.6K", trend: "+18.6%" },
      { label: "Occupancy", value: "82%", trend: "+9.2%" },
      { label: "RevPAR", value: "€124", trend: "+10.8%" },
    ],
    tags: ["POS", "Reservations", "PMS", "Channel Manager", "Housekeeping", "CRM & Loyalty"],
    quote: "Restaurants, hotels, bars and multi-property groups — AI demand forecasting and revenue optimization built in.",
  },
  {
    icon: "🧠",
    title: "Business & Enterprise",
    tag: "ORCHESTRATE AI. ACCELERATE GROWTH.",
    metrics: [
      { label: "Agents Active", value: "32", trend: "+12%" },
      { label: "Tasks Automated", value: "1,248", trend: "+18%" },
      { label: "Cost Savings", value: "$312K", trend: "+22%" },
    ],
    tags: ["AI Orchestration", "Unified Data Layer", "Process Automation", "Integrations", "Compliance"],
    quote: "Coordinate multiple AI agents, unify your data and automate workflows — one intelligent ecosystem for your company.",
  },
];

const CAPS = [
  { icon: "🧠", title: "AI Orchestration", desc: "Coordinate specialized AI agents and models across every department — one brain, many hands." },
  { icon: "🗄️", title: "Unified Data Layer", desc: "Bring data from every system together, secure it, and activate it with real-time insights." },
  { icon: "⚙️", title: "Process Automation", desc: "Design intelligent workflows that automate tasks and eliminate inefficiencies end-to-end." },
  { icon: "🛡️", title: "Enterprise Grade", desc: "Zero-trust security, role-based access, encryption and audit-ready compliance built in." },
  { icon: "🧩", title: "Modular by Design", desc: "Every module is a pluggable component. Enable what you need, integrate what you already use." },
  { icon: "🔌", title: "Open Integrations", desc: "MCP servers, REST APIs and connectors for the tools your teams already rely on." },
];

const STEPS = [
  { icon: "📋", title: "Plan", desc: "Define scope, data and workflows." },
  { icon: "🔗", title: "Connect", desc: "Integrate systems and data sources." },
  { icon: "🤖", title: "Orchestrate", desc: "Deploy AI agents and automations." },
  { icon: "📊", title: "Monitor", desc: "Real-time dashboards and insights." },
  { icon: "📈", title: "Scale", desc: "Grow across teams, sites, sectors." },
];

const WHY = [
  { title: "One platform for every AI need", desc: "Agents, workflows, data, analytics and integrations — unified instead of stitched together." },
  { title: "Reduce costs, increase productivity", desc: "Automation removes manual work; AI insights surface the highest-impact optimizations." },
  { title: "Decisions backed by data, faster", desc: "Live dashboards, predictive analytics and AI recommendations in real time." },
  { title: "Future-proof your company", desc: "Modular architecture that adapts as your industry, tools and teams evolve." },
];

export const metadata = {
  title: "Showcase — AEON OS",
  description: "One OS. Every industry. Total control. See what AEON OS can do across healthcare, construction, government, factories, media, transportation, hospitality and business.",
};

export default function ShowcasePage() {
  return (
    <div className="showcase">
      <div className="showcase-inner">
        {/* Hero */}
        <section className="sh-hero">
          <div className="sh-brand">
            <AeonLogo size={30} />
            <div style={{ textAlign: "left" }}>
              <div className="sh-brand-name">AEON OS</div>
              <div className="sh-brand-tag">AI OPERATIVE SYSTEM</div>
            </div>
          </div>

          <div className="sh-kicker">ONE OS. EVERY INDUSTRY. TOTAL CONTROL.</div>
          <h1 className="sh-title">
            THE INTELLIGENT OS
            <br />
            FOR YOUR <span className="sh-title-accent">ENTIRE COMPANY</span>
          </h1>
          <p className="sh-sub">
            AEON OS orchestrates AI, data, people and processes into one modular platform — from hospitals to
            factories, city halls to creative studios. Automate. Optimize. Accelerate.
          </p>
          <div className="sh-cta">
            <Link className="sh-btn sh-btn-primary" href="/login">
              ▶ Try the live demo
            </Link>
            <Link className="sh-btn sh-btn-ghost" href="/os">
              Explore the OS modules
            </Link>
          </div>
        </section>

        {/* Stats */}
        <section className="sh-stats">
          <div className="sh-stat">
            <div className="sh-stat-value">8+</div>
            <div className="sh-stat-label">Industries</div>
          </div>
          <div className="sh-stat">
            <div className="sh-stat-value">40+</div>
            <div className="sh-stat-label">Modules</div>
          </div>
          <div className="sh-stat">
            <div className="sh-stat-value">1</div>
            <div className="sh-stat-label">Unified Brain</div>
          </div>
          <div className="sh-stat">
            <div className="sh-stat-value">0</div>
            <div className="sh-stat-label">Lock-in</div>
          </div>
        </section>

        {/* Sectors */}
        <section className="sh-section">
          <div className="sh-section-head">
            <span className="sh-section-kicker">Built for every industry</span>
            <span className="sh-section-line" />
          </div>
          <h2 className="sh-section-title">One platform. Every sector. Endless possibilities.</h2>
          <p className="sh-section-desc">
            The same core engine — AI orchestration, unified data, automation and security — adapts to the
            workflows of any organization. These are live dashboards you can open with the demo account.
          </p>
          <div className="sh-sectors" style={{ marginTop: "1.6rem" }}>
            {SECTORS.map((s) => (
              <article className="sh-card" key={s.title}>
                <div className="sh-card-head">
                  <div className="sh-card-icon">{s.icon}</div>
                  <div>
                    <div className="sh-card-title">{s.title}</div>
                    <div className="sh-card-sub">{s.tag}</div>
                  </div>
                </div>
                <div className="sh-card-metrics">
                  {s.metrics.map((m) => (
                    <div className="sh-metric" key={m.label}>
                      <div className="sh-metric-label">{m.label}</div>
                      <div className="sh-metric-value">{m.value}</div>
                      <div className="sh-metric-trend">{m.trend}</div>
                    </div>
                  ))}
                </div>
                <div className="sh-card-tags">
                  {s.tags.map((t) => (
                    <span className="sh-tag" key={t}>
                      {t}
                    </span>
                  ))}
                </div>
                <p className="sh-card-quote">{s.quote}</p>
              </article>
            ))}
          </div>
        </section>

        {/* Capabilities */}
        <section className="sh-section">
          <div className="sh-section-head">
            <span className="sh-section-kicker">Core platform</span>
            <span className="sh-section-line" />
          </div>
          <h2 className="sh-section-title">Powerful foundations. Modular everything.</h2>
          <div className="sh-caps" style={{ marginTop: "1.4rem" }}>
            {CAPS.map((c) => (
              <div className="sh-cap" key={c.title}>
                <div className="sh-cap-icon">{c.icon}</div>
                <div className="sh-cap-title">{c.title}</div>
                <div className="sh-cap-desc">{c.desc}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Workflow */}
        <section className="sh-section">
          <div className="sh-section-head">
            <span className="sh-section-kicker">From concept to scale</span>
            <span className="sh-section-line" />
          </div>
          <h2 className="sh-section-title">Deploy in days, not quarters.</h2>
          <div className="sh-flow">
            {STEPS.map((st) => (
              <div className="sh-step" key={st.title}>
                <div className="sh-step-icon">{st.icon}</div>
                <div className="sh-step-title">{st.title}</div>
                <div className="sh-step-desc">{st.desc}</div>
              </div>
            ))}
          </div>
        </section>

        {/* Why */}
        <section className="sh-section">
          <div className="sh-section-head">
            <span className="sh-section-kicker">Why AEON OS?</span>
            <span className="sh-section-line" />
          </div>
          <div className="sh-why">
            {WHY.map((w) => (
              <div className="sh-why-item" key={w.title}>
                <div className="sh-why-check">✓</div>
                <div>
                  <div className="sh-why-title">{w.title}</div>
                  <div className="sh-why-desc">{w.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* CTA */}
        <section className="sh-banner">
          <div className="sh-banner-title">ORCHESTRATE TODAY. TRANSFORM TOMORROW.</div>
          <p className="sh-banner-sub">
            Log in with the demo account and explore the full AEON OS experience — every module, every
            dashboard, every sector — live, with sample data and a free AI brain.
          </p>
          <div className="sh-banner-cta">
            <Link className="sh-btn sh-btn-primary" href="/login">
              ▶ Launch the demo
            </Link>
            <Link className="sh-btn sh-btn-ghost" href="/llm">
              Connect the free AI brain
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
