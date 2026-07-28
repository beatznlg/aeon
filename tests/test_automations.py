"""Tests for AEON automations — Phase 23 dynamic context mapping & outbound webhooks."""

import json
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
    def _exec_side_effect(action_type, action_config, context, dry_run=False):
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


def test_execute_action_wait_for_event_returns_sleeping(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {"type": "outbound_webhook", "config": {"url": "https://api.test/step1", "method": "POST"}},
            {
                "type": "wait_for_event",
                "config": {
                    "event_type": "payment.received",
                    "correlation_key": "invoice_id",
                    "correlation_value": "inv-123",
                    "timeout_minutes": 60,
                },
            },
            {"type": "outbound_webhook", "config": {"url": "https://api.test/step2", "method": "POST"}},
        ],
    }
    def _exec_side_effect(action_type, action_config, context, dry_run=False):
        if action_type == "wait_for_event":
            return {
                "ok": True,
                "status": "sleeping",
                "waiting_for_event": action_config.get("event_type"),
                "correlation_key": action_config.get("correlation_key"),
                "correlation_value": action_config.get("correlation_value"),
                "resume_at": "2025-01-01T00:00:00+00:00",
            }
        return {"ok": True, "status_code": 200}

    with mock.patch("aeon_automations.execute_action_by_type") as mock_exec:
        mock_exec.side_effect = _exec_side_effect
        result = _execute_action(rule, sample_event)

    assert result["ok"] is True
    assert result["status"] == "sleeping"
    assert result["pending_step_index"] == 2
    assert len(result["steps"]) == 2
    wait_step = result["steps"][1]
    assert wait_step.get("waiting_for_event") == "payment.received"
    assert wait_step.get("correlation_key") == "invoice_id"
    assert wait_step.get("correlation_value") == "inv-123"
    assert wait_step.get("status") == "sleeping"
    assert "resume_at" in wait_step


def test_wait_for_event_resumes_on_matching_event(sample_event, sample_rule):
    from aeon_automations import _try_resume_waiting_executions, resume_execution

    # Simulate a sleeping execution waiting for payment.received with invoice_id=inv-123
    execution = {
        "id": "exec-1",
        "rule_id": sample_rule["id"],
        "event_type": sample_event["type"],
        "event_payload": sample_event.get("payload"),
        "workspace_id": sample_rule.get("workspace_id"),
        "user_id": sample_event.get("user_id"),
        "status": "sleeping",
        "state": {
            "pending_step_index": 2,
            "steps": [
                {"ok": True, "status_code": 200},
                {
                    "ok": True,
                    "status": "sleeping",
                    "waiting_for_event": "payment.received",
                    "correlation_key": "invoice_id",
                    "correlation_value": "inv-123",
                },
            ],
        },
    }

    waking_event = {
        "type": "payment.received",
        "payload": {"invoice_id": "inv-123", "amount": 100},
        "user_id": sample_event.get("user_id"),
        "workspace_id": sample_rule.get("workspace_id"),
    }

    with mock.patch("aeon_automations._supabase_headers", return_value={"Authorization": "Bearer test"}):
        with mock.patch("aeon_automations._get_db_url", return_value="http://test.supabase"):
            with mock.patch("requests.get") as mock_get, mock.patch("requests.patch") as mock_patch:
                mock_get.return_value.json.return_value = [execution]
                mock_get.return_value.raise_for_status.return_value = None
                mock_patch.return_value.raise_for_status.return_value = None

                with mock.patch("aeon_automations.resume_execution") as mock_resume:
                    mock_resume.return_value = {"ok": True, "execution_id": "exec-1", "status": "completed"}
                    resumed = _try_resume_waiting_executions(waking_event)

    assert len(resumed) == 1
    mock_resume.assert_called_once()
    call_args = mock_resume.call_args
    assert call_args.kwargs.get("waking_event") == waking_event


