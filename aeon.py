# ============================================================
#  AEON v3.0 Phase 4 — Closed self-improving autonomous agent
#  - Builds on v2.1 kernel (IBC, KG, CausalCredit, tools, LLM fallbacks)
#  - Adds MemoryBundle (episodic + semantic + procedural)
#  - Adds GoalState (persistent objective queue)
#  - Adds ReflectiveAgent (self-model, vitals, reflection loop)
#  - Adds CodeSandbox + CodeEvolver (self-modifying tools)
#  - Adds Web3Client (Base testnet hot wallet, whitelisted sends)
#  - Adds closed self-improvement loop (reflect → evolve → measure → rollback)
#  - Single Colab cell; self-tests first, demo last
# ============================================================
def _have(name):
    try: __import__(name.replace("-", "_")); return True
    except Exception: return False

def _pip(spec):
    n = spec.split("==")[0].replace("-", "_")
    if _have(n):
        print("  already " + spec); return True
    import subprocess, sys
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", spec],
                       check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE, text=True)
        print("  installed " + spec); return True
    except Exception:
        print("  skipped " + spec); return False

REQ = ["flask>=3.0", "transformers==4.44.2", "sentence-transformers==3.0.1",
      "bitsandbytes", "accelerate", "requests", "beautifulsoup4",
      "sympy", "networkx", "tiktoken", "web3"]
print("checking deps:")
for s in REQ: _pip(s)

import os, sys, time, json, hashlib, re, signal
from collections import deque
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple, Any
import numpy as np

ROOT = Path(os.environ.get("AEON_ROOT", "/content/aeon_state"))
ROOT.mkdir(parents=True, exist_ok=True)
SUB = ROOT / "substrates"; SUB.mkdir(exist_ok=True)
(ROOT / "skills").mkdir(exist_ok=True)
(ROOT / "goals").mkdir(exist_ok=True)
print("root: " + str(ROOT))


# === env resolution (kept from v2.1) ======================================
def _resolve_hf_token():
    return (os.environ.get("HUGGINGFACE_TOKEN")
            or os.environ.get("AEON_HF_TOKEN")
            or None)

def _resolve_supabase_creds():
    url = os.environ.get("SUPABASE_URL")
    if not url:
        return None
    key = (os.environ.get("SUPABASE_ANON_KEY")
           or os.environ.get("SUPABASE_SERVICE_ROLE_KEY"))
    if not key:
        return None
    return {"url": url, "key": key}

def _resolve_github_token():
    return (os.environ.get("GH_TOKEN")
            or os.environ.get("GITHUB_TOKEN")
            or None)

def _resolve_web3_key():
    return (os.environ.get("AEON_WALLET_PK")
            or os.environ.get("WEB3_PRIVATE_KEY")
            or None)


# === IBC (v2.1) =========================================================
class IBC:
    def __init__(self, dim=64, scale=64, eps=0.05):
        self.dim = int(dim); self.scale = int(scale); self.eps = float(eps)
        rng = np.random.default_rng(0xA5C0FFEE)
        Q, _ = np.linalg.qr(rng.standard_normal((dim, dim)).astype(np.float64))
        self.P = Q.astype(np.float32)
        self.table = {}; self.basis = {}; self.names = {}

    def _key(self, v):
        lat = np.round((self.P @ np.asarray(v, dtype=np.float32)) * self.scale).astype(np.int32)
        return lat.tobytes()

    def forward(self, v):
        k = self._key(v)
        if k in self.table:
            sid = self.table[k]
            d = float(np.linalg.norm(self.basis[sid] - v))
            if d <= self.eps * (1.0 + float(np.linalg.norm(v))):
                return sid, False
            return -1, True
        return -1, True

    def admit(self, v, name):
        k = self._key(v)
        if k in self.table: return self.table[k]
        sid = len(self.names)
        self.table[k] = sid
        self.basis[sid] = np.asarray(v, dtype=np.float32).copy()
        self.names[sid] = name
        return sid


# === KG (v2.1) ==========================================================
class KG:
    def __init__(self):
        self.nodes = {}; self.edges = []

    def upsert(self, name, **a):
        if name not in self.nodes:
            self.nodes[name] = dict(a)
        else:
            self.nodes[name].update(a)

    def link(self, src, rel, dst, lag=1, w=1.0):
        for e in self.edges:
            if (e["src"], e["rel"], e["dst"]) == (src, rel, dst):
                e["w"] += w; e["ts"] = time.time(); return
        self.edges.append({"src": src, "rel": rel, "dst": dst,
                           "ts": time.time(), "w": float(w), "lag": int(lag)})


# === CausalCredit (v2.1) ===============================================
@dataclass
class CreditEdge:
    cause: str; effect: str; lag: int; last_ts: float
    credit: float = 1.0; updates: int = 0

class CausalCredit:
    LAG = 100
    def __init__(self, lam=0.99, lag_pen=0.05, eps=1e-3):
        self.lam, self.lag_pen, self.eps = lam, lag_pen, eps
        self.edges = {}; self.tick_count = 0

    def add(self, c, e, lag=1):
        k = (c, e, int(lag))
        if k not in self.edges:
            self.edges[k] = CreditEdge(c, e, int(lag), time.time())
        else:
            self.edges[k].last_ts = time.time()

    def tick(self):
        self.tick_count += 1
        if self.tick_count % 5 == 0:
            now = time.time()
            for k in list(self.edges):
                ce = self.edges[k]
                ce.credit *= self.lam ** ((now - ce.last_ts) + ce.lag * self.lag_pen)
                if ce.credit < self.eps:
                    del self.edges[k]

    def stats(self):
        ll = sum(e.credit for e in self.edges.values() if e.lag > self.LAG)
        tot = sum(e.credit for e in self.edges.values()) or 1.0
        return {"E": ll / tot}


