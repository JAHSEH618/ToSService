FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables for Python optimization
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=2 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Uvicorn performance settings
    UVICORN_WORKERS=4 \
    UVICORN_LOOP=uvloop \
    UVICORN_HTTP=httptools

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create logs directory
RUN mkdir -p /app/logs

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 10086

# Health check
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:10086/api/v1/health/live || exit 1

# Production startup with multiple workers and performance optimizations
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
