"""
AEON backend as a Vercel Python function (WSGI entry point).

Vercel's Python runtime detects the top-level ``app`` WSGI object below and
forwards every HTTP request to it. The rewrite rule in ``vercel.backend.json``
makes this the single entry point for all backend paths.

Limitations on Vercel:
* Filesystem is ephemeral; only ``/tmp`` is writable.
* In-memory state (agents, rate limiter, job queue) resets on every cold start.
* Long-running background threads from aeon_server's JobQueue will be created
  per-invocation but are killed when the function returns.
* Heavy ML dependencies (torch, transformers, sentence-transformers) may exceed
  Vercel's serverless function size limits and cause very slow cold starts.
"""

import os
import sys

# Vercel functions only have a writable /tmp directory.
os.environ.setdefault("AEON_ROOT", "/tmp/aeon_state")
os.environ.setdefault("AEON_PYTHON_HOST", "0.0.0.0")
os.environ.setdefault("AEON_PYTHON_PORT", "5000")

# Ensure the repo root (where aeon_server.py lives) is on the import path.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Import the Flask application.  Vercel's WSGI adapter will use this ``app``.

# ``app`` is intentionally exposed at module scope for the Vercel runtime.
