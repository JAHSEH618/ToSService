"""
Upload router for image upload endpoints.
Optimized for high performance with async operations.
"""

from fastapi import APIRouter, Depends, UploadFile, File, Form
from typing import Optional
import asyncio

from ..config import get_settings
from ..models import (
    Base64UploadRequest,
    UploadResult,
    ApiResponse,
    ErrorCode,
    ImageFormat
)
from ..dependencies import verify_api_key
from ..tos_client import get_tos_client
from ..exceptions import InvalidFileFormatError, FileSizeExceededError


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
    description="Upload a Base64 encoded image to TOS. Suitable for mobile clients."
)
async def upload_base64(
    request: Base64UploadRequest,
    api_key: str = Depends(verify_api_key)
) -> ApiResponse[UploadResult]:
    """
    Async upload Base64 encoded image to TOS.
    
    Performance optimizations:
    - Async upload using thread pool
    - Early size validation (avoids decoding large invalid data)
    - Fast Base64 decoding
    """
    settings = get_settings()
    tos_client = get_tos_client()
    
    # Early size check (rough estimate: base64 is ~4/3 of original)
    max_base64_size = settings.max_file_size_mb * 1024 * 1024 * 4 // 3
    if len(request.image_base64) > max_base64_size:
        raise FileSizeExceededError(settings.max_file_size_mb)
    
    # Async upload to TOS
    result = await tos_client.upload_base64_async(
        base64_data=request.image_base64,
        format=request.format,
        prefix=request.prefix,
        quality=request.quality
    )
    
    return ApiResponse(
        success=True,
        code=ErrorCode.SUCCESS,
        message="Upload successful",
        data=result
    )


@router.post(
    "/image",
    response_model=ApiResponse[UploadResult],
    summary="Upload image file",
    description="Upload an image file via multipart form. Suitable for web clients."
)
async def upload_image(
    file: UploadFile = File(..., description="Image file (JPEG/PNG/WEBP, max 10MB)"),
    prefix: Optional[str] = Form(default="generated/", description="Storage path prefix"),
    quality: Optional[int] = Form(default=90, ge=1, le=100, description="JPEG compression quality"),
    api_key: str = Depends(verify_api_key)
) -> ApiResponse[UploadResult]:
    """
    Async upload image file to TOS via multipart form.
    
    Performance optimizations:
    - Async file reading
    - Streaming for large files
    - Early content-type validation
    - Async upload using thread pool
    """
    settings = get_settings()
    tos_client = get_tos_client()
    
    # Early content type validation (fail fast)
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise InvalidFileFormatError(
            f"Invalid content type: {content_type}. Supported: JPEG, PNG, WEBP"
        )
    
    # Async file reading
    file_content = await file.read()
    
    # Validate file size after reading
    max_size_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(file_content) > max_size_bytes:
        raise FileSizeExceededError(settings.max_file_size_mb)
    
    # Determine format from content type
    image_format = ALLOWED_CONTENT_TYPES[content_type]
    
    # Async upload to TOS
    result = await tos_client.upload_bytes_async(
        data=file_content,
        format=image_format,
        prefix=prefix,
        validate=True
    )
    
    return ApiResponse(
        success=True,
        code=ErrorCode.SUCCESS,
        message="Upload successful",
        data=result
    )


@router.post(
    "/batch",
    response_model=ApiResponse[list[UploadResult]],
    summary="Batch upload Base64 images",
    description="Upload multiple Base64 encoded images concurrently."
)
async def upload_batch(
    requests: list[Base64UploadRequest],
    api_key: str = Depends(verify_api_key)
) -> ApiResponse[list[UploadResult]]:
    """
    Batch upload multiple Base64 images concurrently.
    
    Performance optimizations:
    - Concurrent uploads using asyncio.gather
    - Parallel processing for multiple images
    """
    if len(requests) > 10:
        raise InvalidFileFormatError("Maximum 10 images per batch upload")
    
    settings = get_settings()
    tos_client = get_tos_client()
    max_base64_size = settings.max_file_size_mb * 1024 * 1024 * 4 // 3
    
    # Validate all sizes first (fail fast)
    for req in requests:
        if len(req.image_base64) > max_base64_size:
            raise FileSizeExceededError(settings.max_file_size_mb)
    
    # Create upload tasks
    tasks = [
        tos_client.upload_base64_async(
            base64_data=req.image_base64,
            format=req.format,
            prefix=req.prefix,
            quality=req.quality
        )
        for req in requests
    ]
    
    # Execute concurrently
    results = await asyncio.gather(*tasks)
    
    return ApiResponse(
        success=True,
        code=ErrorCode.SUCCESS,
        message=f"Successfully uploaded {len(results)} images",
        data=list(results)
    )
