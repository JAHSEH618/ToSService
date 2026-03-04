"""
Custom exception handlers for the TOS Upload Service.
All handlers now log the error details before returning the JSON response.
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse

from .models import ApiResponse, ErrorCode
from .logging_config import get_logger


logger = get_logger("tos_upload.exception")


# ============== Custom Exceptions ==============

class TosUploadException(Exception):
    """Base exception for TOS upload errors."""

    def __init__(self, code: int, message: str, status_code: int = 500):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class InvalidFileFormatError(TosUploadException):
    """Raised when file format is not supported."""

    def __init__(self, message: str = "Invalid file format. Supported: JPEG, PNG, WEBP"):
        super().__init__(
            code=ErrorCode.INVALID_FILE_FORMAT,
            message=message,
            status_code=400,
        )


class FileSizeExceededError(TosUploadException):
    """Raised when file size exceeds the limit."""

    def __init__(self, max_size_mb: int):
        super().__init__(
            code=ErrorCode.FILE_SIZE_EXCEEDED,
            message=f"File size exceeds maximum limit of {max_size_mb}MB",
            status_code=400,
        )


class Base64DecodeError(TosUploadException):
    """Raised when Base64 decoding fails."""

    def __init__(self, message: str = "Failed to decode Base64 image data"):
        super().__init__(
            code=ErrorCode.BASE64_DECODE_FAILED,
            message=message,
            status_code=400,
        )


class TosUploadError(TosUploadException):
    """Raised when TOS upload fails."""

    def __init__(self, message: str = "Failed to upload to TOS"):
        super().__init__(
            code=ErrorCode.TOS_UPLOAD_FAILED,
            message=message,
            status_code=500,
        )


class AuthenticationError(TosUploadException):
    """Raised for authentication failures."""

    def __init__(
        self,
        code: int = ErrorCode.MISSING_API_KEY,
        message: str = "Authentication failed",
    ):
        super().__init__(
            code=code,
            message=message,
            status_code=401,
        )


# ============== Exception Handlers ==============

async def tos_exception_handler(request: Request, exc: TosUploadException) -> JSONResponse:
    """Handle TosUploadException — log as warning with request context."""
    logger.warning(
        "Business exception  path=%s  method=%s  status=%d  code=%d  message=%s",
        request.url.path,
        request.method,
        exc.status_code,
        exc.code,
        exc.message,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse(
            success=False,
            code=exc.code,
            message=exc.message,
            data=None,
        ).model_dump(),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTPException — log as warning with request context."""
    logger.warning(
        "HTTP exception  path=%s  method=%s  status=%d  detail=%s",
        request.url.path,
        request.method,
        exc.status_code,
        exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ApiResponse(
            success=False,
            code=exc.status_code * 100,
            message=exc.detail,
            data=None,
        ).model_dump(),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions — log as ERROR with full traceback."""
    logger.error(
        "Unhandled exception  path=%s  method=%s  error=%s",
        request.url.path,
        request.method,
        str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content=ApiResponse(
            success=False,
            code=ErrorCode.INTERNAL_ERROR,
            message="Internal server error",
            data=None,
        ).model_dump(),
    )
