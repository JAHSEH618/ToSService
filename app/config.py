"""
Configuration management for TOS Upload Service.
Loads settings from environment variables.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # TOS Configuration
    tos_region: str = "ap-southeast-1"
    tos_endpoint: str = "tos-ap-southeast-1.volces.com"
    tos_bucket_name: str = "aipohto-lky"
    tos_access_key: str = ""
    tos_secret_key: str = ""
    tos_public_domain: str = "aipohto-lky.tos-ap-southeast-1.volces.com"
    
    # Service Configuration
    service_port: int = 10086
    api_key: str = ""
    max_file_size_mb: int = 10
    log_level: str = "INFO"
    
    # Application Info
    app_name: str = "TOS Upload Service"
    app_version: str = "1.0.0"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
