"""
Pytest configuration for AEON OS.

The Flask server (aeon_server.py) imports several heavy modules
(torch/transformers, etc.) at the top of the file. For fast unit tests we
stub those modules out before anything can import them. Auth/database helpers
(aeon_auth, aeon_db) are lightweight and are left as the real code.
"""

import os
import sys
import types

# ── Dev/test secrets used by the auth endpoints ───────────────────────────────
import pytest
from werkzeug.security import generate_password_hash

os.environ.setdefault("NEXTAUTH_SECRET", "test-secret-do-not-use-in-production")
os.environ.setdefault("AEON_ENV", "test")
os.environ.setdefault("ADMIN_EMAIL", "admin@test.local")
os.environ.setdefault("ADMIN_PASSWORD_HASH", generate_password_hash("adminpass"))


# ── Lightweight stubs for heavy AEON modules ────────────────────────────────
class FakeAgent:
    """Stand-in for aeon.ReflectiveAgent used by the Flask routes."""

    def __init__(self, root=None):
        self.root = root
        self.tick_count = 0
        self.self_model = types.SimpleNamespace(vitals=lambda: {"ok": True})
        self.goals = types.SimpleNamespace(open_goals=lambda: [])

    def act(self, query):
        self.tick_count += 1
        return {"backend": "stub", "answer": f"echo: {query}"}

    def reflect(self):
        return {"reflection": "ok"}

    def evolve(self, **kwargs):
        return {"evolved": True}


class FakeAeonOS:
    def __init__(self, root=None):
        self.root = root

    def list_workflows(self):
        return []

    def save_workflow(self, workflow):
        return workflow

    def get_workflow(self, workflow_id):
        return None

    def delete_workflow(self, workflow_id):
        return False

    def run_workflow(self, workflow_id, initial_input, workspace_id=None):
        return {"ok": True, "workflow_id": workflow_id, "output": initial_input}

    def run_swarm(self, app_ids, prompt):
        return {"ok": True, "app_ids": app_ids, "prompt": prompt}


class FakeWorkflowDefinition:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        return {"id": getattr(self, "id", None), "name": getattr(self, "name", None)}


class FakeWorkflowNode:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class FakeWorkflowEdge:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class FakeIntegrationConfig:
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "fake-id")
        self.name = kwargs.get("name", "fake")
        self.type = kwargs.get("type", "fake")
        self.enabled = kwargs.get("enabled", True)
        for k, v in kwargs.items():
            if not hasattr(self, k):
                setattr(self, k, v)

    def to_dict(self, mask=False):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "enabled": self.enabled,
        }


class FakeWebhookDelivery:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class FakeIntegrationManager:
    def __init__(self, root=None):
        self.root = root

    def list_integrations(self, mask=False):
        return []

    def save(self, data, integration_id=None):
        return FakeIntegrationConfig(**data)

    def get(self, integration_id):
        return None

    def delete(self, integration_id):
        return False

    def run(self, integration_id, endpoint=None, method="GET", payload=None):
        return {"ok": True}

    def proxy(self, integration_id, endpoint=None, method="GET", payload=None):
        return {"ok": True}

    def verify_webhook(self, integration_id, signature, raw):
        return True

    def record_delivery(self, delivery):
        pass


class FakeUsageMeter:
    def __init__(self, root=None):
        self.root = root

    def record_event(self, **kwargs):
        return types.SimpleNamespace(to_dict=lambda: {"ok": True, "recorded": kwargs})

    def get_summary(self, workspace_id=None, days=30):
        return {"ok": True, "events": [], "total": 0}


class FakeBillingCalculator:
    def __init__(self, root=None, meter=None):
        self.root = root
        self.meter = meter
        self.plans = {"free": {}, "team": {}, "enterprise": {}}

    def set_plan(self, workspace_id, plan_id, credits=0):
        pass

    def add_credits(self, workspace_id, amount):
        pass

    def workspace_status(self, workspace_id, days=30):
        return {"ok": True, "workspace_id": workspace_id, "credits": 0}


class FakeHealthCollector:
    def __init__(self, root=None):
        self.root = root

    def snapshot(self, agent_vitals=None, queue_size=0, integrations=None):
        return {"ok": True, "agent_vitals": agent_vitals or [], "queue_size": queue_size}


class FakeGovernanceManager:
    def log_audit(self, **kwargs):
        pass

    def query_audit(self, **kwargs):
        return {"ok": True, "logs": [], "count": 0}

    def run_compliance_check(self, check_type, workspace_id=None):
        return {"ok": True, "check_type": check_type}

    def get_retention_policy(self, workspace_id=None):
        return {"ok": True, "workspace_id": workspace_id, "retention_days": 365}

    def set_retention_policy(self, workspace_id, retention_days, action):
        return {"ok": True}


