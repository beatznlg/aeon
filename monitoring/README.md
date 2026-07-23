# AEON v3.0 Monitoring

This directory contains the Prometheus and Grafana configuration for monitoring the AEON Python kernel (`aeon_server.py`).

## Architecture overview

```
┌──────────────────┐      scrape /metrics      ┌──────────────────┐
│   Prometheus     │  ───────────────────────   │   AEON Kernel    │
│  (monitoring/    │                            │  (aeon_server.py)│
│   prometheus/)   │                            │   :5000/metrics  │
└────────┬─────────                            └──────────────────┘
         │
         │ sends alerts
         ▼
┌──────────────────┐
│  Alertmanager    │  routes to email / Slack
│  (monitoring/    │
│   alertmanager/) │
└────────┬─────────
         │
         │ query
         ▼
┌──────────────────┐
│     Grafana      │  imports dashboards/aeon-metrics.json
│  (monitoring/    │  loads alertmanager notifications
│   grafana/)      │
└──────────────────
```

### Metrics pipeline

- **AEON kernel** (`aeon_server.py`) exposes `/metrics` in Prometheus text format (Content-Type `text/plain; version=0.0.4`).
- **Prometheus** scrapes `/metrics` every 15 seconds.
- **Recording rules** pre-compute rates and latency percentiles.
- **Alert rules** fire when error rate, latency, or job queue depth exceeds thresholds.
- **Grafana** visualizes the metrics using `monitoring/grafana/aeon-metrics.json`.

### Key metrics exposed by AEON

| Metric | Type | Description |
|---|---|---|
| `aeon_http_requests_total` | Counter | HTTP requests by `method`, `path`, `status` |
| `aeon_http_request_duration_seconds` | Histogram | Request latency by `method`, `path` |
| `aeon_chat_requests_total` | Counter | Total `/chat` requests |
| `aeon_app_chat_requests_total` | Counter | Per-app chat requests |
| `aeon_agent_ticks_total` | Counter | Per-app agent ticks |
| `aeon_agent_reflections_total` | Counter | Per-app agent reflections |
| `aeon_workflow_runs_total` | Counter | Workflow runs by `workflow_id`, `ok` |
| `aeon_swarm_runs_total` | Counter | Swarm runs by `ok` |
| `aeon_integration_runs_total` | Counter | Integration runs by `integration_id`, `ok` |
| `aeon_proxy_requests_total` | Counter | Proxy requests by `integration_id`, `ok` |
| `aeon_webhook_deliveries_total` | Counter | Webhook deliveries by `verified` |
| `aeon_agents_loaded` | Gauge | Currently loaded agents |
| `aeon_job_queue_size` | Gauge | Async job queue size |

## Quick start

### Option A: One-command Docker Compose stack

```bash
cd monitoring
docker compose up --build
```

This starts four services:

| Service | URL | Notes |
|---|---|---|
| AEON kernel | http://localhost:5000 | Built from the project root |
| Prometheus | http://localhost:9090 | Scrapes `aeon-server:5000/metrics`, forwards alerts to Alertmanager |
| Alertmanager | http://localhost:9093 | Routes alerts to email and Slack |
| Grafana | http://localhost:3000 | Default login `admin` / `admin`, dashboard auto-imported |

To stop:

```bash
docker compose down
```

To stop and remove volumes:

```bash
docker compose down -v
```

#### Alertmanager notifications

To enable email and Slack notifications, copy the example env file and fill in your credentials:

```bash
cp monitoring/alertmanager/dotenv.example monitoring/.env
# Edit monitoring/.env with your SMTP and Slack webhook details
```

The `alertmanager` service reads these variables from `monitoring/.env` and passes them into `monitoring/alertmanager/alertmanager.yml`.

