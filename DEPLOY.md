# AEON v3.0 — Deployment Guide

This document describes how to build, run, and deploy the AEON Python kernel in production.

## Quick reference

| Artifact | Purpose |
|---|---|
| `Dockerfile` | Production container image for `aeon_server.py` |
| `docker-compose.yml` | Local production-like stack (AEON + Postgres + monitoring) |
| `monitoring/docker-compose.yml` | AEON + monitoring only |
| `k8s/` | Kubernetes manifests for staging/production |
| `.github/workflows/aeon-ci.yml` | CI pipeline including Docker build + smoke test |

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `AEON_PYTHON_HOST` | No | Bind host (default `0.0.0.0`) |
| `AEON_PYTHON_PORT` | No | Bind port (default `5000`) |
| `AEON_ROOT` | No | Runtime state directory (default `/home/aeon/app/aeon_state`) |
| `AEON_LOG_LEVEL` | No | Python log level (default `INFO`) |
| `SUPABASE_URL` | Yes* | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes* | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes* | Supabase service role key |
| `HUGGINGFACE_TOKEN` | No | Required to download Qwen from Hugging Face |
| `OPENAI_API_KEY` | No | For OpenAI provider |
| `ANTHROPIC_API_KEY` | No | For Anthropic provider |
| `GH_TOKEN` | No | For GitHub integrations |

*Required for cloud persistence; the kernel can run in stub mode without them.

## Local development with Docker

### Build and run the full image (includes GPU/ML deps)

```bash
docker build -t aeon-server:latest .
docker run -p 5000:5000 aeon-server:latest
```

### Build and run the lightweight stub image

```bash
docker build --build-arg STUB_MODE=true -t aeon-server:stub .
docker run -p 5000:5000 aeon-server:stub
```

### Full local stack (AEON + Postgres + Prometheus + Alertmanager + Grafana)

```bash
docker compose up --build
```

Then open:
- AEON kernel: http://localhost:5000
- Prometheus: http://localhost:9090
- Alertmanager: http://localhost:9093
- Grafana: http://localhost:3000 (admin / admin)

## Monitoring-only stack

```bash
cd monitoring
docker compose up --build
```

## Kubernetes

1. Create the namespace and secrets:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
# Copy and edit k8s/secret.example.yaml, then apply:
kubectl apply -f k8s/secret.yaml
```

2. Deploy the application:

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

3. Verify:

```bash
kubectl -n aeon get pods
kubectl -n aeon logs -l app=aeon-server
```

## Health endpoints

| Endpoint | Use |
|---|---|
| `GET /live` | Liveness probe |
| `GET /ready` | Readiness probe + environment validation |
| `GET /health` | Basic health |
| `GET /metrics` | Prometheus metrics |

## Notes

- The full image downloads `torch` + `transformers` and can exceed 6 GB. Use `STUB_MODE=true` for CI or lightweight deployments.
- The container runs as a non-root `aeon` user.
- `/metrics` is intentionally not rate-limited; protect it at the ingress/reverse-proxy level.

## CI note

Pushing to `main` automatically triggers the `AEON CI` workflow. If GitHub Actions is ever paused due to billing, the workflow will resume once the account payment issue is resolved.
