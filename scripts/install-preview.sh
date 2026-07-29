#!/usr/bin/env bash
# Install dependencies for the AEON preview environment.
set -e

# Make user-installed Python packages visible when the preview runs under a
# different user or a stripped environment.
export PYTHONPATH="/home/daytona/.local/lib/python3.10/site-packages:${PYTHONPATH}"

# Skip pip install if the heavy Python packages are already importable.
python3 -c "import flask, requests, torch, transformers, sentence_transformers" 2>/dev/null || pip install -q -r requirements.txt

cd web
npm install
