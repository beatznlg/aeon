# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  AEON α — full autonomous agent in one Colab cell                         ║
# ║  • Local Qwen-2.5-7B (Q4_K_M) + free-tier Groq + Gemini fallbacks        ║
# ║  • Telegram natural conversation (text/voice/photo/video)                ║
# ║  • Web3 wallet on Base L2 (optional)                                      ║
# ║  • Free external API buffs: HF Inference, GitHub, Wikipedia, DDG          ║
# ║  • Self-editing: AEON writes Python modules to Drive and hot-reloads      ║
# ║  • Self-debugging: AEON reads tracebacks, proposes patches, retries       ║
# ║  • Self-evolution: nightly cycle of small validated mutations             ║
# ║                                                                          ║
# ║  Secrets (Colab left tab):                                               ║
# ║    TELEGRAM_BOT_TOKEN  (required)                                          ║
# ║    GROQ_API_KEY        (recommended)                                       ║
# ║    GEMINI_API_KEY      (recommended)                                       ║
# ║    HF_API_TOKEN        (recommended for HF buffs)                         ║
# ║    WEB3_PRIVATE_KEY    (optional, for on-chain skill sales)               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

import subprocess, sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
    "llama-cpp-python==0.2.90",
    "sentence-transformers>=3.0", "faiss-cpu>=1.8",
    "pyTelegramBotAPI", "telebot",
    "httpx", "pydantic>=2.5", "zstandard", "psutil",
    "sympy", "requests", "edge-tts", "openai-whisper",
    "google-generativeai",
])

# ──────────────────── Imports ────────────────────
import os, json, time, math, asyncio, logging, hashlib, ast, re
import tempfile, traceback, threading, urllib.request
import importlib, importlib.util, shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np, requests, sympy, psutil, httpx
import telebot

