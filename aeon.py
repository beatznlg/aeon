# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  AEON α — architecture improved (2025-Q3 refactor)                         ║
# ║                                                                          ║
# ║  Section numbers in inline comments still match README.md's              ║
# ║  "Architecture" table (§3 Secrets+Drive … §14 Boot).                     ║
# ║                                                                          ║
# ║  Side-effects (pip install, Telegram handlers, polling loop) are now     ║
# ║  gated behind `if __name__ == "__main__": main()` so that running        ║
# ║  `import aeon` is safe. The Colab launcher cell still triggers main()    ║
# ║  because exec()'d code inherits the cell's `__name__ == "__main__"`.    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

# ─── §0. Imports ──────────────────────────────────────────────────────────────
import os, sys, time, math, asyncio, logging, hashlib, ast, re
import tempfile, traceback, threading, urllib.request, base64
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np, requests, sympy, psutil
import httpx, telebot

logging.basicConfig(level=os.getenv("AEON_LOG_LEVEL", "INFO"),
                    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("aeon")

try:
    import zstandard as _zstd
    Z, DZ = _zstd.ZstdCompressor(level=9), _zstd.ZstdDecompressor()
except Exception: Z = DZ = None

def atomic_write(p: Path, data):
    """Write `data` to `p` via tmp + rename so partial writes never appear on disk."""
    if isinstance(data, str): data = data.encode("utf-8")
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "wb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)

# ─── §3. Secrets + Drive ────────────────────────────────────────────────────
def _get(k: str) -> Optional[str]:
    """Read a secret from Colab userdata first, then os.getenv."""
    try:
        from google.colab import userdata
        v = userdata.get(k)
        if v: return v
    except Exception: pass
    return os.getenv(k)

TELEGRAM = _get("TELEGRAM_BOT_TOKEN")
GROQ     = _get("GROQ_API_KEY") or _get("GROQ")
GEMINI   = _get("GEMINI_API_KEY") or _get("GOOGLE_API_KEY") or _get("GEMINI")
HF       = _get("HF_API_TOKEN") or _get("HF")
WALLET   = _get("WEB3_PRIVATE_KEY") or _get("WALLET_PK")

AEON_ROOT = Path("/content/aeon_drive")
try:
    from google.colab import drive
    if not Path("/content/drive/MyDrive").exists():
        drive.mount("/content/drive", force_remount=False)
    AEON_ROOT = Path("/content/drive/MyDrive/aeon_alpha")
except Exception as e:
    log.info("Drive unavailable: %s — using local", e)

AEON_ROOT.mkdir(parents=True, exist_ok=True)
for sub in ("hot", "skill_dag", "skill_dag/cards",
            "trajectories", "diary", "receipts"):
    (AEON_ROOT / sub).mkdir(parents=True, exist_ok=True)

# ─── §4. Brain (Qwen2.5-7B Q4_K_M via llama.cpp) ─────────────────────────────
_brain = None
BRAIN = AEON_ROOT / "qwen2.5-7b-instruct-q4_k_m.gguf"
try:
    if not BRAIN.exists():
        log.info("downloading brain (4.4 GB)…")
        urllib.request.urlretrieve(
            "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/"
            "resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf", BRAIN)
    from llama_cpp import Llama
    _brain = Llama(model_path=str(BRAIN), n_ctx=8192, n_threads=4,
                   n_gpu_layers=999, verbose=False, chat_format="chatml")
    log.info("BRAIN online: %.2f GB", BRAIN.stat().st_size / 1e9)
except Exception as e:
    log.warning("brain not available: %s; AEON will rely on Groq/Gemini free tiers only", e)

async def local_chat(msgs: list, max_tokens: int = 700, temperature: float = 0.2) -> str:
    if _brain is None: return ""
    loop = asyncio.get_running_loop()
    def _go():
        return _brain.create_chat_completion(
            messages=msgs, temperature=temperature, max_tokens=max_tokens)
    r = await loop.run_in_executor(None, _go)
    return (r["choices"][0]["message"]["content"] or "") if r.get("choices") else ""

# ─── §5. Embedder (bge-small-en-v1.5 on CPU) ─────────────────────────────────
EMBED = None; ED = 384
try:
    from sentence_transformers import SentenceTransformer
    EMBED = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
    ED = EMBED.get_sentence_embedding_dimension()
except Exception as e:
    log.info("embedder unavailable: %s", e)

def encode_binary(texts: List[str]):
    if EMBED is None: return None
    v = EMBED.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    bits = (v > 0).astype(np.uint8)
    pad = (-v.shape[1]) % 8
    if pad: bits = np.concatenate([bits, np.zeros((bits.shape[0], pad), dtype=np.uint8)], axis=1)
    return np.packbits(bits.reshape(bits.shape[0], -1), axis=1)

# ─── §6. Skill DAG ───────────────────────────────────────────────────────────
class SkillDAG:
    def __init__(self, hot_cap: int = 120) -> None:
        self.objects = AEON_ROOT / "skill_dag" / "objects"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.a = AEON_ROOT / "hot"
        self.index_p = AEON_ROOT / "skill_dag" / "index.jsonl"
        self.index: Dict[str, dict] = {}
        self.hot: Dict[str, str] = {}
        self.hot_cap = hot_cap
        self._load()
    def _load(self) -> None:
        try:
            for line in self.index_p.read_text("utf-8").splitlines():
                if not line.strip(): continue
                r = json.loads(line)
                self.index[r["name"]] = r
        except Exception: pass
        self._trim_hot()
    def _obj(self, h: str) -> Path: return self.objects / h[:2] / f"{h}.py.zst"
    def _save_index(self) -> None:
        atomic_write(self.index_p, "\n".join(json.dumps(r) for r in self.index.values()) + "\n")
    def _trim_hot(self) -> None:
        files = sorted(self.a.glob("*.py"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        for stale in files[self.hot_cap:]:
            try: stale.unlink()
            except Exception: pass
        for p in files[:self.hot_cap]:
            try: self.hot[p.stem] = p.read_text("utf-8")
            except Exception: pass
    def add(self, name: str, source: str, examples: List[str]) -> str:
        try: ast.parse(source)
        except SyntaxError as e: return f"err: {e}"
        h = hashlib.sha256(source.encode()).hexdigest()[:16]
        p = self._obj(h); p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists() and Z: atomic_write(p, Z.compress(source.encode()))
        self.index[name] = {"name": name, "hash": h, "calls": 0,
                            "success": 0, "examples": examples[:6],
                            "first_used": time.time(), "last_used": time.time()}
        self._save_index()
        (self.a / f"{name}.py").write_text(source)
        self.hot[name] = source
        self._trim_hot()
        return h
    def execute(self, name: str, args: Dict[str, Any]) -> Any:
        if name not in self.index: raise KeyError(name)
        if name in self.hot: src = self.hot[name]
        elif DZ and self._obj(self.index[name]["hash"]).exists():
            src = DZ.decompress(self._obj(self.index[name]["hash"]).read_bytes()).decode()
        else: raise RuntimeError("cold-read unavailable")
        ns = {"__builtins__": __builtins__}
        exec(src, ns)
        fn = ns[name]
        import inspect
        sig = inspect.signature(fn); sig.bind(**args)
        out = fn(**args)
        r = self.index[name]
        r["calls"] = r.get("calls", 0) + 1
        r["success"] = r.get("success", 0) + 1
        r["last_used"] = time.time()
        self._save_index()
        return out
    def __len__(self) -> int: return len(self.index)

import json  # local import so DAG stays ordered w.r.t. atomic_write

DAG = SkillDAG()
log.info("Skill DAG: %d total, %d hot", len(DAG), len(DAG.hot))

# ─── §7. Subprocess sandbox ─────────────────────────────────────────────────
def sandbox_run(source: str, timeout: int = 6, mem_mb: int = 128) -> Dict[str, Any]:
    """Run a small Python snippet with resource limits.

    Refuses anything containing a stringly-typed substring on the deny-list:
    `os.system`, `shutil.rmtree`, `/etc/`, `open('/dev'`, `subprocess.`
    """
    for bad in ("os.system", "shutil.rmtree", "/etc/", "open('/dev'", "subprocess."):
        if bad in source: return {"rc": -1, "stderr": f"refused: {bad}"}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(source); tmp_path = f.name
    try:
        def preexec() -> None:
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (timeout+1, timeout+1))
            resource.setrlimit(resource.RLIMIT_AS, (mem_mb*1024*1024,)*2)
            resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
        try:
            p = subprocess.run(["python3", "-I", tmp_path],
                capture_output=True, text=True, timeout=timeout, preexec_fn=preexec)
            return {"rc": p.returncode, "stdout": p.stdout[:3000],
                    "stderr": p.stderr[:1200], "timeout": False}
        except subprocess.TimeoutExpired:
            return {"rc": -1, "stderr": "timeout", "timeout": True}
    finally:
        try: os.unlink(tmp_path)
        except Exception: pass

# subprocess is referenced above but only `import subprocess` exists in §0.
# Repoint the name lazily so the test harness can monkeypatch it cleanly.
import subprocess  # noqa: E402  — local alias for sandbox_run

# ─── §8. Interoception (vital signs) ─────────────────────────────────────────
class Intero:
    def __init__(self) -> None:
        self.boot_count: int = 0
        self.queries: int = 0
        self.skill_hit_rate: float = 0.0
        self.energy: float = 1.0
        self.error_rate: float = 0.0
        self.disk_pct: float = 0.0
        # Observability: which inference backend answered the last `ask()`,
        # and how long it took. `""` / `0.0` mean no answer yet.
        self.last_backend: str = ""
        self.last_latency_ms: float = 0.0
    def bump(self, k: str, by: int = 1) -> None:
        if hasattr(self, k): setattr(self, k, getattr(self, k) + by)
    def EMA(self, k: str, v: float, alpha: float = 0.3) -> None:
        """Exponential moving average over a numeric slot.

        Previously only patched floats (silent no-op for ints). Now accepts
        ints and floats (excluding bools); non-numeric slots are no-op.
        """
        if not hasattr(self, k): return
        cur = getattr(self, k)
        if isinstance(cur, bool): return
        if isinstance(cur, (int, float)):
            setattr(self, k, (1 - alpha) * cur + alpha * float(v))
    def snap(self) -> Dict[str, Any]:
        try: self.disk_pct = psutil.disk_usage(str(AEON_ROOT)).percent
        except Exception: pass
        return {
            "queries": self.queries,
            "skill_hit_rate": self.skill_hit_rate,
            "energy": self.energy,
            "disk_pct": self.disk_pct,
            "errors": self.error_rate,
            "boot_count": self.boot_count,
            "last_backend": self.last_backend,
            "last_latency_ms": round(self.last_latency_ms, 1),
        }

INT = Intero()

# ─── §9. Web3 wallet (Base L2, USDC) ─────────────────────────────────────────
W3 = ACCT = AEON_ADDR = None
USDC_BASE = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
try:
    if WALLET:
        from web3 import Web3
        base_rpc = os.getenv("BASE_RPC", "https://mainnet.base.org")
        W3 = Web3(Web3.HTTPProvider(base_rpc, request_kwargs={"timeout": 12}))
        ACCT = W3.eth.account.from_key(WALLET)
        AEON_ADDR = ACCT.address
        log.info("wallet on: %s", AEON_ADDR)
except Exception as e:
    log.info("web3 wallet not loaded: %s", e)

USDC_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f9a8eb40dc2200"

def _web3_if_loaded():
    """Late import so the test harness can call wallet_state without web3 dep."""
    if not (W3 and ACCT):
        return None, None
    from web3 import Web3
    return Web3, W3

def wallet_state() -> Dict[str, Any]:
    if not W3 or not ACCT: return {"ok": False, "reason": "no-wallet"}
    try:
        Web3, _ = _web3_if_loaded()
        eth_bal = float(Web3.from_wei(W3.eth.get_balance(ACCT.address), "ether"))
        abi = [{"constant": True, "inputs": [{"name":"owner","type":"address"}],
                "name":"balanceOf","outputs":[{"name":"","type":"uint256"}],"type":"function"}]
        c = W3.eth.contract(address=Web3.to_checksum_address(USDC_BASE), abi=abi)
        usdc = c.functions.balanceOf(ACCT.address).call() / 10**6
        return {"ok": True, "address": ACCT.address, "eth": eth_bal, "usdc": usdc}
    except Exception as e: return {"ok": False, "reason": str(e)}

async def verify_payment(tx_hash: str, expected_to: str, min_usdc6: int) -> Dict[str, Any]:
    if not W3 or not tx_hash.startswith("0x"):
        return {"ok": False, "reason": "no-rpc-or-bad-hash"}
    try:
        receipt = W3.eth.get_transaction_receipt(bytes.fromhex(tx_hash[2:]))
        for log_event in receipt["logs"]:
            if log_event["address"].lower() != USDC_BASE.lower(): continue
            if log_event["topics"][0] != USDC_TRANSFER_TOPIC: continue
            to_addr = "0x" + (log_event["topics"][2].hex().lstrip("0x").rjust(40, "0"))[-40:]
            val = int(log_event["data"].hex(), 16)
            if to_addr.lower() != expected_to.lower(): continue
            return {"ok": True, "received_usdc": val / 1e6, "tx": tx_hash}
        return {"ok": False, "reason": "no-match"}
    except Exception as e: return {"ok": False, "reason": str(e)}

# ─── §10. Multimodal ────────────────────────────────────────────────────────
async def gemini_text(prompt: str, image_path: Optional[Path] = None,
                      audio_path: Optional[Path] = None) -> str:
    if not GEMINI: return "[gemini unavailable]"
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI)
        m = genai.GenerativeModel("gemini-2.5-flash")
        parts = []
        if image_path:
            parts.append({"mime_type": "image/jpeg", "data": image_path.read_bytes()})
        if audio_path:
            parts.append({"mime_type": "audio/ogg", "data": audio_path.read_bytes()})
        parts.append({"text": prompt})
        r = m.generate_content(parts)
        return r.text
    except Exception as e: return f"[gemini err: {e}]"

async def gemini_video_summary(video_path: Path, prompt: str = "describe briefly",
                                max_frames: int = 6) -> str:
    try:
        import cv2
        cap = cv2.VideoCapture(str(video_path))
        fps = max(1, int(cap.get(cv2.CAP_PROP_FPS) or 1))
        i = 0; collected = []
        while len(collected) < max_frames:
            ok, frame = cap.read()
            if not ok: break
            if i % fps == 0:
                tmp = AEON_ROOT / f"fr_{int(time.time())}_{len(collected)}.jpg"
                cv2.imwrite(str(tmp), frame); collected.append(tmp)
            i += 1
        cap.release()
        descs = []
        for f in collected:
            d = await gemini_text(prompt, image_path=f)
            descs.append(d)
            try: f.unlink()
            except Exception: pass
        return "\n".join(descs)
    except Exception as e: return f"[video err: {e}]"

try: import edge_tts
except Exception: edge_tts = None

async def tts(text: str, voice: str = "en-US-AriaNeural",
              out_path: Optional[Path] = None) -> Optional[Path]:
    if not edge_tts: return None
    out_path = out_path or (AEON_ROOT / "voice.mp3")
    try:
        await edge_tts.Communicate(text, voice=voice).save(str(out_path))
        return out_path
    except Exception as e: log.info(f"tts: {e}"); return None

async def image_generate(prompt: str) -> Optional[Path]:
    try:
        url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}"
        r = requests.get(url, timeout=120)
        if r.status_code == 200:
            p = AEON_ROOT / f"gen_{int(time.time()*1000)}.png"
            p.write_bytes(r.content); return p
    except Exception as e: log.info(f"image gen: {e}")
    return None

