# AEON v3.0

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/beatznlg/aeon/blob/main/colab_runner.ipynb)

> **Source of truth = this GitHub repo.** A single launcher cell in
> `colab_runner.ipynb` pulls the latest commit, installs the deps, and executes
> [`aeon.py`](./aeon.py). Push to `main` → re-run the cell → AEON is on the new
> code. See [GitHub → Colab workflow](#github-→-colab-workflow) below.

AEON v3.0 is a self-improving autonomous agent in one Python file. It builds on
the v2.1 kernel (IBC, KG, CausalCredit, episodic store, Qwen2.5-3B-Instruct)
and adds a **ReflectiveAgent** with triad memory, persistent goals, a
self-model, a **CodeSandbox/CodeEvolver** for generating new tools, a
**Web3Client** hot wallet on Base testnet, and a **revenue/service layer**
(ledger, service registry, mock bounty board). All tools run under
`SIGALRM` timeouts and the whole file self-tests on load.

The whole thing is one Python file: [`aeon.py`](./aeon.py). On first run it
self-tests, then runs a short demo, then exits. It is designed to be executed
as a single Colab cell (or directly with `python aeon.py`).

---

## 🚀 Deploy in 5 minutes (start here if you just cloned)

The repo ships with three wrapper scripts so the entire chain — Vercel
frontend + HF Spaces kernel + Supabase database — is reproducible from one
shell call each. None of them require you to paste any secret into chat.

```bash
# 1. Rotate any leaked secrets first (printer-only, no network).
bash scripts/post-rotate.sh

# 2. Local sanity: kernel compiles and the 7 self-tests still pass.
python3 -m py_compile aeon.py && python3 aeon.py   # (Ctrl-C after the demo runs)

# 3a. Push the Vercel frontend (Vercel CLI will print the deployment URL).
bash scripts/deploy-vercel.sh

# 3b. Push the AEON kernel to a Hugging Face Space (the permanent GPU host).
HF_USERNAME=yourname HF_SPACESLUG=aeon-kernel HF_TOKEN=hf_... \
  bash scripts/deploy-hf-space.sh

# 4. Verify the live deployment (replace <host> with the URL from step 3a).
curl -s https://<host>/api/health       | jq
curl -s https://<host>/api/setup_check | jq
```

The first two commands are safe to run anywhere — they make zero network
calls. Steps 3a/3b need the rotate-and-paste flow above so secrets only
land in your dashboards / Secrets tabs, never in your shell history.

The scripts directory:

```
scripts/
├── post-rotate.sh       ← printer-only rotation checklist
├── deploy-vercel.sh     ← py_compile + 7 tests + JSON check + npx vercel --prod
└── deploy-hf-space.sh   ← HF Hub upload of aeon.py + gradio wrapper
```

### What "live" looks like

After `deploy-vercel.sh` returns, hitting `/api/setup_check` shows which
keys are wired into the Vercel instance:

```json
{
  "ok": true,
  "backend": "aeon-kernel",
  "keys": {
    "huggingface_token":       { "present": true,  "length": 41 },
    "supabase_url":            { "present": true,  "host": "xyz.supabase.co" },
    "next_public_supabase_url":{ "present": true,  "host": "xyz.supabase.co" },
    "aeon_hf_space_url":       { "present": true,  "host": "yourname-aeon-kernel.hf.space" },
    "gh_token":                { "present": false, "length": 0 }
  },
  "notes": ["GH_TOKEN missing — GitHub code search capped at 10/min/IP."]
}
```

The Sidebar's status dot reads this endpoint on load and every 30 s:
🟢 green = live + all keys wired · 🟡 yellow = live but missing a key ·
🔴 red = Vercel itself is down · ⚪ grey = still polling.

---

## What's automatic on the free tier — and what isn't

**Free Google Colab has no public run API.** Nothing can externally trigger a
notebook cell to execute without you clicking ▶︎ at least once per session,
and you still have to pick the T4 GPU runtime + tick "Notebook access" on each
🔑 Secret. Everything **outside** those three clicks is fully automatic.

| Step | Driver | Status |
|---|---|---|
| Edit code in Freebuff / repo | you | manual |
| Push new commits to `origin/main` | Freebuff deploy token (`ghs_…`) embedded in the remote URL | **automatic** — every Freebuff save |
| Compile-check `aeon.py` + JSON-validate `colab_runner.ipynb` | GitHub Actions on push to `main` (`.github/workflows/aeon-ci.yml`) | **automatic**; on success it prints the click-to-run URL |
| Print click-to-run Colab badge URL with the latest short SHA | the same Actions run, on success | **automatic** |
| Open the Colab notebook in your browser | you | **manual** — but the URL is one click from either the badge above, the Actions log, or the README header |
| Pick the T4 GPU runtime | you (Runtime ▸ Change runtime type) | **manual** — free Colab's hard ceiling |
| Pull the latest commit, install deps, run `aeon.py` | the launcher cell | **automatic** once you click ▶︎ |

> **Bottom line:** the entire chain is automatic **except** the three clicks —
> open the badge, choose T4 GPU, ▶︎ the cell. No GitHub Actions trick replaces
> those on the free tier without violating Google Cloud ToS (headless
> puppeteer/Chrome automation is detected and reCAPTCHA'd; the only legit
> paid alternative is Colab Enterprise / Vertex AI Workbench).

---

## Phase 0 Foundation — local auth & Postgres (development)

AEON OS now uses SQLAlchemy + Postgres for identity, multi-tenancy, and
persistence. The quickest way to run it locally is:

1. Install PostgreSQL 14 and create a database/user:

   ```bash
   sudo apt-get install -y postgresql postgresql-contrib
   sudo pg_ctlcluster 14 main start
   sudo -u postgres psql -c "CREATE USER aeon WITH PASSWORD 'aeon_test' CREATEDB;"
   sudo -u postgres psql -c "CREATE DATABASE aeon OWNER aeon;"
   ```

2. Apply the Supabase migrations in order:

   ```bash
   psql -h localhost -U aeon -d aeon -f supabase/migrations/0000_users_and_audit.sql
   psql -h localhost -U aeon -d aeon -f supabase/migrations/0001_workspace_rbac.sql
   psql -h localhost -U aeon -d aeon -f supabase/migrations/0002_seed_admin.sql
   psql -h localhost -U aeon -d aeon -f supabase/migrations/0003_governance.sql
   psql -h localhost -U aeon -d aeon -f supabase/migrations/0004_phase0_foundation.sql
   ```

3. Start the Flask server:

   ```bash
   export AEON_DATABASE_URL="postgresql+psycopg2://aeon:aeon_test@localhost:5432/aeon"
   export AEON_JWT_SECRET="change-me-in-production"
   python aeon_server.py
   ```

4. Log in with the seeded admin:

   ```bash
   curl -X POST http://localhost:5000/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"beatznlg@gmail.com","password":"AeonDevAdmin2024!"}'
   ```

   > ⚠️ The development-only admin password is documented in
   > `supabase/migrations/0002_seed_admin.sql`. Change it in production
   > or use the password-reset flow.

### Required environment variables for Phase 0

| Variable | Example | Purpose |
|---|---|---|
| `AEON_DATABASE_URL` | `postgresql+psycopg2://aeon:aeon_test@localhost:5432/aeon` | Postgres connection for SQLAlchemy |
| `AEON_JWT_SECRET` | long random string | HMAC secret for signing access tokens |
| `ADMIN_EMAIL` | `beatznlg@gmail.com` | Fallback bootstrap admin email |
| `ADMIN_PASSWORD_HASH` | `pbkdf2:sha256:...` | Fallback bootstrap admin hash |

---

## Architecture (one file, layered)

| Layer | What it does |
| --- | --- |
| **IBC** | Deterministic continuous → symbolic binding via random projection + lattice keying |
| **KG** | Typed directed graph with weighted, timestamped edges |
| **EpisodicStore** | Append-only JSONL window of observations / queries / answers |
| **CausalCredit** | Eligibility-trace credit assignment with exponential decay |
| **QwenPolicy** | Lazy-loads `Qwen/Qwen2.5-3B-Instruct` with 4-bit bitsandbytes on CUDA; falls back to a deterministic stub on CPU/missing deps |
| **HFClient** | Serverless Hugging Face Inference API fallback (no weights) |
| **GitHubClient** | Code-search buff via GitHub REST API (no-auth or fine-grained PAT) |
| **SupabaseClient** | Optional Postgres mirror of every `EpisodicStore.append` |
| **Tool registry** | `math`, `search`, `fetch`, `read_skill`, `write_skill` — each run under a `SIGALRM` timeout |
| **AeonKernel** | Orchestrates: prompt → LLM → tool-call extraction → execution → telemetry CSV |
| **Self-test + demo** | Runs on module load: 10 self-tests (memory, goals, self-model, reflection, action, sandbox, evolver, web3, github, revenue), then demo ticks |

---

## Environment variables / secrets

These are read via `os.getenv` (the launcher can also inject them). Marked as
**required** or **recommended/optional** below.

| Variable | Required? | What it unlocks |
| --- | --- | --- |
| `HUGGINGFACE_TOKEN` | Recommended | Hugging Face access token. Unlocks (a) Hub model downloads when `QwenPolicy` loads `Qwen/Qwen2.5-3B-Instruct` via `transformers`, and (b) the new `HFClient` serverless Inference API call used as a lightweight third backend. Create one for free at <https://huggingface.co/settings/tokens>. |
| `AEON_HF_TOKEN` | Back-compat alias | Same effect as `HUGGINGFACE_TOKEN`; `HUGGINGFACE_TOKEN` takes precedence. Kept so older configs still work without edits. |
| `SUPABASE_URL` | Optional | Project URL from your free Supabase dashboard, e.g. `https://xyz.supabase.co`. Activates the `SupabaseClient` and `EpisodicStore.append`'s optional cloud sink. Create one free at <https://supabase.com/dashboard>. |
| `SUPABASE_ANON_KEY` | Optional | Public anon JWT issued by Supabase. Together with `SUPABASE_URL` activates the optional Postgres sync of every `EpisodicStore` row. Prefer the **service-role** key if you want server-only writes from a non-AEON CLI. |
| `SUPABASE_SERVICE_ROLE_KEY` | Optional | Server-side admin JWT (treat as secret). Used only when `SUPABASE_ANON_KEY` is not set. |
| `GH_TOKEN` | Optional | GitHub fine-grained PAT for `ghc.search_code(...)` (raises free-tier rate limit from 10/min/IP to 30/min/token). Get one at <https://github.com/settings/tokens?type=beta> — Contents: Read on `Public repositories` is enough. |
| `GITHUB_TOKEN` | Back-compat alias | Same as `GH_TOKEN`; `GH_TOKEN` wins. |
| `AEON_ROOT` | Optional | Override the state root path (defaults to `/content/aeon_state` on Colab). |
| `GITHUB_TOKEN` (Colab launcher) | Optional | Fine-grained PAT with `Contents: Read` — only needed if this repo is private. |

> ⚠️ Both env vars named `GITHUB_TOKEN` are checked by **different** things:
> the Python kernel's `GitHubClient` reads either via `_resolve_github_token()`;
> the Colab launcher's `git clone` reads it via os.getenv. They are the same
> value if you only set one.

The launcher cell **also** reads `GITHUB_TOKEN` so it can clone/pull a private
repo. If the repo is public, leave `GITHUB_TOKEN` blank.

---

## Hugging Face integration

AEON v2.1 uses Hugging Face for **two distinct things**, both gated by
`HUGGINGFACE_TOKEN`:

| Layer | Purpose | When it kicks in |
| --- | --- | --- |
| **Hub download** (via `transformers`) | Downloads `Qwen/Qwen2.5-3B-Instruct` (≈ 1.5 GB in 4-bit) on the first GPU runtime boot. | First `QwenPolicy._try_load()` call after picking a T4 runtime. |
| **Serverless Inference API** (new `HFClient`) | Bare `requests.post` against `https://api-inference.huggingface.co/models/<model>`. Lets AEON reach *any* Hub model without downloading weights — useful as a third fallback behind local Qwen and the deterministic stub. | When `HFC.generate(prompt)` is called explicitly, or wired into the `ask()` decision tree. |

A working `HFC.whoami()` call is the cheapest way to confirm the token is alive:

```python
HFC.whoami()         # -> {"ok": True, "name": "...", "plan": "free"}
HFC.generate("hi")   # -> {"ok": True, "output": "...!"}
```

Be aware the Inference API is rate-limited and small models sometimes
return HTTP 503 ("model loading") on first call — retry once.

---

## Supabase integration

AEON also supports **optional Postgres persistence** via Supabase. When
`SUPABASE_URL` plus an anon or service-role key are present, every
`EpisodicStore.append(...)` is mirrored to a free Postgres table in
addition to the local `history.jsonl`. The local file remains the
source of truth in offline mode; the cloud sink is graceful-fire-and-forget
(wrapped in a try/except so a Supabase outage never breaks the kernel).

### One-time setup (≈ 90 seconds)

1. Create a free project at <https://supabase.com/dashboard> (no card).
2. In **Project Settings ▸ API**, copy:
   - **Project URL** → set as `SUPABASE_URL`
   - **anon public** key → set as `SUPABASE_ANON_KEY`
3. In **SQL Editor**, run **once**:

   ```sql
   create table episodes (
     id  bigint primary key generated always as identity,
     ts  float8 not null,
     kind text  not null,
     text text  not null,
     ref  text
   );

   -- Recommended: enable RLS so anon users cannot write directly
   alter table episodes enable row level security;
   create policy "anon read" on episodes
     for select using (auth.role() = 'anon');
   create policy "service write" on episodes
     for insert with check (auth.role() = 'service_role');

   -- Index for the AEON "last N episodes" query pattern
   -- (chat UI calls /api/memories/tail with .order('id', ascending=false).limit(N))
   create index if not exists episodes_id_desc_idx on episodes (id desc);

   -- Optional: cap the `text` column at the same 2000 chars the web client
   -- trims to; prevents accidental junk uploads inflating the table.
   -- Comment out if you'd rather keep it unbounded.
   -- alter table episodes add constraint episodes_text_len check (length(text) <= 2000);
   ```

4. (Verify step, last 30 seconds)  In the **Supabase ▸ Table Editor**,
   confirm the `episodes` table appears with 5 columns: `id` (bigint,
   auto-increment), `ts` (numeric), `kind` (text), `text` (text), `ref`
   (text, nullable).  RLS should be "enabled" on the table.

### Programmatic usage (after the cell has run)

```python
SBC.whoami()        # -> {"ok": True, "url": "https://xyz.supabase.co"}  # auth OK
SBC.ping()          # -> {"ok": True, "rows": 0}                         # table reachable
SBC.tail(5)         # -> {"ok": True, "rows": [{...}, ...]}             # most recent 5 episodes
```

The `SupabaseClient` is built on `requests` against PostgREST
(`<SUPABASE_URL>/rest/v1/episodes`) — no `supabase-py` SDK is added to
`requirements.txt`, keeping the dep footprint identical to AEON v2.1.

---

## GitHub buff

AEON exposes a **no-auth** GitHub code-search client right in the Python
kernel. The Vercel frontend proxies it via `/api/github_search` (server-side,
so your browser never sees rate-limit issues).

| Layer | Purpose | When it kicks in |
|---|---|---|
| **In-kernel** (`GHC.search_code("python retry decorator")`) | Free no-auth code search across all public GitHub repos. | When `ghc.search_code(...)` is called inside `AeonKernel` or via the kernel's Gradio surface. |
| **Web proxy** (`web/app/api/github_search/route.ts`) | Same API from the browser, but with the server's `GH_TOKEN` if you set it (raises 10 req/min × IP to 30 req/min). | When the chat UI adds a `/github` shorthand command (next iteration). |

Defaults: works with zero env vars but at the cost of strict rate limits
(60 requests/IP/hour across the whole GitHub API). Set `GH_TOKEN`
(Contents: Read on public repos only) for ~30× headroom.

### Self-test 9 (network call)

The kernel's self-test now probes the GitHub `/rate_limit` endpoint and
validates the shape of `search_code`. Without a token the rate-limit check
still works; the search call returns a structured `{"ok": False, "error": ...}`
response because GitHub code search now requires authentication.

---

## Vercel AI SDK frontend (with closed-loop wiring)

For a real chat UI, AEON ships with a minimal **[Vercel AI SDK](https://sdk.vercel.ai)**
Next.js app under [`web/`](./web). It is **independent** of the Python
kernel — `aeon.py` itself is untouched — but it reuses the same
`HUGGINGFACE_TOKEN` you already provide to AEON for Hub model downloads,
now routed through `@ai-sdk/huggingface` on the server side for
streaming responses in the browser.

### What's in `web/`

```
web/
├── package.json              Next.js + ai + @ai-sdk/huggingface + @ai-sdk/react
│                            + @gradio/client + @supabase/supabase-js
├── tsconfig.json
├── .env.example              Sample env keys, all server/browser-labeled
├── app/
│   ├── layout.tsx            Root layout + global styles
│   ├── page.tsx              2-column layout (Sidebar + main with Topbar/ChatPanel)
│   ├── globals.css           Hand-written premium dark theme + glass topbar
│   └── api/
│       ├── chat/route.ts     Stream from AEON-on-HF-Space (preferred) or HF Inference (fallback)
│       ├── health/route.ts   GET liveness probe
│       ├── memories/tail/route.ts   Server-side paginated Supabase tail
│       └── github_search/route.ts    POST body {query,limit} → GitHub code search
└── components/
    ├── Sidebar.tsx           Brand, New chat, nav, footer status dot
    ├── Topbar.tsx            Backend selector + theme toggle (localStorage)
    ├── ChatPanel.tsx         useChat, hero empty state, sticky input
    ├── SettingsDrawer.tsx    Env status + RLS hardening SQL + external links
    └── MemoryBrowser.tsx     Modal paginated episode browser
```

### Run locally (≈ 30 seconds)

```bash
cd web
npm install
HUGGINGFACE_TOKEN=hf_... NEXT_PUBLIC_SUPABASE_URL=... \
  NEXT_PUBLIC_SUPABASE_ANON_KEY=... AEON_HF_SPACE_URL=... \
  npx next dev    # → http://localhost:3000
```

### Deploy on Vercel (1-click, free tier)

```bash
cd web
npx vercel
# in Vercel dashboard: Settings ▸ Environment Variables
# (set the four keys + optionally SUPABASE_SERVICE_ROLE_KEY + GH_TOKEN)
npx vercel --prod
```

The deployed URL is `https://aeon-web-<hash>.vercel.app`.

### Risks (read before deploying)

- **`NEXT_PUBLIC_*` prefix is for browser-visible keys only.** `HUGGINGFACE_TOKEN`,
  `AEON_HF_SPACE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `GH_TOKEN` must NEVER
  be `NEXT_PUBLIC_` — otherwise they ship in the browser bundle. The
  included routes read them server-side only. If you fork and accidentally
  re-export to a `*.client.ts` or `NEXT_PUBLIC_*`, **rotate the token**.
- **Hub rate limits.** Hugging Face's free Inference API is shared
  across all free users; the first call to a small model can return
  HTTP 503 ("model loading") for ~20 s. Retry once.
- **`.env.local` is gitignored, but `.env.example` is committed** with
  example placeholders. Copy `.env.example` to `.env.local` for local dev.

---

## Closed-loop deployment (three free services, one app)

The repo is wired so **all four pieces** of the architecture can talk to
each other end-to-end, each on a free tier:

```
┌────────────────┐    SSE    ┌────────────────┐  HTTP/WS  ┌─────────────────────────┐
│ Browser        │ ────────▶ │ Vercel Edge    │ ────────▶ │ AEON kernel             │
│ web/app/page   │           │ /api/chat route│           │ (HF Spaces, ZeroGPU)    │
│ (useChat +     │           │   @gradio/     │           │  AeonKernel.tick()      │
│  Supabase UI)  │           │   client +     │           │  + Qwen 3-bit on GPU    │
│  + GitHub buff)│           │   fallback)    │           │  + GitHub code search   │
└───────┬────────┘           └────────┬─────────┘           └────────────┬────────────┘
        │                             │                                  │
        │                  ┌────────────────┐                         │
        └────────────────▶ │  Supabase      │ ◀───────────────────────┘
                           │  episodes      │   EpisodicStore.append()
                           │  + future      │   cloud mirror
                           └────────────────┘
