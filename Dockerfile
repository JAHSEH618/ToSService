# =============================================
# Stage 1: Builder — install dependencies
# =============================================
FROM python:3.11-slim AS builder

WORKDIR /build

# Only copy requirements first (Docker layer cache optimisation)
COPY requirements.txt .

# Install to a local prefix so we can copy the result into the runtime stage
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# =============================================
# Stage 2: Runtime — minimal production image
# =============================================
FROM python:3.11-slim AS runtime

LABEL maintainer="ToSService Team"
LABEL description="High-performance TOS upload microservice"

WORKDIR /app

# ---- Environment ----
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=2 \
    PIP_NO_CACHE_DIR=1

# ---- System deps (curl for healthcheck only) ----
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# ---- Copy pre-built Python packages from builder ----
COPY --from=builder /install /usr/local

# ---- Copy application code ----
COPY app/ ./app/

# ---- Non-root user ----
RUN useradd --create-home --shell /bin/bash appuser \
    && mkdir -p /app/logs \
    && chown -R appuser:appuser /app

USER appuser

# ---- Port ----
EXPOSE 10086

# ---- Health check ----
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:10086/api/v1/health/live || exit 1

# ---- Entrypoint ----
CMD ["uvicorn", "app.main:app", \
    "--host", "0.0.0.0", \
    "--port", "10086", \
    "--workers", "4", \
    "--loop", "uvloop", \
    "--http", "httptools", \
    "--no-access-log", \
    "--limit-concurrency", "1000", \
    "--limit-max-requests", "10000", \
    "--backlog", "2048"]
