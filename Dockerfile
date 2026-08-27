# AEON OS — Flask Backend
# ========================
# Multi-stage Docker image for the AEON Python kernel server.
#
# Build:
#   docker build -t aeon-backend -f Dockerfile .
# Run:
#   docker run -p 5000:5000 aeon-backend
#
# Environment variables (see .env.example):
#   AEON_PYTHON_HOST       (default 0.0.0.0)
#   AEON_PYTHON_PORT       (default 5000)
#   AEON_ROOT              (default /app/state)
#   AEON_DATABASE_URL      (required — postgresql://...)
#   AEON_LLM_PROVIDER      (default stub)
#   OPENAI_API_KEY         (optional)
#   ANTHROPIC_API_KEY      (optional)
#   STRIPE_API_KEY         (optional)
#   STRIPE_WEBHOOK_SECRET  (optional)
#   HUGGINGFACE_TOKEN      (optional)

# ─── Stage 1: Build ────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install system deps needed for psycopg2 / bitsandbytes / numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ─── Stage 2: Runtime ──────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code and ordered database migrations
COPY aeon*.py requirements.txt alembic.ini ./
COPY alembic ./alembic

# Copy scripts (entrypoint + admin seeder)
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
COPY scripts/seed_admin.py /app/scripts/seed_admin.py

# Create state directory
RUN mkdir -p /app/state

# Healthcheck follows the same port precedence as aeon_server.py:
# AEON_PYTHON_PORT -> PORT -> 5000.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f "http://localhost:${AEON_PYTHON_PORT:-${PORT:-5000}}/health" || exit 1

EXPOSE 5000

ENTRYPOINT ["docker-entrypoint.sh"]
