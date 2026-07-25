"""
AEON OS Phase 2 — API Gateway & External Integrations
======================================================
Lightweight connector registry, adapter framework, and webhook receiver.

Usage:
    from aeon_integrations import IntegrationManager
    mgr = IntegrationManager(root)
    mgr.save_config({"name": "GitHub", "type": "github", "secrets": {"token": "..."}, ...})
    result = mgr.run(integration_id, endpoint="user/repos", method="GET")
"""

import contextlib
import hashlib
import hmac
import json
import os
import secrets as _secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

# === models ==============================================================

@dataclass
class IntegrationConfig:
    id: str
    name: str
    type: str
    base_url: str = ""
    enabled: bool = True
    secrets: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)
    webhook_secret: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self, mask: bool = False) -> dict[str, Any]:
        data = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "base_url": self.base_url,
            "enabled": self.enabled,
            "secrets": _mask_secrets(self.secrets) if mask else self.secrets,
            "options": self.options,
            "webhook_secret": "********" if self.webhook_secret and mask else self.webhook_secret,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntegrationConfig":
        return cls(
            id=data["id"],
            name=data["name"],
            type=data["type"],
            base_url=data.get("base_url", ""),
            enabled=data.get("enabled", True),
            secrets=data.get("secrets", {}),
            options=data.get("options", {}),
            webhook_secret=data.get("webhook_secret"),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
        )


@dataclass
class WebhookDelivery:
    id: str
    integration_id: str
    timestamp: float
    payload: dict[str, Any]
    response_status: int = 0
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "integration_id": self.integration_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "response_status": self.response_status,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WebhookDelivery":
        return cls(
            id=data["id"],
            integration_id=data["integration_id"],
            timestamp=data["timestamp"],
            payload=data.get("payload", {}),
            response_status=data.get("response_status", 0),
            error_message=data.get("error_message"),
        )


# === helpers =============================================================

def _mask_secrets(secrets: dict[str, Any]) -> dict[str, Any]:
    masked = {}
    for k, v in secrets.items():
        if isinstance(v, dict):
            masked[k] = _mask_secrets(v)
        elif isinstance(v, str):
            masked[k] = "********" if v else ""
        else:
            masked[k] = "********"
    return masked


def _generate_id() -> str:
    return _secrets.token_urlsafe(8)


# === adapters ============================================================

