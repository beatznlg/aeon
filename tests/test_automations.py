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


def test_evaluate_condition_equality():
    from aeon_automations import evaluate_condition

    assert evaluate_condition({"status": "failed"}, {"status": "failed"}) is True
    assert evaluate_condition({"status": "failed"}, {"status": "ok"}) is False


def test_evaluate_condition_operators():
    from aeon_automations import evaluate_condition

    payload = {"amount": 1500, "count": 5, "tag": "urgent", "status": "failed"}
    assert evaluate_condition({"amount": {"$gt": 1000}}, payload) is True
    assert evaluate_condition({"amount": {"$lt": 2000}}, payload) is True
    assert evaluate_condition({"count": {"$gte": 5}}, payload) is True
    assert evaluate_condition({"count": {"$lte": 4}}, payload) is False
    assert evaluate_condition({"status": {"$in": ["failed", "timeout"]}}, payload) is True
    assert evaluate_condition({"tag": {"$contains": "gen"}}, payload) is True
    assert evaluate_condition({"missing": {"$exists": True}}, payload) is False
    assert evaluate_condition({"amount": {"$exists": True}}, payload) is True


def test_evaluate_condition_nested_paths():
    from aeon_automations import evaluate_condition

    payload = {"user": {"plan": "premium"}, "meta": {"score": 95}}
    assert evaluate_condition({"user.plan": "premium"}, payload) is True
    assert evaluate_condition({"user.plan": {"$neq": "free"}}, payload) is True
    assert evaluate_condition({"meta.score": {"$gte": 90}}, payload) is True


def test_evaluate_condition_logical_operators():
    from aeon_automations import evaluate_condition

    payload = {"status": "failed", "severity": 7}
    assert evaluate_condition({"$or": [{"status": "ok"}, {"severity": {"$gt": 5}}]}, payload) is True
    assert evaluate_condition({"$and": [{"status": "failed"}, {"severity": {"$lt": 5}}]}, payload) is False
    assert evaluate_condition({"$not": {"status": "ok"}}, payload) is True


def test_evaluate_condition_regex():
    from aeon_automations import evaluate_condition

    payload = {"message": "RateLimit exceeded"}
    assert evaluate_condition({"message": {"$regex": "RateLimit"}}, payload) is True
    assert evaluate_condition({"message": {"$regex": "^RateLimit"}}, payload) is True
    assert evaluate_condition({"message": {"$regex": "timeout"}}, payload) is False


def test_is_in_cooldown_no_cooldown():
    from aeon_automations import _is_in_cooldown

    assert _is_in_cooldown({"cooldown_minutes": 0}) is False
    assert _is_in_cooldown({"cooldown_minutes": None}) is False
    assert _is_in_cooldown({}) is False


def test_is_in_cooldown_within_window():
    from datetime import datetime, timezone, timedelta
    from aeon_automations import _is_in_cooldown

    last = datetime.now(timezone.utc) - timedelta(minutes=3)
    rule = {"cooldown_minutes": 5, "last_triggered_at": last.isoformat()}
    assert _is_in_cooldown(rule) is True

    # String timestamps with trailing Z should also parse (use a recent time)
    recent_z = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    recent_z = recent_z.replace("+00:00", "Z")
    rule_z = {"cooldown_minutes": 5, "last_triggered_at": recent_z}
    assert _is_in_cooldown(rule_z) is True


def test_is_in_cooldown_expired():
    from datetime import datetime, timezone, timedelta
    from aeon_automations import _is_in_cooldown

    last = datetime.now(timezone.utc) - timedelta(minutes=10)
    rule = {"cooldown_minutes": 5, "last_triggered_at": last.isoformat()}
    assert _is_in_cooldown(rule) is False


def test_interpolate_steps_context(sample_event, sample_rule):
    from aeon_automations import _interpolate

    context = {
        "event": sample_event,
        "rule": sample_rule,
        "steps": [
            {"data": {"summary": "Bug confirmed"}},
            {"data": {"sent": True}},
        ],
    }
    assert _interpolate("{{ steps.0.data.summary }}", context) == "Bug confirmed"
    assert _interpolate("{{ steps[1].data.sent }}", context) == "True"
    assert _interpolate("{{ steps.99.data.summary }}", context) == ""


def test_execute_action_legacy_single_action(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "action_type": "webhook",
        "action_config": {"url": "https://example.com/hook"},
    }
    with mock.patch("requests.post") as mock_post:
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = _execute_action(rule, sample_event)

        assert result["ok"] is True
        assert result["status"] == "completed"
        assert len(result["steps"]) == 1
        assert result["steps"][0]["status_code"] == 200


