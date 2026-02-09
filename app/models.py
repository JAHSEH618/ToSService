"""
Pydantic models for request validation and response serialization.
"""

from datetime import datetime
from typing import Generic, TypeVar, Optional
from pydantic import BaseModel, Field
from enum import Enum


# Generic type for response data
T = TypeVar("T")


class ImageFormat(str, Enum):
    """Supported image formats."""
    JPEG = "jpeg"
    PNG = "png"
    WEBP = "webp"


# ============== Request Models ==============

class Base64UploadRequest(BaseModel):
    """Request model for Base64 image upload."""
    
    image_base64: str = Field(
        ...,
        description="Base64 encoded image data (without data:image/...;base64, prefix)"
    )
    format: ImageFormat = Field(
        default=ImageFormat.JPEG,
        description="Image format: jpeg, png, or webp"
    )
    prefix: str = Field(
        default="generated/",
        description="Storage path prefix"
    )
    quality: int = Field(
        default=90,
        ge=1,
        le=100,
        description="JPEG compression quality (1-100)"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "image_base64": "iVBORw0KGgo...",
                "format": "jpeg",
                "prefix": "generated/",
                "quality": 90
            }
        }
    }


# ============== Response Models ==============

class UploadResult(BaseModel):
    """Result data for successful upload."""
    
    public_url: str = Field(..., description="Public access URL")
    object_key: str = Field(..., description="TOS object key")
    etag: str = Field(..., description="ETag checksum value")
    size_bytes: int = Field(..., description="File size in bytes")
    content_type: str = Field(..., description="MIME type")
    upload_time: datetime = Field(..., description="Upload timestamp")


class ApiResponse(BaseModel, Generic[T]):
    """Unified API response format."""
    
    success: bool = Field(..., description="Whether the request was successful")
    code: int = Field(..., description="Business code")
    message: str = Field(..., description="Response message")
    data: Optional[T] = Field(default=None, description="Response data")


class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    tos_connection: str = Field(..., description="TOS connection status")
    timestamp: datetime = Field(..., description="Current timestamp")


# ============== Error Codes ==============

class ErrorCode:
    """Error code definitions."""
    
    SUCCESS = 0
    INVALID_FILE_FORMAT = 40001
    FILE_SIZE_EXCEEDED = 40002
    BASE64_DECODE_FAILED = 40003
    MISSING_API_KEY = 40101
    INVALID_API_KEY = 40102
    TOS_UPLOAD_FAILED = 50001
    INTERNAL_ERROR = 50002