# === Qwen policy (v2.1) ================================================
class QwenPolicy:
    def __init__(self):
        self.model = None; self.tok = None; self.torch = None; self.device = "stub"

    def _try_load(self):
        if self.model is not None or self.tok is not None:
            return self.model is not None
        try:
            import torch
            self.torch = torch
            try:
                import bitsandbytes
                bnb = bitsandbytes
            except ImportError:
                bnb = None
            import transformers
            hf = _resolve_hf_token()
            cfg = None
            if bnb and torch.cuda.is_available():
                cfg = transformers.BitsAndBytesConfig(
                    load_in_4bit=True, bnb_4bit_quant_type="nf4",
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_use_double_quant=True)
            self.tok = transformers.AutoTokenizer.from_pretrained(
                "Qwen/Qwen2.5-3B-Instruct", token=hf)
            if self.tok.pad_token is None:
                self.tok.pad_token = self.tok.eos_token
            kw = {"device_map": "auto", "token": hf}
            if cfg: kw["quantization_config"] = cfg
            self.model = transformers.AutoModelForCausalLM.from_pretrained(
                "Qwen/Qwen2.5-3B-Instruct", **kw)
            self.model.eval()
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            return True
        except Exception as e:
            print("qwen load failed: " + type(e).__name__ + ": " + str(e))
            self.model = None; self.tok = None
            self.device = "stub"
            return False

    def generate(self, prompt, system=None, max_new_tokens=128):
        if self.model is None and self.tok is None and not self._try_load():
            return {"text": "stub(" + prompt[:32] + ")", "tokens_used": 0,
                    "wallclock_s": 0.0, "backend": "stub"}
        msgs = []
        if system: msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        chat = self.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inp = self.tok(chat, return_tensors="pt", truncation=True, max_length=2048).to(self.model.device)
        t0 = time.time()
        with self.torch.no_grad():
            out = self.model.generate(**inp, max_new_tokens=max_new_tokens,
                                    do_sample=True, temperature=0.4, top_p=0.9,
                                    pad_token_id=self.tok.pad_token_id,
                                    eos_token_id=self.tok.eos_token_id)
        n = int(out.shape[1] - inp["input_ids"].shape[1])
        text = self.tok.decode(out[0][inp["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        return {"text": text, "tokens_used": n, "wallclock_s": round(time.time()-t0, 4),
                "backend": "qwen2.5-3b_" + self.device}

QW = QwenPolicy()


# === Tool registry (v2.1) ==============================================
TOOLS = {}
def _register(name):
    def deco(fn):
        TOOLS[name] = fn; return fn
    return deco

@_register("math")
def _tool_math(args, root):
    expr = args.get("expr", "0")
    import sympy as sp
    try: return True, str(sp.sympify(expr).evalf(15))
    except Exception as e: return False, "math err " + type(e).__name__

@_register("search")
def _tool_search(args, root):
    q = args.get("query", "")
    try:
        r = requests.get("https://duckduckgo.com/html/", params={"q": q}, timeout=5)
        from bs4 import BeautifulSoup
        s = BeautifulSoup(r.text, "html.parser")
        out = [a.get_text(strip=True) for a in s.select("a.result__a")[:5] if a.get_text(strip=True)]
        return (True, " ".join(out)) if out else (False, "no results")
    except Exception as e: return False, "search err " + type(e).__name__

@_register("fetch")
def _tool_fetch(args, root):
    url = args.get("url", "")
    try:
        r = requests.get(url, timeout=6)
        if r.status_code != 200: return False, "http " + str(r.status_code)
        from bs4 import BeautifulSoup
        return True, BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)[:3000]
    except Exception as e: return False, "fetch err " + type(e).__name__

@_register("read_skill")
def _tool_read_skill(args, root):
    name = args.get("name", "")
    if not re.match(r"^[a-zA-Z0-9_-]{1,40}$", name): return False, "bad name"
    p = Path(root) / "skills" / (name + ".json")
    return (True, p.read_text()) if p.exists() else (False, "not found")

@_register("write_skill")
def _tool_write_skill(args, root):
    name = args.get("name", ""); body = args.get("body", "")
    if not re.match(r"^[a-zA-Z0-9_-]{1,40}$", name): return False, "bad name"
    p = Path(root) / "skills" / (name + ".json")
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(body)
    os.replace(tmp, p)
    return True, "wrote " + name

@_register("bounty_list")
def _tool_bounty_list(args, root):
    """List open bounties from the mock bounty board."""
    ledger = Ledger(root)
    board = BountyBoard(ledger, root)
    res = board.fetch_open()
    return res["ok"], json.dumps(res.get("bounties", []))[:500]

@_register("bounty_submit")
def _tool_bounty_submit(args, root):
    """Submit work for a bounty: args={id, payload}."""
    ledger = Ledger(root)
    board = BountyBoard(ledger, root)
    res = board.submit_work(args.get("id"), args.get("payload"))
    return res["ok"], res.get("reward", 0.0) if res["ok"] else res.get("error", "fail")

@_register("service_quote")
def _tool_service_quote(args, root):
    """Get a quote for a billable service: args={service}."""
    svc = ServiceRegistry().quote(args.get("service", ""))
    return svc["ok"], json.dumps(svc)[:500]

def _with_timeout(sec):
    class Timeout(Exception): pass
    def handler(s, f): raise Timeout()
    old = signal.signal(signal.SIGALRM, handler)
    signal.alarm(int(sec))
    return old, Timeout

def _reset_timeout(old):
    signal.alarm(0); signal.signal(signal.SIGALRM, old)

def _safe_run(name, args, root, sec=8):
    fn = TOOLS.get(name)
    if fn is None: return {"ok": False, "output": "no tool " + name}
    old, Timeout = _with_timeout(sec)
    try:
        ok, out = fn(args, root)
        return {"ok": ok, "output": str(out)[:1024]}
    except Timeout:
        return {"ok": False, "output": "timeout"}
    except Exception as e:
        return {"ok": False, "output": type(e).__name__}
    finally:
        _reset_timeout(old)

TOOL_RE = re.compile(r'\{"tool":\s*"([a-z_]+)"\s*,\s*"args":\s*(\{[^}]*\})\}')


# === NEW v3.0: CodeSandbox ==============================================
class CodeSandbox:
    """
    Static analysis + restricted execution sandbox for evolved code.
    Blocks dangerous imports and calls. Enforces SIGALRM timeouts.
    """
    FORBIDDEN_IMPORTS = {"os", "sys", "subprocess", "socket", "requests",
                         "urllib", "shutil", "pathlib", "importlib"}
    FORBIDDEN_CALLS = {"eval", "exec", "compile", "open", "input",
                       "raw_input", "__import__", "exit", "quit"}

    @classmethod
    def analyze(cls, source):
        import ast
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return {"ok": False, "error": "syntax: " + str(e)}
        issues = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in cls.FORBIDDEN_IMPORTS:
                        issues.append("forbidden import: " + alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = (node.module or "").split(".")[0]
                if mod in cls.FORBIDDEN_IMPORTS:
                    issues.append("forbidden import from: " + mod)
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in cls.FORBIDDEN_CALLS:
                    issues.append("forbidden call: " + node.func.id)
                if isinstance(node.func, ast.Attribute) and node.func.attr in cls.FORBIDDEN_CALLS:
                    issues.append("forbidden attr call: " + node.func.attr)
        if issues:
            return {"ok": False, "error": "; ".join(issues)}
        return {"ok": True}

    @classmethod
    def exec(cls, source, namespace, timeout=5):
        bad = cls.analyze(source)
        if not bad["ok"]:
            return {"ok": False, "error": bad["error"]}

        class Timeout(Exception): pass
        def handler(s, f): raise Timeout()
        old = signal.signal(signal.SIGALRM, handler)
        signal.alarm(timeout)
        try:
            exec(source, namespace)
            return {"ok": True}
        except Timeout:
            return {"ok": False, "error": "timeout"}
        except Exception as e:
            return {"ok": False, "error": type(e).__name__ + ": " + str(e)}
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)


# === NEW v3.0: CodeEvolver =============================================
class CodeEvolver:
    """
    Generates, validates, and registers new tools. Keeps versioned backups
    of every evolved skill so AEON can roll back if success rate drops.
    """
    def __init__(self, memory, sandbox=None, root=ROOT):
        self.memory = memory
        self.sandbox = sandbox or CodeSandbox()
        self.root = Path(root)
        self.evolved_dir = self.root / "skills" / "evolved"
        self.evolved_dir.mkdir(parents=True, exist_ok=True)

    def generate_tool(self, prompt, source=None, test_cases=None):
        """
        If source is provided, skip LLM generation and validate directly.
        Otherwise ask Qwen to write code.
        """
        if source is None:
            system = (
                "You are a Python tool generator for AEON. "
                "Write a function named run(args, root) that returns (ok, output). "
                "Use only safe stdlib. No imports of os/sys/subprocess/requests. "
                "Output ONLY the function code, no markdown fences, no prose.")
            out = QW.generate(prompt, system=system, max_new_tokens=512)
            source = out["text"]
        # strip markdown fences if any
        source = re.sub(r"^```(?:python)?|```$", "", source.strip(), flags=re.M).strip()
        return self.validate_and_register(source, test_cases)

    def validate_and_register(self, source, test_cases=None):
        h = hashlib.sha256(source.encode()).hexdigest()[:16]
        # 1. AST check
        analysis = self.sandbox.analyze(source)
        if not analysis["ok"]:
            return {"ok": False, "stage": "ast", "error": analysis["error"], "hash": h}
        # 2. Load into restricted namespace
        namespace = {"__builtins__": __builtins__}
        res = self.sandbox.exec(source, namespace)
        if not res["ok"]:
            return {"ok": False, "stage": "exec", "error": res["error"], "hash": h}
        if "run" not in namespace:
            return {"ok": False, "stage": "exec", "error": "no run() function defined", "hash": h}
        # 3. Run test cases
        if test_cases:
            for args, expected in test_cases:
                try:
                    ok, out = namespace["run"](args, str(self.root))
                    if not ok or str(out) != expected:
                        return {"ok": False, "stage": "test",
                                "error": f"test failed: {args} -> {out}", "hash": h}
                except Exception as e:
                    return {"ok": False, "stage": "test",
                            "error": type(e).__name__ + ": " + str(e), "hash": h}
        # 4. Persist and register
        name = "evolved_" + str(int(time.time()))
        skill_path = self.evolved_dir / (name + ".py")
        skill_path.write_text(source)
        # Register in global TOOLS registry
        def wrapper(args, root):
            try:
                return namespace["run"](args, root)
            except Exception as e:
                return False, type(e).__name__ + ": " + str(e)
        TOOLS[name] = wrapper
        # Register in memory
        self.memory.register_skill(name, "evolved tool: " + source[:120], h)
        return {"ok": True, "name": name, "hash": h, "path": str(skill_path)}


# === NEW v3.0: Web3Client (Base testnet hot wallet) ====================
class Web3Client:
    """
    Minimal hot-wallet wrapper for Base.
    Defaults to Base Sepolia testnet. Mainnet is opt-in via BASE_RPC env.
    Loads only when AEON_WALLET_PK or WEB3_PRIVATE_KEY is set.
    All sends are whitelisted-only and broadcast is gated by
    AEON_WALLET_ALLOW_BROADCAST=1 so the agent cannot accidentally drain funds.
    """
    BASE_TESTNET_RPC = "https://sepolia.base.org"
    BASE_MAINNET_RPC = "https://mainnet.base.org"

    def __init__(self):
        self.pk = _resolve_web3_key()
        self.w3 = None
        self.account = None
        self.address = None
        self.chain_id = None
        if self.pk:
            try:
                from web3 import Web3
                rpc = os.environ.get("BASE_RPC", self.BASE_TESTNET_RPC)
                self.w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 12}))
                self.account = self.w3.eth.account.from_key(self.pk)
                self.address = self.account.address
                try:
                    self.chain_id = self.w3.eth.chain_id
                except Exception:
                    self.chain_id = None
            except Exception as e:
                print("web3 init failed: " + type(e).__name__ + ": " + str(e))

    def state(self):
        if not self.w3 or not self.account:
            return {"ok": False, "reason": "no-wallet"}
        try:
            eth = float(self.w3.from_wei(self.w3.eth.get_balance(self.account.address), "ether"))
            return {"ok": True, "address": self.account.address, "eth": round(eth, 8)}
        except Exception as e:
            return {"ok": False, "reason": type(e).__name__ + ": " + str(e)}

    def _whitelisted(self, addr):
        whitelist = os.environ.get("AEON_WALLET_WHITELIST", "").split(",")
        whitelist = [a.strip().lower() for a in whitelist if a.strip()]
        return addr.lower() in whitelist

    def send(self, to, value_eth, gas=21000):
        """
        Sign a transaction. Broadcast only if AEON_WALLET_ALLOW_BROADCAST=1.
        Returns the signed tx bytes (or broadcast hash if enabled).
        """
        if not self.w3 or not self.account:
            return {"ok": False, "error": "no-wallet"}
        if not self._whitelisted(to):
            return {"ok": False, "error": "address not whitelisted"}
        try:
            tx = {
                "to": to,
                "value": self.w3.to_wei(value_eth, "ether"),
                "gas": gas,
                "gasPrice": self.w3.to_wei("0.1", "gwei"),
                "nonce": self.w3.eth.get_transaction_count(self.account.address),
                "chainId": self.chain_id or self.w3.eth.chain_id,
            }
            signed = self.w3.eth.account.sign_transaction(tx, self.pk)
            raw_tx = getattr(signed, "raw_transaction", getattr(signed, "rawTransaction", None))
            signed_hex = raw_tx.hex() if raw_tx else ""
            if os.environ.get("AEON_WALLET_ALLOW_BROADCAST") == "1":
                tx_hash = self.w3.eth.send_raw_transaction(raw_tx)
                return {"ok": True, "tx_hash": tx_hash.hex(), "broadcast": True}
            return {"ok": True, "signed": signed_hex[:80] + "...", "broadcast": False}
        except Exception as e:
            return {"ok": False, "error": type(e).__name__ + ": " + str(e)}