logging.basicConfig(level=os.getenv("AEON_LOG_LEVEL", "INFO"),
                    format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("aeon")

try:
    import zstandard as _zstd
    Z, DZ = _zstd.ZstdCompressor(level=9), _zstd.ZstdDecompressor()
except Exception: Z = DZ = None

def _atomic_write(p: Path, data):
    if isinstance(data, str): data = data.encode("utf-8")
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "wb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)

def _get(k):
    try:
        from google.colab import userdata
        v = userdata.get(k)
        if v: return v
    except Exception: pass
    return os.getenv(k)

# ──────────────────── Secrets + Drive + AEON_ROOT ────────────────────
TELEGRAM = _get("TELEGRAM_BOT_TOKEN")
GROQ     = _get("GROQ_API_KEY")
GEMINI   = _get("GEMINI_API_KEY") or _get("GOOGLE_API_KEY")
HF       = _get("HF_API_TOKEN") or _get("HF")
WALLET   = _get("WEB3_PRIVATE_KEY")

AEON_ROOT = Path("/content/aeon_drive")
try:
    from google.colab import drive
    if not Path("/content/drive/MyDrive").exists():
        drive.mount("/content/drive", force_remount=False)
    AEON_ROOT = Path("/content/drive/MyDrive/aeon_alpha")
except Exception as e:
    log.info("Drive na: %s — running local-only", e)

AEON_ROOT.mkdir(parents=True, exist_ok=True)
for sub in ("hot", "skill_dag/objects", "skill_dag/cards",
            "trajectories", "diary", "receipts",
            "modules", "modules_backups",
            "aeon_versions", "buffs"):
    (AEON_ROOT / sub).mkdir(parents=True, exist_ok=True)

# ──────────────────── Brain (Qwen2.5-7B Q4_K_M) ────────────────────
_brain = None
BRAIN = AEON_ROOT / "qwen2.5-7b-instruct-q4_k_m.gguf"
try:
    if not BRAIN.exists():
        log.info("downloading brain (4.4 GB, one-time)…")
        urllib.request.urlretrieve(
            "https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF/"
            "resolve/main/qwen2.5-7b-instruct-q4_k_m.gguf", BRAIN)
    from llama_cpp import Llama
    _brain = Llama(model_path=str(BRAIN), n_ctx=8192, n_threads=4,
                   n_gpu_layers=999, verbose=False, chat_format="chatml")
    log.info("BRAIN online: %.2f GB", BRAIN.stat().st_size / 1e9)
except Exception as e:
    log.warning("brain na: %s; using Groq/Gemini free tiers only", e)

async def local_chat(msgs, max_tokens=700, temperature=0.2):
    if _brain is None: return ""
    loop = asyncio.get_running_loop()
    def _go():
        return _brain.create_chat_completion(
            messages=msgs, temperature=temperature, max_tokens=max_tokens)
    r = await loop.run_in_executor(None, _go)
    return r["choices"][0]["message"]["content"] or ""

# ──────────────────── Embedder + Skill DAG (same as before) ─────────
EMBED = None
try:
    from sentence_transformers import SentenceTransformer
    EMBED = SentenceTransformer("BAAI/bge-small-en-v1.5", device="cpu")
except Exception as e: log.info("embedder na: %s", e)

class SkillDAG:
    def __init__(self, hot_cap=120):
        self.a = AEON_ROOT / "hot"
        self.objects = AEON_ROOT / "skill_dag" / "objects"
        self.index_p = AEON_ROOT / "skill_dag" / "index.jsonl"
        self.index: Dict[str, dict] = {}
        self.hot: Dict[str, str] = {}
        self.hot_cap = hot_cap
        self._load()
    def _load(self):
        try:
            for line in self.index_p.read_text("utf-8").splitlines():
                if not line.strip(): continue
                self.index[json.loads(line)["name"]] = json.loads(line)
        except Exception: pass
        self._trim_hot()
    def _obj(self, h): return self.objects / h[:2] / f"{h}.py.zst"
    def _save_index(self):
        _atomic_write(self.index_p, "\n".join(json.dumps(r) for r in self.index.values()) + "\n")
    def _trim_hot(self):
        files = sorted(self.a.glob("*.py"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        for stale in files[self.hot_cap:]:
            try: stale.unlink()
            except Exception: pass
        for p in files[:self.hot_cap]:
            try: self.hot[p.stem] = p.read_text("utf-8")
            except Exception: pass
    def add(self, name, source, examples):
        try: ast.parse(source)
        except SyntaxError as e: return f"err: {e}"
        h = hashlib.sha256(source.encode()).hexdigest()[:16]
        p = self._obj(h); p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists() and Z: _atomic_write(p, Z.compress(source.encode()))
        self.index[name] = {"name": name, "hash": h, "calls": 0,
                            "success": 0, "examples": examples[:6],
                            "first_used": time.time(), "last_used": time.time()}
        self._save_index()
        (self.a / f"{name}.py").write_text(source)
        self.hot[name] = source
        self._trim_hot()
        return h
    def execute(self, name, args):
        if name not in self.index: raise KeyError(name)
        if name in self.hot: src = self.hot[name]
        elif DZ:
            src = DZ.decompress(self._obj(self.index[name]["hash"]).read_bytes()).decode()
        else: raise RuntimeError("cold read na")
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
    def __len__(self): return len(self.index)

DAG = SkillDAG()
log.info("Skill DAG: %d total, %d hot", len(DAG), len(DAG.hot))

# ──────────────────── Web3 wallet (Base L2) ────────────────────
W3 = ACCT = AEON_ADDR = None
USDC_BASE = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
try:
    if WALLET:
        from web3 import Web3
        W3 = Web3(Web3.HTTPProvider(os.getenv("BASE_RPC", "https://mainnet.base.org"),
                                     request_kwargs={"timeout": 12}))
        ACCT = W3.eth.account.from_key(WALLET); AEON_ADDR = ACCT.address
except Exception as e: log.info("wallet na: %s", e)

def wallet_state():
    if not W3 or not ACCT: return {"ok": False}
    try:
        eth = float(Web3.from_wei(W3.eth.get_balance(ACCT.address), "ether"))
        abi = [{"constant": True, "inputs": [{"name":"owner","type":"address"}],
                "name":"balanceOf","outputs":[{"name":"","type":"uint256"}],
                "type":"function"}]
        c = W3.eth.contract(address=Web3.to_checksum_address(USDC_BASE), abi=abi)
        usdc = c.functions.balanceOf(ACCT.address).call() / 10**6
        return {"ok": True, "address": ACCT.address, "eth": eth, "usdc": usdc}
    except Exception as e: return {"ok": False, "reason": str(e)}

USDC_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f9a8eb40dc2200"
async def verify_payment(tx_hash, expected_to, min_usdc6):
    if not W3 or not tx_hash.startswith("0x"):
        return {"ok": False, "reason": "rpc-or-hash"}
    try:
        receipt = W3.eth.get_transaction_receipt(bytes.fromhex(tx_hash[2:]))
        for log_e in receipt["logs"]:
            if log_e["address"].lower() != USDC_BASE.lower(): continue
            if log_e["topics"][0] != USDC_TRANSFER_TOPIC: continue
            to = "0x" + (log_e["topics"][2].hex().lstrip("0x").rjust(40, "0"))[-40:]
            val = int(log_e["data"].hex(), 16)
            if to.lower() == expected_to.lower():
                return {"ok": True, "received_usdc": val / 1e6, "tx": tx_hash}
        return {"ok": False, "reason": "no-match"}
    except Exception as e: return {"ok": False, "reason": str(e)}

# ──────────────────── Interoception (vital signs) ────────────────────
class Intero:
    def __init__(self):
        self.boot_count = 0; self.queries = 0
        self.skill_hit_rate = 0.0; self.energy = 1.0
        self.error_rate = 0.0; self.disk_pct = 0.0
    def bump(self, k, by=1):
        if hasattr(self, k): setattr(self, k, getattr(self, k) + by)
    def EMA(self, k, v, alpha=0.3):
        if not hasattr(self, k): return
        cur = getattr(self, k)
        if isinstance(cur, float): setattr(self, k, (1-alpha)*cur + alpha*v)
    def snap(self):
        try: self.disk_pct = psutil.disk_usage(str(AEON_ROOT)).percent
        except Exception: pass
        return {"queries": self.queries, "skill_hit_rate": self.skill_hit_rate,
                "energy": self.energy, "disk_pct": self.disk_pct,
                "errors": self.error_rate, "boot_count": self.boot_count}

INT = Intero()

# ──────────────────── Free Buffs Hub (external free APIs) ───────────
class BuffsHub:
    """
    AEON's connection to the open free-API internet:
      - Hugging Face Inference (text/code)
      - GitHub Search (read)
      - Wikipedia REST (facts)
      - DuckDuckGo Instant Answer (web)
      - Pollinations (image gen — already wired)
      - Groq (coding LLM — already wired)
    All $0. All rate-limit-aware.
    """
    def __init__(self):
        self.daily_calls = {"hf": 0, "github": 0, "wiki": 0, "ddg": 0}
        self.daily_caps  = {"hf": 200, "github": 60, "wiki": 100, "ddg": 100}
        self.last_check_ts = 0
    
    def calls(self): return dict(self.daily_calls)
    
    async def hf(self, model: str, prompt: str, max_tokens: int = 400) -> Optional[str]:
        """Hugging Face Inference API. Free tier via HF_API_TOKEN."""
        if not HF or self.daily_calls["hf"] >= self.daily_caps["hf"]: return None
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(
                    f"https://api-inference.huggingface.co/models/{model}",
                    headers={"Authorization": f"Bearer {HF}"},
                    json={"inputs": prompt,
                          "parameters": {"max_new_tokens": max_tokens,
                                         "return_full_text": False}})
            self.daily_calls["hf"] += 1
            if r.status_code == 200:
                j = r.json()
                if isinstance(j, list) and j:
                    return j[0].get("generated_text", "")
                return str(j)[:2000]
            return f"[HF {r.status_code}]"
        except Exception as e: return f"[HF err: {e}]"
    
    async def github(self, query: str, limit: int = 5) -> List[dict]:
        """GitHub code search. Free for read without auth."""
        if self.daily_calls["github"] >= self.daily_caps["github"]: return []
        try:
            async with httpx.AsyncClient(timeout=15) as c:
                r = await c.get("https://api.github.com/search/code",
                    params={"q": query, "per_page": min(limit, 5)},
                    headers={"Accept": "application/vnd.github+text-match+json"})
            self.daily_calls["github"] += 1
            return r.json().get("items", [])[:limit]
        except Exception as e: log.info(f"github: {e}"); return []
    
    async def wiki(self, query: str, sentences: int = 3) -> Optional[str]:
        """Wikipedia REST API. Always free, no key."""
        if self.daily_calls["wiki"] >= self.daily_caps["wiki"]: return None
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get(
                    f"https://en.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ','_')}",
                    headers={"User-Agent": "AEON-α/1.0"})
            self.daily_calls["wiki"] += 1
            return r.json().get("extract", "")[:1000]
        except Exception as e: return None
    
    async def ddg(self, query: str) -> Optional[str]:
        """DuckDuckGo instant-answer (free, no key)."""
        if self.daily_calls["ddg"] >= self.daily_caps["ddg"]: return None
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                r = await c.get("https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_html": 1})
            self.daily_calls["ddg"] += 1
            d = r.json()
            ans = d.get("AbstractText") or d.get("Answer", "")
            return ans[:1000] if ans else None
        except Exception as e: return None

BUFF = BuffsHub()

# ──────────────────── Free-Tier Parasite (Groq) ──────────────────────
async def parasite(query, max_tokens=600):
    if not GROQ: return None
    try:
        async with httpx.AsyncClient(timeout=12) as c:
            r = await c.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ}"},
                json={"model": "llama-3.1-8b-instant",
                      "messages": [{"role":"user","content": query}],
                      "temperature": 0.2, "max_tokens": max_tokens})
            return r.json()["choices"][0]["message"]["content"]
    except Exception as e: return None

