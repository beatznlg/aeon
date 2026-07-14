# AEON α

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/beatznlg/aeon/blob/main/colab_runner.ipynb)

> **Source of truth = this GitHub repo.** A single launcher cell in
> `colab_runner.ipynb` pulls the latest commit, installs the deps, and executes
> [`aeon.py`](./aeon.py). Push to `main` → re-run the cell → bot is on the new
> code. See [GitHub → Colab workflow](#github-→-colab-workflow) below.

A single-cell, always-on Telegram bot backed by a **local Qwen2.5-7B** (via
`llama.cpp` on GPU) with **free-tier Groq** and **Gemini** as fallbacks, a
bge-small semantic embedder, a content-addressed Python **Skill DAG** that
stores learned "skill" callables on Google Drive, an `exec`-based subprocess
sandbox, vision + audio understanding through Gemini, edge-tts voice replies,
an on-chain **USDC wallet on Base L2**, and persistent interoception
(boot_count / skill_hit_rate / energy / error_rate / disk_pct).

The whole thing is one Python file: [`aeon.py`](./aeon.py). The script
downloads the model weights on first boot (~4.4 GB) and then long-polls a
Telegram bot indefinitely, replying to text, photos, voice notes, audio
files, and videos.

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
| Bot replies to Telegram messages | `aeon.py`'s `infinity_polling` | **automatic** while the cell runs |

> **Bottom line:** the entire chain is automatic **except** the three clicks —
> open the badge, choose T4 GPU, ▶︎ the cell. No GitHub Actions trick replaces
> those on the free tier without violating Google Cloud ToS (headless
> puppeteer/Chrome automation is detected and reCAPTCHA'd; the only legit
> paid alternative is Colab Enterprise / Vertex AI Workbench).

---

## Architecture (one file, but layered)

| Layer | What it does | Lives in |
| --- | --- | --- |
| **Secrets + Drive mount** | Pulls Colab secrets, mounts `MyDrive/aeon_alpha` | §3 |
| **Brain** | Qwen2.5-7B Q4_K_M GGUF → `llama_cpp.Llama`, n_ctx 8192, GPU offloaded | §4 |
| **Embedder** | bge-small-en-v1.5, packing into binary bits for cheap similarity | §5 |
| **Skill DAG** | Hot (`hot/*.py`) + cold (`skill_dag/objects/<hh>/<hash>.py.zst`) tiers; index is `skill_dag/index.jsonl` on Drive | §6 |
| **Sandbox** | `subprocess.run` + `RLIMIT_CPU`/`RLIMIT_AS`/`RLIMIT_NPROC`, refuse-lists dangerous symbols | §7 |
| **Intero** | Running vital signs for the `/status` heartbeat | §8 |
| **Wallet** | `web3` against `https://mainnet.base.org`, USDC contract `0x8335…2913` | §9 |
| **Multimodal** | Gemini 2.5 Flash for image description + audio transcription; edge-tts for voice replies; pollinations.ai for image gen | §10 |
| **Parasite** | Falls back to Groq `llama-3.1-8b-instant` when the local brain is offline | §11 |
| **`ask()`** | The single fused entry point: local → Groq → Gemini | §12 |
| **Telegram surface** | pyTelegramBotAPI handlers for text, voice, audio, photo, video, plus `/start /status /wallet /skills /gen /say` | §13 |
| **Boot** | Writes a dated diary markdown, starts the asyncio loop in a background thread, begins polling with exponential backoff | §14 |

---

## Environment variables / secrets

These are read via `google.colab.userdata` first, then `os.getenv` as a
fallback. Marked as **required** or **recommended/optional** below.

| Variable | Required? | What it unlocks |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | **Required** to actually chat | The whole Telegram bot surface. Without it, AEON runs headless and logs a message. |
| `GROQ_API_KEY` (alias `GROQ`) | Recommended | Free-tier Groq `llama-3.1-8b-instant` fallback when the local Qwen brain isn't loaded. |
| `GEMINI_API_KEY` (aliases `GOOGLE_API_KEY`, `GEMINI`) | Recommended | Gemini 2.5 Flash — needed for **image understanding**, **video frame summarization**, and **audio/voice-note transcription**. Without it, photo / video / voice replies degrade to text-only. |
| `HF_API_TOKEN` (alias `HF`) | Optional | Reserved for Hugging Face endpoints (script header mentions `musicgen`; not yet wired into `ask()`). |
| `WEB3_PRIVATE_KEY` (alias `WALLET_PK`) | Optional | Activates the Base L2 wallet, `/wallet` command, and `verify_payment()`. **Treat this like a password** — anyone with it can drain the account. |
| `BASE_RPC` | Optional | Override Base RPC URL (defaults to `https://mainnet.base.org`). |
| `AEON_LOG_LEVEL` | Optional | Standard logging level (defaults to `INFO`). |

> Note: `web3` is **only** imported if `WEB3_PRIVATE_KEY` is set (lazy import
> in §9). The other lazy import is `opencv-python` for video frame sampling.

`telebot.parse_mode` is set to `"Markdown"` and replies are clipped to **3500
chars** to stay under Telegram's per-message limit.

The launcher cell **also** reads `GITHUB_TOKEN` (an *optional* fine-grained
PAT with `Contents: Read`) — only needed if the repo is private. If the repo
is public, leave `GITHUB_TOKEN` blank.

---

## How to run

The canonical way to run AEON α is to **click the "Open in Colab" badge at
the top** — that opens [`colab_runner.ipynb`](./colab_runner.ipynb) which is a
single code cell that does:

1. **Clone or pull** `https://github.com/beatznlg/aeon.git` into `/content/aeon`
2. **Install** dependencies with `pip install -r requirements.txt`
3. **Run** `aeon.py` via `exec()` (the cell then blocks indefinitely —
   `bot.infinity_polling()` never returns)

### One-time pre-flight per notebook

Before you click ▶︎ on the launcher cell:

1. **Runtime ▸ Change runtime type** → **T4 GPU** (free tier is fine; the
   launcher enforces no specific GPU but the GGUF model expects CUDA).
2. Open the left sidebar **🔑 Secrets** panel and add each variable from the
   table above (including `GITHUB_TOKEN` only if the repo is private),
   ticking **"Notebook access"** for every secret.
3. *(alternative)* — set `TELEGRAM_BOT_TOKEN`, `GROQ_API_KEY`, etc. as
   `os.environ[...]` directly in the cell if you'd rather skip the Secrets
   tab.

### To run outside Colab (Linux + NVIDIA GPU)

You don't need the launcher notebook — just run the script directly:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
TELEGRAM_BOT_TOKEN=... GROQ_API_KEY=... GEMINI_API_KEY=... python aeon.py
```

> Caveats outside Colab: the script will try to `from google.colab import
> userdata` (fails gracefully and falls back to `os.getenv`), and it will try
> to `drive.mount("/content/drive")` (also fails gracefully and falls back to
> a local `/content/aeon_drive/` — already `.gitignore`d so it won't dirty
> the repo).

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
           aeon.py runs forever on the latest commit;
           bot replies on Telegram as long as the cell is alive
```

### Re-deploy after a push

1. Go back to your open Colab tab.
2. **Stop** the running cell (■ button).
3. **Re-run** the same cell. The launcher will see the working dir already
   exists, do `git pull --rebase --autostash`, re-install deps (incrementally
   — `-q -r requirements.txt` only fetches what's missing), and re-exec
   `aeon.py` with the new commit.
4. The `[launcher] HEAD = …` print line right before `%run` confirms which
   commit you're on. Match it against the short SHA in your last Actions run.

---

## ⚠️ Freebuff-preview note

The repo can absolutely host `aeon.py` — it's just Python source. **No code
was changed**, no install/dev/build scripts were wired up for the Freebuff
web preview:

- **No `package.json` was added.** AEON α is a Python process, not a web
  app, and Freebuff's preview tooling targets Node/Bun + Vite + browser
  WebContainer, which can't execute Python, can't mount a GPU, can't
  hold a long-polling Telegram connection.
- **`requirements.txt` is provided** so the *real* runtime (Colab, VPS,
  Hugging Face Space, etc.) can install with `pip install -r requirements.txt`.
- **`colab_runner.ipynb` is provided** so editing code in this repo and
  clicking the badge in Colab is a two-step loop.

If you want a *runnable* Freebuff web preview, the project needs to be wrapped
into something Freebuff can serve — e.g. a FastAPI control panel around the
bot — and that's a separate change from putting the bot in the repo.

---

## File listing

```
.
├── .github/
│   └── workflows/
│       └── aeon-ci.yml    ← syntax check + notebook sanity on every push
├── README.md             ← this file
├── aeon.py               ← the entire single-cell bot
├── colab_runner.ipynb    ← Open-in-Colab launchpad (clone + pip + exec)
├── .gitignore            ← Python cache, virtualenv, aeon_drive/, editor cruft
└── requirements.txt      ← pip install -r requirements.txt
```
