"""Regression tests for the background JobQueue retry and dead-letter handling.

A transient failure must be retried up to the configured bound; a job that
always fails must land in the dead-letter ledger without hanging the queue,
and a successful job must reach ``done`` and never be counted as a dead letter.
"""

from __future__ import annotations

import time

import pytest

import aeon_server


@pytest.fixture
def queue(monkeypatch):
    q = aeon_server.JobQueue(workers=1, max_retries=2)
    yield q
    q.shutdown()


def _wait_for(predicate, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError("condition not met before timeout")


def test_successful_job_reaches_done(queue, monkeypatch):
    calls = {"n": 0}

    class _Agent:
        def act(self, query, llm_provider=None):
            calls["n"] += 1
            return {"answer": f"echo: {query}"}

        def reflect(self):
            calls["n"] += 1
            return {"reflection": "ok"}

        def evolve(self, **kwargs):
            return {"evolved": True}

    monkeypatch.setattr(aeon_server, "get_agent", lambda app_id: _Agent())

    job_id = queue.submit("ws-test", "reflect", {})
    _wait_for(lambda: (queue.status(job_id) or {}).get("status") == "done")
    assert calls["n"] == 1
    assert queue.status(job_id)["attempts"] == 1
    assert queue.dead_letters() == []


def test_transient_failure_retries_then_recovers(queue, monkeypatch):
    calls = {"n": 0}

    class _Agent:
        def act(self, query, llm_provider=None):
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("transient boom")
            return {"answer": "recovered"}

        def reflect(self):
            raise RuntimeError("nope")


    monkeypatch.setattr(aeon_server, "get_agent", lambda app_id: _Agent())

    job_id = queue.submit("ws-test", "act", {"query": "hi"})
    _wait_for(lambda: (queue.status(job_id) or {}).get("status") == "done", timeout=15)
    status = queue.status(job_id)
    assert status["attempts"] == 2
    assert status["result"]["answer"] == "recovered"
    assert queue.dead_letters() == []


def test_persistent_failure_dead_letters_with_full_attempts(queue, monkeypatch):
    def _boom(app_id):
        raise RuntimeError("always failing")

    monkeypatch.setattr(aeon_server, "get_agent", _boom)

    job_id = queue.submit("ws-test", "act", {"query": "hi"})
    _wait_for(lambda: (queue.status(job_id) or {}).get("status") == "failed", timeout=15)
    status = queue.status(job_id)
    assert status["attempts"] == 2  # max_retries=2

    letters = queue.dead_letters()
    assert letters, "persistent failure must be dead-lettered"
    assert letters[0]["job_id"] == job_id
    assert letters[0]["attempts"] == 2
    assert "always failing" in letters[0]["error"]