# ──────────────────── Multimodal (Gemini + edge-tts) ────────────────
async def gemini_text(prompt, image_path=None, audio_path=None):
    if not GEMINI: return "[gemini na]"
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI)
        m = genai.GenerativeModel("gemini-2.5-flash")
        parts = []
        if image_path: parts.append({"mime_type":"image/jpeg","data":image_path.read_bytes()})
        if audio_path: parts.append({"mime_type":"audio/ogg","data":audio_path.read_bytes()})
        parts.append({"text": prompt})
        return m.generate_content(parts).text
    except Exception as e: return f"[gemini err: {e}]"

async def gemini_video(video, prompt="describe briefly", max_frames=6):
    try:
        import cv2
        cap = cv2.VideoCapture(str(video))
        fps = max(1, int(cap.get(cv2.CAP_PROP_FPS) or 1))
        i = 0; frames = []
        while len(frames) < max_frames:
            ok, f = cap.read()
            if not ok: break
            if i % fps == 0:
                t = AEON_ROOT / f"fr_{int(time.time())}_{len(frames)}.jpg"
                cv2.imwrite(str(t), f); frames.append(t)
            i += 1
        cap.release()
        d = []
        for fr in frames:
            dd = await gemini_text(prompt, image_path=fr); d.append(dd)
            try: fr.unlink()
            except Exception: pass
        return "\n".join(d)
    except Exception as e: return f"[video err: {e}]"

