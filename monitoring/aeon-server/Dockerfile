# Dockerfile for the AEON Python kernel used in the local monitoring stack.
# Build context: project root.

FROM python:3.10-slim

WORKDIR /app

# Install system dependencies needed by some Python packages (torch, bitsandbytes, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the AEON source code
COPY . .

EXPOSE 5000

ENV AEON_PYTHON_HOST=0.0.0.0
ENV AEON_PYTHON_PORT=5000

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -fsS http://localhost:5000/health || exit 1

CMD ["python", "aeon_server.py"]
