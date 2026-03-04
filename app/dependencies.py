"""
FastAPI dependency injection functions.
"""

from fastapi import Header, HTTPException, Request
from fastapi.security import APIKeyHeader

from .config import get_settings
from .models import ErrorCode
from .exceptions import AuthenticationError
from .logging_config import get_logger


logger = get_logger("tos_upload.auth")


# API Key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    request: Request,
    x_api_key: str = Header(None, alias="X-API-Key"),
) -> str:
    """
    Verify the API key from request header.

    Args:
        request: The incoming request (used for logging client IP)
        x_api_key: API key from X-API-Key header

    Returns:
        The validated API key

    Raises:
        AuthenticationError: If API key is missing or invalid
    """
    client_ip = request.client.host if request.client else "unknown"

    if x_api_key is None:
        logger.warning(
            "Authentication failed: missing API key  client=%s  path=%s",
            client_ip,
            request.url.path,
        )
        raise AuthenticationError(
            code=ErrorCode.MISSING_API_KEY,
            message="Missing API key. Please provide X-API-Key header.",
        )

    settings = get_settings()

    if x_api_key != settings.api_key:
        logger.warning(
            "Authentication failed: invalid API key  client=%s  path=%s  key_prefix=%s***",
            client_ip,
            request.url.path,
            x_api_key[:4] if len(x_api_key) >= 4 else "****",
        )
        raise AuthenticationError(
            code=ErrorCode.INVALID_API_KEY,
            message="Invalid API key.",
        )

    logger.debug(
        "Authentication successful  client=%s  path=%s",
        client_ip,
        request.url.path,
    )
    return x_api_key
