"""
Health check router with caching for performance.
"""

import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter

from ..config import get_settings
from ..models import HealthResponse
from ..tos_client import get_tos_client


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
    else:
        # Async TOS connection check
        tos_ok = await tos_client.check_connection_async()
        _health_cache["tos_connection"] = (tos_ok, current_time)
    
    tos_status = "ok" if tos_ok else "error"
    
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
        tos_connection=tos_status,
        timestamp=datetime.now(timezone.utc)
    )


@router.get("/health/live")
async def liveness_probe() -> dict[str, str]:
    """
    Kubernetes liveness probe - lightweight check.
    Only checks if the service is running, not external dependencies.
    """
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
        return {"status": "not_ready", "reason": "TOS connection failed"}
    
    return {"status": "ready"}