def test_wait_for_event_does_not_resume_on_mismatched_correlation(sample_event, sample_rule):
    from aeon_automations import _try_resume_waiting_executions

    execution = {
        "id": "exec-1",
        "rule_id": sample_rule["id"],
        "event_type": sample_event["type"],
        "event_payload": sample_event.get("payload"),
        "workspace_id": sample_rule.get("workspace_id"),
        "user_id": sample_event.get("user_id"),
        "status": "sleeping",
        "state": {
            "pending_step_index": 2,
            "steps": [
                {"ok": True, "status_code": 200},
                {
                    "ok": True,
                    "status": "sleeping",
                    "waiting_for_event": "payment.received",
                    "correlation_key": "invoice_id",
                    "correlation_value": "inv-123",
                },
            ],
        },
    }

    waking_event = {
        "type": "payment.received",
        "payload": {"invoice_id": "inv-999", "amount": 100},
        "user_id": sample_event.get("user_id"),
        "workspace_id": sample_rule.get("workspace_id"),
    }

    with mock.patch("aeon_automations._supabase_headers", return_value={"Authorization": "Bearer test"}):
        with mock.patch("aeon_automations._get_db_url", return_value="http://test.supabase"):
            with mock.patch("requests.get") as mock_get:
                mock_get.return_value.json.return_value = [execution]
                mock_get.return_value.raise_for_status.return_value = None

                with mock.patch("aeon_automations.resume_execution") as mock_resume:
                    resumed = _try_resume_waiting_executions(waking_event)

    assert len(resumed) == 0
    mock_resume.assert_not_called()


def test_execute_wait_for_event_requires_event_type():
    from aeon_automations import _execute_wait_for_event

    result = _execute_wait_for_event({"correlation_key": "id", "correlation_value": "x"}, {})
    assert result["ok"] is False
    assert "event_type" in result["error"]


def test_execute_wait_for_event_requires_correlation():
    from aeon_automations import _execute_wait_for_event

    result = _execute_wait_for_event({"event_type": "payment.received"}, {})
    assert result["ok"] is False
    assert "correlation" in result["error"]


def test_set_variable_and_state_interpolation(sample_event, sample_rule):
    from aeon_automations import _execute_action, _interpolate

    rule = {
        **sample_rule,
        "actions": [
            {"type": "set_variable", "config": {"key": "alert_count", "value": 3}},
            {"type": "outbound_webhook", "config": {"url": "https://api.test/count/{{ state.alert_count }}"}},
        ],
    }
    with mock.patch("aeon_automations.execute_action_by_type") as mock_exec:
        call_results = [
            {"ok": True, "key": "alert_count", "value": 3},
        ]
        # Subsequent calls are for the outbound_webhook; return a successful response.
        def _side_effect(action_type, action_config, context, dry_run=False):
            if action_type == "set_variable":
                return call_results.pop(0)
            return {"ok": True, "status_code": 200}
        mock_exec.side_effect = _side_effect
        result = _execute_action(rule, sample_event)

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["steps"][0]["value"] == 3


def test_interpolate_state_context(sample_event, sample_rule):
    from aeon_automations import _interpolate

    context = {
        "event": sample_event,
        "rule": sample_rule,
        "steps": [],
        "state": {"alert_count": 5, "last_issue": "timeout"},
    }
    assert _interpolate("{{ state.alert_count }}", context) == "5"
    assert _interpolate("{{ state.last_issue }}", context) == "timeout"
    assert _interpolate("{{ state.missing }}", context) == ""


def test_set_variable_requires_key(sample_event):
    from aeon_automations import _execute_set_variable

    result = _execute_set_variable({"value": "x"}, sample_event)
    assert result["ok"] is False
    assert "key" in result["error"]


def test_delete_variable_requires_key(sample_event):
    from aeon_automations import _execute_delete_variable

    result = _execute_delete_variable({}, sample_event)
    assert result["ok"] is False
    assert "key" in result["error"]


def test_increment_variable_requires_workspace_id():
    from aeon_automations import _execute_increment_variable

    result = _execute_increment_variable({"key": "counter", "amount": 1}, {})
    assert result["ok"] is False
    assert "workspace_id" in result["error"]


def test_call_rule_requires_rule_id():
    from aeon_automations import _execute_call_rule

    result = _execute_call_rule({}, {}, {"event": {}, "rule": {}})
    assert result["ok"] is False
    assert "rule_id" in result["error"]


def test_call_rule_executes_sub_rule(sample_event, sample_rule):
    from aeon_automations import _execute_action

    child_rule = {
        "id": "child-rule",
        "workspace_id": "ws-1",
        "actions": [
            {"type": "set_variable", "config": {"key": "sub_key", "value": "sub_value"}},
        ],
    }
    parent_rule = {
        **sample_rule,
        "actions": [
            {
                "type": "call_rule",
                "config": {
                    "rule_id": "child-rule",
                    "payload": {"issue": "{{ event.payload.issue }}"},
                },
            },
        ],
    }

    with mock.patch("aeon_automations._fetch_rule_by_id", return_value=child_rule):
        with mock.patch("aeon_automations._execute_set_variable") as mock_set:
            mock_set.return_value = {"ok": True, "key": "sub_key", "value": "sub_value"}
            result = _execute_action(parent_rule, sample_event)

    assert result["ok"] is True
    assert result["status"] == "completed"
    assert result["steps"][0]["rule_id"] == "child-rule"
    assert result["steps"][0]["sub_result"]["ok"] is True