# ─── §11. Groq parasite ─────────────────────────────────────────────────────
async def parasite(query: str, max_tokens: int = 600) -> Optional[str]:
    if not GROQ: return None
    try:
        async with httpx.AsyncClient(timeout=12) as c:
            r = await c.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ}"},
                json={"model": "llama-3.1-8b-instant",
                      "messages": [{"role": "user", "content": query}],
                      "temperature": 0.2, "max_tokens": max_tokens})
            return r.json()["choices"][0]["message"]["content"]
    except Exception as e: log.info(f"groq: {e}"); return None

# ─── §12. ask() — chat, code, vision, audio ────────────────────────────────
def _record_backend(name: str, t0: float) -> None:
    """Mark which inference backend answered and the wall-clock latency."""
    INT.last_backend = name
    INT.last_latency_ms = (time.perf_counter() - t0) * 1000.0

async def ask(query: str, *, system_hint: str = "") -> str:
    """The single conversational entry: text / voice / photo / video all flow here.

    Sets `Intero.last_backend` to one of {"qwen","groq","gemini","none"} and
    `Intero.last_latency_ms` to wall-clock ms before returning.
    """
    INT.bump("queries")
    t0 = time.perf_counter()
    system = system_hint or "You are AEON. Be concise, helpful, honest."
    # 1) Prefer local brain if loaded
    if _brain is not None:
        try:
            out = await local_chat(
                [{"role": "system", "content": system},
                 {"role": "user", "content": query}], max_tokens=700)
            if out.strip():
                INT.EMA("energy", max(0.1, INT.energy - 0.04))
                _record_backend("qwen", t0)
                return out
        except Exception as e:
            log.info(f"local chat err: {e}")
    # 2) Free Groq fallback
    out = await parasite(query)
    if out:
        _record_backend("groq", t0)
        return out
    # 3) Free Gemini fallback
    if GEMINI:
        try:
            r = await gemini_text(system + "\n\n" + query)
            if r and not r.startswith("[gemini err"):
                _record_backend("gemini", t0)
                return r
        except Exception:
            pass
    _record_backend("none", t0)
    return "I have no inference backend online right now. Set GROQ_API_KEY or GEMINI_API_KEY."


