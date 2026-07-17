# AEON v2.1

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/beatznlg/aeon/blob/main/colab_runner.ipynb)

> **Source of truth = this GitHub repo.** A single launcher cell in
> `colab_runner.ipynb` pulls the latest commit, installs the deps, and executes
> [`aeon.py`](./aeon.py). Push to `main` → re-run the cell → AEON is on the new
> code. See [GitHub → Colab workflow](#github-→-colab-workflow) below.

AEON v2.1 is a minimal-but-complete autonomous kernel in one Python file. It
combines a deterministic **IBC** symbolic-binding layer, a typed **knowledge
graph**, an causal-credit eligibility-trace learner, an episodic store, and a
lazy-loading **Qwen2.5-3B-Instruct** policy (via `transformers` + `bitsandbytes`
on GPU, stub fallback on CPU). A small tool registry (`math`, `search`, `fetch`,
`read_skill`, `write_skill`) is sandboxed with `SIGALRM` timeouts.

The whole thing is one Python file: [`aeon.py`](./aeon.py). On first run it
self-tests, then runs a short demo, then exits. It is designed to be executed
as a single Colab cell (or directly with `python aeon.py`).

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

## Architecture (one file, layered)

| Layer | What it does |
| --- | --- |
| **IBC** | Deterministic continuous → symbolic binding via random projection + lattice keying |
| **KG** | Typed directed graph with weighted, timestamped edges |
| **EpisodicStore** | Append-only JSONL window of observations / queries / answers |
| **CausalCredit** | Eligibility-trace credit assignment with exponential decay |
| **QwenPolicy** | Lazy-loads `Qwen/Qwen2.5-3B-Instruct` with 4-bit bitsandbytes on CUDA; falls back to a deterministic stub on CPU/missing deps |
| **Tool registry** | `math`, `search`, `fetch`, `read_skill`, `write_skill` — each run under a `SIGALRM` timeout |
| **AeonKernel** | Orchestrates: prompt → LLM → tool-call extraction → execution → telemetry CSV |
| **Self-test + demo** | Runs on module load: validates IBC, tools, skill I/O, then performs 5 demo ticks |

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
| `AEON_ROOT` | Optional | Override the state root path (defaults to `/content/aeon_state` on Colab). |
| `GITHUB_TOKEN` | Optional | Fine-grained PAT with `Contents: Read` — only needed if this repo is private. |

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
   ```

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

## How to run

The canonical way to run AEON v2.1 is to **click the "Open in Colab" badge at
the top** — that opens [`colab_runner.ipynb`](./colab_runner.ipynb) which is a
single code cell that does:

1. **Clone or pull** `https://github.com/beatznlg/aeon.git` into `/content/aeon`
2. **Install** dependencies with `pip install -r requirements.txt`
3. **Run** `aeon.py` via `exec()` (the cell runs self-tests + demo, then exits)

### One-time pre-flight per notebook

Before you click ▶︎ on the launcher cell:

1. **Runtime ▸ Change runtime type** → **T4 GPU** (free tier is fine; the
   model will load with 4-bit quantization on CUDA).
2. Open the left sidebar **🔑 Secrets** panel and add each variable from the
   table above (including `GITHUB_TOKEN` only if the repo is private),
   ticking **"Notebook access"** for every secret.
3. *(alternative)* — set `AEON_HF_TOKEN`, `AEON_ROOT`, etc. as
   `os.environ[...]` directly in the cell if you'd rather skip the Secrets
   tab.

### To run outside Colab (Linux + NVIDIA GPU)

You don't need the launcher notebook — just run the script directly:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
AEON_HF_TOKEN=... python aeon.py
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
           aeon.py runs self-tests + demo on the latest commit
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
from aeon import AeonKernel, QW

ak = AeonKernel()
result = ak.tick("What is the integral of x^2?")
print(result["answer"])
print(result["backend"])   # "stub" or "qwen2.5-3b_cuda"/"qwen2.5-3b_cpu"
```

---

## File listing

```
.
├── .github/
│   └── workflows/
│       └── aeon-ci.yml    ← syntax check + notebook sanity on every push
├── README.md             ← this file
├── aeon.py               ← the entire single-cell kernel
├── colab_runner.ipynb    ← Open-in-Colab launchpad (clone + pip + exec)
├── .gitignore            ← Python cache, virtualenv, aeon state, editor cruft
└── requirements.txt      ← pip install -r requirements.txt
```
