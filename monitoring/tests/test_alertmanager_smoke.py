"""Smoke test for Alertmanager routing.

Starts a throw-away Alertmanager instance using the production configuration,
sends a test alert to ``/api/v2/alerts``, and verifies that the alert is
received and routed to the correct receiver.

Run with Docker (default):

    python -m unittest monitoring.tests.test_alertmanager_smoke

Run with a local Alertmanager binary instead of Docker:

    AEON_ALERTMANAGER_BINARY=/path/to/alertmanager \
        python -m unittest monitoring.tests.test_alertmanager_smoke

When neither Docker nor a local binary is available the test is skipped.
No real email or Slack messages are sent because the test substitutes a
dummy Slack URL in the temporary configuration.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

try:
    from monitoring.tests.test_utils import (
        DEFAULT_ALERTMANAGER_BINARY,
        TEMPLATES_DIR,
        docker_available,
        free_port,
        prepare_alertmanager_config,
    )
except ImportError:  # when running `python -m unittest discover -s tests`
    from test_utils import (
        DEFAULT_ALERTMANAGER_BINARY,
        TEMPLATES_DIR,
        docker_available,
        free_port,
        prepare_alertmanager_config,
    )

IMAGE = "prom/alertmanager:v0.27.0"
CONTAINER_NAME = "aeon-alertmanager-smoke"


class AlertmanagerSmokeTest(unittest.TestCase):
    """Start Alertmanager, send a synthetic alert, and inspect the API."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.port = free_port()
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls._binary: Path | None = None
        cls._process: subprocess.Popen | None = None
        cls._log_file = None
        cls._docker_used = False

        env_binary = os.environ.get("AEON_ALERTMANAGER_BINARY")
        if env_binary:
            cls._binary = Path(env_binary)
            if not cls._binary.exists():
                raise unittest.SkipTest(f"Alertmanager binary not found: {cls._binary}")
        elif DEFAULT_ALERTMANAGER_BINARY.exists():
            cls._binary = DEFAULT_ALERTMANAGER_BINARY

        if cls._binary:
            config = prepare_alertmanager_config()
            log_path = Path("/tmp/alertmanager_smoke.log")
            with log_path.open("w") as log_file:
                cls._process = subprocess.Popen(
                    [
                        str(cls._binary),
                        f"--config.file={config}",
                        "--storage.path=/tmp/alertmanager_smoke_data",
                        f"--web.listen-address=127.0.0.1:{cls.port}",
                        f"--web.external-url=http://127.0.0.1:{cls.port}",
                    ],
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                )
        elif docker_available():
            cls._docker_used = True
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-d",
                    "--name",
                    CONTAINER_NAME,
                    "-p",
                    f"127.0.0.1:{cls.port}:9093",
                    "-v",
                    f"{prepare_alertmanager_config()}:/etc/alertmanager/alertmanager.yml:ro",
                    "-v",
                    f"{TEMPLATES_DIR}:/etc/alertmanager/templates:ro",
                    "-e",
                    "ALERTMANAGER_SLACK_WEBHOOK_URL=",
                    IMAGE,
                    "--config.file=/etc/alertmanager/alertmanager.yml",
                    "--storage.path=/alertmanager",
                    f"--web.external-url=http://127.0.0.1:{cls.port}",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        else:
            raise unittest.SkipTest(
                "Docker not available and no local Alertmanager binary found"
            )

        cls._wait_for_alertmanager()

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._process is not None:
            cls._process.terminate()
            try:
                cls._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls._process.kill()
        if cls._docker_used:
            subprocess.run(
                ["docker", "rm", "-f", CONTAINER_NAME],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        if cls._log_file is not None:
            cls._log_file.close()

    @classmethod
    def _wait_for_alertmanager(cls, timeout: float = 30.0) -> None:
        deadline = time.time() + timeout
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    f"{cls.base_url}/api/v2/status", timeout=2
                ) as resp:
                    if resp.status == 200:
                        return
            except (urllib.error.URLError, ConnectionError) as exc:
                last_error = exc
                time.sleep(0.5)
        raise RuntimeError(
            f"Alertmanager did not become ready within {timeout}s"
        ) from last_error

    def _get_json(self, path: str) -> dict:
        req = urllib.request.Request(f"{self.base_url}{path}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _post_json(self, path: str, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertIn(resp.status, (200, 201))

    def test_alertmanager_exposes_required_receivers(self) -> None:
        receivers = self._get_json("/api/v2/receivers")
        names = {r["name"] for r in receivers}
        self.assertTrue({"default", "critical", "warning"}.issubset(names))

    def test_send_alert_and_verify_routing(self) -> None:
        """Send a critical alert and verify it is routed to the critical receiver."""
        alert = {
            "labels": {
                "alertname": "AeonSmokeTest",
                "severity": "critical",
                "service": "aeon-server",
            },
            "annotations": {
                "summary": "Smoke test alert",
                "description": "This alert was generated by the Alertmanager smoke test.",
                "runbook_url": "https://example.com/runbooks/aeon-smoke-test",
            },
        }
        self._post_json("/api/v2/alerts", [alert])

        # Poll for the alert to be ingested and grouped (usually < 1s).
        deadline = time.time() + 10
        while time.time() < deadline:
            groups = self._get_json("/api/v2/alerts/groups")
            matches = [
                g
                for g in groups
                if g["labels"].get("alertname") == "AeonSmokeTest"
                and g["labels"].get("severity") == "critical"
                and g["labels"].get("service") == "aeon-server"
            ]
            if matches:
                break
            time.sleep(0.5)
        else:
            self.fail("Test alert did not appear in /api/v2/alerts/groups")

        group = matches[0]
        self.assertEqual(group["receiver"]["name"], "critical")
        self.assertTrue(
            any(
                a["labels"].get("alertname") == "AeonSmokeTest"
                for a in group["alerts"]
            )
        )
        self.assertTrue(
            any(
                a["status"]["state"] == "active"
                for a in group["alerts"]
            )
        )


if __name__ == "__main__":
    unittest.main()