```

### Step 1. AEON brain on Hugging Face Spaces (the permanent GPU host)

Equivalent to running your Colab session **permanently with a T4/A100**.

1. Create a fresh Space: <https://huggingface.co/new-space> → SDK **Gradio**,
   hardware **ZeroGPU** (free A100 slices on demand).
2. Push these three files from the repo root into your Space:
   - `aeon.py` (the kernel — unchanged)
   - `aeon_app_gradio.py` (the Gradio wrapper)
   - `requirements.txt`
3. In **Space Settings ▸ Variables and secrets**, add `HUGGINGFACE_TOKEN`
   so the Qwen 3-bit download works on first request.
4. Wait ~2 minutes for the Space to boot. Visit
   `https://<your-username>-aeon-kernel.hf.space` and confirm
   the chat works directly there.

### Step 2. Vercel frontend setup

```bash
cd web
npx vercel                 # one-time project creation
```

Then in **Project Settings ▸ Environment Variables**, paste these keys
(copy from `web/.env.example` for the right names):

| Variable | Prefix | Required | Purpose |
|---|---|---|---|
| `HUGGINGFACE_TOKEN` | none (server) | yes | Used by `/api/chat` if it falls back to direct HF Inference API. |
| `NEXT_PUBLIC_SUPABASE_URL` | `NEXT_PUBLIC_` | recommended | Browser's recent-episode panel + per-turn write through the UI. |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `NEXT_PUBLIC_` | recommended | Pairs with the URL above. |
| `AEON_HF_SPACE_URL` | none (server) | recommended | **The closed-loop wire.** URL of your HF Space from Step 1, without trailing `/chat`. When set, the Vercel route proxies AEON's `tick()` from there. When unset, the route falls back to the HF Inference API directly. |
| `SUPABASE_SERVICE_ROLE_KEY` | none (server) | optional | Server-side write log inside `/api/chat` (and `/api/memories/tail`). Do **NOT** add `NEXT_PUBLIC_` prefix. |
| `GH_TOKEN` | none (server) | optional | Raises GitHub code-search rate limit from 10/min/IP to 30/min. |