class FakeApiKeyManager:
    def __init__(self, root=None):
        self.root = root
        self._keys = {}

    def create_key(self, **kwargs):
        key = types.SimpleNamespace(
            id="fake-key-id",
            to_dict=lambda: {"id": "fake-key-id", "name": kwargs.get("name")},
        )
        return key, "fake-plaintext-key"

    def validate_key(self, plaintext):
        return None

    def check_rate_limit(self, key_hash):
        return True

    def list_keys(self, workspace_id=None):
        return []

    def get_key_by_id(self, key_id):
        return None

    def revoke_key(self, key_id):
        return True

    def update_key(self, key_id, **kwargs):
        return None

    def get_usage_stats(self, **kwargs):
        return {"ok": True}


class FakeStripeClient:
    available = False

    def create_checkout_session(self, **kwargs):
        return {"ok": True, "simulated": True}

    def create_portal_session(self, **kwargs):
        return {"ok": True, "simulated": True}

    def handle_webhook(self, raw_body, signature):
        return {"ok": True, "type": "invoice.paid", "handled": True}

    def get_subscription_status(self, workspace_id):
        return {"ok": True, "status": "inactive"}


def _make_module(name, **attrs):
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    return mod


# aeon.py
aeon_mod = _make_module("aeon", ReflectiveAgent=FakeAgent, QW=None)
sys.modules["aeon"] = aeon_mod

# aeon_os.py
aeon_os_mod = _make_module("aeon_os", AeonOS=FakeAeonOS)
sys.modules["aeon_os"] = aeon_os_mod

# aeon_workflows.py
aeon_workflows_mod = _make_module(
    "aeon_workflows",
    WorkflowDefinition=FakeWorkflowDefinition,
    WorkflowNode=FakeWorkflowNode,
    WorkflowEdge=FakeWorkflowEdge,
)
sys.modules["aeon_workflows"] = aeon_workflows_mod

# aeon_integrations.py
aeon_integrations_mod = _make_module(
    "aeon_integrations",
    IntegrationManager=FakeIntegrationManager,
    IntegrationConfig=FakeIntegrationConfig,
    WebhookDelivery=FakeWebhookDelivery,
    get_integration_catalog=lambda: [],
)
sys.modules["aeon_integrations"] = aeon_integrations_mod

# aeon_usage.py
aeon_usage_mod = _make_module(
    "aeon_usage",
    UsageMeter=FakeUsageMeter,
    BillingCalculator=FakeBillingCalculator,
    HealthCollector=FakeHealthCollector,
)
sys.modules["aeon_usage"] = aeon_usage_mod

# aeon_governance.py
aeon_governance_mod = _make_module(
    "aeon_governance",
    GovernanceManager=FakeGovernanceManager,
    get_governance=lambda: FakeGovernanceManager(),
)
sys.modules["aeon_governance"] = aeon_governance_mod

# aeon_llm.py
aeon_llm_mod = _make_module(
    "aeon_llm",
    list_providers=lambda: [],
    set_active_provider=lambda p: {"ok": True, "provider": p},
    get_llm_provider=lambda p=None: None,
    test_provider=lambda p: {"ok": True},
)
sys.modules["aeon_llm"] = aeon_llm_mod

# aeon_api_keys.py
aeon_api_keys_mod = _make_module("aeon_api_keys", ApiKeyManager=FakeApiKeyManager)
sys.modules["aeon_api_keys"] = aeon_api_keys_mod

# aeon_stripe.py
aeon_stripe_mod = _make_module(
    "aeon_stripe",
    get_stripe_client=lambda: FakeStripeClient(),
    init_stripe=lambda root: None,
)
sys.modules["aeon_stripe"] = aeon_stripe_mod


# Make the Python SDK importable from tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk", "python"))


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Flask test client with a fresh temporary AEON_ROOT and SQLite database."""
    root = tmp_path / "aeon_state"
    root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("AEON_ROOT", str(root))
    monkeypatch.setenv("AEON_ENV", "test")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@test.local")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", generate_password_hash("adminpass"))
    monkeypatch.setenv("AEON_DATABASE_URL", f"sqlite:///{root}/aeon.db")

    import aeon_server
    from aeon_db import init_db

    init_db()
    with aeon_server.app.test_client() as test_client:
        yield test_client
