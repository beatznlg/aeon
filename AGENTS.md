# AEON OS — Project Guide for Coding Agents

AEON OS (Advanced Evolutionary Orchestrator Network) is an open-source AI agent
platform: multi-tenant workspaces, workflow builder, LLM provider switching,
RAG knowledge bases, Stripe billing, and Prometheus monitoring.

## Repository layout

This is a **monorepo with two halves**:

- **Flask/Python backend — lives at the repository root.**
  - Entry point: `aeon_server.py` (Flask app; run with `python3 aeon_server.py`).
  - Core modules are `aeon_*.py` (auth, db, llm, automations, sectors, billing,
    governance, observability, DR, traces, marketplace, MCP, etc.).
  - Database access and ORM models live in `aeon_db.py` (SQLAlchemy + Alembic
    migrations under `alembic/`).
  - Tests live in `tests/` and run with pytest.
  - `requirements.txt` pins backend dependencies.

- **Next.js 14 frontend — lives in `web/`.**
  - React 18 + TypeScript + Tailwind CSS + shadcn/ui-style components.
  - API routes under `web/app/api/**/route.ts` proxy to the Flask backend
    (see `web/lib/proxy.ts` and `web/lib/backend-fetch.ts`). Most GET routes
    fall back to realistic demo data (`web/lib/demo-data.ts`) when the backend
    is unreachable, so pages still render.
  - Auth via Auth.js v5 (`web/auth.ts`, `web/app/api/auth/[...nextauth]`).
  - Supabase server client in `web/lib/supabase.ts` (server-only service role).

## Commands

Backend (run from repo root):

```bash
python3 -m pytest -q                      # full backend test suite
python3 -m pytest -q tests/test_llm.py    # focused LLM tests
python3 aeon_server.py                    # run Flask backend (port 5000)
python3 -m ruff check aeon_*.py           # lint backend
```

Frontend (run from `web/`):

```bash
cd web && npm install
cd web && npm run dev                     # Next.js dev server
cd web && npm run build                   # production build (typechecks)
cd web && npm run lint                    # ESLint
```

Full stack locally:

```bash
npm run dev:full   # from web/: runs Flask + Next.js concurrently
```

## Conventions

- **Never edit `web/src/convex/_generated/*`** (not used here — ignore Convex).
- Backend routes are workspace-scoped: auth + membership/role are enforced in
  `aeon_auth.py` (e.g. `require_auth`, `require_workspace_role`). New sensitive
  endpoints must use those decorators, not hand-rolled checks.
- Frontend API routes forward the browser JWT (`Authorization` header) to the
  backend; keep API keys and secrets server-side only.
- Demo data: when adding a new page-rendering GET route, route it through
  `backendFetch`/`proxyApiRequest` and add a matching entry in
  `web/lib/demo-data.ts` so it renders without the backend.
- Keep responses shaped as `{ ok: true, demo?: true, ...data }`.
- TypeScript strict — run `npm run build` in `web/` before finishing changes.

## LLM / AI

- Backend LLM provider is selected per workspace via `AEON_LLM_PROVIDER`
  (openai | anthropic | google | mistral | openrouter | ollama | lmstudio |
  vllm | hf | qwen | custom | stub). Provider keys are read from environment
  variables (e.g. `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`).
- `aeon_llm.py` owns provider implementations; `/llm/models` discovery probes
  OpenAI-compatible providers server-side.
- All AI calls are recorded in the AI execution ledger (`aeon_ai_ledger.py`).

## Environment

- `env.example` documents every variable. Never commit real secrets.
- Keys live in the platform's Keys/API Keys tab (e.g. `ANTHROPIC_API_KEY`),
  not in `.env` files committed to Git.