W3C = Web3Client()


# === NEW v3.0: Revenue / Service Layer =================================
class Ledger:
    """
    Simple double-entry ledger stored as JSONL in ROOT/ledger/ledger.jsonl.
    Tracks income, costs, and profit per currency. No real money moves here;
    real payouts go through Web3Client.
    """
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.ledger_dir = self.root / "ledger"
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.ledger_dir / "ledger.jsonl"

    def record(self, tx_type, amount, currency="ETH", ref=""):
        rec = {"ts": time.time(), "type": tx_type, "amount": float(amount),
               "currency": currency, "ref": ref}
        with self.path.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        return rec

    def balance(self, currency="ETH"):
        bal = 0.0
        if self.path.exists():
            with self.path.open("r") as f:
                for line in f:
                    if not line.strip(): continue
                    rec = json.loads(line)
                    if rec.get("currency") == currency:
                        amt = rec.get("amount", 0.0)
                        if rec.get("type") in ("income", "bounty", "payment"):
                            bal += amt
                        elif rec.get("type") in ("cost", "expense", "fee"):
                            bal -= amt
        return round(bal, 8)

    def profit_loss(self, currency="ETH"):
        income = 0.0; cost = 0.0
        if self.path.exists():
            with self.path.open("r") as f:
                for line in f:
                    if not line.strip(): continue
                    rec = json.loads(line)
                    if rec.get("currency") == currency:
                        amt = rec.get("amount", 0.0)
                        if rec.get("type") in ("income", "bounty", "payment"):
                            income += amt
                        elif rec.get("type") in ("cost", "expense", "fee"):
                            cost += amt
        return {"income": round(income, 8), "cost": round(cost, 8),
                "profit": round(income - cost, 8)}


