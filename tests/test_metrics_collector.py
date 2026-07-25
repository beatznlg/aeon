"""Tests for aeon_server.MetricsCollector."""

from aeon_server import MetricsCollector


def test_counter_increment():
    collector = MetricsCollector()
    collector.inc("test_counter", labels={"env": "test"})
    collector.inc("test_counter", labels={"env": "test"})
    summary = collector.snapshot_summary()
    assert summary["counters"]["test_counter"]["(('env', 'test'),)"] == 2


def test_histogram_observe():
    collector = MetricsCollector()
    collector.observe("test_hist", 0.05, labels={"path": "/health"})
    summary = collector.snapshot_summary()
    hist = summary["histograms"]["test_hist"]["(('path', '/health'),)"]
    assert hist["count"] == 1
    assert hist["sum"] == 0.05


def test_gauge_set():
    collector = MetricsCollector()
    collector.set_gauge("test_gauge", 42.0)
    assert collector.snapshot_summary()["gauges"]["test_gauge"] == 42.0


def test_render_outputs_prometheus_text():
    collector = MetricsCollector()
    collector.inc("aeon_test_total", labels={"method": "GET"})
    collector.set_gauge("aeon_test_gauge", 1.0)
    text = collector.render()
    assert "aeon_test_total" in text
    assert "aeon_test_gauge" in text
    assert "# HELP" in text