def test_execute_action_multi_step_chain(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {"type": "outbound_webhook", "config": {"url": "https://api.test/step1", "method": "POST", "body": "first"}},
            {"type": "outbound_webhook", "config": {"url": "https://api.test/step2", "method": "POST", "body": "{{ steps.0.status_code }}"}},
        ],
    }
    with mock.patch("requests.request") as mock_request:
        mock_response = mock.Mock()
        mock_response.status_code = 202
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        result = _execute_action(rule, sample_event)

        assert result["ok"] is True
        assert result["status"] == "completed"
        assert len(result["steps"]) == 2
        assert result["steps"][0]["status_code"] == 202
        assert result["steps"][1]["status_code"] == 202
        # Second step body should interpolate to the first step's status code
        second_call = mock_request.call_args_list[1]
        assert second_call.kwargs["data"] == "202"


def test_execute_action_stops_on_failure(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {"type": "outbound_webhook", "config": {"url": "", "method": "POST"}},
            {"type": "outbound_webhook", "config": {"url": "https://api.test/step2", "method": "POST"}},
        ],
    }
    result = _execute_action(rule, sample_event)

    assert result["ok"] is False
    assert result["failed_step"] == 0
    assert len(result["steps"]) == 1


def test_evaluate_condition_list_paths():
    from aeon_automations import evaluate_condition

    payload = {"steps": [{"data": {"score": 75}}, {"data": {"score": 30}}]}
    assert evaluate_condition({"steps.0.data.score": {"$gte": 70}}, payload) is True
    assert evaluate_condition({"steps.1.data.score": {"$lt": 50}}, payload) is True
    assert evaluate_condition({"steps.0.data.score": {"$lt": 70}}, payload) is False


def test_execute_action_run_if_skips_step(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {"type": "outbound_webhook", "config": {"url": "https://api.test/step1", "method": "POST"}},
            {
                "type": "outbound_webhook",
                "config": {"url": "https://api.test/step2", "method": "POST"},
                "run_if": {"event.payload.issue": "feature"},
            },
        ],
    }
    with mock.patch("aeon_automations.execute_action_by_type") as mock_exec:
        mock_exec.return_value = {"ok": True, "status_code": 200}
        result = _execute_action(rule, sample_event)

    assert result["ok"] is True
    assert len(result["steps"]) == 2
    assert result["steps"][1]["skipped"] is True
    assert mock_exec.call_count == 1


def test_execute_action_run_if_runs_step_based_on_previous_output(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {"type": "outbound_webhook", "config": {"url": "https://api.test/step1", "method": "POST"}},
            {
                "type": "outbound_webhook",
                "config": {"url": "https://api.test/step2", "method": "POST"},
                "run_if": {"steps.0.data.score": {"$gte": 50}},
            },
        ],
    }
    with mock.patch("aeon_automations.execute_action_by_type") as mock_exec:
        mock_exec.side_effect = [
            {"ok": True, "status_code": 200, "data": {"score": 75}},
            {"ok": True, "status_code": 202},
        ]
        result = _execute_action(rule, sample_event)

    assert result["ok"] is True
    assert len(result["steps"]) == 2
    assert "skipped" not in result["steps"][1]
    assert result["steps"][1]["status_code"] == 202


def test_execute_action_loop_over_iterates_and_interpolates_item(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {
                "type": "outbound_webhook",
                "config": {"url": "https://api.test/fetch", "method": "GET"},
            },
            {
                "type": "outbound_webhook",
                "config": {"url": "https://api.test/send/{{ item.id }}"},
                "loop_over": "{{ steps.0.data.items }}",
            },
        ],
    }
    with mock.patch("aeon_automations.execute_action_by_type") as mock_exec:
        mock_exec.side_effect = [
            {"ok": True, "status_code": 200, "data": {"items": [{"id": "a"}, {"id": "b"}]}},
            {"ok": True, "status_code": 201},
            {"ok": True, "status_code": 202},
        ]
        result = _execute_action(rule, sample_event)

    assert result["ok"] is True
    assert len(result["steps"]) == 2
    assert "results" in result["steps"][1]
    assert len(result["steps"][1]["results"]) == 2
    assert result["steps"][1]["results"][0]["status_code"] == 201
    assert result["steps"][1]["results"][1]["status_code"] == 202
    # Verify item context was passed into the looped executions
    calls = mock_exec.call_args_list
    # First call is step 0 fetch; subsequent two are loop iterations
    assert calls[1].args[2]["item"]["id"] == "a"
    assert calls[2].args[2]["item"]["id"] == "b"
    assert calls[1].args[2]["loop"]["index"] == 0
    assert calls[2].args[2]["loop"]["index"] == 1


def test_execute_action_loop_over_empty_list(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {"type": "outbound_webhook", "config": {"url": "https://api.test/fetch", "method": "GET"}},
            {
                "type": "outbound_webhook",
                "config": {"url": "https://api.test/send"},
                "loop_over": "{{ steps.0.data.items }}",
            },
        ],
    }
    with mock.patch("aeon_automations.execute_action_by_type") as mock_exec:
        mock_exec.return_value = {"ok": True, "status_code": 200, "data": {"items": []}}
        result = _execute_action(rule, sample_event)

    assert result["ok"] is True
    assert result["steps"][1]["results"] == []