class BaseAdapter(ABC):
    def __init__(self, config: IntegrationConfig):
        self.config = config

    @abstractmethod
    def run(self, endpoint: str = "", method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        pass


class RestAdapter(BaseAdapter):
    def run(self, endpoint: str = "", method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = (self.config.base_url or "").rstrip("/")
        if endpoint:
            url = f"{url}/{endpoint.lstrip('/')}"
        headers = self.config.options.get("headers", {})
        timeout = self.config.options.get("timeout", 30)
        try:
            resp = requests.request(method.upper(), url, headers=headers, json=payload, timeout=timeout)
            return {
                "ok": True,
                "status": resp.status_code,
                "data": _safe_json(resp),
                "url": url,
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "url": url}


class SupabaseAdapter(BaseAdapter):
    def run(self, endpoint: str = "", method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        base = self.config.base_url or os.environ.get("SUPABASE_URL", "")
        anon = self.config.secrets.get("anon_key") or os.environ.get("SUPABASE_ANON_KEY", "")
        svc = self.config.secrets.get("service_role_key") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        url = f"{base.rstrip('/')}/{endpoint.lstrip('/')}"
        headers = {
            "apikey": anon or svc,
            "Authorization": f"Bearer {svc or anon}",
            "Content-Type": "application/json",
        }
        try:
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers, timeout=30)
            else:
                resp = requests.request(method.upper(), url, headers=headers, json=payload, timeout=30)
            return {"ok": resp.status_code < 400, "status": resp.status_code, "data": _safe_json(resp), "url": url}
        except Exception as e:
            return {"ok": False, "error": str(e), "url": url}


class GitHubAdapter(BaseAdapter):
    def run(self, endpoint: str = "", method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        token = self.config.secrets.get("token") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
        url = endpoint or "https://api.github.com/user"
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AEON-OS/1.0",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            resp = requests.request(method.upper(), url, headers=headers, json=payload, timeout=30)
            return {"ok": resp.status_code < 400, "status": resp.status_code, "data": _safe_json(resp), "url": url}
        except Exception as e:
            return {"ok": False, "error": str(e), "url": url}


class HuggingFaceAdapter(BaseAdapter):
    def run(self, endpoint: str = "", method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        token = self.config.secrets.get("token") or os.environ.get("HUGGINGFACE_TOKEN", "")
        model = self.config.options.get("model", "meta-llama/Llama-3.1-8B-Instruct")
        url = endpoint or f"https://api-inference.huggingface.co/models/{model}/v1/chat/completions"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            if method.upper() == "GET":
                resp = requests.get(url, headers=headers, timeout=30)
            else:
                resp = requests.request(method.upper(), url, headers=headers, json=payload, timeout=60)
            return {"ok": resp.status_code < 400, "status": resp.status_code, "data": _safe_json(resp), "url": url}
        except Exception as e:
            return {"ok": False, "error": str(e), "url": url}


class SlackAdapter(BaseAdapter):
    def run(self, endpoint: str = "", method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        token = self.config.secrets.get("token") or os.environ.get("SLACK_BOT_TOKEN", "")
        channel = self.config.options.get("channel", "#general")
        if not token and not endpoint:
            return {"ok": False, "error": "missing SLACK_BOT_TOKEN"}

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # If no explicit endpoint, default to sending a message
        if not endpoint:
            url = "https://slack.com/api/chat.postMessage"
            body = {
                "channel": channel,
                "text": (payload or {}).get("text", "AEON OS notification"),
            }
            if (payload or {}).get("blocks"):
                body["blocks"] = payload["blocks"]
        else:
            base = self.config.base_url or "https://slack.com/api"
            url = f"{base.rstrip('/')}/{endpoint.lstrip('/')}"
            body = payload

        try:
            resp = requests.post(url, headers=headers, json=body, timeout=30)
            data = _safe_json(resp)
            # Slack API returns {"ok": true/false} even on 200
            slack_ok = data.get("ok", resp.status_code < 400) if isinstance(data, dict) else resp.status_code < 400
            return {
                "ok": slack_ok,
                "status": resp.status_code,
                "data": data,
                "url": url,
                "error": data.get("error", "") if isinstance(data, dict) else "",
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "url": url}


def _safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return resp.text[:1000]


# === integration catalog =================================================

INTEGRATION_CATALOG = [
    {
        "id": "rest",
        "name": "Generic REST API",
        "icon": "🌐",
        "description": "Connect to any REST API with bearer token or custom headers. Supports GET, POST, PUT, DELETE.",
        "required_secrets": ["base_url", "token"],
        "optional_secrets": ["headers"],
        "adapter_type": "rest",
    },
    {
        "id": "github",
        "name": "GitHub",
        "icon": "🐙",
        "description": "Access GitHub API: list repos, issues, PRs, search code. Uses GH_TOKEN or fine-grained PAT.",
        "required_secrets": ["token"],
        "optional_secrets": [],
        "adapter_type": "github",
    },
    {
        "id": "slack",
        "name": "Slack",
        "icon": "💬",
        "description": "Send messages to channels, list conversations, and integrate with Slack workspaces. Uses SLACK_BOT_TOKEN.",
        "required_secrets": ["token"],
        "optional_secrets": [],
        "adapter_type": "slack",
    },
    {
        "id": "supabase",
        "name": "Supabase",
        "icon": "⚡",
        "description": "Query Supabase tables, manage Row Level Security, and interact with your Postgres database.",
        "required_secrets": ["anon_key"],
        "optional_secrets": ["service_role_key"],
        "adapter_type": "supabase",
    },
    {
        "id": "huggingface",
        "name": "Hugging Face Inference",
        "icon": "🤗",
        "description": "Call any model on the Hugging Face Inference API. Configure model ID and parameters.",
        "required_secrets": ["token"],
        "optional_secrets": [],
        "adapter_type": "huggingface",
    },
]


def get_integration_catalog() -> list[dict[str, Any]]:
    """Return the catalog of available integration types with metadata."""
    return list(INTEGRATION_CATALOG)


# === adapter factory =====================================================

ADAPTER_MAP = {
    "rest": RestAdapter,
    "http": RestAdapter,
    "supabase": SupabaseAdapter,
    "github": GitHubAdapter,
    "huggingface": HuggingFaceAdapter,
    "slack": SlackAdapter,
}


def get_adapter(config: IntegrationConfig) -> BaseAdapter:
    adapter_cls = ADAPTER_MAP.get(config.type, RestAdapter)
    return adapter_cls(config)


# === manager =============================================================

class IntegrationManager:
    """CRUD for integrations, adapter execution, and webhook delivery log."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.config_dir = self.root / "integrations"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.configs_path = self.config_dir / "configs.json"
        self.deliveries_path = self.config_dir / "deliveries.json"
        self._configs: dict[str, IntegrationConfig] = {}
        self._deliveries: list[WebhookDelivery] = []
        self._load()

    def _load(self) -> None:
        if self.configs_path.exists():
            try:
                data = json.loads(self.configs_path.read_text())
                for item in data:
                    try:
                        cfg = IntegrationConfig.from_dict(item)
                        self._configs[cfg.id] = cfg
                    except Exception:  #nosec B110
                        pass
            except Exception:  #nosec B110
                pass
        if self.deliveries_path.exists():
            try:
                data = json.loads(self.deliveries_path.read_text())
                for item in data:
                    with contextlib.suppress(Exception):
                        self._deliveries.append(WebhookDelivery.from_dict(item))
            except Exception:  #nosec B110
                pass

    def _save_configs(self) -> None:
        self.configs_path.write_text(json.dumps([c.to_dict() for c in self._configs.values()], indent=2))

    def _save_deliveries(self) -> None:
        self.deliveries_path.write_text(json.dumps([d.to_dict() for d in self._deliveries[-100:]], indent=2))

    def list_integrations(self, mask: bool = True) -> list[dict[str, Any]]:
        return [c.to_dict(mask=mask) for c in self._configs.values()]

    def get(self, integration_id: str) -> IntegrationConfig | None:
        return self._configs.get(integration_id)

    def save(self, data: dict[str, Any], integration_id: str | None = None) -> IntegrationConfig:
        if integration_id and integration_id in self._configs:
            cfg = self._configs[integration_id]
            cfg.name = data.get("name", cfg.name)
            cfg.type = data.get("type", cfg.type)
            cfg.base_url = data.get("base_url", cfg.base_url)
            cfg.enabled = data.get("enabled", cfg.enabled)
            cfg.options = data.get("options", cfg.options)
            cfg.webhook_secret = data.get("webhook_secret", cfg.webhook_secret)
            # Merge secrets: do not overwrite with masked placeholder
            new_secrets = data.get("secrets", {})
            for k, v in new_secrets.items():
                if v == "********" and k in cfg.secrets:
                    continue
                cfg.secrets[k] = v
            cfg.updated_at = time.time()
        else:
            cfg = IntegrationConfig(
                id=integration_id or _generate_id(),
                name=data.get("name", "Untitled"),
                type=data.get("type", "rest"),
                base_url=data.get("base_url", ""),
                enabled=data.get("enabled", True),
                secrets=data.get("secrets", {}),
                options=data.get("options", {}),
                webhook_secret=data.get("webhook_secret"),
            )
            self._configs[cfg.id] = cfg
        self._save_configs()
        return cfg

    def delete(self, integration_id: str) -> bool:
        if integration_id in self._configs:
            del self._configs[integration_id]
            self._save_configs()
            return True
        return False

    def run(self, integration_id: str, endpoint: str = "", method: str = "GET", payload: dict[str, Any] | None = None) -> dict[str, Any]:
        cfg = self._configs.get(integration_id)
        if not cfg:
            return {"ok": False, "error": "integration not found"}
        if not cfg.enabled:
            return {"ok": False, "error": "integration disabled"}
        adapter = get_adapter(cfg)
        return adapter.run(endpoint=endpoint, method=method, payload=payload)

    def proxy(self, integration_id: str, endpoint: str, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.run(integration_id, endpoint=endpoint, method=method, payload=payload)

    def verify_webhook(self, integration_id: str, signature_header: str | None, payload: bytes, algo: str = "sha256") -> bool:
        cfg = self._configs.get(integration_id)
        if not cfg or not cfg.webhook_secret:
            return True  # no secret configured, accept all
        secret = cfg.webhook_secret.encode()
        if algo == "sha256":
            expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
            # Support "sha256=<hex>" or raw hex
            if signature_header and signature_header.startswith("sha256="):
                signature_header = signature_header.split("=", 1)[1]
            return hmac.compare_digest(expected, signature_header or "")
        return False

    def record_delivery(self, delivery: WebhookDelivery) -> None:
        self._deliveries.append(delivery)
        self._save_deliveries()

    def list_deliveries(self, limit: int = 100) -> list[dict[str, Any]]:
        return [d.to_dict() for d in self._deliveries[-limit:][::-1]]
