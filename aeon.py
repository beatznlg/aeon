# ============================================================
#  AEON v2.1 — minimal-but-complete single cell
#  - Defensive installer, never aborts on a single package's failure
#  - All primitives inline (no file imports)
#  - Self-tests first, demo last
#  - Plain ASCII only, no smart quotes, no lambdas-in-ternaries
#  - Tested shapes: CPU stub mode + GPU+bitsandbytes Qwen mode
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
      "sympy", "networkx", "tiktoken"]
print("checking deps:")
for s in REQ: _pip(s)

import os, sys, time, json, hashlib, hmac, re, secrets, signal
from collections import deque
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List
import numpy as np

ROOT = Path(os.environ.get("AEON_ROOT", "/content/aeon_state"))
ROOT.mkdir(parents=True, exist_ok=True)
SUB = ROOT / "substrates"; SUB.mkdir(exist_ok=True)
(ROOT / "skills").mkdir(exist_ok=True)
print("root: " + str(ROOT))


# === IBC (deterministic continuous to symbolic binding) ================
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


# === KG (typed directed graph) ==========================================
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


# === EpisodicStore =====================================================
class EpisodicStore:
    def __init__(self, path, maxlen=2000):
        self.path = Path(path); self.path.parent.mkdir(parents=True, exist_ok=True)
        self.window = deque(maxlen=maxlen)

    def append(self, text, ref=None, kind="obs"):
        rec = {"ts": time.time(), "kind": kind, "text": text}
        if ref is not None: rec["ref"] = ref
        with self.path.open("a") as f:
            f.write(json.dumps(rec) + "\n")
        self.window.append(json.dumps(rec))
        return rec

    def window_bytes(self):
        return sum(len(t.encode()) + 1 for t in self.window)


# === CausalCredit (eligibility traces) ================================
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


# === Qwen policy (lazy load; stub fallback) ============================
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
            hf = os.environ.get("AEON_HF_TOKEN") or None
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


# === Tool registry (sandboxed with SIGALRM timeout) ====================
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


# === AeonKernel ====================================================
class AeonKernel:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.sub = self.root / "substrates"; self.sub.mkdir(exist_ok=True)
        self.ibc = IBC(dim=64, scale=64, eps=0.05)
        self.kg = KG()
        self.epi = EpisodicStore(self.sub / "history.jsonl", maxlen=2000)
        self.cc = CausalCredit()
        self.csv = self.root / "lambda_delta.csv"
        self.tick_count = 0

    def _embed(self, txt):
        h = int(hashlib.sha256(txt.encode()).hexdigest()[:8], 16)
        return np.random.default_rng(h).normal(0, 1, self.ibc.dim).astype(np.float32)

    def _save_csv_row(self, row):
        new = not self.csv.exists()
        if new: self.csv.write_text("t,tool_calls,bs,E\n")
        with self.csv.open("a") as f:
            f.write(row + "\n")

    def tick(self, query):
        t0 = time.time()
        tool_count = 0
        sys_prompt = (
            "Format tool calls ONLY as JSON: "
            '{"tool":"math","args":{"expr":"integrate(x**2, x)"}} '
            "Always answer the question; do not refuse.")
        out = QW.generate(query, system=sys_prompt)
        body = out["text"]
        for m in TOOL_RE.finditer(body):
            tool_count = tool_count + 1
            try:
                name = m.group(1)
                args = json.loads(m.group(2))
            except Exception:
                args = {}
            res = _safe_run(name, args, str(self.root))
            mark = "ok" if res.get("ok") else "fail"
            replacement = "[" + name + "=" + mark + ": " + (res.get("output","") or "")[:200] + "]"
            body = body[:m.start()] + replacement + body[m.end():]
        if tool_count:
            self.cc.add("aeon", "tick_" + str(self.tick_count), lag=10)
            self.kg.link("aeon", "called_tool", "tick_" + str(self.tick_count), lag=1)
        self.epi.append("q: " + query[:80])
        self.epi.append("a: " + body[:160])
        self.cc.tick()
        E = self.cc.stats()["E"]
        bs = len(body.encode()) + len(json.dumps(self.kg.nodes).encode())
        self._save_csv_row(
            f"{time.time():.3f},{tool_count},{bs},{E:.4f}")
        self.tick_count = self.tick_count + 1
        return {
            "query": query,
            "answer": body,
            "tokens_used": out["tokens_used"],
            "wall_s": round(time.time() - t0, 3),
            "backend": out["backend"],
            "tool_calls": tool_count,
            "E": round(E, 4),
            "bs": bs,
        }


# === SELF-TEST ====================================================
def _test():
    print("self-test 1: IBC admit/forward")
    rng = np.random.default_rng(0)
    ak = AeonKernel(ROOT)
    v = rng.standard_normal(64).astype(np.float32)
    sid = ak.ibc.admit(v, "t1")
    assert sid == 0
    s, c = ak.ibc.forward(v)
    assert s == sid and c == False
    print("  PASS")

    print("self-test 2: tool math")
    res = _safe_run("math", {"expr": "integrate(x**2, x)"}, str(ROOT))
    assert res["ok"] and "x**3" in res["output"]
    print("  PASS")

    print("self-test 3: tool write_skill + read_skill")
    ok_msg = _safe_run("write_skill", {"name": "test_skill", "body": "do thing"}, str(ROOT))
    assert ok_msg["ok"]
    rd = _safe_run("read_skill", {"name": "test_skill"}, str(ROOT))
    assert rd["ok"] and "do thing" in rd["output"]
    print("  PASS")

    print("self-test 4: tick produces telemetry")
    r = ak.tick("compute 1+1")
    assert r["backend"] in ("stub",) or r["backend"].startswith("qwen2.5-3b")
    assert isinstance(r["tokens_used"], int)
    assert isinstance(r["tool_calls"], int)
    print("  PASS  r=" + str(r))

    print("all self-tests passed.")

print("running self-tests...")
_test()


# === DEMO ========================================================
print()
print("running 5 demo ticks:")
ak = AeonKernel(ROOT)
for i in range(5):
    r = ak.tick("tick " + str(i) + ": solve a basic math problem using math tool")
    print("  t=" + str(i) + " backend=" + r["backend"] +
          " tool=" + str(r["tool_calls"]) +
          " tokens=" + str(r["tokens_used"]) +
          " bs=" + str(r["bs"]) +
          " E=" + str(r["E"]))
print()
print("done. CSV at:", ak.csv)