def test_call_rule_depth_guard(sample_event, sample_rule):
    from aeon_automations import _execute_action, MAX_CALL_DEPTH

    # A rule that calls itself; the depth guard should stop the recursion.
    recursive_rule = {
        "id": "recursive-rule",
        "workspace_id": "ws-1",
        "actions": [
            {"type": "call_rule", "config": {"rule_id": "recursive-rule"}},
        ],
    }

    with mock.patch("aeon_automations._fetch_rule_by_id", return_value=recursive_rule):
        result = _execute_action(recursive_rule, sample_event)

    # The recursion should be halted cleanly before exhausting the stack.
    assert result["ok"] is False
    assert "depth" in str(result)


def test_transform_math_operations():
    from aeon_automations import _execute_transform

    assert _execute_transform({"operation": "math", "operator": "+", "left": 5, "right": 3}, {})["result"] == 8
    assert _execute_transform({"operation": "math", "operator": "-", "left": 5, "right": 3}, {})["result"] == 2
    assert _execute_transform({"operation": "math", "operator": "*", "left": 5, "right": 3}, {})["result"] == 15
    assert _execute_transform({"operation": "math", "operator": "/", "left": 6, "right": 3}, {})["result"] == 2.0


def test_transform_math_invalid_operands():
    from aeon_automations import _execute_transform

    result = _execute_transform({"operation": "math", "operator": "+", "left": "abc", "right": 3}, {})
    assert result["ok"] is False
    assert "numeric" in result["error"]


def test_transform_date_format():
    from aeon_automations import _execute_transform

    result = _execute_transform(
        {"operation": "date_format", "input": "2024-03-15T12:30:00+00:00", "output_format": "%Y-%m-%d"},
        {},
    )
    assert result["ok"] is True
    assert result["result"] == "2024-03-15"


def test_transform_regex_extract():
    from aeon_automations import _execute_transform

    result = _execute_transform(
        {"operation": "regex_extract", "pattern": "Order #(\\d+)", "input": "Order #12345 shipped", "group": 1},
        {},
    )
    assert result["ok"] is True
    assert result["result"] == "12345"


def test_transform_json_parse():
    from aeon_automations import _execute_transform

    result = _execute_transform({"operation": "json_parse", "input": '{"key": "value"}'}, {})
    assert result["ok"] is True
    assert result["result"] == {"key": "value"}


def test_transform_json_stringify():
    from aeon_automations import _execute_transform

    result = _execute_transform({"operation": "json_stringify", "input": {"key": "value"}}, {})
    assert result["ok"] is True
    assert result["result"] == '{"key": "value"}'


def test_execute_action_transform_chain(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {"type": "transform", "config": {"operation": "math", "operator": "*", "left": 10, "right": 2}},
            {"type": "outbound_webhook", "config": {"url": "https://api.test/value/{{ steps.0.result }}"}},
        ],
    }
    with mock.patch("requests.request") as mock_request:
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response

        result = _execute_action(rule, sample_event)

    assert result["ok"] is True
    assert result["steps"][0]["result"] == 20
    called_url = mock_request.call_args.args[1]
    assert "value/20" in called_url


def test_execute_parallel_branches_success(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {
                "type": "parallel",
                "config": {
                    "branches": [
                        {
                            "name": "double",
                            "actions": [
                                {"type": "transform", "config": {"operation": "math", "operator": "*", "left": 2, "right": 3}}
                            ],
                        },
                        {
                            "name": "add",
                            "actions": [
                                {"type": "transform", "config": {"operation": "math", "operator": "+", "left": 10, "right": 5}}
                            ],
                        },
                    ]
                },
            }
        ],
    }
    result = _execute_action(rule, sample_event)
    assert result["ok"] is True
    assert result["status"] == "completed"
    parallel_step = result["steps"][0]
    assert parallel_step["ok"] is True
    assert len(parallel_step["branches"]) == 2
    assert parallel_step["branches"][0]["name"] == "double"
    assert parallel_step["branches"][0]["steps"][0]["result"] == 6
    assert parallel_step["branches"][1]["steps"][0]["result"] == 15


