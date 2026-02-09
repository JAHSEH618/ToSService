"""
FastAPI dependency injection functions.
"""

from fastapi import Header, HTTPException
from fastapi.security import APIKeyHeader

from .config import get_settings
from .models import ErrorCode
from .exceptions import AuthenticationError


# API Key header scheme
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(x_api_key: str = Header(None, alias="X-API-Key")) -> str:
    """
    Verify the API key from request header.
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Returns:
        The validated API key
        
    Raises:
        AuthenticationError: If API key is missing or invalid
    """
    if x_api_key is None:
        raise AuthenticationError(
            code=ErrorCode.MISSING_API_KEY,
            message="Missing API key. Please provide X-API-Key header."
        )
    
    settings = get_settings()
    
    if x_api_key != settings.api_key:
        raise AuthenticationError(
            code=ErrorCode.INVALID_API_KEY,
            message="Invalid API key."
        )
    
    return x_api_key
