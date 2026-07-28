"""End-to-end test for the Prometheus → Alertmanager alert pipeline.

Starts a real Prometheus instance that evaluates an always-firing alert rule
and sends it to a real Alertmanager instance. The test then verifies that the
alert appears in Alertmanager grouped and routed to the correct receiver.

Run with local binaries (default path is the official release extracted to /tmp):

    python -m unittest monitoring.tests.test_prometheus_alertmanager_e2e

Override binary paths via environment variables:

    AEON_ALERTMANAGER_BINARY=/path/to/alertmanager \
    AEON_PROMETHEUS_BINARY=/path/to/prometheus \
        python -m unittest monitoring.tests.test_prometheus_alertmanager_e2e

If Docker is available and a local binary is not, the test falls back to
running the official container images.
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
        DEFAULT_PROMETHEUS_BINARY,
        TEMPLATES_DIR,
        docker_available,
        free_port,
        prepare_alertmanager_config,
    )
except ImportError:  # when running `python -m unittest discover -s tests`
    from test_utils import (
        DEFAULT_ALERTMANAGER_BINARY,
        DEFAULT_PROMETHEUS_BINARY,
        TEMPLATES_DIR,
        docker_available,
        free_port,
        prepare_alertmanager_config,
    )

ALERTMANAGER_IMAGE = "prom/alertmanager:v0.27.0"
PROMETHEUS_IMAGE = "prom/prometheus:v2.53.0"
ALERT_CONTAINER = "aeon-alertmanager-e2e"
PROM_CONTAINER = "aeon-prometheus-e2e"


class PrometheusAlertmanagerE2ETest(unittest.TestCase):
    """Run Prometheus + Alertmanager and verify an alert flows end-to-end."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.am_port = free_port()
        cls.am_url = f"http://127.0.0.1:{cls.am_port}"
        cls.prom_port = free_port()
        cls.prom_url = f"http://127.0.0.1:{cls.prom_port}"

        cls._am_binary, cls._prom_binary = cls._resolve_binaries()
        cls._am_process: subprocess.Popen | None = None
        cls._prom_process: subprocess.Popen | None = None
        cls._am_log = None
        cls._prom_log = None
        cls._docker_used = not cls._am_binary or not cls._prom_binary

        if cls._am_binary and cls._prom_binary:
            cls._start_native()
        elif docker_available():
            cls._start_docker()
        else:
            raise unittest.SkipTest(
                "Need either local Prometheus/Alertmanager binaries or Docker"
            )

        cls._wait_for_am()
        cls._wait_for_prometheus()

    @classmethod
    def _resolve_binaries(cls) -> tuple[Path | None, Path | None]:
        am_env = os.environ.get("AEON_ALERTMANAGER_BINARY")
        prom_env = os.environ.get("AEON_PROMETHEUS_BINARY")

        am_binary = Path(am_env) if am_env else None
        prom_binary = Path(prom_env) if prom_env else None

        if am_binary and not am_binary.exists():
            raise unittest.SkipTest(f"Alertmanager binary not found: {am_binary}")
        if prom_binary and not prom_binary.exists():
            raise unittest.SkipTest(f"Prometheus binary not found: {prom_binary}")

        if am_binary is None and DEFAULT_ALERTMANAGER_BINARY.exists():
            am_binary = DEFAULT_ALERTMANAGER_BINARY
        if prom_binary is None and DEFAULT_PROMETHEUS_BINARY.exists():
            prom_binary = DEFAULT_PROMETHEUS_BINARY

        return am_binary, prom_binary

    @classmethod
    def _start_native(cls) -> None:
        am_config = prepare_alertmanager_config()
        with Path("/tmp/alertmanager_e2e.log").open("w") as am_log:
            cls._am_process = subprocess.Popen(
                [
                    str(cls._am_binary),
                    f"--config.file={am_config}",
                    "--storage.path=/tmp/alertmanager_e2e_data",
                    f"--web.listen-address=127.0.0.1:{cls.am_port}",
                    f"--web.external-url={cls.am_url}",
                ],
                stdout=am_log,
                stderr=subprocess.STDOUT,
            )

        prom_config = cls._write_prometheus_config()
        with Path("/tmp/prometheus_e2e.log").open("w") as prom_log:
            cls._prom_process = subprocess.Popen(
                [
                    str(cls._prom_binary),
                    f"--config.file={prom_config}",
                    "--storage.tsdb.path=/tmp/prometheus_e2e_data",
                    f"--web.listen-address=127.0.0.1:{cls.prom_port}",
                    f"--web.external-url={cls.prom_url}",
                ],
                stdout=prom_log,
                stderr=subprocess.STDOUT,
            )

    @classmethod
    def _start_docker(cls) -> None:
        am_config = prepare_alertmanager_config()
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-d",
                "--name",
                ALERT_CONTAINER,
                "-p",
                f"127.0.0.1:{cls.am_port}:9093",
                "-v",
                f"{am_config}:/etc/alertmanager/alertmanager.yml:ro",
                "-v",
                f"{TEMPLATES_DIR}:/etc/alertmanager/templates:ro",
                "-e",
                "ALERTMANAGER_SLACK_WEBHOOK_URL=",
                ALERTMANAGER_IMAGE,
                "--config.file=/etc/alertmanager/alertmanager.yml",
                "--storage.path=/alertmanager",
                f"--web.external-url={cls.am_url}",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        prom_config = cls._write_prometheus_config()
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-d",
                "--name",
                PROM_CONTAINER,
                "-p",
                f"127.0.0.1:{cls.prom_port}:9090",
                "-v",
                f"{prom_config}:/etc/prometheus/prometheus.yml:ro",
                PROMETHEUS_IMAGE,
                "--config.file=/etc/prometheus/prometheus.yml",
                "--storage.tsdb.path=/prometheus",
                f"--web.external-url={cls.prom_url}",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @classmethod
    def _write_prometheus_config(cls) -> Path:
        rule_path = Path("/tmp/e2e_alert_rule.yml")
        rule_path.write_text(
            "groups:\n"
            "  - name: e2e\n"
            "    rules:\n"
            "      - alert: E2ETestAlert\n"
            "        expr: up{job=\"prometheus\"} == 1\n"
            "        for: 0s\n"
            "        labels:\n"
            "          severity: critical\n"
            "          service: aeon-server\n"
            "        annotations:\n"
            "          summary: Prometheus-to-Alertmanager E2E test alert\n",
            encoding="utf-8",
        )

        config = f"""global:
  evaluation_interval: 1s
  scrape_interval: 1s

alerting:
  alertmanagers:
    - api_version: v2
      static_configs:
        - targets: ['127.0.0.1:{cls.am_port}']

rule_files:
  - '{rule_path}'

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['127.0.0.1:{cls.prom_port}']
"""
        prom_config = Path("/tmp/prometheus_e2e.yml")
        prom_config.write_text(config, encoding="utf-8")
        return prom_config

    @classmethod
    def _wait_for_am(cls, timeout: float = 30.0) -> None:
        cls._wait_for_url(f"{cls.am_url}/api/v2/status", timeout)

    @classmethod
    def _wait_for_prometheus(cls, timeout: float = 30.0) -> None:
        cls._wait_for_url(f"{cls.prom_url}/-/ready", timeout)

    @staticmethod
    def _wait_for_url(url: str, timeout: float) -> None:
        deadline = time.time() + timeout
        last_error: Exception | None = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=2) as resp:
                    if resp.status == 200:
                        return
            except (urllib.error.URLError, ConnectionError) as exc:
                last_error = exc
                time.sleep(0.5)
        raise RuntimeError(f"Service at {url} did not become ready") from last_error

    @classmethod
    def tearDownClass(cls) -> None:
        for proc, log in ((cls._am_process, cls._am_log), (cls._prom_process, cls._prom_log)):
            if proc is not None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            if log is not None:
                log.close()

        if cls._docker_used:
            for container in (ALERT_CONTAINER, PROM_CONTAINER):
                subprocess.run(
                    ["docker", "rm", "-f", container],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

    def test_prometheus_alert_reaches_alertmanager(self) -> None:
        """Wait for the always-firing E2E alert to appear in Alertmanager."""
        raw_alert = None
        deadline = time.time() + 45
        while time.time() < deadline:
            with urllib.request.urlopen(f"{self.am_url}/api/v2/alerts", timeout=5) as resp:
                alerts = json.loads(resp.read().decode("utf-8"))
            raw_alert = next(
                (a for a in alerts if a["labels"].get("alertname") == "E2ETestAlert"),
                None,
            )
            if raw_alert is not None:
                break
            time.sleep(1)
        else:
            self.fail("E2ETestAlert did not reach Alertmanager")

        self.assertEqual(raw_alert["labels"]["severity"], "critical")
        self.assertEqual(raw_alert["labels"]["service"], "aeon-server")

        # The grouped view may take an additional group_wait to appear; poll a
        # little longer before giving up.
        deadline = time.time() + 20
        while time.time() < deadline:
            with urllib.request.urlopen(
                f"{self.am_url}/api/v2/alerts/groups", timeout=5
            ) as resp:
                groups = json.loads(resp.read().decode("utf-8"))
            matches = [g for g in groups if g["labels"].get("alertname") == "E2ETestAlert"]
            if matches:
                break
            time.sleep(1)
        else:
            self.fail("E2ETestAlert was received but not grouped in Alertmanager")

        group = matches[0]
        self.assertEqual(group["labels"].get("severity"), "critical")
        self.assertEqual(group["labels"].get("service"), "aeon-server")
        self.assertEqual(group["receiver"]["name"], "critical")
        self.assertTrue(
            any(
                a["labels"].get("alertname") == "E2ETestAlert"
                for a in group["alerts"]
            )
        )


if __name__ == "__main__":
    unittest.main()
