"""
Upload router for image upload endpoints.
Optimized for high performance with async operations.
Includes detailed business-level logging for every upload request.
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form
from typing import Optional
import asyncio

from ..config import get_settings
from ..logging_config import get_logger
from ..models import (
    Base64UploadRequest,
    UploadResult,
    ApiResponse,
    ErrorCode,
    ImageFormat,
)
from ..dependencies import verify_api_key
from ..tos_client import get_tos_client
from ..exceptions import InvalidFileFormatError, FileSizeExceededError


# Logger
logger = get_logger("tos_upload.upload")

router = APIRouter(prefix="/api/v1/upload", tags=["Upload"])


# Allowed content types (use frozenset for O(1) lookup)
ALLOWED_CONTENT_TYPES: dict[str, ImageFormat] = {
    "image/jpeg": ImageFormat.JPEG,
    "image/jpg": ImageFormat.JPEG,
    "image/png": ImageFormat.PNG,
    "image/webp": ImageFormat.WEBP,
}


@router.post(
    "/base64",
    response_model=ApiResponse[UploadResult],
    summary="Upload Base64 encoded image",
    description="Upload a Base64 encoded image to TOS. Suitable for mobile clients.",
)
async def upload_base64(
    request: Base64UploadRequest,
    api_key: str = Depends(verify_api_key),
) -> ApiResponse[UploadResult]:
    """
    Async upload Base64 encoded image to TOS.
    """
    settings = get_settings()
    tos_client = get_tos_client()

    b64_len = len(request.image_base64)
    logger.info(
        "Base64 upload request received  format=%s  prefix=%s  quality=%d  b64_len=%d",
        request.format.value,
        request.prefix,
        request.quality,
        b64_len,
    )

    # Early size check (rough estimate: base64 is ~4/3 of original)
    max_base64_size = settings.max_file_size_mb * 1024 * 1024 * 4 // 3
    if b64_len > max_base64_size:
        logger.warning(
            "Base64 upload rejected: size exceeded  b64_len=%d  max=%d",
            b64_len,
            max_base64_size,
        )
        raise FileSizeExceededError(settings.max_file_size_mb)

    # Async upload to TOS
    result = await tos_client.upload_base64_async(
        base64_data=request.image_base64,
        format=request.format,
        prefix=request.prefix,
        quality=request.quality,
    )

    logger.info(
        "Base64 upload completed  url=%s  size=%d bytes",
        result.public_url,
        result.size_bytes,
    )

    return ApiResponse(
        success=True,
        code=ErrorCode.SUCCESS,
        message="Upload successful",
        data=result,
    )


@router.post(
    "/image",
    response_model=ApiResponse[UploadResult],
    summary="Upload image file",
    description="Upload an image file via multipart form. Suitable for web clients.",
)
async def upload_image(
    file: UploadFile = File(..., description="Image file (JPEG/PNG/WEBP, max 10MB)"),
    prefix: Optional[str] = Form(
        default="generated/", description="Storage path prefix"
    ),
    quality: Optional[int] = Form(
        default=90, ge=1, le=100, description="JPEG compression quality"
    ),
    api_key: str = Depends(verify_api_key),
) -> ApiResponse[UploadResult]:
    """
    Async upload image file to TOS via multipart form.
    """
    settings = get_settings()
    tos_client = get_tos_client()

    # Early content type validation (fail fast)
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "unknown"

    logger.info(
        "Image upload request received  filename=%s  content_type=%s  prefix=%s  quality=%s",
        filename,
        content_type,
        prefix,
        quality,
    )

    if content_type not in ALLOWED_CONTENT_TYPES:
        logger.warning(
            "Image upload rejected: invalid content type  filename=%s  content_type=%s",
            filename,
            content_type,
        )
        raise InvalidFileFormatError(
            f"Invalid content type: {content_type}. Supported: JPEG, PNG, WEBP"
        )

    # Async file reading
    file_content = await file.read()
    file_size = len(file_content)

    logger.info(
        "Image file read  filename=%s  size=%d bytes (%.2f KB)",
        filename,
        file_size,
        file_size / 1024,
    )

    # Validate file size after reading
    max_size_bytes = settings.max_file_size_mb * 1024 * 1024
    if file_size > max_size_bytes:
        logger.warning(
            "Image upload rejected: size exceeded  filename=%s  size=%d  max=%d",
            filename,
            file_size,
            max_size_bytes,
        )
        raise FileSizeExceededError(settings.max_file_size_mb)

    # Determine format from content type
    image_format = ALLOWED_CONTENT_TYPES[content_type]

    # Async upload to TOS
    result = await tos_client.upload_bytes_async(
        data=file_content,
        format=image_format,
        prefix=prefix,
        validate=True,
    )

    logger.info(
        "Image upload completed  filename=%s  url=%s  size=%d bytes",
        filename,
        result.public_url,
        result.size_bytes,
    )

    return ApiResponse(
        success=True,
        code=ErrorCode.SUCCESS,
        message="Upload successful",
        data=result,
    )


@router.post(
    "/batch",
    response_model=ApiResponse[list[UploadResult]],
    summary="Batch upload Base64 images",
    description="Upload multiple Base64 encoded images concurrently.",
)
async def upload_batch(
    requests: list[Base64UploadRequest],
    api_key: str = Depends(verify_api_key),
) -> ApiResponse[list[UploadResult]]:
    """
    Batch upload multiple Base64 images concurrently.
    """
    batch_size = len(requests)
    logger.info(
        "Batch upload request received  count=%d  formats=%s",
        batch_size,
        [r.format.value for r in requests],
    )

    if batch_size > 10:
        logger.warning("Batch upload rejected: too many images  count=%d  max=10", batch_size)
        raise InvalidFileFormatError("Maximum 10 images per batch upload")

    settings = get_settings()
    tos_client = get_tos_client()
    max_base64_size = settings.max_file_size_mb * 1024 * 1024 * 4 // 3

    # Validate all sizes first (fail fast)
    for i, req in enumerate(requests):
        if len(req.image_base64) > max_base64_size:
            logger.warning(
                "Batch upload rejected: image #%d size exceeded  b64_len=%d  max=%d",
                i,
                len(req.image_base64),
                max_base64_size,
            )
            raise FileSizeExceededError(settings.max_file_size_mb)

    # Create upload tasks
    tasks = [
        tos_client.upload_base64_async(
            base64_data=req.image_base64,
            format=req.format,
            prefix=req.prefix,
            quality=req.quality,
        )
        for req in requests
    ]

    # Execute concurrently
    results = await asyncio.gather(*tasks)

    logger.info(
        "Batch upload completed  count=%d  urls=%s",
        len(results),
        [r.public_url for r in results],
    )

    return ApiResponse(
        success=True,
        code=ErrorCode.SUCCESS,
        message=f"Successfully uploaded {len(results)} images",
        data=list(results),
    )