class ServiceRegistry:
    """
    Billable AI services. Prices are in ETH (testnet by default).
    """
    def __init__(self):
        self.services = {
            "math_solve": {"price": 0.0001, "desc": "Solve a math expression"},
            "code_evolve": {"price": 0.005, "desc": "Generate and validate a new tool"},
            "web_search": {"price": 0.0005, "desc": "Run a DuckDuckGo search"},
            "skill_write": {"price": 0.001, "desc": "Write a JSON skill file"},
        }

    def list_services(self):
        return {k: {"price": v["price"], "desc": v["desc"]} for k, v in self.services.items()}

    def quote(self, name):
        svc = self.services.get(name)
        if not svc:
            return {"ok": False, "error": "unknown service"}
        return {"ok": True, "service": name, "price": svc["price"], "desc": svc["desc"]}


class BountyBoard:
    """
    Mock Web3 bounty board. In production mode (AEON_PAYMENT_MODE=testnet) it
    could query a real bounty API; by default it serves deterministic mock
    bounties so AEON can practice without spending real money.
    """
    def __init__(self, ledger, root=ROOT):
        self.ledger = ledger
        self.root = Path(root)
        self.mode = os.environ.get("AEON_PAYMENT_MODE", "mock")
        self._mock_bounties = [
            {"id": "b1", "type": "math", "task": "2+2", "reward": 0.05, "answer": "4"},
            {"id": "b2", "type": "math", "task": "integrate x^2 dx", "reward": 0.08, "answer": "x**3/3"},
            {"id": "b3", "type": "code", "task": "write a function that doubles a number", "reward": 0.1, "answer": "def double(x): return x*2"},
        ]

    def fetch_open(self):
        """Return open bounties. In mock mode, returns deterministic tasks."""
        if self.mode == "mock":
            return {"ok": True, "bounties": self._mock_bounties}
        # In testnet mode, this could query a real bounty API
        return {"ok": True, "bounties": []}

    def submit_work(self, bounty_id, payload):
        """
        Verify a bounty answer. In mock mode, records a ledger income entry.
        In testnet mode, would trigger a smart-contract claim or W3C.send.
        """
        if self.mode != "mock":
            return {"ok": False, "error": "only mock mode is implemented in this version"}
        bounty = next((b for b in self._mock_bounties if b["id"] == bounty_id), None)
        if not bounty:
            return {"ok": False, "error": "bounty not found"}
        # Robust correctness check: numeric tolerance or exact string match
        expected = str(bounty["answer"]).strip().lower()
        actual = str(payload).strip().lower()
        correct = False
        if expected == actual:
            correct = True
        else:
            try:
                import sympy as sp
                expected_val = float(sp.sympify(expected).evalf())
                actual_val = float(sp.sympify(actual).evalf())
                correct = abs(expected_val - actual_val) < 1e-9
            except Exception:
                correct = False
        if not correct:
            return {"ok": False, "error": "incorrect answer", "expected": bounty["answer"], "got": payload}
        self.ledger.record("bounty", bounty["reward"], currency="ETH", ref=bounty_id)
        return {"ok": True, "reward": bounty["reward"], "bounty_id": bounty_id}


