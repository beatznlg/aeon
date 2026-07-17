#!/usr/bin/env bash
# scripts/deploy-hf-space.sh
#
# Pushes the AEON kernel + Gradio wrapper to a Hugging Face Space, which is
# the FREE PERMANENT GPU equivalent of running a Colab T4 notebook 24/7.
#
# Pre-flight (this script runs it):
#   - py_compile aeon.py + 7 self-tests
#   - JFIF of aeon_app_gradio.py
#
# What YOU must do before running this:
#   1. Create a free HF account at https://huggingface.co/join
#   2. Create a new Space at https://huggingface.co/new-space
#        - SDK = Gradio
#        - Hardware = ZeroGPU  (free A100 on demand)
#        - Visibility = Public
#      Take note of the Space's URL — it'll look like
#        https://huggingface.co/spaces/<your-username>/<space-slug>
#   3. Create a fine-grained HF access token:
#        https://huggingface.co/settings/tokens
#        Scopes:  read repos in your account  +  write to Spaces you own
#
# Usage:
#   HF_USERNAME=yourname HF_SPACESLUG=aeon-kernel HF_TOKEN=hf_xxx \
#     bash scripts/deploy-hf-space.sh

set -euo pipefail

: "${HF_USERNAME:?Set HF_USERNAME (your HF handle, lowercase)}"
: "${HF_SPACESLUG:?Set HF_SPACESLUG (Space slug, e.g. aeon-kernel)}"
: "${HF_TOKEN:?Set HF_TOKEN (fine-grained; needs write to your Spaces)}"

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

echo "==> 1/4  Pre-flight: py_compile + 7 self-tests"
python3 -m py_compile aeon.py && echo "    PASS_compile"
python3 - <<'PY'
import tempfile, os, sys, subprocess, re
src = open("aeon.py").read()
src = src.replace("for s in REQ: _pip(s)", "for s in REQ: print(\"  skip\", s)")
m = re.search(r"\n# === DEMO", src)
if m: src = src[:m.start()]
src += '\nprint("smoke: self-tests only, no demo")\n'
with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, "aeon.py"); open(p, "w").write(src)
    env = {**os.environ, "AEON_ROOT": td}
    r = subprocess.run([sys.executable, p], cwd=td, timeout=60, env=env)
sys.exit(0 if r.returncode == 0 else 1)
PY
echo "    PASS_tests"
echo

echo "==> 2/4  Verify aeon_app_gradio.py exists"
[ -f aeon_app_gradio.py ] || { echo "    ABORT — aeon_app_gradio.py missing"; exit 2; }
python3 -m py_compile aeon_app_gradio.py && echo "    PASS"
echo

echo "==> 3/4  Probe Space endpoint"
SPACE_URL="https://huggingface.co/api/spaces/${HF_USERNAME}/${HF_SPACESLUG}"
echo "    GET $SPACE_URL"
PROBE=$(curl -sS -o /tmp/aeon_space.json -w "%{http_code}" \
    -H "Authorization: Bearer ${HF_TOKEN}" "$SPACE_URL")
echo "    http_code = $PROBE"
if [ "$PROBE" != "200" ]; then
    echo "    ABORT — Space not visible at expected URL.  Confirm the slug:"
    echo "           https://huggingface.co/spaces/${HF_USERNAME}/${HF_SPACESLUG}"
    exit 2
fi
echo

echo "==> 4/4  Upload aeon.py, aeon_app_gradio.py, requirements.txt via HF Hub API"
SPACE_REPO="https://huggingface.co/spaces/${HF_USERNAME}/${HF_SPACESLUG}"
do_upload() {
    local file="$1" rev="$2"
    echo "    -> ${file}"
    curl -sS -X POST \
        -H "Authorization: Bearer ${HF_TOKEN}" \
        -H "Content-Type: application/json" \
        --data "$(python3 -c "import json,sys; print(json.dumps({'repo_id':'${HF_USERNAME}/${HF_SPACESLUG}','repo_type':'space','revision':'${rev}','files':[open(sys.argv[1],'rb').read().decode('latin-1')],'summary':'AEON kernel from aeon/'+sys.argv[1].split('/')[-1]}))" "$file")" \
        "https://huggingface.co/api/spaces/${HF_USERNAME}/${HF_SPACESLUG}/commit/${rev}" \
        >/dev/null \
      || echo "       (Hub multipart used as fallback — see next step)"
}
# HF Hub expects multipart, not JSON for commit. Use the hub CLI if available.
if python3 -c "import huggingface_hub" >/dev/null 2>&1; then
    echo "    using huggingface_hub.upload_folder (preferred path)"
    HF_TOKEN="${HF_TOKEN}" python3 - <<PY
import os
from huggingface_hub import HfApi, upload_folder
api = HfApi(token=os.environ["HF_TOKEN"])
api.repo_info("${HF_USERNAME}/${HF_SPACESLUG}", repo_type="space")  # raises if missing
# upload_folder repackages with proper LFS handling
files_to_send = ["aeon.py", "aeon_app_gradio.py", "requirements.txt"]
import tempfile, pathlib
with tempfile.TemporaryDirectory() as td:
    for f in files_to_send:
        pathlib.Path(td, f).write_bytes(pathlib.Path("$ROOT", f).read_bytes())
    upload_folder(
        folder_path=td,
        repo_id="${HF_USERNAME}/${HF_SPACESLUG}",
        repo_type="space",
        commit_message="AEON kernel: aeon.py + gradio wrapper",
    )
print("    upload complete")
PY
else
    echo "    (huggingface_hub not installed in this env; install it: pip install huggingface_hub)"
    echo "    Then re-run this script.  Or use the manual upload via git:"
    echo "       git clone https://huggingface.co/spaces/${HF_USERNAME}/${HF_SPACESLUG}"
    echo "       cp $ROOT/aeon.py $ROOT/aeon_app_gradio.py $ROOT/requirements.txt ."
    echo "       git add . && git commit -m 'AEON kernel' && git push"
fi

echo
echo "Done.  Visit https://huggingface.co/spaces/${HF_USERNAME}/${HF_SPACESLUG}"
echo "to monitor the build.  Once it shows Running, set AEON_HF_SPACE_URL"
echo "(without trailing /chat) in your Vercel env vars to wire it up."
