#!/usr/bin/env python3
"""
AEON Production Health Check
=============================
Lightweight CLI to verify a deployed AEON stack is alive and ready.

Usage:
    python scripts/healthcheck.py https://backend-url/health
    python scripts/healthcheck.py https://backend-url/health https://frontend-url/api/health
"""
import sys
import urllib.request
import urllib.error
import json
from urllib.parse import urlparse


def fetch_json(url: str) -> tuple:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = {"raw": body}
            return resp.status, data
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", errors="ignore")}
    except Exception as e:
        return 0, {"error": str(e)}


def check(name: str, url: str) -> bool:
    if not url:
        return True
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        print(f"[{name}] SKIP — invalid URL: {url}")
        return True
    status, data = fetch_json(url)
    ok = status == 200 and (isinstance(data, dict) and data.get("ok") is True)
    if ok:
        print(f"[{name}] OK ({status}) -> {data}")
    else:
        print(f"[{name}] FAIL ({status}) -> {data}")
    return ok


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("No URLs provided — pass at least one endpoint to check.")
        sys.exit(0)

    urls = sys.argv[1:]
    backend = urls[0]
    frontend = urls[1] if len(urls) > 1 else None

    results = []
    results.append(check("backend", backend))
    if frontend:
        results.append(check("frontend", frontend))

    if all(results):
        print("\n✅ All health checks passed")
        sys.exit(0)
    else:
        print("\n❌ One or more health checks failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