def test_execute_action_loop_over_non_list_fails(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {"type": "outbound_webhook", "config": {"url": "https://api.test/fetch", "method": "GET"}},
            {
                "type": "outbound_webhook",
                "config": {"url": "https://api.test/send"},
                "loop_over": "{{ steps.0.data.items }}",
            },
        ],
    }
    with mock.patch("aeon_automations.execute_action_by_type") as mock_exec:
        mock_exec.return_value = {"ok": True, "status_code": 200, "data": {"items": "not-a-list"}}
        result = _execute_action(rule, sample_event)

    assert result["ok"] is False
    assert result["failed_step"] == 1


def test_execute_action_delay_returns_sleeping(sample_event, sample_rule):
    from aeon_automations import _execute_action
    from datetime import datetime, timezone, timedelta

    rule = {
        **sample_rule,
        "actions": [
            {"type": "outbound_webhook", "config": {"url": "https://api.test/step1", "method": "POST"}},
            {"type": "delay", "config": {"duration_minutes": 10}},
            {"type": "outbound_webhook", "config": {"url": "https://api.test/step2", "method": "POST"}},
        ],
    }
    def _exec_side_effect(action_type, action_config, context):
        if action_type == "delay":
            from datetime import timezone as _tz
            return {
                "ok": True,
                "status": "sleeping",
                "delayed": True,
                "duration_minutes": action_config.get("duration_minutes"),
                "resume_at": (datetime.now(_tz.utc) + timedelta(minutes=10)).isoformat(),
            }
        return {"ok": True, "status_code": 200}

    with mock.patch("aeon_automations.execute_action_by_type") as mock_exec:
        mock_exec.side_effect = _exec_side_effect
        result = _execute_action(rule, sample_event)

    assert result["ok"] is True
    assert result["status"] == "sleeping"
    assert result["pending_step_index"] == 2
    assert len(result["steps"]) == 2
    assert result["steps"][1].get("delayed") is True
    resume_at = datetime.fromisoformat(result["resume_at"])
    assert (resume_at - datetime.now(timezone.utc)).total_seconds() > 500


def test_execute_action_resumes_after_delay(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {"type": "outbound_webhook", "config": {"url": "https://api.test/step1", "method": "POST"}},
            {"type": "delay", "config": {"duration_minutes": 10}},
            {"type": "outbound_webhook", "config": {"url": "https://api.test/step2", "method": "POST"}},
        ],
    }
    initial_steps = [
        {"ok": True, "status_code": 200},
        {"ok": True, "status": "sleeping", "delayed": True, "duration_minutes": 10, "resume_at": "2025-01-01T00:00:00+00:00"},
    ]
    with mock.patch("aeon_automations.execute_action_by_type") as mock_exec:
        mock_exec.return_value = {"ok": True, "status_code": 201}
        result = _execute_action(rule, sample_event, start_index=2, initial_steps=initial_steps)

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert len(result["steps"]) == 3
    assert result["steps"][2]["status_code"] == 201


def test_execute_delay_validates_duration():
    from aeon_automations import _execute_delay

    assert _execute_delay({"duration_minutes": 5}, {})["status"] == "sleeping"
    assert _execute_delay({"duration_minutes": 0}, {})["ok"] is False
    assert _execute_delay({"duration_minutes": -1}, {})["ok"] is False
    assert _execute_delay({}, {})["ok"] is False


def test_execute_action_on_error_fallback_runs_and_halt(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {
                "type": "outbound_webhook",
                "config": {"url": "", "method": "POST"},
                "on_error": {"type": "outbound_webhook", "config": {"url": "https://api.test/fallback"}},
            },
            {"type": "outbound_webhook", "config": {"url": "https://api.test/step2", "method": "POST"}},
        ],
    }
    with mock.patch("requests.request") as mock_request:
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        result = _execute_action(rule, sample_event)

    assert result["ok"] is False
    assert result["failed_step"] == 0
    assert result["steps"][0]["on_error_result"]["status_code"] == 200
    assert len(result["steps"]) == 1


def test_execute_action_on_error_fallback_runs_and_continue(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {
                "type": "outbound_webhook",
                "config": {"url": "", "method": "POST"},
                "on_error": {"type": "outbound_webhook", "config": {"url": "https://api.test/fallback"}},
                "continue_on_error": True,
            },
            {"type": "outbound_webhook", "config": {"url": "https://api.test/step2", "method": "POST"}},
        ],
    }
    with mock.patch("requests.request") as mock_request:
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        result = _execute_action(rule, sample_event)

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["steps"][0]["on_error_result"]["status_code"] == 200
    assert len(result["steps"]) == 2


def test_execute_action_on_error_interpolates_error_context(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {
                "type": "outbound_webhook",
                "config": {"url": "", "method": "POST"},
                "on_error": {
                    "type": "outbound_webhook",
                    "config": {"url": "https://api.test/alert?message={{ error.message }}"},
                },
                "continue_on_error": True,
            },
        ],
    }
    with mock.patch("requests.request") as mock_request:
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        result = _execute_action(rule, sample_event)

    assert result["ok"] is True
    called_url = mock_request.call_args.args[1]
    assert "URL missing" in called_url
    assert "error.message" not in called_url