| Variable | Purpose |
|---|---|
| `ALERTMANAGER_SMTP_HOST` | SMTP server host:port |
| `ALERTMANAGER_SMTP_FROM` | From address for email alerts |
| `ALERTMANAGER_SMTP_USERNAME` | SMTP username |
| `ALERTMANAGER_SMTP_PASSWORD` | SMTP password |
| `ALERTMANAGER_EMAIL_TO` | Default email recipient |
| `ALERTMANAGER_SLACK_WEBHOOK_URL` | Slack incoming webhook URL |
| `ALERTMANAGER_SLACK_CHANNEL` | Slack channel to post to |

Do not commit `monitoring/.env` to version control.

### Option B: Manual local setup

#### 1. Start the AEON kernel

```bash
python aeon_server.py
# or
AEON_PYTHON_PORT=5000 python aeon_server.py
```

Verify metrics are available:

```bash
curl http://localhost:5000/metrics
```

#### 2. Start Prometheus

```bash
cd monitoring/prometheus
prometheus --config.file=prometheus.yml
```

#### 3. Start Grafana

```bash
cd monitoring/grafana
docker run -d -p 3000:3000 -v "$PWD/aeon-metrics.json:/var/lib/grafana/dashboards/aeon-metrics.json" grafana/grafana
```

Add a Prometheus data source at `http://localhost:9090`, then import `aeon-metrics.json`.

## Alert rules

Rules are defined in `monitoring/prometheus/rules/alert-rules.yml` and loaded by `prometheus.yml`.

| Alert | Expression | Threshold |
|---|---|---|
| `AeonHighErrorRate` | `sum(rate(aeon_http_requests_total{status=~"5.."}[5m])) / sum(rate(aeon_http_requests_total[5m]))` | > 5% for 2 min |
| `AeonHighLatency` | `histogram_quantile(0.99, sum(rate(aeon_http_request_duration_seconds_bucket[5m])) by (le, method, path))` | > 1 s for 3 min |
| `AeonJobQueueDeep` | `aeon_job_queue_size` | > 50 for 5 min |
| `AeonAgentTickErrors` | `sum(rate(aeon_http_requests_total{status=~"5..", path=~"/apps/.*/tick"}[5m]))` | > 0.1/sec for 2 min |

## Runbook

### AeonHighErrorRate

**Symptom:** More than 5% of HTTP requests to the AEON kernel are returning 5xx.

**Investigate:**

1. Check the AEON kernel logs for stack traces.
2. Identify which endpoint is failing: `sum(rate(aeon_http_requests_total{status=~"5.."}[5m])) by (path)`.
3. Look for recent deployments or configuration changes.
4. Check `/health` and `/ready` to confirm the service is running.

**Mitigate:**

1. Restart the AEON kernel if it is in a bad state.
2. If a specific app is failing, restart that agent context (POST `/apps/<app_id>/reflect` or restart the process).
3. If the error is persistent, roll back to the last known good commit.

### AeonHighLatency

**Symptom:** P99 HTTP latency is above 1 second.

**Investigate:**

1. Identify slow endpoints: `histogram_quantile(0.99, sum(rate(aeon_http_request_duration_seconds_bucket[5m])) by (le, path))`.
2. Check if the slow path is `/chat`, `/apps/<app_id>/tick`, or RAG queries.
3. Review the job queue size and agent tick counters.
4. Check underlying LLM provider latency or Hugging Face model loading times.

**Mitigate:**

1. If `/chat` is slow, consider switching to a faster LLM provider or using the TypeScript bridge.
2. If a specific app is slow, reduce the complexity of the query or lower the `top_k` for RAG.
3. Scale horizontally or increase the rate limit if the kernel is overloaded.
4. Restart the kernel to clear any stuck agents.

### AeonJobQueueDeep

**Symptom:** The async job queue has more than 50 jobs pending for 5 minutes.

**Investigate:**

1. Check the queue size trend: `aeon_job_queue_size`.
2. Compare with agent tick rate: `sum(rate(aeon_agent_ticks_total[1m]))`.
3. Identify if workers are stuck or slow.

**Mitigate:**