`npx vercel --prod` for the production deploy.

### Step 3. Supabase one-time schema (already in turn 9 + RLS hardening above)

Already documented under [Supabase integration](#supabase-integration)
above. The `episodes` table already exists once the AEON Python side has
written to it once; the web frontend will read from the same table.

### Step 4. Verify the closed loop

1. Visit `https://aeon-web-<hash>.vercel.app`
2. Send a prompt; you should see it stream from the AEON HF Space.
3. Refresh the page; your recent turn should appear in the **Memories**
   panel (loaded from Supabase).
4. Open **Memory browser** from the sidebar — paginate through past turns.
5. Open the Supabase dashboard → **Table Editor ▸ episodes** — each turn
   is there with `ref` like `web_v3` (browser) or `web_api_aeon_kernel`
   (server route).

### What runs where

| Component | Runs on | Free tier? | Notes |
|---|---|---|---|
| `web/` Next.js app | Vercel Edge | ✅ | Static + Serverless, no time limit. |
| `web/app/api/chat` route | Vercel Edge Function (maxDuration=60) | ✅ | Streams from AEON via `@gradio/client`. |
| AEON kernel `tick()` | Hugging Face Spaces (Gradio SDK) | ✅ ZeroGPU | Real GPU on demand; same Qwen code path that previously only ran on Colab T4. |
| AEON self-tests 1-7 | Colab (dev surface) | ✅ | Used interactively while developing; not on the request path. |
| AEON's EpisodicStore | Google Drive (dev) + Supabase `episodes` (prod) | ✅ | Cloud mirror is automatic whenever `SUPABASE_URL` + a key are set. |
| GitHub code search buff | In-process | ✅ | No-auth by default; `GH_TOKEN` raises the quota. |

### Why this is better than Vercel-talks-to-HF-Inference-direct

When `AEON_HF_SPACE_URL` is set, the call path is now:

```
Vercel Edge → AEON kernel → Qwen 3-bit model on real GPU
   (Bypasses HF Inference API's strict rate limits.)
```

This means:

- ✅ Every Vercel user gets a real GPU inference result, not a 503 "model loading" from the HF queue.
- ✅ AEON's tools (`math`, `search`, `fetch`, `read_skill`, `write_skill`) actually run for every Vercel prompt — the inference path used to skip them.
- ✅ AEON's `EpisodicStore.append()` runs for every prompt and AWS writes to the episodes table.
- ✅ Each prompt contributes a row to `episodes` regardless of which model backend served it.

When `AEON_HF_SPACE_URL` is **not** set, the route gracefully falls back to
the original HF Inference API direct call (still uses `HUGGINGFACE_TOKEN`).
This keeps the Vercel deploy working even before you finish Step 1.

---

## How to run

The canonical way to run AEON v2.1 is to **click the "Open in Colab" badge at
the top** — that opens [`colab_runner.ipynb`](./colab_runner.ipynb) which is a
single code cell that does:

1. **Clone or pull** `https://github.com/beatznlg/aeon.git` into `/content/aeon`
2. **Install** dependencies with `pip install -r requirements.txt`
3. **Run** `aeon.py` via `exec()` (the cell runs 7 self-tests + 5 demo ticks, then exits)

### One-time pre-flight per notebook

Before you click ▶︎ on the launcher cell:

1. **Runtime ▸ Change runtime type** → **T4 GPU** (free tier is fine; the
   model will load with 4-bit quantization on CUDA).
2. Open the left sidebar **🔑 Secrets** panel and add each variable from the
   table above (including `GITHUB_TOKEN` only if the repo is private),
   ticking **"Notebook access"** for every secret.
3. *(alternative)* — set `HUGGINGFACE_TOKEN`, `AEON_ROOT`, etc. as
   `os.environ[...]` directly in the cell if you'd rather skip the Secrets tab.

### To run outside Colab (Linux + NVIDIA GPU)

You don't need the launcher notebook — just run the script directly:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
HUGGINGFACE_TOKEN=... python aeon.py
```

> Caveat outside Colab: the script defaults `AEON_ROOT` to `/content/aeon_state`;
> override with `AEON_ROOT=/path/to/state`.

---

## GitHub → Colab workflow

This is the edit / push / run loop. The IDE side is automatic (Freebuff
auto-pushes on save via the embedded `ghs_…` deploy token). The cell side is
automatic once per session you click ▶︎ (the launcher pulls + pip-installs +
execs). What's manual is the badge click, the runtime choice, and the run
button — see [the automation table above](#whats-automatic-on-the-free-tier--and-what-isnt).

```text
       (edit in Freebuff)
                │
        ┌───────▼────────┐
        │  Freebuff UI    │  ← manual
        └───────┬────────┘
                │  git push (deploy token ghs_…)
                ▼
        github.com/beatznlg/aeon  (source of truth)  ← automatic
                │
                ▼
        GitHub Actions: smoke-check aeon.py + notebook JSON
        on-success print: https://colab.research.google.com/github/.../colab_runner.ipynb  ← automatic
                │
                ▼
        (you click the badge or follow the URL)          ← manual
                │
                ▼
        colab_runner.ipynb  →  T4 GPU  →  cell runs
        ┌───────────────────────────────────────┐
        │ 1. !git clone / !git pull (with PAT)  │
        │ 2. pip install -r requirements.txt    │
        │ 3. exec(open("aeon.py").read())       │
        └─────────────┬─────────────────────────┘
                      ▼
           aeon.py runs 7 self-tests + demo on the latest commit
```

### Re-deploy after a push

1. Go back to your open Colab tab.
2. **Stop** the running cell (■ button).
3. **Re-run** the same cell. The launcher will see the working dir already
   exists, do `git pull --rebase --autostash`, re-install deps (incrementally
   — `pip install -r requirements.txt` only fetches what's missing), and re-exec
   `aeon.py` with the new commit.
4. The `[launcher] HEAD = …` print line right before `exec` confirms which
   commit you're on. Match it against the short SHA in your last Actions run.

---

## Programmatic usage

After the cell runs (or after `exec` in your own notebook), the public classes
are available:

```python
from aeon import AeonKernel, QW, HFC, SBC, GHC

ak = AeonKernel()
result = ak.tick("What is the integral of x^2?")
print(result["answer"])
print(result["backend"])   # "stub" or "qwen2.5-3b_cuda"/"qwen2.5-3b_cpu"

# Suite of available buff clients
HFC.whoami()                                  # HF Identity probe
HFC.generate("hello")                         # HF inference fallback
SBC.tail(5)                                   # Recent Supabase episodes
SBC.insert_episode({"ts": time.time(),        # Manual episode write
                    "kind": "bot", "text": "...",
                    "ref": "my-tool"})
GHC.search_code("python retry decorator")     # GitHub code search (requires token)
GHC.rate_limit()                              # GitHub API quota probe (works without token)
GHC.whoami()                                  # GitHub authenticated user info
```

---

---

## 🛡️ Security (GitHub Advanced Security)

AEON ships with GitHub Advanced Security enabled at the workflow / config
level. **It is FREE for public repositories** — every built-in component
(CodeQL code scanning, secret scanning, Dependabot alerts, Dependabot
version updates) is included at no cost on `beatznlg/aeon`. For private
repos the same features require a GitHub Enterprise + GHAS entitlement.

### What's running automatically on every push

| Tool | Trigger | What it does | Where alerts land |
|---|---|---|---|
| **CodeQL** (`.github/workflows/codeql.yml`) | push to `main`, every PR, weekly Sunday 04:00 UTC | Static analysis on Python (`aeon.py`, `scripts/*.py`) and JS/TS (`web/`) using the `security-extended` query pack | [Security tab ▸ Code scanning](https://github.com/beatznlg/aeon/security/code-scanning) |
| **Dependabot** (`.github/dependabot.yml`) | weekly (Mon 04:00 UTC) | Watches `requirements.txt`, `web/package.json`, and `/.github/workflows/*` for outdated or vulnerable deps. Auto-opens PRs for safe bumps. LLM kernel majors + Next.js + AI-SDK majors are ignored (bump manually). | [Security tab ▸ Dependabot alerts](https://github.com/beatznlg/aeon/security/dependabot) + Dependabot PRs |
| **Secret scanning** | every push | Built into GitHub for public repos — detects tokens matching known partner patterns (GitHub PATs, OpenAI keys, Hugging Face tokens, Supabase keys, etc.). New patterns auto-added by GitHub over time. | [Security tab ▸ Secret scanning alerts](https://github.com/beatznlg/aeon/security/secret-scanning) |
| **Push protection** | every push | (if enabled) blocks a push that would expose a known-pattern secret. **Strongly recommended.** | [Settings ▸ Code security and analysis](https://github.com/beatznlg/aeon/settings/security_analysis) |
| **`aeon-ci.yml`** (existing) | every push | Compile check + 7 self-tests + JSON + TS lint. Non-blocking web TS job. | Actions tab |

### One-time clicks in GitHub UI (≈ 2 minutes; free for public repos)

1. Open <https://github.com/beatznlg/aeon/settings/security_analysis>
2. Under **Code security and analysis** enable these:
   - **Code scanning → CodeQL analysis** ▸ **Default** (uses workflow we just shipped)
   - **Dependabot → Dependabot security updates** ▸ **Enable**
   - **Dependabot → Dependabot version updates** ▸ **Enable** (auto-enabled by `dependabot.yml`)
   - **Secret scanning** ▸ **Enable**
   - **Push protection** ▸ **Enable** (blocks known-pattern secrets, won't block source code)
3. (Optional later) Add a `.github/CODEOWNERS` file for review-required-from-owner on `web/` and `scripts/`.

### URLs that surface alerts

| URL | What it shows |
|---|---|
| <https://github.com/beatznlg/aeon/security> | All advisories in one feed |
| <https://github.com/beatznlg/aeon/security/code-scanning> | CodeQL findings — open one to see the data-flow graph |
| <https://github.com/beatznlg/aeon/security/dependabot> | Vulnerable deps + auto-fix PRs |
| <https://github.com/beatznlg/aeon/security/secret-scanning> | Tokens pushed into history. **If anything appears here, rotate IMMEDIATELY and consider `git filter-repo` to scrub history.** |

### Free vs Paid in GHAS

| Feature | Public repo | Private repo |
|---|---|---|
| Code scanning (CodeQL) | ✅ Free | Requires GitHub Enterprise + GHAS |
| Secret scanning | ✅ Free | Requires GHAS |
| Push protection | ✅ Free | Requires GHAS |
| Dependabot alerts | ✅ Free | ✅ Free (no GHAS needed) |
| Dependabot version updates | ✅ Free | ✅ Free |
| CodeQL custom query packs | ✅ Free | Requires GHAS |

Conclusion: if `beatznlg/aeon` stays public, every warning surfaced above
is at no monetary cost.

### Keys to add — ⛔ none new for the workflow itself

This is the part where the integration is unusual: **GHAS at the
workflow level requires no new PAT or API key**. The CodeQL + Dependabot
workflows rely on GitHub's auto-injected `${{ secrets.GITHUB_TOKEN }}`,
with the narrowest principle-of-least-privilege permissions declared
per job (`contents: read`, `security-events: write`).

If you later want to surface CodeQL alerts **inside the Vercel chat UI**
(an in-app Security tab), you would add one optional fine-grained PAT:
- `GITHUB_SECURITY_TOKEN` — fine-grained PAT with `security_events: read` scope,
  to wire a `/api/security` Vercel route. **Not required for the workflow to run.**

### What I am NOT changing

- **No new PATs in the workflow.** CodeQL + Dependabot use the auto-injected token only.
- **No new files in `web/` or `scripts/`.** GHAS runs on the existing pipeline; the web frontend stays untouched.
- **`aeon.py` kernel is untouched.** The 7 self-tests + behavior are unchanged.

---

## File listing

```
.
├── .github/
│   └── workflows/
│       └── aeon-ci.yml    ← syntax + JS type-check on every push
├── scripts/              ← NEW: one-command deploy + rotate wrappers
│   ├── post-rotate.sh       (printer-only; leak-mitigation checklist)
│   ├── deploy-vercel.sh     (py_compile + 7 tests + npx vercel --prod)
│   └── deploy-hf-space.sh   (HF Hub upload of aeon.py + gradio wrapper)
├── README.md             ← this file
├── aeon.py               ← the entire single-cell kernel (7 self-tests)
├── aeon_app_gradio.py    ← Gradio wrapper for HF Spaces deploy
├── colab_runner.ipynb    ← Open-in-Colab launchpad (clone + pip + exec)
├── .gitignore            ← Python cache, virtualenv, aeon state, JS frontend build artifacts
├── requirements.txt      ← pip install -r requirements.txt
└── web/                  ← (optional) Vercel AI SDK chat UI — Next.js 14 + TS
```
