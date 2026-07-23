"""Shared helpers for the AEON monitoring smoke and end-to-end tests.

These utilities are intentionally kept in a private-ish module so that multiple
test files can avoid duplicating code. They are not part of the public API.
"""

from __future__ import annotations

import re
import socket
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "alertmanager" / "alertmanager.yml"
TEMPLATES_DIR = BASE_DIR / "alertmanager" / "templates"

# Pre-downloaded binary paths used when running outside of Docker (e.g. CI
# environments where the official release tarballs have been extracted to /tmp).
DEFAULT_ALERTMANAGER_BINARY = Path("/tmp/alertmanager-0.27.0.linux-amd64/alertmanager")
DEFAULT_PROMETHEUS_BINARY = Path("/tmp/prometheus-2.53.0.linux-amd64/prometheus")


def free_port() -> int:
    """Return an ephemeral port that is free on 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def docker_available() -> bool:
    try:
        subprocess.run(
            ["docker", "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def prepare_alertmanager_config() -> Path:
    """Return a fully-resolved temp config that Alertmanager can load directly.

    The committed ``alertmanager.yml`` uses ``${VAR:-default}`` placeholders for
    secrets and points templates at ``/etc/alertmanager/templates``. For tests we
    do not want to require real secrets, so this helper expands the
    placeholders to their defaults, fixes the template path, and injects a
    non-functional Slack URL so the config validates.
    """
    text = CONFIG_PATH.read_text(encoding="utf-8")
    text = re.sub(
        r"\$\{([A-Z_][A-Z0-9_]*)(?::-([^}]*))?\}",
        lambda m: m.group(2) or "",
        text,
    )
    text = text.replace("/etc/alertmanager/templates", str(TEMPLATES_DIR.resolve()))
    text = re.sub(
        r"^([ \t]*slack_api_url:[ \t]*).*$",
        r"\1'https://hooks.slack.com/services/FAKE'",
        text,
        flags=re.MULTILINE,
    )
    dest = Path("/tmp/alertmanager_smoke.yml")
    dest.write_text(text, encoding="utf-8")
    return dest
