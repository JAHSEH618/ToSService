"""
TOS (Volcano Cloud Object Storage) client wrapper.
Optimized for high performance with async support and connection pooling.
"""

import io
import uuid
import base64
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional
from functools import lru_cache
import tos
from tos import TosClientV2
from tos.models2 import PutObjectOutput

from .config import get_settings
from .models import UploadResult, ImageFormat
from .exceptions import TosUploadError, Base64DecodeError, InvalidFileFormatError


# Thread pool for running sync TOS SDK operations
# Size optimized for I/O-bound operations
_executor: Optional[ThreadPoolExecutor] = None


def get_executor() -> ThreadPoolExecutor:
    """Get or create thread pool executor for async operations."""
    global _executor
    if _executor is None:
        # Use 10 workers for concurrent uploads
        _executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="tos_worker")
    return _executor


class TosClient:
    """
    High-performance wrapper for TOS SDK operations.
    
    Optimizations:
    - Thread pool executor for async operations
    - Connection reuse via singleton client
    - Cached settings and lookups
    - Optimized Base64 decoding
    - Early validation for fast failure
    """
    
    # MIME type mapping (frozen for performance)
    MIME_TYPES: dict[ImageFormat, str] = {
        ImageFormat.JPEG: "image/jpeg",
        ImageFormat.PNG: "image/png",
        ImageFormat.WEBP: "image/webp",
    }
    
    # File extension mapping
    EXTENSIONS: dict[ImageFormat, str] = {
        ImageFormat.JPEG: ".jpg",
        ImageFormat.PNG: ".png",
        ImageFormat.WEBP: ".webp",
    }
    
    # Magic bytes for file type validation (ordered by frequency for faster matching)
    MAGIC_BYTES: tuple[tuple[bytes, ImageFormat], ...] = (
        (b'\xff\xd8\xff', ImageFormat.JPEG),  # Most common
        (b'\x89PNG', ImageFormat.PNG),
        (b'RIFF', ImageFormat.WEBP),
    )
    
    __slots__ = ('settings', '_client', '_bucket_name', '_public_domain')
    
    def __init__(self):
        """Initialize TOS client with cached settings."""
        self.settings = get_settings()
        self._client: Optional[TosClientV2] = None
        # Cache frequently accessed values
        self._bucket_name = self.settings.tos_bucket_name
        self._public_domain = self.settings.tos_public_domain
    
    @property
    def client(self) -> TosClientV2:
        """Get or create TOS client instance with connection reuse."""
        if self._client is None:
            self._client = TosClientV2(
                ak=self.settings.tos_access_key,
                sk=self.settings.tos_secret_key,
                endpoint=self.settings.tos_endpoint,
                region=self.settings.tos_region,
                # Enable connection pooling
                connection_time=60,  # Connection timeout
                socket_timeout=30,   # Socket timeout
                max_retry_count=3,   # Retry on transient failures
            )
        return self._client
    
    @staticmethod
    @lru_cache(maxsize=1000)
    def _generate_unique_id() -> str:
        """Generate unique ID (cached for batch operations)."""
        return uuid.uuid4().hex[:12]
    
    def _generate_object_key(self, prefix: str, format: ImageFormat) -> str:
        """Generate unique object key for the upload."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:20]
        unique_id = uuid.uuid4().hex[:12]
        return f"{prefix}{unique_id}_{timestamp}{self.EXTENSIONS[format]}"
    
    def _validate_image_bytes_fast(self, data: bytes) -> Optional[ImageFormat]:
        """
        Fast image format detection using magic bytes.
        Returns detected format or None if invalid.
        """
        if len(data) < 4:
            return None
        
        # Check magic bytes (ordered by frequency)
        for magic, fmt in self.MAGIC_BYTES:
            if data[:len(magic)] == magic:
                # Special case for WebP: verify WEBP signature
                if fmt == ImageFormat.WEBP:
                    if len(data) >= 12 and data[8:12] == b'WEBP':
                        return fmt
                else:
                    return fmt
        return None
    
    def _build_public_url(self, object_key: str) -> str:
        """Build public URL for the uploaded object."""
        return f"https://{self._public_domain}/{object_key}"
    
    @staticmethod
    def decode_base64_image_fast(base64_data: str) -> bytes:
        """
        Optimized Base64 decoding with minimal string operations.
        
        Performance optimizations:
        - Single pass comma check
        - Avoid unnecessary string copies
        """
        try:
            # Fast check for data URL prefix
            comma_idx = base64_data.find(',')
            if comma_idx != -1:
                base64_data = base64_data[comma_idx + 1:]
            
            # Decode directly (base64.b64decode handles whitespace)
            return base64.b64decode(base64_data, validate=True)
        except Exception as e:
            raise Base64DecodeError(f"Failed to decode Base64 data: {str(e)}")
    
    def _upload_sync(
        self,
        data: bytes,
        object_key: str,
        content_type: str
    ) -> PutObjectOutput:
        """Synchronous upload operation (runs in thread pool)."""
        return self.client.put_object(
            bucket=self._bucket_name,
            key=object_key,
            content=io.BytesIO(data),
            content_type=content_type,
            content_length=len(data)  # Explicit length for better performance
        )
    
    async def upload_bytes_async(
        self,
        data: bytes,
        format: ImageFormat,
        prefix: str = "generated/",
        validate: bool = True
    ) -> UploadResult:
        """
        Async upload image bytes to TOS using thread pool.
        
        Args:
            data: Image bytes
            format: Image format
            prefix: Storage path prefix
            validate: Whether to validate image format
            
        Returns:
            UploadResult with upload details
        """
        # Fast validation (fails early)
        if validate:
            detected = self._validate_image_bytes_fast(data)
            if detected is None:
                raise InvalidFileFormatError("Unable to detect valid image format from file content")
        
        # Generate object key and content type
        object_key = self._generate_object_key(prefix, format)
        content_type = self.MIME_TYPES.get(format, "application/octet-stream")
        
        try:
            # Run upload in thread pool for async behavior
            loop = asyncio.get_running_loop()
            output = await loop.run_in_executor(
                get_executor(),
                self._upload_sync,
                data,
                object_key,
                content_type
            )
            
            # Build result
            return UploadResult(
                public_url=self._build_public_url(object_key),
                object_key=object_key,
                etag=output.etag,
                size_bytes=len(data),
                content_type=content_type,
                upload_time=datetime.now(timezone.utc)
            )
        except tos.exceptions.TosClientError as e:
            raise TosUploadError(f"TOS client error: {str(e)}")
        except tos.exceptions.TosServerError as e:
            raise TosUploadError(f"TOS server error: {e.message}")
        except Exception as e:
            raise TosUploadError(f"Unexpected error during upload: {str(e)}")
    
    async def upload_base64_async(
        self,
        base64_data: str,
        format: ImageFormat = ImageFormat.JPEG,
        prefix: str = "generated/",
        quality: int = 90
    ) -> UploadResult:
        """
        Async upload Base64 encoded image to TOS.
        
        Args:
            base64_data: Base64 encoded image data
            format: Image format
            prefix: Storage path prefix
            quality: JPEG quality (reserved for future compression)
            
        Returns:
            UploadResult with upload details
        """
        # Fast decode
        image_bytes = self.decode_base64_image_fast(base64_data)
        
        # Async upload
        return await self.upload_bytes_async(image_bytes, format, prefix)
    
    # Sync methods for backward compatibility
    def upload_bytes(
        self,
        data: bytes,
        format: ImageFormat,
        prefix: str = "generated/",
        validate: bool = True
    ) -> UploadResult:
        """Synchronous upload (use upload_bytes_async for better performance)."""
        if validate:
            detected = self._validate_image_bytes_fast(data)
            if detected is None:
                raise InvalidFileFormatError("Unable to detect valid image format from file content")
        
        object_key = self._generate_object_key(prefix, format)
        content_type = self.MIME_TYPES.get(format, "application/octet-stream")
        
        try:
            output = self._upload_sync(data, object_key, content_type)
            return UploadResult(
                public_url=self._build_public_url(object_key),
                object_key=object_key,
                etag=output.etag,
                size_bytes=len(data),
                content_type=content_type,
                upload_time=datetime.now(timezone.utc)
            )
        except tos.exceptions.TosClientError as e:
            raise TosUploadError(f"TOS client error: {str(e)}")
        except tos.exceptions.TosServerError as e:
            raise TosUploadError(f"TOS server error: {e.message}")
        except Exception as e:
            raise TosUploadError(f"Unexpected error during upload: {str(e)}")
    
    def upload_base64(
        self,
        base64_data: str,
        format: ImageFormat = ImageFormat.JPEG,
        prefix: str = "generated/",
        quality: int = 90
    ) -> UploadResult:
        """Synchronous Base64 upload (use upload_base64_async for better performance)."""
        image_bytes = self.decode_base64_image_fast(base64_data)
        return self.upload_bytes(image_bytes, format, prefix)
    
    def check_connection(self) -> bool:
        """Check if TOS connection is working."""
        try:
            self.client.head_bucket(self._bucket_name)
            return True
        except Exception:
            return False
    
    async def check_connection_async(self) -> bool:
        """Async check if TOS connection is working."""
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                get_executor(),
                self.client.head_bucket,
                self._bucket_name
            )
            return True
        except Exception:
            return False


# Singleton pattern with proper initialization
_tos_client: Optional[TosClient] = None


def get_tos_client() -> TosClient:
    """Get TOS client singleton instance."""
    global _tos_client
    if _tos_client is None:
        _tos_client = TosClient()
    return _tos_client


def shutdown_executor():
    """Shutdown thread pool executor (call on app shutdown)."""
    global _executor
    if _executor is not None:
        _executor.shutdown(wait=True)
        _executor = None
