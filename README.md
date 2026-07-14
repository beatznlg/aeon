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
   table above, ticking **"Notebook access"** for every secret.
3. *(optional, only if you also pasted them as `os.environ[...]` setting in
   the cell)* — add a SETUP block.

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
> a local `/content/aeon_drive/`).

---

## GitHub → Colab workflow

This is the edit / push / run loop. It's **manual per push** (free Colab
doesn't expose a public "trigger a run" API; CI-style automation would
require Colab Enterprise / Vertex AI Workbench, which is paid). The mechanism
is just `git pull` inside a launcher cell you re-run yourself.

```text
                       GitHub: beatznlg/aeon  (this repo)
                              ▲
            ┌─────────────────┴────────────────┐
            │   git push  /  edits via Freebuff │
            └─────────────────┬────────────────┘
                              ▼
              colab_runner.ipynb (single cell)
              ┌──────────────────────────────────────┐
              │  1. !git clone or !git pull          │
              │  2. pip install -r requirements.txt  │
              │  3. exec(open("aeon.py").read())     │
              └────────────────┬─────────────────────┘
                               ▼
                Colab runtime → aeon.py runs forever
                (Telegram bot is live, replies to text/voice/photo/video)
```

### Re-deploy after a push

1. Go back to your open Colab tab.
2. **Stop** the running cell (■ button).
3. **Re-run** the same cell. The launcher will see the working dir already
   exists, do `git pull --rebase --autostash`, re-install deps (incrementally
   — `-q -r requirements.txt` only fetches what's missing), and re-exec
   `aeon.py` with the new commit.
4. The `[launcher] HEAD = …` print line right before `%run` confirms which
   commit you're on.

### What this workflow is and isn't

| ✅ Yes | ❌ No |
| --- | --- |
| Single badge click opens the latest launcher | No auto-redeploy when you push — you must hit Run again |
| Pulls the latest `main` commit on each cell run | No background daemon — runtime idles 12h then disconnects |
| Pip-deps are reproducible from `requirements.txt` | No paid Colab Enterprise / Workbench required |
| Secrets live in Colab's Secrets tab, not in this repo | No CI tests run on this repo |
| Same flow works for any future `.py` you add to the repo | Not a general "run any Python from GitHub" service — tuned to `aeon.py` |

If you ever want push-triggered CI runs (e.g. a smoke-import check that
`aeon.py` still parses), add a `.github/workflows/python-ci.yml` later —
that's doable on free GitHub Actions and orthogonal to the Colab side.

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
  clicking Start in Colab is a two-step loop.

If you want a *runnable* Freebuff web preview, the project needs to be wrapped
into something Freebuff can serve — e.g. a FastAPI control panel around the
bot — and that's a separate change from putting the bot in the repo.

---

## File listing

```
.
├── README.md             ← this file
├── aeon.py               ← the entire single-cell bot
├── colab_runner.ipynb    ← Open-in-Colab launchpad (clone + pip + exec)
└── requirements.txt      ← pip install -r requirements.txt
```