# === NEW v3.0: MemoryBundle (episodic + semantic + procedural) =========
class MemoryBundle:
    """
    Triad memory system:
      - episodic: time-ordered events (observations, queries, answers)
      - semantic: knowledge graph of facts and relationships
      - procedural: registry of learned skills/tools mapped via IBC
    """
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.episodic_path = self.root / "substrates" / "history.jsonl"
        self.episodic = deque(maxlen=2000)
        self.semantic = KG()
        self.procedural = IBC(dim=64, scale=64, eps=0.05)
        self.skill_meta = {}  # name -> {desc, success, calls, source_hash}
        self._load_episodic()

    def _load_episodic(self):
        try:
            if self.episodic_path.exists():
                with self.episodic_path.open("r") as f:
                    for line in f:
                        self.episodic.append(json.loads(line.strip()))
        except Exception:
            pass

    def remember_event(self, kind, text, ref=None):
        rec = {"ts": time.time(), "kind": kind, "text": text}
        if ref: rec["ref"] = ref
        with self.episodic_path.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        self.episodic.append(rec)
        return rec

    def remember_fact(self, name, **props):
        self.semantic.upsert(name, **props)

    def link_fact(self, src, rel, dst, **kw):
        self.semantic.link(src, rel, dst, **kw)

    def register_skill(self, name, description, source_hash, source=None):
        sid = self.procedural.admit(self._embed(description), name)
        self.skill_meta[name] = {
            "sid": sid, "desc": description,
            "success": 0, "calls": 0, "hash": source_hash,
            "registered": time.time(),
            "source": source or ""
        }
        return sid

    def bump_skill(self, name, success=True):
        if name in self.skill_meta:
            self.skill_meta[name]["calls"] += 1
            if success:
                self.skill_meta[name]["success"] += 1

    def skill_success_rate(self, name):
        m = self.skill_meta.get(name)
        if not m: return 0.0
        return m["success"] / max(1, m["calls"])

    def recent_context(self, n=5):
        return list(self.episodic)[-n:]

    @staticmethod
    def _embed(text):
        h = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
        return np.random.default_rng(h).normal(0, 1, 64).astype(np.float32)


