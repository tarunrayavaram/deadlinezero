# ============================================================
# DeadlineZero – Production Dockerfile
# Multi-stage build: minimises final image size
# Compatible with Google Cloud Run
# ============================================================

# ─── Stage 1: Builder ────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─── Stage 2: Runtime ────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Security: run as non-root user
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Cloud Run injects PORT env var; default to 8000
ENV PORT=8000
ENV APP_HOST=0.0.0.0
ENV APP_ENV=production
ENV APP_DEBUG=false

EXPOSE 8000

# Health check for Cloud Run
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

# Use exec form to handle signals properly
CMD ["sh", "-c", "uvicorn app.main:app --host $APP_HOST --port $PORT --workers 1 --log-level info"]
