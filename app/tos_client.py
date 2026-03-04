"""
TOS (Volcano Cloud Object Storage) client wrapper.
Optimized for high performance with async support and connection pooling.
Full lifecycle logging for every upload operation.
"""

import io
import uuid
import base64
import asyncio
import time
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
from .logging_config import get_logger


logger = get_logger("tos_upload.tos_client")


# Thread pool for running sync TOS SDK operations
# Size optimized for I/O-bound operations
_executor: Optional[ThreadPoolExecutor] = None


def get_executor() -> ThreadPoolExecutor:
    """Get or create thread pool executor for async operations."""
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="tos_worker")
        logger.info("Thread pool executor created  workers=10")
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

    # Magic bytes for file type validation (ordered by frequency)
    MAGIC_BYTES: tuple[tuple[bytes, ImageFormat], ...] = (
        (b"\xff\xd8\xff", ImageFormat.JPEG),
        (b"\x89PNG", ImageFormat.PNG),
        (b"RIFF", ImageFormat.WEBP),
    )

    __slots__ = ("settings", "_client", "_bucket_name", "_public_domain")

    def __init__(self):
        """Initialize TOS client with cached settings."""
        self.settings = get_settings()
        self._client: Optional[TosClientV2] = None
        self._bucket_name = self.settings.tos_bucket_name
        self._public_domain = self.settings.tos_public_domain
        logger.info(
            "TosClient initialized  region=%s  endpoint=%s  bucket=%s  domain=%s",
            self.settings.tos_region,
            self.settings.tos_endpoint,
            self._bucket_name,
            self._public_domain,
        )

    @property
    def client(self) -> TosClientV2:
        """Get or create TOS client instance with connection reuse."""
        if self._client is None:
            logger.info("Creating TOS SDK client (first connection)...")
            self._client = TosClientV2(
                ak=self.settings.tos_access_key,
                sk=self.settings.tos_secret_key,
                endpoint=self.settings.tos_endpoint,
                region=self.settings.tos_region,
                connection_time=60,
                socket_timeout=30,
                max_retry_count=3,
            )
            logger.info(
                "TOS SDK client created  endpoint=%s  region=%s  timeout=60/30  retries=3",
                self.settings.tos_endpoint,
                self.settings.tos_region,
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
            logger.debug("Image validation failed: data too short (%d bytes)", len(data))
            return None

        for magic, fmt in self.MAGIC_BYTES:
            if data[: len(magic)] == magic:
                if fmt == ImageFormat.WEBP:
                    if len(data) >= 12 and data[8:12] == b"WEBP":
                        logger.debug("Detected image format: %s", fmt.value)
                        return fmt
                else:
                    logger.debug("Detected image format: %s", fmt.value)
                    return fmt

        logger.debug(
            "Image validation failed: unrecognised magic bytes %s",
            data[:4].hex(),
        )
        return None

    def _build_public_url(self, object_key: str) -> str:
        """Build public URL for the uploaded object."""
        return f"https://{self._public_domain}/{object_key}"

    @staticmethod
    def decode_base64_image_fast(base64_data: str) -> bytes:
        """
        Optimized Base64 decoding with minimal string operations.
        """
        try:
            comma_idx = base64_data.find(",")
            if comma_idx != -1:
                base64_data = base64_data[comma_idx + 1 :]

            decoded = base64.b64decode(base64_data, validate=True)
            logger.debug(
                "Base64 decoded successfully  input_len=%d  output_bytes=%d",
                len(base64_data),
                len(decoded),
            )
            return decoded
        except Exception as e:
            logger.error("Base64 decode failed: %s", str(e))
            raise Base64DecodeError(f"Failed to decode Base64 data: {str(e)}")

    def _upload_sync(
        self,
        data: bytes,
        object_key: str,
        content_type: str,
    ) -> PutObjectOutput:
        """Synchronous upload operation (runs in thread pool)."""
        t0 = time.time()
        logger.debug(
            "TOS SDK put_object starting  key=%s  size=%d  type=%s",
            object_key,
            len(data),
            content_type,
        )
        result = self.client.put_object(
            bucket=self._bucket_name,
            key=object_key,
            content=io.BytesIO(data),
            content_type=content_type,
            content_length=len(data),
        )
        elapsed = (time.time() - t0) * 1000
        logger.debug(
            "TOS SDK put_object finished  key=%s  etag=%s  elapsed=%.2fms",
            object_key,
            result.etag,
            elapsed,
        )
        return result

    # ============== Async Methods ==============

    async def upload_bytes_async(
        self,
        data: bytes,
        format: ImageFormat,
        prefix: str = "generated/",
        validate: bool = True,
    ) -> UploadResult:
        """
        Async upload image bytes to TOS using thread pool.
        """
        size_bytes = len(data)
        logger.info(
            "Upload starting  format=%s  size=%d bytes (%.2f KB)  prefix=%s  validate=%s",
            format.value,
            size_bytes,
            size_bytes / 1024,
            prefix,
            validate,
        )

        # Fast validation
        if validate:
            detected = self._validate_image_bytes_fast(data)
            if detected is None:
                logger.warning(
                    "Upload rejected: invalid image format  size=%d  prefix=%s",
                    size_bytes,
                    prefix,
                )
                raise InvalidFileFormatError(
                    "Unable to detect valid image format from file content"
                )

        object_key = self._generate_object_key(prefix, format)
        content_type = self.MIME_TYPES.get(format, "application/octet-stream")

        t0 = time.time()
        try:
            loop = asyncio.get_running_loop()
            output = await loop.run_in_executor(
                get_executor(),
                self._upload_sync,
                data,
                object_key,
                content_type,
            )

            elapsed = (time.time() - t0) * 1000
            public_url = self._build_public_url(object_key)
            logger.info(
                "Upload successful  key=%s  size=%d  etag=%s  elapsed=%.2fms  url=%s",
                object_key,
                size_bytes,
                output.etag,
                elapsed,
                public_url,
            )

            return UploadResult(
                public_url=public_url,
                object_key=object_key,
                etag=output.etag,
                size_bytes=size_bytes,
                content_type=content_type,
                upload_time=datetime.now(timezone.utc),
            )
        except tos.exceptions.TosClientError as e:
            elapsed = (time.time() - t0) * 1000
            logger.error(
                "TOS client error  key=%s  size=%d  elapsed=%.2fms  error=%s",
                object_key,
                size_bytes,
                elapsed,
                str(e),
            )
            raise TosUploadError(f"TOS client error: {str(e)}")
        except tos.exceptions.TosServerError as e:
            elapsed = (time.time() - t0) * 1000
            logger.error(
                "TOS server error  key=%s  size=%d  elapsed=%.2fms  status=%s  code=%s  message=%s  request_id=%s",
                object_key,
                size_bytes,
                elapsed,
                e.status_code,
                e.code,
                e.message,
                e.request_id,
            )
            raise TosUploadError(f"TOS server error: {e.message}")
        except TosUploadError:
            raise
        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            logger.error(
                "Unexpected upload error  key=%s  size=%d  elapsed=%.2fms  error=%s",
                object_key,
                size_bytes,
                elapsed,
                str(e),
                exc_info=True,
            )
            raise TosUploadError(f"Unexpected error during upload: {str(e)}")

    async def upload_base64_async(
        self,
        base64_data: str,
        format: ImageFormat = ImageFormat.JPEG,
        prefix: str = "generated/",
        quality: int = 90,
    ) -> UploadResult:
        """
        Async upload Base64 encoded image to TOS.
        """
        logger.info(
            "Base64 upload starting  format=%s  prefix=%s  quality=%d  b64_len=%d",
            format.value,
            prefix,
            quality,
            len(base64_data),
        )

        image_bytes = self.decode_base64_image_fast(base64_data)
        return await self.upload_bytes_async(image_bytes, format, prefix)

    # ============== Sync Methods (backward compat) ==============

    def upload_bytes(
        self,
        data: bytes,
        format: ImageFormat,
        prefix: str = "generated/",
        validate: bool = True,
    ) -> UploadResult:
        """Synchronous upload (use upload_bytes_async for better performance)."""
        size_bytes = len(data)
        logger.info(
            "Sync upload starting  format=%s  size=%d bytes  prefix=%s",
            format.value,
            size_bytes,
            prefix,
        )

        if validate:
            detected = self._validate_image_bytes_fast(data)
            if detected is None:
                logger.warning("Sync upload rejected: invalid image format")
                raise InvalidFileFormatError(
                    "Unable to detect valid image format from file content"
                )

        object_key = self._generate_object_key(prefix, format)
        content_type = self.MIME_TYPES.get(format, "application/octet-stream")

        t0 = time.time()
        try:
            output = self._upload_sync(data, object_key, content_type)
            elapsed = (time.time() - t0) * 1000
            public_url = self._build_public_url(object_key)
            logger.info(
                "Sync upload successful  key=%s  size=%d  elapsed=%.2fms",
                object_key,
                size_bytes,
                elapsed,
            )
            return UploadResult(
                public_url=public_url,
                object_key=object_key,
                etag=output.etag,
                size_bytes=size_bytes,
                content_type=content_type,
                upload_time=datetime.now(timezone.utc),
            )
        except tos.exceptions.TosClientError as e:
            logger.error("TOS client error (sync): %s", str(e))
            raise TosUploadError(f"TOS client error: {str(e)}")
        except tos.exceptions.TosServerError as e:
            logger.error("TOS server error (sync): status=%s  message=%s", e.status_code, e.message)
            raise TosUploadError(f"TOS server error: {e.message}")
        except Exception as e:
            logger.error("Unexpected upload error (sync): %s", str(e), exc_info=True)
            raise TosUploadError(f"Unexpected error during upload: {str(e)}")

    def upload_base64(
        self,
        base64_data: str,
        format: ImageFormat = ImageFormat.JPEG,
        prefix: str = "generated/",
        quality: int = 90,
    ) -> UploadResult:
        """Synchronous Base64 upload (use upload_base64_async for better performance)."""
        logger.info(
            "Sync base64 upload starting  format=%s  b64_len=%d",
            format.value,
            len(base64_data),
        )
        image_bytes = self.decode_base64_image_fast(base64_data)
        return self.upload_bytes(image_bytes, format, prefix)

    # ============== Health Check ==============

    def check_connection(self) -> bool:
        """Check if TOS connection is working."""
        try:
            self.client.head_bucket(self._bucket_name)
            logger.debug("TOS connection check passed  bucket=%s", self._bucket_name)
            return True
        except Exception as e:
            logger.warning(
                "TOS connection check failed  bucket=%s  error=%s",
                self._bucket_name,
                str(e),
            )
            return False

    async def check_connection_async(self) -> bool:
        """Async check if TOS connection is working."""
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                get_executor(),
                self.client.head_bucket,
                self._bucket_name,
            )
            logger.debug("TOS async connection check passed  bucket=%s", self._bucket_name)
            return True
        except Exception as e:
            logger.warning(
                "TOS async connection check failed  bucket=%s  error=%s",
                self._bucket_name,
                str(e),
            )
            return False


# Singleton pattern
_tos_client: Optional[TosClient] = None


def get_tos_client() -> TosClient:
    """Get TOS client singleton instance."""
    global _tos_client
    if _tos_client is None:
        logger.info("Initializing TOS client singleton...")
        _tos_client = TosClient()
    return _tos_client


def shutdown_executor():
    """Shutdown thread pool executor (call on app shutdown)."""
    global _executor
    if _executor is not None:
        logger.info("Shutting down thread pool executor...")
        _executor.shutdown(wait=True)
        _executor = None
        logger.info("Thread pool executor shutdown complete")