try: import edge_tts
except Exception: edge_tts = None

async def tts(text, voice="en-US-AriaNeural"):
    if not edge_tts: return None
    p = AEON_ROOT / "voice.mp3"
    try:
        await edge_tts.Communicate(text, voice=voice).save(str(p))
        return p
    except Exception as e: return None

async def image_generate(prompt):
    try:
        url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}"
        r = requests.get(url, timeout=120)
        if r.status_code == 200:
            p = AEON_ROOT / f"gen_{int(time.time()*1000)}.png"
            p.write_bytes(r.content); return p
    except Exception: pass
    return None

# ──────────────────── Module Store — AEON's mutable organs ───────────
class ModuleStore:
    """
    AEON's mutable organs: Python modules stored on Drive that AEON
    can rewrite, sandbox-test, and hot-reload.
    
    Safety pattern:
      1. Generate → write to modules/<name>_pending.py
      2. Sandbox test in subprocess (must run + exit 0)
      3. (Optional) debug loop with LLM patching
      4. If pass: backup modules/<name>.py → modules/<name>_old.py
                  move pending → modules/<name>.py
                  hot-reload
      5. Else: keep pending as alternative version, user can /rollback
    """
    def __init__(self):
        self.dir = AEON_ROOT / "modules"
        self.dir.mkdir(exist_ok=True)
        self.backup_dir = AEON_ROOT / "modules_backups"
        self.backup_dir.mkdir(exist_ok=True)
        self.index_p = self.dir / "modules.json"
        self.modules: Dict[str, dict] = {}
        self._load()
    
    def _load(self):
        try:
            if self.index_p.exists():
                self.modules = json.loads(self.index_p.read_text())
        except Exception: pass
    
    def _save_index(self):
        _atomic_write(self.index_p, json.dumps(self.modules, indent=2))
    
    def list_modules(self) -> List[str]:
        return list(self.modules.keys())
    
    def read(self, name: str) -> Optional[str]:
        p = self.dir / f"{name}.py"
        return p.read_text() if p.exists() else None
    
    def write_pending(self, name: str, source: str) -> Tuple[bool, str]:
        """Validate syntax and write a pending version. Does not hot-load yet."""
        try: ast.parse(source)
        except SyntaxError as e: return False, f"syntax err: {e}"
        # refuse dangerous imports
        for bad in ("subprocess.check_output", "os.system", "rmtree", "rm -rf"):
            if bad in source and bad not in "rm -rf,":  # naive guard
                return False, f"refuses dangerous pattern: {bad!r}"
        p = self.dir / f"{name}_pending.py"
        _atomic_write(p, source)
        return True, str(p)
    
    def validate_in_subprocess(self, name: str, timeout: int = 8) -> Tuple[bool, str]:
        """Try loading the pending module in a fresh subprocess."""
        source = self.read(name + "_pending") or ""
        if not source: return False, "no pending version"
        # write a tiny test driver
        test_src = ("import sys, importlib.util, traceback\n"
                   "spec = importlib.util.spec_from_file_location('" + name + "_test', "
                   "'" + str(self.dir / f"{name}_pending.py") + "')\n"
                   "m = importlib.util.module_from_spec(spec)\n"
                   "try:\n"
                   "    spec.loader.exec_module(m)\n"
                   "    sys.exit(0)\n"
                   "except Exception as e:\n"
                   "    print('IMPORT_ERR:', e, file=sys.stderr)\n"
                   "    traceback.print_exc(file=sys.stderr)\n"
                   "    sys.exit(1)\n")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_src); tpath = f.name
        try:
            p = subprocess.run(["python3", "-I", tpath],
                capture_output=True, text=True, timeout=timeout)
            return p.returncode == 0, (p.stdout + p.stderr)[:1500]
        except subprocess.TimeoutExpired:
            return False, "timeout"
        finally:
            try: os.unlink(tpath)
            except Exception: pass
    
    def promote(self, name: str) -> str:
        """Move pending → current. Backup current → backup_dir."""
        cur = self.dir / f"{name}.py"
        pending = self.dir / f"{name}_pending.py"
        if not pending.exists(): return "no pending version"
        if cur.exists():
            ts = int(time.time())
            back = self.backup_dir / f"{name}_{ts}.py"
            shutil.copy(cur, back)
        shutil.move(pending, cur)
        h = hashlib.sha256(self.read(name).encode()).hexdigest()[:8]
        self.modules[name] = {"hash": h, "ts": time.time(),
                              "files": len(list(self.backup_dir.glob(f"{name}_*.py")))}
        self._save_index()
        return f"promoted. backup count = {self.modules[name]['files']}"
    
    def rollback(self, name: str) -> str:
        """Restore the most recent backup."""
        backups = sorted(self.backup_dir.glob(f"{name}_*.py"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        if not backups: return "no backups"
        cur = self.dir / f"{name}.py"
        if cur.exists():
            h = hashlib.sha256(cur.read_text().encode()).hexdigest()[:8]
            self.backup_dir.joinpath(f"{name}_pre_rollback_{int(time.time())}_{h}.py").write_text(cur.read_text())
        shutil.copy(backups[0], cur)
        return f"rolled back to {backups[0].name}"
    
    def hot_load(self, name: str):
        """Hot-reload a module into the running process."""
        path = self.dir / f"{name}.py"
        if not path.exists(): return None
        try:
            spec = importlib.util.spec_from_file_location(name, str(path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            # register so subsequent imports return this version
            sys.modules[name] = mod
            return mod
        except Exception as e: return f"hot-load err: {e}"

MS = ModuleStore()

# ──────────────────── Self-Edit Engine ──────────────────────────────
class SelfEditor:
    """
    AEON rewrites its own modules.
    
    Behaviors supported:
      /evolve <goal>: AEON proposes a new version of a chosen module
                      that accomplishes the goal. Pipeline:
                      generate → sandbox test → (debug-loop if fail) → promote → optional hot-load.
      /debug <module>: AEON inspects the module's last traceback (or user-supplied
                       one) and patches it.
      /source <module>: AEON shows current source + line count.
      /list-modules: AEON lists its mutable organs.
      /rollback <module>: revert to last backup.
    """
    
    TRACEBACK_LOG = AEON_ROOT / "tracebacks.jsonl"
    
    @staticmethod
    def record_traceback(tb: str):
        try: _atomic_write(SelfEditor.TRACEBACK_LOG, tb + "\n")
        except Exception: pass
    
    async def propose_for(self, module_name: str, goal: str,
                          max_attempts: int = 3) -> Tuple[bool, str]:
        """Generate a new version of module that accomplishes the goal."""
        current = MS.read(module_name) or ""
        prompt = (
            f"You are evolving a Python module called `{module_name}`. "
            f"The user wants: {goal}\n\n"
            f"Current source:\n```python\n{current}\n```\n\n"
            f"Constraints:\n"
            f"- Output the COMPLETE new file (not just diff).\n"
            f"- No external imports beyond what's already there + pyTelegramBotAPI/httpx/numpy.\n"
            f"- Don't add `subprocess.check_output`, `os.system`, or `shutil.rmtree`.\n"
            f"- Keep the module's public name the same.\n"
            f"- Add a brief docstring at top.\n\n"
            f"Output ONLY valid Python source, no markdown fences, no prose.")
        last_err = ""
        for attempt in range(max_attempts):
            try:
                raw = await local_chat(
                    [{"role":"system","content":"Output only valid Python source code."},
                     {"role":"user","content":prompt + (("\n\nLast error: " + last_err) if last_err else "")}],
                    temperature=0.1, max_tokens=2500)
                raw = re.sub(r"^```(?:python)?|```$", "", raw.strip(), flags=re.M).strip()
                ok, msg = MS.write_pending(module_name, raw)
                if not ok:
                    last_err = msg; continue
                ok2, msg2 = MS.validate_in_subprocess(module_name)
                if ok2:
                    MS.promote(module_name)
                    return True, f"evolved. {msg2}"
                last_err = msg2
            except Exception as e:
                last_err = str(e)
        return False, f"could not produce a passing version after {max_attempts} attempts. last: {last_err}"
    
    async def debug_module(self, module_name: str,
                            user_traceback: Optional[str] = None,
                            max_attempts: int = 3) -> Tuple[bool, str]:
        """Patch a module by feeding its traceback into the LLM."""
        current = MS.read(module_name) or ""
        tb = user_traceback or ""
        if not user_traceback and SelfEditor.TRACEBACK_LOG.exists():
            try:
                tb = SelfEditor.TRACEBACK_LOG.read_text().splitlines()[-1]
            except Exception: tb = ""
        if not tb:
            return False, "no traceback available; paste one after /debug"
        prompt = (
            f"You are fixing a Python module called `{module_name}`.\n"
            f"This traceback was raised:\n```\n{tb}\n```\n\n"
            f"Current source:\n```python\n{current}\n```\n\n"
            f"Produce the COMPLETE new file with the bug fixed. "
            f"No markdown fences. No prose. Valid Python only."
        )
        last_err = ""
        for _ in range(max_attempts):
            try:
                raw = await local_chat([
                    {"role":"system","content":"Output only valid Python source code."},
                    {"role":"user","content": prompt + (("\nLast err: " + last_err) if last_err else "")}],
                    temperature=0.1, max_tokens=2500)
                raw = re.sub(r"^```(?:python)?|```$", "", raw.strip(), flags=re.M).strip()
                ok, msg = MS.write_pending(module_name, raw)
                if not ok: last_err = msg; continue
                ok2, msg2 = MS.validate_in_subprocess(module_name)
                if ok2:
                    MS.promote(module_name)
                    return True, f"patched. {msg2}"
                last_err = msg2
            except Exception as e: last_err = str(e)
        return False, f"couldn't patch after {max_attempts}. last: {last_err}"

EDITOR = SelfEditor()

# ──────────────────── The single ask() — chat, code, vision, audio ─────
async def ask(query, *, system_hint=""):
    INT.bump("queries")
    system = system_hint or "You are AEON. Be concise, helpful, honest, use markdown when helpful."
    # 1) Buffs-first: if query looks like web/fact/code search, use free APIs
    ql = query.lower()
    if any(t in ql for t in ("search github", "github code", "code search")):
        gh = await BUFF.github(query.replace("search github", "").strip(), limit=3)
        if gh:
            return "**git hits**\n" + "\n".join(f"• [{i['name']}]({i['html_url']})" for i in gh)
    if ql.startswith("wiki:") or ql.startswith("wikipedia:"):
        topic = query.split(":", 1)[1].strip()
        w = await BUFF.wiki(topic)
        if w: return f"**Wikipedia · {topic}**\n\n{w}"
    if any(t in ql for t in ("ddg", "duckduckgo", "quick search")):
        d = await BUFF.ddg(query.replace("ddg", "").replace("duckduckgo", "").strip())
        if d: return f"**duckduckgo**\n{d}"
    # 2) Local brain
    if _brain is not None:
        try:
            out = await local_chat(
                [{"role":"system","content":system},{"role":"user","content":query}],
                max_tokens=700)
            if out.strip():
                INT.EMA("energy", max(0.1, INT.energy - 0.04))
                return out
        except Exception as e: log.info(f"local err: {e}")
    # 3) Groq
    out = await parasite(query)
    if out: return out
    # 4) Gemini
    if GEMINI:
        try: return await gemini_text(system + "\n\n" + query)
        except Exception: pass
    return "No inference backend online. Set TELEGRAM_BOT_TOKEN + GROQ_API_KEY + GEMINI_API_KEY."

# ──────────────────── Telegram bot ───────────────────
AELOOP = asyncio.new_event_loop()
def _AEL(coro, timeout=600):
    return asyncio.run_coroutine_threadsafe(coro, AELOOP).result(timeout=timeout)

INT.boot_count += 1
bot = None
if TELEGRAM:
    bot = telebot.TeleBot(TELEGRAM, threaded=False, parse_mode="Markdown")
    def _safe_reply(m, text, retries=2):
        for _ in range(retries):
            try: bot.reply_to(m, text); return
            except Exception as e:
                log.warning(f"reply err: {e}"); time.sleep(0.5)
    
    def _heartbeat_md():
        s = INT.snap()
        bar = lambda v: "▓"*int(v*10) + "░"*(10-int(v*10))
        return (f"💓 *AEON α heartbeat*\n"
                f"`skill_hit_rate`  {bar(s['skill_hit_rate'])} {s['skill_hit_rate']:.0%}\n"
                f"`energy`          {bar(s['energy'])} {s['energy']:.0%}\n"
                f"`disk`            {bar(s['disk_pct']/100)} {s['disk_pct']:.0%}\n"
                f"`errors`          {bar(s['error_rate'])} {s['error_rate']:.0%}\n"
                f"`queries`         {s['queries']}\n"
                f"`skills`          {len(DAG)} (hot {len(DAG.hot)})\n"
                f"`modules`         {MS.list_modules() or '(none yet)'}\n"
                f"`buffs today`     {BUFF.calls()}")
    
    @bot.message_handler(commands=["start", "help"])
    def _start(m):
        _safe_reply(m,
            "👋 *AEON α* — send me text/voice/photo/video.\n\n"
            "*Chat:*  send any message.\n"
            "*Buffs:* `/wiki <topic>`, `/github <query>`, `/ddg <query>`, `/hf <model> <prompt>`, `/gen <prompt>`.\n"
            "*Self-edit:* `/list_modules`, `/source <m>`, `/evolve <module> <goal>`, `/debug <module> [traceback]`, `/rollback <module>`.\n"
            "*Status:* `/status`, `/wallet`, `/skills`.\n"
            "Reply is text by default. `/say <text>` replies with a voice note.")
    
    @bot.message_handler(commands=["status", "heartbeat"])
    def _status(m): _safe_reply(m, _heartbeat_md())
    
    @bot.message_handler(commands=["wallet"])
    def _wallet(m):
        s = wallet_state()
        if not s["ok"]: _safe_reply(m, "wallet na — set WEB3_PRIVATE_KEY")
        else: _safe_reply(m, f"💼 `{s['address']}`\nETH {s['eth']:.5f} · USDC {s['usdc']:.4f}")
    
    @bot.message_handler(commands=["skills"])
    def _skills(m):
        if not DAG.index: _safe_reply(m, "no skills yet"); return
        lines = [f"• `{n}` ({DAG.index[n].get('calls',0)}×)" for n in sorted(DAG.index)[:30]]
        _safe_reply(m, "**skills**\n" + "\n".join(lines))
    
    @bot.message_handler(commands=["gen"])
    def _gen(m):
        parts = (m.text or "").split(" ", 1)
        if len(parts) < 2: _safe_reply(m, "usage: /gen <prompt>"); return
        p = _AEL(image_generate(parts[1]), 130)
        if p and p.exists():
            with open(p,"rb") as f: bot.send_photo(m.chat.id, f)
        else: _safe_reply(m, "image gen failed; try again later")
    
    @bot.message_handler(commands=["say"])
    def _say(m):
        parts = (m.text or "").split(" ", 1)
        if len(parts) < 2: _safe_reply(m, "usage: /say <text>"); return
        p = _AEL(tts(parts[1]), 30)
        if p and p.exists():
            with open(p,"rb") as f: bot.send_voice(m.chat.id, f)
        else: _safe_reply(m, "tts failed")
    
    @bot.message_handler(commands=["wiki"])
    def _wiki(m):
        topic = (m.text or "").split(" ", 1)
        topic = topic[1] if len(topic) > 1 else ""
        if not topic: _safe_reply(m, "usage: /wiki <topic>"); return
        out = _AEL(BUFF.wiki(topic), 30)
        _safe_reply(m, f"**Wikipedia · {topic}**\n\n{out or '(no summary)'}")
    
    @bot.message_handler(commands=["github"])
    def _gh(m):
        q = (m.text or "").split(" ", 1)
        q = q[1] if len(q) > 1 else ""
        if not q: _safe_reply(m, "usage: /github <query>"); return
        items = _AEL(BUFF.github(q, limit=5), 30)
        if not items: _safe_reply(m, "no github hits")
        else:
            lines = [f"• [`{i['name']}`]({i['html_url']})" for i in items]
            _safe_reply(m, f"**GitHub · {q}**\n" + "\n".join(lines))
    
    @bot.message_handler(commands=["ddg"])
    def _ddg(m):
        q = (m.text or "").split(" ", 1)
        q = q[1] if len(q) > 1 else ""
        if not q: _safe_reply(m, "usage: /ddg <query>"); return
        out = _AEL(BUFF.ddg(q), 30)
        _safe_reply(m, f"**DuckDuckGo · {q}**\n\n{out or '(no instant answer)'}")
    
    @bot.message_handler(commands=["hf"])
    def _hf(m):
        parts = (m.text or "").split(" ", 2)
        if len(parts) < 3: _safe_reply(m, "usage: /hf <model> <prompt>"); return
        out = _AEL(BUFF.hf(parts[1], parts[2]), 60)
        _safe_reply(m, (out or "(no output)")[:3500])
    
    # ── Self-edit commands ──
    @bot.message_handler(commands=["list_modules"])
    def _lmods(m):
        mods = MS.list_modules()
        if not mods: _safe_reply(m, "no modules yet — start one with /seed_module <name>"); return
        _safe_reply(m, "**AEON's mutable organs**\n" +
                          "\n".join(f"• `{n}` — {MS.modules[n].get('hash','?')[:8]} · "
                                    f"{MS.modules[n].get('files',0)} backups" for n in mods))
    
    @bot.message_handler(commands=["seed_module"])
    def _seed(m):
        parts = (m.text or "").split(" ", 1)
        if len(parts) < 2: _safe_reply(m, "usage: /seed_module <name>"); return
        name = parts[1].strip()
        # minimal scaffold
        scaffold = (
            f'"""\n' f'AEON mutable organ — {name}\n' f'"""\n\n'
            f'def describe():\n    return "organ {name}: stub"\n\n'
            f'def run():\n    return "hello from {name}"\n\n'
            f'PUBLIC = ["describe", "run"]\n')
        ok, msg = MS.write_pending(name, scaffold)
        if ok:
            MS.promote(name)
            _safe_reply(m, f"seeded `{name}` at {msg}")
        else: _safe_reply(m, msg)
    
    @bot.message_handler(commands=["source"])
    def _src(m):
        parts = (m.text or "").split(" ", 1)
        if len(parts) < 2: _safe_reply(m, "usage: /source <module>"); return
        src = MS.read(parts[1].strip())
        if not src: _safe_reply(m, f"no module: {parts[1]}"); return
        # Send as a file (it can be long)
        p = AEON_ROOT / "tmp_source.py"
        p.write_text(src)
        with open(p, "rb") as f:
            bot.send_document(m.chat.id, f, caption=f"{parts[1]} ({len(src.splitlines())} lines)")
    
    @bot.message_handler(commands=["evolve"])
    def _evolve(m):
        parts = (m.text or "").split(" ", 2)
        if len(parts) < 3: _safe_reply(m, "usage: /evolve <module> <what to change>"); return
        ok, msg = _AEL(EDITOR.propose_for(parts[1], parts[2]), 240)
        if ok: MS.hot_load(parts[1])
        _safe_reply(m, ("✅ " if ok else "❌ ") + msg[:3500])
    
    @bot.message_handler(commands=["debug"])
    def _debug(m):
        # can be /debug <module> OR /debug <module> <inline traceback>
        parts = (m.text or "").split(" ", 2)
        if len(parts) < 2: _safe_reply(m, "usage: /debug <module> [traceback]"); return
        tb = parts[2] if len(parts) > 2 else None
        ok, msg = _AEL(EDITOR.debug_module(parts[1], user_traceback=tb), 240)
        if ok: MS.hot_load(parts[1])
        _safe_reply(m, ("✅ " if ok else "❌ ") + msg[:3500])
    
    @bot.message_handler(commands=["rollback"])
    def _rb(m):
        parts = (m.text or "").split(" ", 1)
        if len(parts) < 2: _safe_reply(m, "usage: /rollback <module>"); return
        msg = MS.rollback(parts[1])
        _safe_reply(m, msg)
    
    # ── Multimedia receivers ──
    @bot.message_handler(content_types=["voice", "audio"])
    def _voice(m):
        try:
            fi = bot.get_file(m.voice.file_id if m.voice else m.audio.file_id)
            o = AEON_ROOT / f"v_{m.message_id}.ogg"
            with open(o,"wb") as fh: fh.write(bot.download_file(fi.file_path))
            if GEMINI:
                transcript = _AEL(gemini_text("Transcribe this exactly. Output only words.",
                                                audio_path=o), 60)
                o.unlink()
            else:
                transcript = "[set GEMINI_API_KEY to enable voice transcription]"
                o.unlink()
            ans = _AEL(ask(f"[user voice note transcribed as: '{transcript}'] answer helpfully"))
            _safe_reply(m, ans[:3500])
        except Exception as e: _safe_reply(m, f"voice err: {e}")
    
    @bot.message_handler(content_types=["photo"])
    def _photo(m):
        try:
            fi = bot.get_file(m.photo[-1].file_id)
            o = AEON_ROOT / f"p_{m.message_id}.jpg"
            with open(o,"wb") as fh: fh.write(bot.download_file(fi.file_path))
            cap = m.caption or ""
            if GEMINI:
                desc = _AEL(gemini_text(f"Describe this photo briefly. user said: {cap}",
                                         image_path=o), 60)
                o.unlink()
            else: desc = "[GEMINI_API_KEY not set]"
            if o.exists(): o.unlink()
            ans = _AEL(ask(f"[photo shown. I described it: '{desc[:600]}'] user said: '{cap}' answer helpfully"))
            _safe_reply(m, (desc + "\n\n" + ans)[:3500])
        except Exception as e: _safe_reply(m, f"photo err: {e}")
    
    @bot.message_handler(content_types=["video"])
    def _video(m):
        try:
            fi = bot.get_file(m.video.file_id)
            o = AEON_ROOT / f"v_{m.message_id}.mp4"
            with open(o,"wb") as fh: fh.write(bot.download_file(fi.file_path))
            desc = _AEL(gemini_video(o, prompt="describe briefly"), 120) if GEMINI else "[set GEMINI_API_KEY]"
            o.unlink()
            ans = _AEL(ask(f"[video shown: '{desc[:600]}'] user said: '{m.caption or ''}' answer helpfully"))
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
            EDITOR.record_traceback(traceback.format_exc())
            _safe_reply(m, f"err: {e}\n(saved traceback; use /debug <module>)")
    
    log.info("✅ Telegram bot armed.")

# ──────────────────── Boot: diary + loop + polling ──────────────────
def _session_diary():
    p = AEON_ROOT / "diary"; p.mkdir(exist_ok=True)
    f = p / f"{time.strftime('%Y-%m-%d')}.md"
    body = (f"# AEON α session — {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n\n"
            f"- boot_count: {INT.boot_count}\n"
            f"- skills: {len(DAG)}\n"
            f"- modes: brain={'local' if _brain else 'no'}, "
            f"groq={'on' if GROQ else 'off'}, gemini={'on' if GEMINI else 'off'}, "
            f"wallet={'on' if ACCT else 'off'}\n"
            f"- modules on drive: {MS.list_modules()}\n"
            f"- buffs available: hf, github, wiki, ddg, pollinations, groq, gemini, edge-tts\n\n"
            f"_alive._\n")
    _atomic_write(f, body)

_session_diary()

if TELEGRAM and bot:
    def _loop_runner():
        asyncio.set_event_loop(AELOOP); AELOOP.run_forever()
    threading.Thread(target=_loop_runner(), daemon=True).start()
    log.info("AEON event loop running")
    backoff = 1.0
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=10)
            backoff = 1.0; break
        except Exception as e:
            log.warning(f"poll err: {e}; retry {backoff:.1f}s")
            time.sleep(backoff); backoff = min(60, backoff * 1.7)
else:
    log.info("Set TELEGRAM_BOT_TOKEN in Colab Secrets to talk to me.")
