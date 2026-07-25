"""Tests for sdk/python/aeon_sdk.py using mocked requests.Session."""

import json
from unittest import mock

import pytest
from aeon_sdk import AeonClient, AeonError


class _FakeResponse:
    """Minimal fake requests.Response."""

    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    @property
    def ok(self):
        return self.status_code < 400

    @property
    def text(self):
        return json.dumps(self._payload)

    @property
    def reason(self):
        return "error"


def _patch_session():
    """Return a context manager that patches requests.Session used by aeon_sdk."""
    return mock.patch("aeon_sdk.requests.Session")


def test_health_performs_get_request():
    with _patch_session() as mock_session_class:
        mock_session_class.return_value.request.return_value = _FakeResponse(200, {"ok": True})
        client = AeonClient(base_url="https://aeon.test", api_key="test-key")
        result = client.health()
        assert result == {"ok": True}
        request_call = mock_session_class.return_value.request.call_args
        assert request_call.args[0] == "GET"
        assert request_call.args[1] == "https://aeon.test/health"
        assert request_call.kwargs["headers"]["X-API-Key"] == "test-key"


def test_chat_posts_json_payload():
    with _patch_session() as mock_session_class:
        mock_session_class.return_value.request.return_value = _FakeResponse(
            200, {"ok": True, "data": {"answer": "hi"}}
        )
        client = AeonClient(base_url="https://aeon.test")
        result = client.chat("hello")
        assert result["ok"] is True
        request_call = mock_session_class.return_value.request.call_args
        assert request_call.args[0] == "POST"
        assert request_call.args[1] == "https://aeon.test/chat"
        sent = request_call.kwargs["json"]
        assert sent["query"] == "hello"


def test_chat_raises_on_error_response():
    with _patch_session() as mock_session_class:
        mock_session_class.return_value.request.return_value = _FakeResponse(500, {"ok": False, "error": "boom"})
        client = AeonClient(base_url="https://aeon.test")
        with pytest.raises(AeonError):
            client.chat("hello")
