"""
Logging configuration for TOS Upload Service.
Provides structured logging with file and console output.
Includes request ID tracing via contextvars for full request lifecycle tracking.
"""

import logging
import sys
import os
import uuid
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

from .config import get_settings


# ============== Request ID Context ==============

# Context variable for request ID tracing across the entire call chain
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def generate_request_id() -> str:
    """Generate a short unique request ID."""
    return uuid.uuid4().hex[:12]


def get_request_id() -> str:
    """Get the current request ID from context."""
    return request_id_ctx.get()


def set_request_id(rid: str) -> None:
    """Set the request ID in context."""
    request_id_ctx.set(rid)


# ============== Custom Log Filter ==============

class RequestIdFilter(logging.Filter):
    """
    Inject the current request_id from contextvars into every log record.
    This allows %(request_id)s to be used in log format strings.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


# ============== Log Setup ==============

def ensure_log_file_exists(log_file: Path) -> None:
    """
    Ensure the log file and its parent directory exist.
    Creates them if they don't exist to ensure service robustness.

    Args:
        log_file: Path to the log file
    """
    log_dir = log_file.parent
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)
        print(f"[Logging] Created log directory: {log_dir}")

    if not log_file.exists():
        try:
            log_file.touch(exist_ok=True)
            print(f"[Logging] Created log file: {log_file}")
        except PermissionError as e:
            print(f"[Logging] Warning: Cannot create log file {log_file}: {e}")
            return
        except Exception as e:
            print(f"[Logging] Warning: Error creating log file {log_file}: {e}")
            return

    if not os.access(log_file, os.W_OK):
        print(f"[Logging] Warning: Log file {log_file} is not writable")


def _create_file_handler(
    log_file: Path,
    log_level: int,
    formatter: logging.Formatter,
    req_filter: RequestIdFilter,
) -> RotatingFileHandler | None:
    """Create a rotating file handler, returning None on failure."""
    try:
        ensure_log_file_exists(log_file)
        handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8",
        )
        handler.setLevel(log_level)
        handler.setFormatter(formatter)
        handler.addFilter(req_filter)
        print(f"[Logging] File logging enabled: {log_file}")
        return handler
    except PermissionError as e:
        print(f"[Logging] Warning: Cannot setup file handler (permission denied): {e}")
    except Exception as e:
        print(f"[Logging] Warning: Cannot setup file handler: {e}")
    return None


def setup_logging() -> logging.Logger:
    """
    Configure application logging with:
    - Console handler (always)
    - Application log file (tos_upload_YYYYMMDD.log)
    - Access log file (access_YYYYMMDD.log)
    - RequestIdFilter on every handler

    Returns:
        Configured application logger
    """
    settings = get_settings()

    # ---- Formats ----
    app_log_format = (
        "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-28s "
        "| rid=%(request_id)s | %(funcName)s:%(lineno)d | %(message)s"
    )
    access_log_format = (
        "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)-28s "
        "| rid=%(request_id)s | %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Shared filter
    req_filter = RequestIdFilter()

    # ---- Root logger ----
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    # Console handler
    console_formatter = logging.Formatter(app_log_format, date_format)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(req_filter)
    root_logger.addHandler(console_handler)

    # ---- File handlers ----
    log_dir = Path("logs")
    today = datetime.now().strftime("%Y%m%d")

    # App log
    app_formatter = logging.Formatter(app_log_format, date_format)
    app_file = log_dir / f"tos_upload_{today}.log"
    app_fh = _create_file_handler(app_file, log_level, app_formatter, req_filter)
    if app_fh:
        root_logger.addHandler(app_fh)

    # Access log (dedicated)
    access_formatter = logging.Formatter(access_log_format, date_format)
    access_file = log_dir / f"access_{today}.log"
    access_fh = _create_file_handler(access_file, log_level, access_formatter, req_filter)
    if access_fh:
        access_logger = logging.getLogger("tos_upload.access")
        access_logger.addHandler(access_fh)
        access_logger.propagate = True  # still forward to root

    # ---- Application logger ----
    app_logger = logging.getLogger("tos_upload")
    app_logger.setLevel(log_level)

    return app_logger


def get_log_file_path() -> Path:
    """Get the current log file path."""
    log_dir = Path("logs")
    return log_dir / f"tos_upload_{datetime.now().strftime('%Y%m%d')}.log"


# Initialize logging on module import
logger = setup_logging()


def get_logger(name: str = "tos_upload") -> logging.Logger:
    """
    Get a logger with the specified name.

    Args:
        name: Logger name (will be prefixed to log messages)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
