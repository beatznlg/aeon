"""Unit tests for the Alertmanager configuration.

These tests verify that ``monitoring/alertmanager/alertmanager.yml`` is
structurally sound and that the required receivers, routes, and templates are
present. They do not require Docker or a running Alertmanager instance.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "alertmanager" / "alertmanager.yml"
TEMPLATES_DIR = BASE_DIR / "alertmanager" / "templates"

# Regex for ${VAR:-default} / ${VAR} style env-var references used by
# Alertmanager config expansion.
ENV_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)(?::-([^}]*))?\}")


def expand_env_placeholders(text: str, defaults: dict[str, str] | None = None) -> str:
    """Replace ``${VAR:-default}`` placeholders with their default values.

    Alertmanager expands environment variables at startup. For unit testing we
    are only interested in the YAML structure, so we substitute the defaults (or
    empty string if no default is given).
    """
    defaults = defaults or {}

    def repl(match: re.Match[str]) -> str:
        var = match.group(1)
        default = match.group(2)
        if default is not None:
            return defaults.get(var, default)
        return defaults.get(var, "")

    return ENV_VAR_RE.sub(repl, text)


class AlertmanagerConfigTests(unittest.TestCase):
    """Validate the static Alertmanager configuration."""

    def test_config_file_exists(self) -> None:
        self.assertTrue(CONFIG_PATH.is_file(), f"Missing config file: {CONFIG_PATH}")

    def test_config_parses_as_yaml(self) -> None:
        text = CONFIG_PATH.read_text(encoding="utf-8")
        expanded = expand_env_placeholders(text)
        config = yaml.safe_load(expanded)
        self.assertIsInstance(config, dict)
        for key in ("global", "templates", "route", "receivers", "inhibit_rules"):
            self.assertIn(key, config)

    def test_top_level_route_is_sensible(self) -> None:
        config = yaml.safe_load(expand_env_placeholders(CONFIG_PATH.read_text()))
        route = config["route"]
        self.assertEqual(route["receiver"], "default")
        self.assertEqual(route["group_by"], ["alertname", "severity", "service"])
        self.assertIn("routes", route)
        severities = set()
        for r in route["routes"]:
            for matcher in r.get("matchers", []):
                if matcher.startswith("severity"):
                    # matcher looks like severity="critical"
                    parts = matcher.split("=", 1)
                    if len(parts) == 2:
                        severities.add(parts[1].strip('"'))
        self.assertTrue({"critical", "warning"}.issubset(severities))

    def test_required_receivers_exist(self) -> None:
        config = yaml.safe_load(expand_env_placeholders(CONFIG_PATH.read_text()))
        names = {r["name"] for r in config["receivers"]}
        self.assertTrue({"default", "critical", "warning"}.issubset(names))

    def test_receivers_use_aeon_templates(self) -> None:
        config = yaml.safe_load(expand_env_placeholders(CONFIG_PATH.read_text()))
        for receiver in config["receivers"]:
            for email_config in receiver.get("email_configs", []):
                html = email_config.get("html", "")
                text = email_config.get("text", "")
                self.assertIn("aeon.email", html)
                self.assertIn("aeon.email.text", text)
            for slack_config in receiver.get("slack_configs", []):
                self.assertIn("aeon.slack", slack_config.get("title", ""))
                self.assertIn("aeon.slack", slack_config.get("text", ""))

    def test_template_file_exists_and_contains_aeon_templates(self) -> None:
        self.assertTrue(TEMPLATES_DIR.is_dir())
        files = list(TEMPLATES_DIR.glob("*.tmpl"))
        self.assertTrue(files, "No template files found")
        combined = "\n".join(f.read_text(encoding="utf-8") for f in files)
        for name in ("aeon.email", "aeon.email.text", "aeon.slack.title", "aeon.slack.text"):
            self.assertIn(f'{{{{ define "{name}" }}}}', combined)

    def test_inhibit_rule_suppresses_warning_by_critical(self) -> None:
        config = yaml.safe_load(expand_env_placeholders(CONFIG_PATH.read_text()))
        inhibit_rules = config["inhibit_rules"]
        self.assertTrue(inhibit_rules)
        rule = inhibit_rules[0]
        self.assertIn('severity="critical"', rule["source_matchers"])
        self.assertIn('severity="warning"', rule["target_matchers"])


if __name__ == "__main__":
    unittest.main()
