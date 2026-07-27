"""Tests for AEON automations — Phase 23 dynamic context mapping & outbound webhooks."""

from unittest import mock

import pytest


@pytest.fixture
def sample_event():
    return {
        "type": "inbound_webhook",
        "payload": {"user": "Alice", "issue": "bug", "nested": {"id": "42"}},
        "user_id": "user-123",
        "workspace_id": "ws-123",
        "timestamp": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def sample_rule():
    return {
        "id": "rule-1",
        "name": "Bug Alert",
        "workspace_id": "ws-123",
    }


def test_template_interpolation_in_string(sample_event, sample_rule):
    from aeon_automations import _interpolate

    result = _interpolate(
        "{{ event.payload.user }} reported {{ event.payload.issue }}",
        sample_event,
        sample_rule,
    )
    assert result == "Alice reported bug"


def test_template_interpolation_nested_payload(sample_event, sample_rule):
    from aeon_automations import _interpolate

    result = _interpolate("{{ event.payload.nested.id }}", sample_event, sample_rule)
    assert result == "42"


def test_template_interpolation_rule_context(sample_event, sample_rule):
    from aeon_automations import _interpolate

    result = _interpolate("{{ rule.name }} ({{ rule.id }})", sample_event, sample_rule)
    assert result == "Bug Alert (rule-1)"


def test_template_interpolation_in_dict(sample_event, sample_rule):
    from aeon_automations import _interpolate

    config = {
        "url": "https://example.com/issues/{{ event.payload.issue }}",
        "body": "User: {{ event.payload.user }}",
    }
    result = _interpolate(config, sample_event, sample_rule)
    assert result["url"] == "https://example.com/issues/bug"
    assert result["body"] == "User: Alice"


def test_execute_outbound_webhook_missing_url(sample_event):
    from aeon_automations import _execute_outbound_webhook

    result = _execute_outbound_webhook({}, sample_event)
    assert result["ok"] is False
    assert "URL missing" in result["error"]


def test_execute_outbound_webhook_unsupported_method(sample_event):
    from aeon_automations import _execute_outbound_webhook

    result = _execute_outbound_webhook({"url": "https://example.com", "method": "FOOBAR"}, sample_event)
    assert result["ok"] is False
    assert "unsupported HTTP method" in result["error"]


def test_execute_outbound_webhook_posts_json(sample_event):
    from aeon_automations import _execute_outbound_webhook

    with mock.patch("requests.request") as mock_request:
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        result = _execute_outbound_webhook(
            {
                "url": "https://zapier.test/hook",
                "method": "POST",
                "headers": {"X-Custom": "value"},
                "body": {"alert": "bug"},
            },
            sample_event,
        )

        assert result["ok"] is True
        assert result["status_code"] == 200
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args.args[0] == "POST"
        assert call_args.args[1] == "https://zapier.test/hook"
        assert call_args.kwargs["headers"] == {"X-Custom": "value"}
        assert call_args.kwargs["json"] == {"alert": "bug"}


def test_execute_action_by_type_interpolates_outbound_webhook(sample_event, sample_rule):
    from aeon_automations import execute_action_by_type

    with mock.patch("requests.request") as mock_request:
        mock_response = mock.Mock()
        mock_response.status_code = 202
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        result = execute_action_by_type(
            "outbound_webhook",
            {
                "url": "https://api.test/events/{{ event.type }}",
                "method": "POST",
                "body": "{{ event.payload.user }}",
            },
            sample_event,
            sample_rule,
        )

        assert result["ok"] is True
        called_url = mock_request.call_args.args[1]
        called_data = mock_request.call_args.kwargs["data"]
        assert called_url == "https://api.test/events/inbound_webhook"
        assert called_data == "Alice"
