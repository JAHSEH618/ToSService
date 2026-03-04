"""
Health check router with caching for performance.
Includes logging for connection status and cache hits.
"""

import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter

from ..config import get_settings
from ..models import HealthResponse
from ..tos_client import get_tos_client
from ..logging_config import get_logger


logger = get_logger("tos_upload.health")

router = APIRouter(prefix="/api/v1", tags=["Health"])

# Cache for health check (avoid hitting TOS on every request)
_health_cache: dict[str, tuple[bool, float]] = {}
HEALTH_CACHE_TTL = 30.0  # Cache health status for 30 seconds


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint for container orchestration and load balancer probing.

    Optimizations:
    - Cached TOS connection status (30s TTL)
    - Async connection check

    Returns:
        HealthResponse with service status and TOS connection status.
    """
    settings = get_settings()
    tos_client = get_tos_client()

    # Check cached health status
    current_time = asyncio.get_event_loop().time()
    cache_entry = _health_cache.get("tos_connection")

    if cache_entry and (current_time - cache_entry[1]) < HEALTH_CACHE_TTL:
        tos_ok = cache_entry[0]
        logger.debug(
            "Health check: using cached TOS status  tos_ok=%s  cache_age=%.1fs",
            tos_ok,
            current_time - cache_entry[1],
        )
    else:
        # Async TOS connection check
        logger.debug("Health check: querying TOS connection (cache expired or missing)")
        tos_ok = await tos_client.check_connection_async()
        _health_cache["tos_connection"] = (tos_ok, current_time)
        logger.info("Health check: TOS connection refreshed  tos_ok=%s", tos_ok)

    tos_status = "ok" if tos_ok else "error"

    if not tos_ok:
        logger.warning("Health check: TOS connection is DOWN")

    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
        tos_connection=tos_status,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/health/live")
async def liveness_probe() -> dict[str, str]:
    """
    Kubernetes liveness probe - lightweight check.
    Only checks if the service is running, not external dependencies.
    """
    logger.debug("Liveness probe: alive")
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness_probe() -> dict[str, str]:
    """
    Kubernetes readiness probe - checks if ready to accept traffic.
    Includes TOS connection check.
    """
    tos_client = get_tos_client()
    tos_ok = await tos_client.check_connection_async()

    if not tos_ok:
        logger.warning("Readiness probe FAILED: TOS connection unavailable")
        return {"status": "not_ready", "reason": "TOS connection failed"}

    logger.debug("Readiness probe: ready")
    return {"status": "ready"}
