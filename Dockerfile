# AEON Python Kernel — Production Dockerfile
#
# Build (full image, includes torch/transformers for GPU inference):
#   docker build -t aeon-server:latest .
#
# Build (stub mode, lightweight, no GPU deps):
#   docker build --build-arg STUB_MODE=true -t aeon-server:stub .
#
# Run:
#   docker run -p 5000:5000 aeon-server:latest

FROM python:3.10-slim

# Install system dependencies required by Python packages and health checks.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        libgomp1 && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user for running the AEON kernel.
RUN useradd -m -s /bin/bash aeon
WORKDIR /home/aeon/app

# Ensure pip user bin is available.
ENV PATH="/home/aeon/.local/bin:${PATH}"

# Copy and install Python requirements.  We install as root first so compile-time
# deps work, then switch to the aeon user for runtime.
COPY --chown=aeon:aeon requirements.txt .

# Optional stub mode: strip heavy ML/GPU packages for a smaller, faster image.
ARG STUB_MODE=false
RUN if [ "$STUB_MODE" = "true" ]; then \
      sed -i '/^[[:space:]]*torch/d; /^[[:space:]]*transformers/d; /^[[:space:]]*bitsandbytes/d; /^[[:space:]]*accelerate/d; /^[[:space:]]*sentence-transformers/d' requirements.txt; \
    fi

# Install dependencies + gunicorn production server.
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copy application source and set permissions.
COPY --chown=aeon:aeon . .
RUN chmod +x docker-entrypoint.sh

# Switch to non-root user for runtime.
USER aeon

# Default environment.
ENV AEON_PYTHON_HOST=0.0.0.0
ENV AEON_PYTHON_PORT=5000
ENV AEON_ROOT=/home/aeon/app/aeon_state

EXPOSE 5000

# Health check against the dedicated liveness endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS http://127.0.0.1:5000/live || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "aeon_server:app"]
