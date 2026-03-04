"""
TOS Upload Service - FastAPI Application Entry Point

A high-performance containerized microservice for uploading images to Volcano Cloud TOS.

Features:
- Async request handling
- Thread pool for TOS SDK operations
- Connection pooling
- Structured logging with request ID tracing
- Graceful shutdown
"""

import logging
import platform
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .config import get_settings
from .logging_config import (
    setup_logging,
    get_logger,
    generate_request_id,
    set_request_id,
)
from .exceptions import (
    TosUploadException,
    tos_exception_handler,
    http_exception_handler,
    generic_exception_handler,
)
from .routers import health, upload
from .tos_client import shutdown_executor


# Initialize loggers
logger = get_logger("tos_upload.main")
access_logger = get_logger("tos_upload.access")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler for startup and shutdown events.
    """
    # ---- Startup ----
    settings = get_settings()
    logger.info("=" * 70)
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Python : {platform.python_version()}  |  PID: {os.getpid()}")
    logger.info(f"OS     : {platform.system()} {platform.release()}")
    logger.info(f"Port   : {settings.service_port}")
    logger.info(f"TOS Endpoint   : {settings.tos_endpoint}")
    logger.info(f"TOS Region     : {settings.tos_region}")
    logger.info(f"TOS Bucket     : {settings.tos_bucket_name}")
    logger.info(f"TOS Domain     : {settings.tos_public_domain}")
    logger.info(f"Max file size  : {settings.max_file_size_mb} MB")
    logger.info(f"Log level      : {settings.log_level}")
    logger.info("Thread pool executor initialized with 10 workers")
    logger.info("=" * 70)

    yield

    # ---- Shutdown ----
    logger.info("Shutting down TOS Upload Service...")
    shutdown_executor()
    logger.info("Thread pool executor shutdown complete")
    logger.info("Service stopped  (PID: %s)", os.getpid())


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="""
## TOS Upload Service

A high-performance containerized microservice for uploading images to Volcano Cloud TOS.

### Features

- **Async Operations**: Non-blocking request handling
- **Thread Pool**: Parallel TOS SDK operations
- **Connection Pooling**: Reused TOS connections
- **Batch Upload**: Concurrent multi-image uploads
- **Structured Logging**: Request ID tracing, file and console output
- **GZip Compression**: Compressed API responses

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/upload/base64` | Upload Base64 encoded image |
| `POST /api/v1/upload/image` | Upload image file (multipart) |
| `POST /api/v1/upload/batch` | Batch upload multiple images |
| `GET /api/v1/health` | Health check with TOS status |
| `GET /api/v1/health/live` | Kubernetes liveness probe |
| `GET /api/v1/health/ready` | Kubernetes readiness probe |

### Authentication

All upload endpoints require `X-API-Key` header.
        """,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # GZip compression for responses > 1KB
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register exception handlers
    app.add_exception_handler(TosUploadException, tos_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Register routers
    app.include_router(health.router)
    app.include_router(upload.router)

    return app


# Create application instance
app = create_app()


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Log all incoming requests with:
    - Auto-generated Request ID (set in contextvars & response header)
    - Timing information
    - Client IP, User-Agent, Content-Length
    - Adaptive log level based on response status code
    """
    # Generate & propagate request ID
    rid = generate_request_id()
    set_request_id(rid)

    start_time = time.time()

    # Collect request metadata
    client_ip = request.client.host if request.client else "unknown"
    method = request.method
    path = request.url.path
    query = str(request.query_params) if request.query_params else ""
    user_agent = request.headers.get("user-agent", "-")
    content_length = request.headers.get("content-length", "0")

    access_logger.info(
        ">>> %s %s%s  client=%s  ua=%s  content_length=%s",
        method,
        path,
        f"?{query}" if query else "",
        client_ip,
        user_agent,
        content_length,
    )

    # Process request
    response = await call_next(request)

    # Timing
    duration_ms = (time.time() - start_time) * 1000

    # Attach request ID to response
    response.headers["X-Request-ID"] = rid

    # Adaptive log level
    status = response.status_code
    if status >= 500:
        log_fn = access_logger.error
    elif status >= 400:
        log_fn = access_logger.warning
    else:
        log_fn = access_logger.info

    log_fn(
        "<<< %s %s  status=%d  duration=%.2fms  client=%s",
        method,
        path,
        status,
        duration_ms,
        client_ip,
    )

    return response


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with service information."""
    settings = get_settings()
    logger.debug("Root endpoint accessed")
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "port": settings.service_port,
        "docs": "/docs",
        "health": "/api/v1/health",
        "features": [
            "async_operations",
            "thread_pool_executor",
            "connection_pooling",
            "batch_upload",
            "gzip_compression",
            "structured_logging",
            "request_id_tracing",
        ],
    }
