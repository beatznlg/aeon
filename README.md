# AEON α

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
| `HF_API_TOKEN` (alias `HF`) | Optional | Reserved for Hugging Face endpoints (script header mentions `musicgen`; not wired into `ask()` yet). |
| `WEB3_PRIVATE_KEY` (alias `WALLET_PK`) | Optional | Activates the Base L2 wallet, `/wallet` command, and `verify_payment()`. **Treat this like a password** — anyone with it can drain the account. |
| `BASE_RPC` | Optional | Override Base RPC URL (defaults to `https://mainnet.base.org`). |
| `AEON_LOG_LEVEL` | Optional | Standard logging level (defaults to `INFO`). |

> Note: `web3` is **only** imported if `WEB3_PRIVATE_KEY` is set (lazy import
> in §9). The other lazy import is `opencv-python` for video frame sampling.

`telebot.parse_mode` is set to `"Markdown"` and replies are clipped to **3500
chars** to stay under Telegram's per-message limit.

---

## How to run

This script is **designed to be pasted as one cell into a Google Colab
notebook** with the runtime set to **T4 GPU**:

1. Open Colab → `Runtime ▸ Change runtime type` → **T4 GPU**.
2. Open the left-tab **Secrets** panel and add the variables above.
3. Paste the entire contents of `aeon.py` as a single cell and run it.
4. On first boot it will download `Qwen2.5-7B-Instruct-Q4_K_M.gguf`
   (~4.4 GB) into `MyDrive/aeon_alpha/`, then start polling your bot.
5. Send any message to your bot. `/start`, `/status`, `/wallet`, `/skills`,
   `/gen <prompt>`, `/say <text>` are all available.

To run outside Colab (e.g. a Linux box with an NVIDIA card):

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

## ⚠️ Freebuff-preview note

The repo can absolutely host `aeon.py` — it's just Python source. **No code
was changed**, no install/dev/build scripts were wired up:

- **No `package.json` was added.** AEON α is a Python process, not a web
  app, and Freebuff's preview tooling targets Node/Bun + Vite + browser
  WebContainer, which can't execute Python, can't mount a GPU, can't
  hold a long-polling Telegram connection.
- **`requirements.txt` is provided** so the *real* runtime (Colab, VPS,
  Hugging Face Space, etc.) can install with `pip install -r requirements.txt`.

If you want a *runnable* Freebuff preview, this project needs to be wrapped
into something Freebuff can serve — e.g. a FastAPI control panel around the
bot — and that's a separate change from putting the script in the repo.

---

## File listing

```
.
├── README.md          ← this file
├── aeon.py            ← the entire single-cell bot
└── requirements.txt   ← pip install -r requirements.txt
```
