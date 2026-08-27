#!/usr/bin/env python3
"""Build a self-contained, slide-style PDF presentation for AEON OS.

This intentionally uses only Python's standard library so the artifact can be
regenerated in minimal CI or deployment environments without adding runtime
dependencies to AEON itself.
"""
from __future__ import annotations

import unicodedata
from pathlib import Path

W, H = 960, 540
OUT = Path(__file__).resolve().parents[1] / "docs" / "AEON_OS_Project_Presentation.pdf"

BG = (10, 16, 31)
PANEL = (18, 28, 49)
PANEL_2 = (22, 37, 62)
TEXT = (238, 244, 252)
MUTED = (158, 176, 201)
CYAN = (58, 213, 220)
BLUE = (83, 137, 255)
ORANGE = (255, 170, 85)
GREEN = (90, 220, 155)
RED = (255, 104, 122)


def rgb(c: tuple[int, int, int]) -> str:
    return " ".join(f"{v / 255:.3f}" for v in c)


def ascii_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "replace").decode("ascii")
    return text.replace("\ufffd", "?")


def esc(value: object) -> str:
    return ascii_text(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def wrap(text: str, width: int, size: float) -> list[str]:
    limit = max(12, int(width / max(1, size * 0.52)))
    lines: list[str] = []
    for paragraph in ascii_text(text).split("\n"):
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split()
        current = ""
        for word in words:
            candidate = word if not current else current + " " + word
            if len(candidate) > limit and current:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


class Slide:
    def __init__(self, number: int):
        self.number = number
        self.ops: list[str] = []
        self.rect(0, 0, W, H, BG)
        # Fine top rule and accent beacon create a consistent visual system.
        self.rect(0, H - 7, W, 7, CYAN)
        self.circle(884, H - 42, 22, (24, 56, 83))
        self.circle(884, H - 42, 8, CYAN)

    def rect(self, x: float, y: float, w: float, h: float, color: tuple[int, int, int], stroke: tuple[int, int, int] | None = None, line: float = 1) -> None:
        self.ops.append(f"{rgb(color)} rg {x:.1f} {y:.1f} {w:.1f} {h:.1f} re f")
        if stroke:
            self.ops.append(f"{rgb(stroke)} RG {line:.1f} {x:.1f} {y:.1f} {w:.1f} {h:.1f} re S")

    def line(self, x1: float, y1: float, x2: float, y2: float, color: tuple[int, int, int], width: float = 1.5) -> None:
        self.ops.append(f"{rgb(color)} RG {width:.1f} w {x1:.1f} {y1:.1f} m {x2:.1f} {y2:.1f} l S")

    def circle(self, cx: float, cy: float, r: float, color: tuple[int, int, int]) -> None:
        # Four cubic curves approximate a circle.
        k = 0.5522848 * r
        self.ops.append(
            f"{rgb(color)} rg {cx+r:.1f} {cy:.1f} m {cx+r:.1f} {cy+k:.1f} {cx+k:.1f} {cy+r:.1f} {cx:.1f} {cy+r:.1f} c "
            f"{cx-k:.1f} {cy+r:.1f} {cx-r:.1f} {cy+k:.1f} {cx-r:.1f} {cy:.1f} c "
            f"{cx-r:.1f} {cy-k:.1f} {cx-k:.1f} {cy-r:.1f} {cx:.1f} {cy-r:.1f} c "
            f"{cx+k:.1f} {cy-r:.1f} {cx+r:.1f} {cy-k:.1f} {cx+r:.1f} {cy:.1f} c f"
        )

    def text(self, value: object, x: float, top: float, size: float, color: tuple[int, int, int] = TEXT, font: str = "F1") -> None:
        y = H - top - size
        self.ops.append(f"BT /{font} {size:.1f} Tf {rgb(color)} rg 1 0 0 1 {x:.1f} {y:.1f} Tm ({esc(value)}) Tj ET")

    def block(self, value: object, x: float, top: float, width: float, size: float = 13, color: tuple[int, int, int] = TEXT, leading: float | None = None, font: str = "F1", bullet: bool = False) -> float:
        leading = leading or size * 1.35
        y = top
        paragraphs = value if isinstance(value, list) else [value]
        for para in paragraphs:
            prefix = "- " if bullet else ""
            lines = wrap(prefix + str(para), int(width), size)
            for line in lines:
                self.text(line, x, y, size, color, font)
                y += leading
            y += size * 0.18
        return y

    def heading(self, title: str, subtitle: str = "") -> None:
        self.text(title, 58, 38, 27, TEXT, "F2")
        self.rect(58, H - 82, 78, 3, CYAN)
        if subtitle:
            self.text(subtitle, 58, 88, 11.5, MUTED, "F1")

    def card(self, x: float, top: float, w: float, h: float, title: str, body: object, accent: tuple[int, int, int] = CYAN, size: float = 12.5) -> None:
        y = H - top - h
        self.rect(x, y, w, h, PANEL, PANEL_2, 1)
        self.rect(x, y + h - 4, w, 4, accent)
        self.text(title, x + 16, top + 16, 13, TEXT, "F2")
        self.block(body, x + 16, top + 42, w - 32, size, MUTED, leading=size * 1.38)

    def footer(self, label: str = "AEON OS | repository presentation | August 2026") -> None:
        self.line(58, 31, W - 58, 31, (36, 54, 80), 0.8)
        self.text(label, 58, H - 27, 9, MUTED, "F1")
        self.text(f"{self.number:02d}", W - 84, H - 27, 9, CYAN, "F2")

    def finish(self) -> bytes:
        return ("\n".join(self.ops) + "\n").encode("latin-1", "replace")


class Pdf:
    def __init__(self):
        self.objects: list[bytes] = []
        self.fonts: dict[str, int] = {}

    def obj(self, data: bytes) -> int:
        self.objects.append(data)
        return len(self.objects)

    def build(self, slides: list[Slide]) -> bytes:
        f1 = self.obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        f2 = self.obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
        f3 = self.obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
        fonts = f"<< /F1 {f1} 0 R /F2 {f2} 0 R /F3 {f3} 0 R >>".encode()
        pages_id = self.obj(b"PLACEHOLDER")
        page_ids: list[int] = []
        for slide in slides:
            stream = slide.finish()
            stream_id = self.obj(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"endstream")
            page = (
                f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 {W} {H}] "
                f"/Resources << /Font {fonts.decode()} >> /Contents {stream_id} 0 R >>"
            ).encode()
            page_ids.append(self.obj(page))
        kids = " ".join(f"{pid} 0 R" for pid in page_ids)
        self.objects[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()
        catalog_id = self.obj(f"<< /Type /Catalog /Pages {pages_id} 0 R /PageLayout /SinglePage >>".encode())
        return self.serialize(catalog_id)

    def serialize(self, root: int) -> bytes:
        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for i, data in enumerate(self.objects, 1):
            offsets.append(len(out))
            out.extend(f"{i} 0 obj\n".encode())
            out.extend(data)
            out.extend(b"\nendobj\n")
        xref = len(out)
        out.extend(f"xref\n0 {len(self.objects)+1}\n0000000000 65535 f \n".encode())
        for offset in offsets[1:]:
            out.extend(f"{offset:010d} 00000 n \n".encode())
        out.extend(f"trailer\n<< /Size {len(self.objects)+1} /Root {root} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
        return bytes(out)


def add_cover(slides: list[Slide]) -> None:
    s = Slide(1)
    s.circle(755, 300, 142, (17, 42, 69))
    s.circle(755, 300, 105, (20, 53, 76))
    s.circle(755, 300, 62, (24, 72, 83))
    s.circle(755, 300, 25, CYAN)
    for i in range(5):
        s.line(755, 300, 755 + (i - 2) * 120, 300 + (i % 2 * 2 - 1) * 110, (42, 119, 142), 1)
    s.text("AEON OS", 70, 116, 52, TEXT, "F2")
    s.text("Advanced Evolutionary Orchestrator Network", 74, 181, 17, CYAN, "F1")
    s.block("Project architecture, implemented capabilities, runtime flow, and production readiness", 74, 236, 470, 18, MUTED, leading=25)
    s.rect(74, 347, 220, 34, PANEL_2)
    s.text("REPOSITORY SNAPSHOT", 91, 357, 11, ORANGE, "F2")
    s.text("beatznlg/aeon", 74, 438, 13, MUTED, "F3")
    s.text("August 4, 2026", 74, 462, 12, MUTED)
    s.footer("AEON OS | project presentation")
    slides.append(s)


def add_two_col(slides: list[Slide], title: str, subtitle: str, left_title: str, left: list[str], right_title: str, right: list[str], accents=(CYAN, BLUE)) -> None:
    s = Slide(len(slides) + 1)
    s.heading(title, subtitle)
    s.card(58, 126, 405, 335, left_title, left, accents[0], 12.4)
    s.card(497, 126, 405, 335, right_title, right, accents[1], 12.4)
    s.footer()
    slides.append(s)


def add_three_col(slides: list[Slide], title: str, subtitle: str, cards: list[tuple[str, list[str], tuple[int, int, int]]]) -> None:
    s = Slide(len(slides) + 1)
    s.heading(title, subtitle)
    x = 58
    for name, body, accent in cards:
        s.card(x, 126, 267, 335, name, body, accent, 11.8)
        x += 282
    s.footer()
    slides.append(s)


def build_slides() -> list[Slide]:
    slides: list[Slide] = []
    add_cover(slides)
    add_two_col(slides, "01 | What has been built", "AEON is an AI operating layer for multi-tenant workspaces, not only a chat screen.", "Product surface", [
        "Next.js 14 dashboard with protected OS, chat, settings, admin, monitoring, automation, RAG, swarm, billing, and sector surfaces.",
        "Flask/Python kernel for auth, agent execution, tools, workflows, automations, integrations, health, metrics, and governance.",
        "OpenAPI documentation plus Python, TypeScript, and Go client paths for programmatic use.",
    ], "Runtime capabilities", [
        "Pluggable LLM providers: stub, OpenAI, Anthropic, Ollama, Hugging Face, and local Qwen path.",
        "Persistent memory, goals, reflection, tool execution, RAG retrieval, workflow actions, and multi-agent swarms.",
        "Operational controls: budgets, approvals, cooldowns, audit logs, anomaly detection, incident models, backups, DR, and SIEM exports.",
    ])
    add_three_col(slides, "02 | Repository at a glance", "Measured from the repository snapshot used for this presentation.", [
        ("Frontend", ["36 page surfaces", "99 Next.js API route files", "React + TypeScript + Tailwind", "Recharts, Framer Motion, NextAuth"], CYAN),
        ("Backend", ["41 root Python modules", "Flask HTTP kernel", "SQLAlchemy models", "Supabase REST integrations", "Celery/Redis option"], BLUE),
        ("Delivery", ["22 test files", "18 Supabase migrations", "Docker Compose stack", "Oracle Cloud deployment guide", "OpenAPI + SDKs"], ORANGE),
    ])
    add_two_col(slides, "03 | System topology", "The intended production split keeps long-running AI and automation work off the frontend host.", "Request plane", [
        "Browser -> Next.js dashboard and server-side proxy routes.",
        "NextAuth session and JWT claims establish identity, role, and selected workspace.",
        "Next.js forwards protected operations to Flask through AEON_PYTHON_URL.",
        "Flask returns workspace-scoped JSON and operational status.",
    ], "Execution plane", [
        "Flask -> ReflectiveAgent / AeonKernel -> selected LLM provider.",
        "SQLAlchemy/Postgres stores identity, governance, automation, incident, DR, and SIEM state.",
        "AEON_ROOT stores agent files, memory, goals, skills, ledgers, and local vector indexes.",
        "Redis/Celery provides optional distributed automation dispatch and scheduled work.",
    ])
    add_two_col(slides, "04 | The most important request flow", "A single chat or domain request crosses several policy and persistence boundaries.", "Browser to kernel", [
        "1. User enters chat or app prompt in the dashboard.",
        "2. Next.js route checks session and resolves workspace context.",
        "3. Proxy forwards method, JSON body, bearer context, and workspace headers.",
        "4. Flask decorators enforce authentication and workspace role.",
        "5. Kernel chooses the workspace agent and provider.",
    ], "Kernel to result", [
        "6. Agent builds context from memory, goals, RAG, and tool registry.",
        "7. LLM response may emit structured tool calls.",
        "8. Safe runner validates and executes allowed tools.",
        "9. Memory, vitals, audit, metrics, and usage are updated.",
        "10. JSON result returns to the UI with backend and execution metadata.",
    ])
    add_three_col(slides, "05 | Frontend product experience", "The web application organizes AEON by operator task and business sector.", [
        ("Workspace OS", ["Dashboard overview", "Chat and history", "App/sector launcher", "Automations", "Workflows", "Approvals"], CYAN),
        ("Operations", ["Monitoring", "Observability", "Incidents", "Anomalies", "Audit/governance", "Disaster recovery", "SIEM"], GREEN),
        ("Control plane", ["Settings", "API keys", "Billing", "Integrations", "SSO/SCIM", "Admin panel", "Notifications"], ORANGE),
    ])
    add_two_col(slides, "06 | Backend kernel modules", "The root Python modules are intentionally separated by responsibility, while aeon_server.py composes the HTTP surface.", "Core AI", [
        "aeon.py: AeonKernel, ReflectiveAgent, MemoryBundle, GoalState, SelfModel, CodeSandbox, CodeEvolver, tools, ledger, and service registry.",
        "aeon_os.py: workspace-scoped agent lifecycle and orchestration.",
        "aeon_llm.py: provider abstraction and provider-specific adapters.",
        "aeon_chat.py: chat/session helpers.",
        "aeon_rag.py + aeon_vector_store.py: ingestion, chunking, embeddings, indexing, hybrid retrieval.",
    ], "Platform services", [
        "aeon_db.py: SQLAlchemy schema and persistence helpers.",
        "aeon_auth.py: JWT/API-key auth and workspace authorization.",
        "aeon_automations.py: event rules, chains, schedules, budgets, approvals, and resumptions.",
        "aeon_worker.py: Celery bridge with eager/inline fallback.",
        "aeon_integrations.py, aeon_security.py, aeon_anomalies.py, aeon_siem.py, and DR modules.",
    ])
    add_two_col(slides, "07 | Tenancy, identity, and authorization", "Every sensitive capability is designed around a current user and workspace context.", "Identity model", [
        "Users belong to tenants and can have memberships in multiple workspaces.",
        "Workspace membership carries VIEWER, OPERATOR, ADMIN, or SUPER_ADMIN-style access.",
        "JWT access tokens and hashed API keys support human and machine callers.",
        "Refresh-token storage and JWT rotation endpoints support credential lifecycle management.",
    ], "Enforcement", [
        "require_auth protects authenticated routes.",
        "Workspace access and role decorators guard data-plane mutations.",
        "Frontend middleware protects /os, /settings, and /chat and redirects unauthorized admin routes.",
        "Audit events retain user, module, workspace, action, metadata, and PII-redaction status.",
    ])
    add_three_col(slides, "08 | Relational data model", "SQLAlchemy models mirror the durable control-plane entities; Supabase migrations extend the same domain.", [
        ("Identity", ["tenants", "users", "workspaces", "memberships", "refresh_tokens", "identity_links"], CYAN),
        ("Automation", ["automation_executions", "automation_policies", "automation_budgets", "rule snapshots", "variables", "approvals"], ORANGE),
        ("Enterprise ops", ["audit_logs", "SSO providers", "SCIM tokens", "security config", "anomalies", "incidents", "runbooks", "backups", "DR", "SIEM"], GREEN),
    ])
    add_two_col(slides, "09 | Filesystem state and memory persistence", "AEON uses files for agent-local state and SQL for shared governance and operational records.", "AEON_ROOT state", [
        "Agent directories hold state.json and other per-agent artifacts.",
        "MemoryBundle maintains episodic events, semantic facts/links, and procedural skill metadata.",
        "GoalState persists objectives in goals/goals.jsonl and reloads them across restarts.",
        "Ledgers, bounty state, evolved skills, and local vector indexes are also file-oriented in the local backend.",
    ], "Durability boundary", [
        "Local filesystem is useful for development and a mounted production volume.",
        "Serverless /tmp or in-memory fallback is ephemeral and cannot be the source of truth for durable operations.",
        "Production should mount AEON_ROOT and use Postgres/Supabase for shared records.",
        "Storage abstraction supports local and Supabase-backed object/file storage.",
    ])
    add_two_col(slides, "10 | Agent loop, memory, and reflection", "The reflective agent wraps a tool loop with durable context and self-observation.", "Tick lifecycle", [
        "Receive query and build a system prompt with available tools.",
        "Generate with the selected LLM provider.",
        "Parse structured tool-call JSON and execute through the safe runner.",
        "Replace tool calls with bounded result summaries in the answer.",
        "Record user/bot events, tool outcomes, causal credit, and self-model vitals.",
    ], "Reflection layer", [
        "MemoryBundle supplies recent context and semantic facts.",
        "GoalState selects the highest-priority open objective.",
        "SelfModel tracks uptime, ticks, calls, errors, success rate, and wellbeing.",
        "Decision logic can tick, reduce error, or trigger controlled tool evolution after poor performance.",
        "CodeEvolver validates candidate tools before registration; evolution suggestions are not auto-executed.",
    ])
    add_three_col(slides, "11 | Tools, safety, and model providers", "Provider choice is configuration-driven; tool execution is deliberately more constrained than text generation.", [
        ("Providers", ["stub for local boot", "OpenAI", "Anthropic", "Ollama", "Hugging Face inference", "Qwen local path"], BLUE),
        ("Tool surface", ["Math", "search/fetch", "GitHub search", "API catalog/fetch", "skills", "bounties", "service quotes"], CYAN),
        ("Safety gates", ["AST/code analysis", "blocked imports/calls", "HTTP scheme validation", "wallet whitelist", "broadcast disabled by default"], GREEN),
    ])
    add_two_col(slides, "12 | RAG and knowledge retrieval", "Knowledge bases extend agent context without requiring every document to fit in a prompt.", "Ingestion path", [
        "Documents are accepted through the RAG API and normalized into chunks.",
        "Chunk metadata preserves document/workspace identity and retrieval context.",
        "Embeddings use sentence-transformers when available, with a deterministic local fallback path.",
        "Vector storage can be local/disk-backed or backed by Supabase/pgvector-compatible infrastructure.",
    ], "Search path", [
        "Query is embedded and/or keyword-indexed.",
        "Hybrid scoring combines lexical and semantic relevance.",
        "Top chunks are returned to the agent or chat route as grounded context.",
        "Operational requirement: durable document storage and vector persistence must be configured for production.",
    ])
    add_two_col(slides, "13 | Automation engine", "AEON automations behave like governed event-driven workflows rather than one-shot webhooks.", "Trigger and policy", [
        "Rules match event types and nested conditions with operators such as $gt, $in, $contains, $regex, $and/$or/$not.",
        "Cooldowns prevent runaway repetition; workspace/rule budgets can warn or block.",
        "Approval-required rules pause at a human-in-the-loop checkpoint.",
        "Cron scheduling and inbound webhooks create external and time-based triggers.",
    ], "Execution and state", [
        "Actions support sequential chains, conditional run_if, loops, fallbacks, continue_on_error, delays, wait_for_event, variables, sub-rules, transforms, and parallel branches.",
        "Execution history captures status, result, errors, and runtime metadata.",
        "Sleeping executions persist pending step state and resume later.",
        "Dry-run mode simulates side effects while evaluating logic and transformations.",
    ])
    add_three_col(slides, "14 | Automation lifecycle", "This is the control path for a typical rule execution.", [
        ("1. Evaluate", ["Fetch workspace rules", "Match event", "Apply condition", "Check cooldown", "Check budget"], CYAN),
        ("2. Govern", ["Create approval request if required", "Notify operators", "Write audit/execution event", "Persist pending state"], ORANGE),
        ("3. Execute", ["Dispatch Celery when configured", "Otherwise run inline", "Run action chain", "Retry/fallback/resume", "Record final status"], GREEN),
    ])
    add_two_col(slides, "15 | Multi-agent swarms", "SwarmManager coordinates specialized agents around a shared prompt and task graph.", "Roles and planning", [
        "Planner decomposes the prompt into SwarmTask records.",
        "Executor agents work assigned tasks by capability.",
        "Reviewer agents inspect outputs and can request corrective work.",
        "Summarizer agents synthesize the final answer.",
    ], "Coordination contract", [
        "SwarmMessage provides sender, recipient, type, timestamp, and swarm identity.",
        "Inbox/outbox and broadcast methods form a lightweight message bus.",
        "Status and messages endpoints expose the run to the dashboard.",
        "Tool-improvement suggestions are returned for explicit human review, never silently applied.",
    ])
    add_three_col(slides, "16 | Integrations and approvals", "The platform is designed to connect outside systems while keeping sensitive actions governed.", [
        ("Inbound", ["Workspace-created webhook tokens", "External event acceptance", "Automation event logging", "Integration receive routes"], CYAN),
        ("Outbound", ["Webhook actions", "Slack notifications", "Slack interactive approvals", "Catalog/connector registry", "GitHub-facing tools"], BLUE),
        ("Human control", ["Pending approval queue", "Operator resolve endpoint", "Approved deferred execution", "Rejected action audit trail"], ORANGE),
    ])
    add_two_col(slides, "17 | Security and enterprise governance", "The codebase includes security controls across HTTP, data handling, identity, and operations.", "Security controls", [
        "Configurable CORS and baseline security headers including CSP, frame, content-type, and permissions policies.",
        "PII/PHI scanner and recursive metadata sanitization for email, phone, SSN, MRN, API key, and token patterns.",
        "Hashed API keys, rotation endpoints, JWT rotation/status, and workspace RBAC.",
        "Slack HMAC signature verification and restricted webhook behavior.",
    ], "Enterprise controls", [
        "OIDC provider CRUD and SAML degradation path are represented in SSO modules/tests.",
        "SCIM token models support provisioning integration.",
        "Audit logging includes redacted export behavior.",
        "SIEM integrations model provider endpoints, filters, batches, delivery status, and retry logs.",
    ])
    add_two_col(slides, "18 | Observability, incidents, and recovery", "The latest pushed change added workspace-scoped operations monitoring and API documentation.", "Live operations", [
        "Health, liveness, readiness, detailed health, Prometheus /metrics, and operations snapshot routes.",
        "Operations snapshot reports readiness, agent vitals, memory/goal counts, worker capacity, and automation status counts without returning prompts or credentials.",
        "Monitoring and observability dashboard pages consume Next.js proxy routes.",
        "Anomaly detection covers automation failure spikes, execution volume, and audit volume.",
    ], "Resilience domain", [
        "Incident, runbook, assignee, severity, and resolution models exist in the persistence layer.",
        "Backup policy, backup job, restore job, DR plan, and DR drill models capture recovery intent.",
        "Docker Compose includes persistent Postgres, Redis, and AEON state volumes.",
        "Operational caveat: durable recovery still requires configured storage, scheduling, and tested runbooks.",
    ])
    add_two_col(slides, "19 | Developer experience and API surface", "The repository is intended to be operated by humans and integrated by other software.", "API contract", [
        "docs/openapi.json documents health, auth, workspaces, apps, workflows, swarm, API keys, billing, integrations, RAG, and governance tags.",
        "Swagger-style documentation is served by the backend docs route when enabled.",
        "Workspace-scoped APIs use bearer security and explicit path/query identifiers.",
        "The latest operations snapshot contract documents redaction and access responses.",
    ], "SDKs and examples", [
        "Python client exposes health, chat, and API request helpers with structured AeonError behavior.",
        "TypeScript client provides typed HTTP access for browser/server consumers.",
        "Go client and SDK generator are included in the repository structure.",
        "examples/ contains runnable integration starting points.",
    ])
    add_two_col(slides, "20 | Deployment and runtime modes", "The repository supports a local all-in-one path and a single-VM Oracle Cloud production stack.", "Recommended production", [
        "Oracle Cloud VM -> Caddy TLS proxy in front of the full stack.",
        "Next.js frontend container with AUTH_SECRET and AEON_PYTHON_URL.",
        "Docker -> long-running Flask backend with Postgres and mounted state volume.",
        "Prometheus/Grafana/Alertmanager for production telemetry.",
    ], "Local and experimental", [
        "docker compose up --build starts Postgres, Redis, Flask, Celery worker/beat, and Next.js.",
        "web/package.json offers dev, dev:full, build, start, lint, and formatting scripts.",
        "Stub LLM provider is the lowest-friction first boot; external provider keys are optional until needed.",
    ])
    add_three_col(slides, "21 | Configuration checklist", "Names below are configuration categories, not secrets or values.", [
        ("Required core", ["NEXTAUTH_SECRET", "NEXTAUTH_URL", "AEON_DATABASE_URL", "AEON_PYTHON_URL", "AEON_ROOT"], RED),
        ("AI and data", ["AEON_LLM_PROVIDER", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "HUGGINGFACE_TOKEN", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"], BLUE),
        ("Ops and commerce", ["AEON_REDIS_URL", "AEON_WORKER_THREADS", "STRIPE_API_KEY", "STRIPE_WEBHOOK_SECRET", "CORS/HSTS settings", "Slack signing secret"], ORANGE),
    ])
    add_two_col(slides, "22 | Verification and current caveats", "This presentation describes repository capabilities; external services still need environment-specific validation.", "What is verified in code", [
        "22 Python test files cover auth, storage, security, anomalies, swarm, worker dispatch, metrics, SSO, SDK, and governance areas.",
        "18 Supabase migration files extend automation, variables, snapshots, analytics, and enterprise domains.",
        "The observability change was pushed as commit 34d4d05 and main matched origin/main at the snapshot.",
        "The repository working tree was clean before presentation generation.",
    ], "What still needs an environment", [
        "Freebuff preview/deploy CLIs were not available in the earlier shell, so preview readiness was not claimed.",
        "Postgres/Supabase, Redis, provider keys, Stripe, Slack, SSO, and persistent volumes require operator setup.",
        "Serverless filesystem, in-memory caches, thread pools, and local fallbacks are not durable production substitutes.",
        "Sector data generators contain deterministic demo-style values; connect real data sources before regulated use.",
    ])
    add_two_col(slides, "23 | Roadmap from the current foundation", "The platform has a broad control plane; the next work should deepen reliability and product proof.", "Highest-value hardening", [
        "Run the complete test and typecheck gates in a fully provisioned environment.",
        "Exercise every frontend route against a live backend and seeded workspace.",
        "Add end-to-end automation tests covering approval, resume, parallel, retry, and budget paths.",
        "Make migration execution and deployment health checks deterministic across Postgres/Supabase.",
    ], "Scale and product depth", [
        "Replace process-local scheduling with a single durable scheduler topology in production.",
        "Add formal tenant isolation tests and policy tests for every sensitive route.",
        "Connect sector modules to real customer data contracts instead of generated sector samples.",
        "Publish performance, cost, latency, and recovery objectives backed by measured runs.",
    ])
    return slides


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    slides = build_slides()
    pdf = Pdf().build(slides)
    OUT.write_bytes(pdf)
    print(f"wrote {OUT} ({len(pdf)} bytes, {len(slides)} pages)")


if __name__ == "__main__":
    main()