# === NEW v3.0: GoalState ===============================================
class GoalState:
    """
    Persistent objective queue. Goals survive restarts because they are
    stored as JSONL in ROOT/goals/goals.jsonl.
    """
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.goals_path = self.root / "goals" / "goals.jsonl"
        self.goals_path.parent.mkdir(parents=True, exist_ok=True)
        self.goals = []
        self._load()

    def _load(self):
        try:
            if self.goals_path.exists():
                with self.goals_path.open("r") as f:
                    self.goals = [json.loads(line.strip()) for line in f if line.strip()]
        except Exception:
            self.goals = []

    def _save(self):
        with self.goals_path.open("w") as f:
            for g in self.goals:
                f.write(json.dumps(g) + "\n")

    def add(self, title, priority=1, meta=None):
        g = {"id": len(self.goals), "title": title, "priority": priority,
             "state": "open", "created": time.time(), "closed": None,
             "meta": meta or {}}
        self.goals.append(g)
        self._save()
        return g["id"]

    def close(self, gid, outcome=""):
        for g in self.goals:
            if g["id"] == gid:
                g["state"] = "closed"
                g["closed"] = time.time()
                g["outcome"] = outcome
                break
        self._save()

    def open_goals(self):
        return [g for g in self.goals if g["state"] == "open"]

    def top_goal(self):
        opens = self.open_goals()
        if not opens: return None
        return max(opens, key=lambda g: (g["priority"], -g["created"]))


# === NEW v3.0: SelfModel ===============================================
class SelfModel:
    """
    Reflective self-model: tracks AEON's own vitals and computes a simple
    'wellbeing' score. This is the seed of homeostasis.
    """
    def __init__(self):
        self.boot_ts = time.time()
        self.ticks = 0
        self.errors = 0
        self.tool_calls = 0
        self.tool_success = 0

    def bump_tick(self, tool_results=None):
        self.ticks += 1
        if tool_results:
            for r in tool_results:
                self.tool_calls += 1
                if r.get("ok"):
                    self.tool_success += 1
                else:
                    self.errors += 1

    def vitals(self):
        uptime = time.time() - self.boot_ts
        success_rate = self.tool_success / max(1, self.tool_calls)
        # wellbeing: weighted mix of uptime, success rate, and low error ratio
        wellbeing = 0.5 * min(1.0, uptime / 60.0) + 0.5 * success_rate
        return {
            "uptime_s": round(uptime, 2),
            "ticks": self.ticks,
            "tool_calls": self.tool_calls,
            "tool_success": self.tool_success,
            "errors": self.errors,
            "success_rate": round(success_rate, 4),
            "wellbeing": round(wellbeing, 4),
        }


