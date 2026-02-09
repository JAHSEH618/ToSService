"""
Logging configuration for TOS Upload Service.
Provides structured logging with file and console output.
Ensures log directory and files exist before service starts.
"""

import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

from .config import get_settings


def ensure_log_file_exists(log_file: Path) -> None:
    """
    Ensure the log file and its parent directory exist.
    Creates them if they don't exist to ensure service robustness.
    
    Args:
        log_file: Path to the log file
    """
    # Ensure parent directory exists
    log_dir = log_file.parent
    if not log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)
        print(f"[Logging] Created log directory: {log_dir}")
    
    # Ensure log file exists
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
    
    # Verify the file is writable
    if not os.access(log_file, os.W_OK):
        print(f"[Logging] Warning: Log file {log_file} is not writable")


def setup_logging() -> logging.Logger:
    """
    Configure application logging with console and file handlers.
    
    Ensures log directory and files exist before configuring handlers.
    Falls back to console-only logging if file logging fails.
    
    Returns:
        Configured application logger
    """
    settings = get_settings()
    
    # Log format
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # Get log level from settings
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))
    root_logger.addHandler(console_handler)
    
    # File handler setup
    try:
        # Create logs directory and file
        log_dir = Path("logs")
        log_file = log_dir / f"tos_upload_{datetime.now().strftime('%Y%m%d')}.log"
        
        # Ensure log file exists before creating handler
        ensure_log_file_exists(log_file)
        
        # Verify directory and file are ready
        if log_dir.exists() and (log_file.exists() or not log_file.exists()):
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding="utf-8"
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(logging.Formatter(log_format, date_format))
            root_logger.addHandler(file_handler)
            print(f"[Logging] File logging enabled: {log_file}")
        else:
            print("[Logging] Warning: File logging disabled due to directory issues")
            
    except PermissionError as e:
        print(f"[Logging] Warning: Cannot setup file logging (permission denied): {e}")
    except Exception as e:
        print(f"[Logging] Warning: Cannot setup file logging: {e}")
    
    # Application logger
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