def test_execute_parallel_branch_failure(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {
                "type": "parallel",
                "config": {
                    "branches": [
                        {
                            "name": "ok_branch",
                            "actions": [
                                {"type": "transform", "config": {"operation": "math", "operator": "+", "left": 1, "right": 1}}
                            ],
                        },
                        {
                            "name": "failing_branch",
                            "actions": [
                                {"type": "outbound_webhook", "config": {"url": ""}}
                            ],
                        },
                    ]
                },
            }
        ],
    }
    result = _execute_action(rule, sample_event)
    assert result["ok"] is False
    assert result["status"] == "failed"
    parallel_step = result["steps"][0]
    assert parallel_step["ok"] is False
    assert "failing_branch" in parallel_step["failed_branches"]


def test_execute_parallel_continue_on_error(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {
                "type": "parallel",
                "config": {
                    "continue_on_error": True,
                    "branches": [
                        {
                            "name": "ok_branch",
                            "actions": [
                                {"type": "transform", "config": {"operation": "math", "operator": "+", "left": 1, "right": 1}}
                            ],
                        },
                        {
                            "name": "failing_branch",
                            "actions": [
                                {"type": "outbound_webhook", "config": {"url": ""}}
                            ],
                        },
                    ]
                },
            }
        ],
    }
    result = _execute_action(rule, sample_event)
    assert result["ok"] is True
    parallel_step = result["steps"][0]
    assert parallel_step["ok"] is True
    assert "failing_branch" in parallel_step["failed_branches"]


def test_execute_parallel_invalid_config(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {"type": "parallel", "config": {"branches": []}}
        ],
    }
    result = _execute_action(rule, sample_event)
    assert result["ok"] is False
    assert "branches" in result["error"].lower()


# Phase 36: Dry-run / simulation mode

def test_dry_run_simulates_webhook_without_http_request(sample_event, sample_rule):
    from aeon_automations import _execute_action
    from unittest import mock

    rule = {
        **sample_rule,
        "actions": [
            {"type": "webhook", "config": {"url": "https://example.com/webhook"}}
        ],
    }
    with mock.patch("requests.post") as mock_post:
        result = _execute_action(rule, sample_event, dry_run=True)
        mock_post.assert_not_called()
    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["steps"][0]["simulated"] is True
    assert result["steps"][0]["status_code"] == 200


def test_dry_run_simulates_variable_set_and_get(sample_event, sample_rule):
    from aeon_automations import _execute_action
    from unittest import mock

    rule = {
        **sample_rule,
        "actions": [
            {"type": "set_variable", "config": {"key": "counter", "value": 5}},
            {"type": "get_variable", "config": {"key": "counter"}},
        ],
    }
    with mock.patch("requests.post") as mock_post, mock.patch("requests.get") as mock_get:
        result = _execute_action(rule, sample_event, dry_run=True)
        mock_post.assert_not_called()
        mock_get.assert_not_called()
    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["steps"][0]["key"] == "counter"
    assert result["steps"][0]["value"] == 5
    assert result["steps"][1]["value"] == 5


def test_dry_run_allows_transform_and_delay_to_continue(sample_event, sample_rule):
    from aeon_automations import _execute_action

    rule = {
        **sample_rule,
        "actions": [
            {"type": "transform", "config": {"operation": "math", "operator": "+", "left": 2, "right": 3}},
            {"type": "delay", "config": {"duration_minutes": 10}},
            {"type": "transform", "config": {"operation": "math", "operator": "*", "left": 5, "right": 2}},
        ],
    }
    result = _execute_action(rule, sample_event, dry_run=True)
    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["status"] == "completed"
    assert len(result["steps"]) == 3
    assert result["steps"][0]["result"] == 5
    assert result["steps"][1]["simulated"] is True
    assert result["steps"][2]["result"] == 10