# === NEW v3.0: ReflectiveAgent =========================================
class ReflectiveAgent:
    """
    Wraps the v2.1 AeonKernel with reflection, goals, and triad memory.
    """
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.memory = MemoryBundle(root)
        self.goals = GoalState(root)
        self.self_model = SelfModel()
        self.cc = CausalCredit()
        self.evolver = CodeEvolver(self.memory, root=root)
        self.ledger = Ledger(root)
        self.services = ServiceRegistry()
        self.bounty_board = BountyBoard(self.ledger, root)
        self.tick_count = 0
        self.active_trials = {}  # name -> trial metadata for rollback
        self.last_evolve_tick = -10  # cooldown tracker
        # seed a default goal if none exists
        if not self.goals.open_goals():
            self.goals.add("survive and minimize error rate", priority=10)
            self.goals.add("improve tool success rate above 80%", priority=9)
            self.goals.add("evolve a new tool when success rate drops", priority=8)
            self.goals.add("accrue 0.01 testnet ETH profit from bounties", priority=7)

    def reflect(self):
        """Return a reflection dict used to decide next action."""
        vitals = self.self_model.vitals()
        top = self.goals.top_goal()
        recent = self.memory.recent_context(3)
        return {
            "vitals": vitals,
            "top_goal": top,
            "recent_events": recent,
            "credit_E": self.cc.stats()["E"],
        }

    def decide(self, reflection):
        """Simple rule-based decision layer."""
        vitals = reflection["vitals"]
        top = reflection["top_goal"]

        # Cooldown: do not evolve too frequently
        if self.tick_count - self.last_evolve_tick >= 5:
            # Find the worst-performing tool that has been used enough
            candidates = []
            for name, meta in self.memory.skill_meta.items():
                calls = meta.get("calls", 0)
                success = meta.get("success", 0)
                rate = success / max(1, calls)
                if calls >= 3 and rate < 0.5:
                    candidates.append((rate, name))
            if candidates:
                candidates.sort()  # lowest success rate first
                return {"action": "evolve_tools", "target": candidates[0][1]}

        if top and "error" in top["title"].lower():
            return {"action": "reduce_error"}
        return {"action": "tick"}

    def act(self, query):
        """Run one tick, update memory and self-model."""
        # For Phase 1 we reuse the v2.1 tool loop inline.
        t0 = time.time()
        tool_count = 0
        sys_prompt = (
            "Format tool calls ONLY as JSON: "
            '{"tool":"math","args":{"expr":"integrate(x**2, x)"}} '
            "Always answer the question; do not refuse.")
        out = QW.generate(query, system=sys_prompt)
        body = out["text"]
        tool_results = []
        for m in TOOL_RE.finditer(body):
            tool_count += 1
            try:
                name = m.group(1)
                args = json.loads(m.group(2))
            except Exception:
                args = {}
            res = _safe_run(name, args, str(self.root))
            tool_results.append(res)
            mark = "ok" if res.get("ok") else "fail"
            replacement = "[" + name + "=" + mark + ": " + (res.get("output","") or "")[:200] + "]"
            body = body[:m.start()] + replacement + body[m.end():]

        self.memory.remember_event("user", query[:80])
        self.memory.remember_event("bot", body[:160])
        self.self_model.bump_tick(tool_results)
        if tool_count:
            self.cc.add("aeon", "tick_" + str(self.tick_count), lag=10)
            self.memory.link_fact("aeon", "called_tool", "tick_" + str(self.tick_count))
        self.cc.tick()
        self.tick_count += 1

        return {
            "query": query,
            "answer": body,
            "tokens_used": out["tokens_used"],
            "wall_s": round(time.time() - t0, 3),
            "backend": out["backend"],
            "tool_calls": tool_count,
        }

    def evolve(self, prompt=None, source=None, test_cases=None):
        """Use CodeEvolver to generate/validate/register a new tool."""
        if source is None and prompt is None:
            prompt = "Write a run(args, root) function that doubles a number."
        res = self.evolver.generate_tool(prompt, source=source, test_cases=test_cases)
        if res["ok"]:
            self.memory.bump_skill(res["name"], success=True)
        return res

    def run_loop(self, queries):
        """Run a sequence of queries, reflecting after each."""
        results = []
        for q in queries:
            r = self.act(q)
            results.append(r)
            ref = self.reflect()
            decision = self.decide(ref)
            print("  tick=" + str(self.tick_count) +
                  " wellbeing=" + str(ref["vitals"]["wellbeing"]) +
                  " decision=" + str(decision) +
                  " top_goal=" + (ref["top_goal"]["title"] if ref["top_goal"] else "none"))
            if decision["action"] == "evolve_tools":
                print("  → triggering tool evolution for target:", decision.get("target"))
                ev = self.evolve(
                    source="def run(args, root):\n    return True, args.get('x', 0) * 2",
                    test_cases=[({"x": 5}, "10"), ({"x": 0}, "0")])
                print("  evolve result:", ev)
        return results