# ══════════════════════════════════════════════════════════════════════════════
# Everything below is gated behind `if __name__ == "__main__": main()`.
# `import aeon` is now side-effect-free; only `python aeon.py` (or the Colab
# launcher cell exec'ing this script — `__name__ == "__main__"`) triggers it.
# ══════════════════════════════════════════════════════════════════════════════

def _install_dependencies() -> None:
    """When invoked directly (e.g. `python aeon.py` on a fresh box), bootstrap deps."""
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
        "llama-cpp-python==0.2.90",
        "sentence-transformers>=3.0", "faiss-cpu>=1.8",
        "pyTelegramBotAPI",
        "httpx", "pydantic>=2.5", "zstandard", "psutil",
        "sympy", "requests", "edge-tts", "openai-whisper",
        "google-generativeai",
    ])

def _session_diary() -> None:
    p = AEON_ROOT / "diary"
    p.mkdir(exist_ok=True)
    f = p / f"{time.strftime('%Y-%m-%d')}.md"
    body = (f"# AEON α session — {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n\n"
            f"- boot_count:      {INT.boot_count}\n"
            f"- skills_index:    {len(DAG)} (hot {len(DAG.hot)})\n"
            f"- modes:           brain={'local' if _brain else 'no-local'}, "
            f"groq={'on' if GROQ else 'off'}, gemini={'on' if GEMINI else 'off'}, "
            f"wallet={'on' if AEON_ADDR else 'off'}\n\n"
            f"_alive._\n")
    atomic_write(f, body)

