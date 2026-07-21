#!/usr/bin/env bash
# scripts/deploy-vercel.sh
#
# Ships the Next.js chat UI in ./web/ to Vercel's free tier.
#
# Pre-flight (this script will run it for you):
#   1. python3 -m py_compile ../aeon.py        → kernel still compiles
#   2. python3 ../aeon.py (stub mode)           → 7 self-tests PASS
#   3. web/package.json is valid JSON
#   4. (optional, requires npm) cd web && npm install && npx tsc --noEmit
#
# What YOU must do before this script can complete:
#   1. Rotate any leaked GitHub PAT and Supabase service-role key
#      (run: bash scripts/post-rotate.sh  for the printable checklist).
#   2. In Vercel dashboard ▸ Project Settings ▸ Environment Variables,
#      make sure these names exist (values NEVER echoed by this script):
#         HUGGINGFACE_TOKEN            (server-only, no NEXT_PUBLIC_ prefix)
#         NEXT_PUBLIC_SUPABASE_URL     (ok to be browser-visible)
#         NEXT_PUBLIC_SUPABASE_ANON_KEY
#         AEON_HF_SPACE_URL            (server-only; the closed-loop wire)
#         SUPABASE_SERVICE_ROLE_KEY    (server-only, no NEXT_PUBLIC_ prefix)
#         GH_TOKEN                     (server-only; raises github rate limit)
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

echo "==> 1/5  py_compile aeon.py"
python3 -m py_compile aeon.py && echo "    PASS"
echo

echo "==> 2/5  AEON 7 self-tests in stub mode"
python3 - <<'PY'
import tempfile, os, sys, subprocess, re, shutil

# Copy both aeon.py and aeon_llm.py (aeon.py imports from aeon_llm)
src = open("aeon.py").read()
src = src.replace("for s in REQ: _pip(s)", "for s in REQ: print(\"  skip\", s)")
m = re.search(r"\n# === DEMO", src)
if m: src = src[:m.start()]
src += '\nprint("smoke: self-tests only, no demo")\n'

with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, "aeon.py"); open(p, "w").write(src)
    # Copy aeon_llm.py so imports resolve in the temp directory
    llm_src = "aeon_llm.py"
    if os.path.exists(llm_src):
        shutil.copy2(llm_src, os.path.join(td, "aeon_llm.py"))
    env = {**os.environ, "AEON_ROOT": td}
    env.pop("HUGGINGFACE_TOKEN", None)  # force stub-mode
    env.pop("SUPABASE_URL", None)
    env.pop("SUPABASE_ANON_KEY", None)
    env.pop("SUPABASE_SERVICE_ROLE_KEY", None)
    env.pop("GH_TOKEN", None)
    r = subprocess.run([sys.executable, p], cwd=td, timeout=60, env=env)
sys.exit(0 if r.returncode == 0 else 1)
PY
echo "    PASS"
echo

echo "==> 3/5  web/package.json valid JSON"
python3 -c 'import json,sys; p=json.load(open("web/package.json")); print("    deps:", ", ".join(sorted(p["dependencies"].keys())))'
echo

if command -v npx >/dev/null 2>&1; then
    echo "==> 4/5  TypeScript syntax check (web/)"
    (cd web && npx --yes -p typescript@5 -- tsc --noEmit 2>&1 | tail -20 || true)
    echo
else
    echo "==> 4/5  SKIPPED  (npx not in PATH; Vercel build will catch any TS issues)"
    echo
fi

echo "==> 5/5  npx vercel --prod"
if ! command -v npx >/dev/null 2>&1; then
    echo "    ABORT — install Node.js + npm first, then re-run."
    exit 2
fi
if [ ! -d web ]; then
    echo "    ABORT — missing web/ directory; cannot deploy."
    exit 2
fi
cd web
# First-time project creation uses `vercel` (no --prod); subsequent deploys
# use `vercel --prod`.  We try `--prod`; if no linked project, fall back.
if npx --yes vercel --prod --yes 2>&1 | tee /tmp/aeon_vercel.log; then
    echo
    echo "✓  Production deploy complete. Vercel printed the URL above."
else
    echo
    echo "First-time project not linked. Re-running without --prod to create it:"
    npx --yes vercel --yes
    echo
    echo "Now re-run this script to push the actual production deploy:"
    echo "    bash scripts/deploy-vercel.sh"
fi