1. Restart the AEON kernel to drain stuck workers.
2. Increase the number of worker threads in `aeon_server.py` (`JobQueue(workers=...)`).
3. Reduce the volume of async jobs submitted by clients.
4. Check for downstream dependencies (LLM, integrations) that may be slow.

### AeonAgentTickErrors

**Symptom:** Agent tick endpoints are returning errors at more than 0.1 per second.

**Investigate:**

1. Filter by app: `sum(rate(aeon_http_requests_total{status=~"5..", path=~"/apps/.*/tick"}[5m])) by (path)`.
2. Check AEON kernel logs for the specific error.
3. Verify the app/agent context is loaded correctly.

**Mitigate:**

1. Restart the failing agent by sending a `/reflect` or recreating the app context.
2. If the issue persists, restart the AEON kernel.
3. Check the `ReflectiveAgent` code and recent changes to `aeon.py`.

## Recording rules

Recording rules pre-compute frequently used queries. They live in `monitoring/prometheus/rules/recording-rules.yml`.

Examples:

- `aeon:http_requests_rate_1m`
- `aeon:http_request_latency_p99_5m`
- `aeon:agent_tick_rate_1m`
- `aeon:chat_requests_rate_1m`

## Testing Alertmanager

Two lightweight tests live in `monitoring/tests/`:

| Test | File | What it checks |
|---|---|---|
| Config unit test | `tests/test_alertmanager_config.py` | YAML structure, receivers, routes, templates, inhibit rules |
| Routing smoke test | `tests/test_alertmanager_smoke.py` | Starts Alertmanager in Docker, sends a test alert, and verifies grouping via the API |

Run the config test (no Docker required):

```bash
cd monitoring
python -m unittest discover -s tests -v
```

Run the smoke test. It first tries to use a local Alertmanager binary at `/tmp/alertmanager-0.27.0.linux-amd64/alertmanager`; if that is not present it falls back to Docker (which may pull the Alertmanager image):

```bash
cd monitoring
python -m unittest tests.test_alertmanager_smoke -v
```

To force a specific binary path:

```bash
AEON_ALERTMANAGER_BINARY=/usr/local/bin/alertmanager \
    python -m unittest tests.test_alertmanager_smoke -v
```

The smoke test:
- Resolves all `${VAR:-default}` placeholders in the committed config to their defaults.
- Substitutes a non-functional Slack URL so no real notifications are sent.
- Starts Alertmanager on an ephemeral port.
- Sends a synthetic critical alert to `/api/v2/alerts`.
- Polls `/api/v2/alerts/groups` to confirm the alert is routed to the `critical` receiver and grouped by `alertname`, `severity`, and `service`.

### Prometheus-to-Alertmanager end-to-end test

`tests/test_prometheus_alertmanager_e2e.py` starts a real Prometheus instance and a real Alertmanager instance, evaluates an always-firing rule against Prometheus's self-scrape target, and verifies that the alert is received and routed by Alertmanager. It runs with the local binaries in CI and falls back to Docker when available.

## Security notes

- The `/metrics` endpoint is intentionally **not** rate-limited so Prometheus can scrape it reliably.
- Do not expose `/metrics` to the public internet without authentication.
- In production, run Prometheus and the AEON kernel in the same private network or use a reverse proxy with authentication.
- Metric label values are sanitized to prevent Prometheus exposition format injection.

## Troubleshooting

### Prometheus cannot scrape AEON

- Verify the AEON kernel is running: `curl http://localhost:5000/health`.
- Verify `/metrics` returns Prometheus text: `curl -H "Accept: text/plain" http://localhost:5000/metrics`.
- Check that `prometheus.yml` points to the correct host/port.

### No data in Grafana

- Confirm Prometheus data source is configured and healthy.
- Check that the dashboard is using the `prometheus_datasource` variable.
- Verify the recording rules have been loaded.

## References

- [Prometheus documentation](https://prometheus.io/docs/introduction/overview/)
- [Grafana documentation](https://grafana.com/docs/grafana/latest/)
- [Prometheus exposition format](https://prometheus.io/docs/instrumenting/exposition_formats/)