def test_dry_run_simulates_call_rule_sub_automation(sample_event, sample_rule):
    from aeon_automations import _execute_action
    from unittest import mock

    sub_rule = {
        **sample_rule,
        "id": "sub-rule-1",
        "actions": [
            {"type": "transform", "config": {"operation": "math", "operator": "+", "left": 1, "right": 1}}
        ],
    }
    parent_rule = {
        **sample_rule,
        "actions": [
            {
                "type": "call_rule",
                "config": {"rule_id": "sub-rule-1", "payload": {"value": 10}, "event_type": "sub_request"},
            }
        ],
    }
    with mock.patch("aeon_automations._fetch_rule_by_id", return_value=sub_rule) as mock_fetch:
        result = _execute_action(parent_rule, sample_event, dry_run=True)
        mock_fetch.assert_called_once_with("sub-rule-1", "ws-123")
    assert result["ok"] is True
    assert result["dry_run"] is True
    sub_result = result["steps"][0]["sub_result"]
    assert sub_result["ok"] is True
    assert sub_result["dry_run"] is True
    assert sub_result["steps"][0]["result"] == 2


def test_normal_run_still_executes_webhook(sample_event, sample_rule):
    from aeon_automations import _execute_action
    from unittest import mock

    rule = {
        **sample_rule,
        "actions": [
            {"type": "webhook", "config": {"url": "https://example.com/webhook"}}
        ],
    }
    with mock.patch("requests.post") as mock_post:
        mock_response = mock.Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        result = _execute_action(rule, sample_event, dry_run=False)
        mock_post.assert_called_once()
    assert result["ok"] is True
    assert "dry_run" not in result or result.get("dry_run") is False


# Phase 37: Automation Blueprints & Import/Export

import uuid as _uuid


@pytest.fixture
def operator_token(client):
    """Register a user and return an auth token for automation endpoint tests."""
    email = f"automation-{_uuid.uuid4().hex[:8]}@test.local"
    resp = client.post(
        "/auth/register",
        json={"email": email, "password": "secure123", "name": "Automation Tester"},
    )
    data = json.loads(resp.data)
    assert "token" in data, f"register failed: {resp.status_code} {data}"
    return data["token"]


def test_automation_blueprints(client, operator_token):
    resp = client.get(
        "/automations/blueprints",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert len(data["blueprints"]) > 0
    assert all("id" in bp and "actions" in bp for bp in data["blueprints"])


def test_automation_export(client, operator_token, monkeypatch):
    import requests as _requests
    from unittest import mock

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    fake_rule = {
        "id": "rule-123",
        "name": "Test Rule",
        "workspace_id": "ws-123",
        "created_at": "2024-01-01T00:00:00Z",
        "event_type": "workflow_status",
        "actions": [{"type": "webhook", "config": {"url": "https://example.com"}}],
    }

    with mock.patch.object(_requests, "get") as mock_get:
        mock_resp = mock.Mock()
        mock_resp.json.return_value = [fake_rule]
        mock_resp.raise_for_status.return_value = None
        mock_get.return_value = mock_resp

        resp = client.get(
            "/automations/export",
            headers={"Authorization": f"Bearer {operator_token}"},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["ok"] is True
        assert data["count"] == 1
        exported = data["rules"][0]
        assert "id" not in exported
        assert "workspace_id" not in exported
        assert "created_at" not in exported
        assert exported["name"] == "Test Rule"


def test_automation_import(client, operator_token, monkeypatch):
    import requests as _requests
    from unittest import mock

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    imported = []

    def fake_post(url, **kwargs):
        resp = mock.Mock()
        resp.raise_for_status.return_value = None
        payload = kwargs.get("json") or {}
        rule = {"id": "imported-1", **payload}
        imported.append(rule)
        resp.json.return_value = [rule]
        return resp

    with mock.patch.object(_requests, "post", side_effect=fake_post):
        resp = client.post(
            "/automations/import",
            headers={"Authorization": f"Bearer {operator_token}"},
            json={
                "rules": [
                    {
                        "name": "Imported Rule",
                        "event_type": "workflow_status",
                        "actions": [{"type": "webhook", "config": {"url": "https://example.com"}}],
                    }
                ]
            },
        )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert data["imported"] == 1
    assert imported[0]["workspace_id"] is not None


def test_automation_import_rejects_invalid_action_type(client, operator_token, monkeypatch):
    import requests as _requests
    from unittest import mock

    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-key")

    resp = client.post(
        "/automations/import",
        headers={"Authorization": f"Bearer {operator_token}"},
        json={
            "rules": [
                {
                    "name": "Bad Rule",
                    "event_type": "workflow_status",
                    "actions": [{"type": "invalid_action", "config": {}}],
                }
            ]
        },
    )
    assert resp.status_code == 207
    data = json.loads(resp.data)
    assert data["ok"] is False
    assert len(data["errors"]) == 1