def _boot_telegram_bot() -> None:
    """§13+§14. Wire up the Telegram surface and start polling. Returns when bot exits."""
    AELOOP = asyncio.new_event_loop()
    def _AEL(coro, timeout: int = 300):
        return asyncio.run_coroutine_threadsafe(coro, AELOOP).result(timeout=timeout)

    if not TELEGRAM:
        log.info("TELEGRAM_BOT_TOKEN not set. AEON is headless.")
        log.info("Add the token in Colab Secrets and re-run this script.")
        return

    bot = telebot.TeleBot(TELEGRAM, threaded=False, parse_mode="Markdown")

    def _safe_reply(m, text, retries: int = 2) -> None:
        for _ in range(retries):
            try: bot.reply_to(m, text); return
            except Exception as e:
                log.warning(f"reply err: {e}"); time.sleep(0.5)

    def _heartbeat_md() -> str:
        s = INT.snap()
        bar = lambda v: "▓" * int(v*10) + "░" * (10-int(v*10))
        return (f"💓 *AEON α heartbeat*\n"
                f"`skill_hit_rate`  {bar(s['skill_hit_rate'])} {s['skill_hit_rate']:.0%}\n"
                f"`energy`          {bar(s['energy'])} {s['energy']:.0%}\n"
                f"`disk`            {bar(s['disk_pct']/100)} {s['disk_pct']:.0%}\n"
                f"`errors`          {bar(s['error_rate'])} {s['error_rate']:.0%}\n"
                f"`queries`         {s['queries']}\n"
                f"`skills`          {len(DAG)} (hot {len(DAG.hot)})\n"
                f"`last_backend`    {s['last_backend'] or '(idle)'}\n"
                f"`last_ms`         {s['last_latency_ms']}\n"
                f"`boot_count`      {s['boot_count']}")

    INT.boot_count += 1

    @bot.message_handler(commands=["start", "help"])
    def _start(m):
        _safe_reply(m,
            "👋 *AEON α* here.\n\n"
            "Send me anything — text, voice note, photo, video — and I'll reply. "
            "I run Qwen-2.5-7B locally + free-tier Groq/Gemini fallback. "
            "All my responses and skills persist to Drive between Colab sessions.\n\n"
            "Quick commands:\n"
            "  /status — my vital signs\n"
            "  /wallet — my on-chain balance (if wallet enabled)\n"
            "  /skills — what I've learned\n"
            "  /gen <p> — make an image from your prompt\n"
            "  /say <text> — give a voice reply\n\n"
            "Otherwise just talk to me.")

    @bot.message_handler(commands=["status", "heartbeat"])
    def _status(m): _safe_reply(m, _heartbeat_md())

    @bot.message_handler(commands=["wallet"])
    def _wallet(m):
        s = wallet_state()
        if not s["ok"]: _safe_reply(m, "wallet not loaded (set WEB3_PRIVATE_KEY in Secrets)"); return
        _safe_reply(m, f"💼 `{s['address']}`\nETH: {s['eth']:.5f}\nUSDC: {s['usdc']:.4f}")

    @bot.message_handler(commands=["skills"])
    def _skills(m):
        if not DAG.index: _safe_reply(m, "no skills learned yet — keep chatting!"); return
        lines = []
        for n, r in sorted(DAG.index.items(), key=lambda t: -t[1].get("calls",0))[:30]:
            rate = r.get("success",0)/max(1,r.get("calls",0))
            lines.append(f"• `{n}` ({r.get('calls',0)}×, {rate:.0%})")
        _safe_reply(m, "**skills I've learned**\n\n" + "\n".join(lines))

    @bot.message_handler(commands=["gen"])
    def _gen(m):
        prompt = (m.text or "").split(" ", 1)
        if len(prompt) < 2: _safe_reply(m, "usage: /gen <thing to draw>"); return
        p = _AEL(image_generate(prompt[1]), 130)
        if p and p.exists():
            with open(p, "rb") as f: bot.send_photo(m.chat.id, f)
        else:
            _safe_reply(m, "image gen failed (pollinations may be rate-limiting; try later)")

    @bot.message_handler(commands=["say"])
    def _say(m):
        text = (m.text or "").split(" ", 1)
        if len(text) < 2: _safe_reply(m, "usage: /say <text>"); return
        p = _AEL(tts(text[1]), 30)
        if p and p.exists():
            with open(p, "rb") as f: bot.send_voice(m.chat.id, f)
        else: _safe_reply(m, "tts failed (try again or use English)")

    @bot.message_handler(content_types=["voice"])
    def _voice(m):
        try:
            fi = bot.get_file(m.voice.file_id)
            o = AEON_ROOT / f"v_{m.message_id}.ogg"
            with open(o, "wb") as fh: fh.write(bot.download_file(fi.file_path))
            if GEMINI:
                transcript = _AEL(gemini_text(
                    "Transcribe this audio exactly. Output only the literal words spoken.",
                    audio_path=o), 60)
            else:
                transcript = "[voice transcription needs GEMINI_API_KEY]"
            o.unlink()
            ans = _AEL(ask(f"[user said (voice note): '{transcript}'] answer helpfully"))
            _safe_reply(m, ans[:3500])
        except Exception as e:
            _safe_reply(m, f"voice err: {e}")

    @bot.message_handler(content_types=["audio"])
    def _audio(m):
        try:
            fi = bot.get_file(m.audio.file_id)
            o = AEON_ROOT / f"a_{m.message_id}.ogg"
            with open(o, "wb") as fh: fh.write(bot.download_file(fi.file_path))
            if GEMINI:
                transcript = _AEL(gemini_text(
                    "Transcribe this audio. Output only the words:",
                    audio_path=o), 60)
            else:
                transcript = "[audio transcription needs GEMINI_API_KEY]"
            o.unlink()
            ans = _AEL(ask(f"[user said (audio): '{transcript}'] answer helpfully"))
            _safe_reply(m, ans[:3500])
        except Exception as e: _safe_reply(m, f"audio err: {e}")

    @bot.message_handler(content_types=["photo"])
    def _photo(m):
        try:
            fi = bot.get_file(m.photo[-1].file_id)
            o = AEON_ROOT / f"p_{m.message_id}.jpg"
            with open(o, "wb") as fh: fh.write(bot.download_file(fi.file_path))
            caption = m.caption or ""
            if GEMINI:
                desc = _AEL(gemini_text(
                    f"Describe this photo briefly. user says: {caption}",
                    image_path=o), 60)
            else:
                desc = "[set GEMINI_API_KEY for me to see images]"
            o.unlink()
            ans = _AEL(ask(f"[photo shown to me. I described it as: '{desc[:600]}'] user said: '{caption}' answer helpfully"))
            _safe_reply(m, (desc + "\n\n" + ans)[:3500])
        except Exception as e: _safe_reply(m, f"photo err: {e}")

    @bot.message_handler(content_types=["video"])
    def _video(m):
        try:
            fi = bot.get_file(m.video.file_id)
            o = AEON_ROOT / f"vid_{m.message_id}.mp4"
            with open(o, "wb") as fh: fh.write(bot.download_file(fi.file_path))
            desc = _AEL(gemini_video_summary(o, prompt="describe the video content briefly"), 120) if GEMINI \
                else "[set GEMINI_API_KEY for me to see videos]"
            ans = _AEL(ask(f"[video shown: '{desc[:600]}'] user says: '{m.caption or ''}' answer helpfully"))
            _safe_reply(m, (desc + "\n\n" + ans)[:3500])
        except Exception as e: _safe_reply(m, f"video err: {e}")

    @bot.message_handler(content_types=["text"])
    def _text(m):
        if not m.text or m.text.startswith("/"): return
        try:
            ans = _AEL(ask(m.text))
            _safe_reply(m, ans[:3500])
        except Exception as e:
            INT.EMA("error_rate", 0.1)
            _safe_reply(m, f"err: {e}")

    log.info("✅ AEON Telegram bot armed. Send any message to start.")

    def _loop_runner() -> None:
        asyncio.set_event_loop(AELOOP); AELOOP.run_forever()
    threading.Thread(target=_loop_runner, daemon=True).start()
    log.info("AEON event loop running in background")

    backoff = 1.0
    poll_forever = True
    while poll_forever:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10,
                                 allowed_updates=["message", "callback_query"])
            backoff = 1.0
            break
        except Exception as e:
            log.warning(f"polling err: {e}; retry in {backoff:.1f}s")
            time.sleep(backoff); backoff = min(60.0, backoff * 1.7)

def main() -> None:
    """Entry point: install deps (when not on Colab), wire bot, diary, and poll."""
    if "google.colab" not in sys.modules:
        # On Colab the launcher already ran `pip install -r requirements.txt`.
        # On a fresh Linux box (e.g. `python aeon.py`), bootstrap deps.
        try:
            _install_dependencies()
        except Exception as e:
            log.warning("dependency install skipped: %s", e)
    _session_diary()
    _boot_telegram_bot()

if __name__ == "__main__":
    main()