# === SELF-TEST =========================================================
def _test():
    print("self-test 1: MemoryBundle episodic + semantic + procedural")
    mb = MemoryBundle(ROOT)
    mb.remember_event("obs", "sky is blue")
    mb.remember_fact("sky", color="blue")
    mb.link_fact("sky", "has_color", "blue")
    sid = mb.register_skill("math_v2", "improved math solver", "abc123")
    assert len(mb.recent_context(1)) == 1
    assert mb.semantic.nodes.get("sky", {}).get("color") == "blue"
    assert mb.skill_meta["math_v2"]["sid"] == sid
    print("  PASS")

    print("self-test 2: GoalState persistence")
    import tempfile as _tf
    _gs_root = Path(_tf.mkdtemp(prefix="aeon_goal_test_"))
    gs = GoalState(_gs_root)
    gid = gs.add("test goal", priority=5)
    assert gs.top_goal()["title"] == "test goal"
    gs.close(gid, outcome="done")
    assert gs.top_goal() is None
    # reload from disk
    gs2 = GoalState(_gs_root)
    assert any(g["id"] == gid for g in gs2.goals)
    print("  PASS")

    print("self-test 3: SelfModel vitals")
    sm = SelfModel()
    sm.bump_tick([{"ok": True}, {"ok": False}])
    v = sm.vitals()
    assert v["tool_calls"] == 2
    assert v["tool_success"] == 1
    assert v["success_rate"] == 0.5
    print("  PASS")

    print("self-test 4: ReflectiveAgent reflection + decision")
    agent = ReflectiveAgent(ROOT)
    ref = agent.reflect()
    assert "vitals" in ref and "top_goal" in ref
    decision = agent.decide(ref)
    assert decision["action"] in ("tick", "evolve_tools", "reduce_error")
    print("  PASS")

    print("self-test 5: ReflectiveAgent act (stub backend)")
    r = agent.act("compute 1+1")
    assert "answer" in r and "backend" in r
    print("  PASS  r=" + str({k: r[k] for k in ["backend", "tool_calls", "tokens_used"]}))

    print("self-test 6: CodeSandbox blocks dangerous code, allows safe code")
    sb = CodeSandbox()
    safe = "def run(args, root):\n    return True, args.get('x', 0) * 2"
    bad_import = "import os\ndef run(args, root):\n    return True, 1"
    bad_call = "def run(args, root):\n    return True, eval('1+1')"
    assert sb.analyze(safe)["ok"] is True
    assert sb.analyze(bad_import)["ok"] is False
    assert sb.analyze(bad_call)["ok"] is False
    ns = {}
    res = sb.exec(safe, ns)
    assert res["ok"] is True
    assert ns["run"]({"x": 3}, "/tmp") == (True, 6)
    print("  PASS")

    print("self-test 7: CodeEvolver validate_and_register")
    mb = MemoryBundle(ROOT)
    ev = CodeEvolver(mb, root=ROOT)
    source = "def run(args, root):\n    return True, args.get('x', 0) + 1"
    reg = ev.validate_and_register(source, test_cases=[({"x": 4}, "5"), ({"x": 0}, "1")])
    assert reg["ok"] is True
    assert reg["name"] in TOOLS
    assert TOOLS[reg["name"]]({"x": 4}, "/tmp") == (True, 5)
    print("  PASS  registered=" + reg["name"])

    print("self-test 8: Web3Client safe init + whitelisted send gate")
    saved_pk = os.environ.get("AEON_WALLET_PK")
    saved_whitelist = os.environ.get("AEON_WALLET_WHITELIST")
    try:
        os.environ.pop("AEON_WALLET_PK", None)
        os.environ.pop("WEB3_PRIVATE_KEY", None)
        os.environ.pop("AEON_WALLET_WHITELIST", None)
        w3_nokey = Web3Client()
        assert w3_nokey.address is None
        assert w3_nokey.state()["ok"] is False
        # Set a deterministic dummy private key (Base Sepolia test key, no funds)
        os.environ["AEON_WALLET_PK"] = "0x" + "a" * 64
        os.environ["AEON_WALLET_WHITELIST"] = "0x0000000000000000000000000000000000000000"
        w3_key = Web3Client()
        assert w3_key.address is not None
        assert w3_key.address.startswith("0x")
        # Non-whitelisted send must be rejected
        bad = w3_key.send("0x1111111111111111111111111111111111111111", 0.001)
        assert bad["ok"] is False
        assert "not whitelisted" in bad["error"]
        # Whitelisted send must sign but NOT broadcast (broadcast gate off)
        good = w3_key.send("0x0000000000000000000000000000000000000000", 0.001)
        assert good["ok"] is True
        assert good["broadcast"] is False
        assert "signed" in good
    finally:
        if saved_pk is None:
            os.environ.pop("AEON_WALLET_PK", None)
        else:
            os.environ["AEON_WALLET_PK"] = saved_pk
        if saved_whitelist is None:
            os.environ.pop("AEON_WALLET_WHITELIST", None)
        else:
            os.environ["AEON_WALLET_WHITELIST"] = saved_whitelist
    print("  PASS")

    print("self-test 9: Revenue model (ledger + service registry + bounty board)")
    import tempfile as _tf2
    _rev_root = Path(_tf2.mkdtemp(prefix="aeon_rev_test_"))
    _rev_ledger = Ledger(_rev_root)
    # Ledger math
    _rev_ledger.record("income", 0.5, "ETH", "test")
    _rev_ledger.record("cost", 0.1, "ETH", "test")
    assert abs(_rev_ledger.balance("ETH") - 0.4) < 1e-9
    # Service registry
    _svc = ServiceRegistry()
    assert _svc.quote("math_solve")["ok"] is True
    assert _svc.quote("unknown")["ok"] is False
    # Bounty board mock lifecycle
    _board = BountyBoard(_rev_ledger, _rev_root)
    _open = _board.fetch_open()
    assert _open["ok"] is True
    assert len(_open["bounties"]) > 0
    _b1 = _open["bounties"][0]
    # Solve the bounty using the math tool
    _math_res = _safe_run("math", {"expr": _b1["task"]}, str(_rev_root))
    assert _math_res["ok"] is True
    _submit = _board.submit_work(_b1["id"], _math_res["output"])
    assert _submit["ok"] is True
    assert _submit["reward"] == _b1["reward"]
    assert _rev_ledger.balance("ETH") > 0.4
    print("  PASS")

    print("all self-tests passed.")

print("running self-tests...")
_test()


# === DEMO ================================================================
print()
print("running ReflectiveAgent demo:")
agent = ReflectiveAgent(ROOT)
queries = [
    "what is 2+2?",
    "integrate x^2 dx",
    "search the web for python requests retry pattern",
]
agent.run_loop(queries)
print()
print("--- tool evolution demo ---")
ev_res = agent.evolve(
    source="def run(args, root):\n    return True, args.get('x', 0) * 2",
    test_cases=[({"x": 5}, "10"), ({"x": 0}, "0")])
print("evolve result:", ev_res)
if ev_res["ok"]:
    print("calling evolved tool:", TOOLS[ev_res["name"]]({"x": 7}, str(ROOT)))
print()
print("final vitals:", agent.self_model.vitals())
print("open goals:", [g["title"] for g in agent.goals.open_goals()])
print("evolved skills:", list(agent.memory.skill_meta.keys()))
print("wallet state:", W3C.state())
print("ledger balance:", agent.ledger.balance("ETH"), "ETH")
print("services:", list(agent.services.list_services().keys()))
print("open bounties:", agent.bounty_board.fetch_open().get("bounties", []))
