"""
AEON Python SDK Quickstart
============================

Run with:
    cd sdk/python && pip install -e .
    python ../../examples/python/quickstart.py
"""

import os
from aeon_sdk import AeonClient

BASE_URL = os.environ.get("AEON_PYTHON_URL", "http://localhost:5000")
EMAIL = os.environ.get("AEON_EMAIL", "admin@aeon.local")
PASSWORD = os.environ.get("AEON_PASSWORD", "admin123")


def main() -> None:
    client = AeonClient(base_url=BASE_URL)

    # Health check
    print("Health:", client.health())

    # Log in (or use an API key)
    login = client.login(EMAIL, PASSWORD)
    print("Logged in as:", login["user"]["email"])

    # Chat
    reply = client.chat("What is the integral of x^2?")
    print("Chat reply:", reply)

    # List workspaces
    print("Workspaces:", client.list_workspaces())

    # List LLM providers
    print("LLM providers:", client.list_llm_providers())

    # Create a workflow
    wf = client.create_workflow(
        name="Example Workflow",
        nodes=[{"id": "start", "type": "agent", "prompt": "Hello!"}],
        edges=[],
    )
    print("Created workflow:", wf)


if __name__ == "__main__":
    main()
