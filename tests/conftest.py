"""
Pytest configuration and fixtures.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

from app.main import app
from app.config import Settings, get_settings


def get_test_settings() -> Settings:
    """Get test settings with mock values."""
    return Settings(
        tos_region="ap-southeast-1",
        tos_endpoint="tos-ap-southeast-1.volces.com",
        tos_bucket_name="test-bucket",
        tos_access_key="test-ak",
        tos_secret_key="test-sk",
        tos_public_domain="test-bucket.tos-ap-southeast-1.volces.com",
        api_key="test-api-key",
        max_file_size_mb=10,
    )


@pytest.fixture
def test_settings():
    """Fixture for test settings."""
    return get_test_settings()


@pytest.fixture
def client(test_settings):
    """
    Fixture for test client with mocked settings.
    
    We clear the LRU cache and patch get_settings everywhere it's imported
    so that all modules (dependencies, routers, etc.) receive the test settings.
    """
    # Clear the LRU cache so the patched function takes effect
    get_settings.cache_clear()

    with patch("app.config.get_settings", return_value=test_settings), \
         patch("app.dependencies.get_settings", return_value=test_settings), \
         patch("app.routers.upload.get_settings", return_value=test_settings):
        app.dependency_overrides[get_settings] = lambda: test_settings
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()

    # Restore clean cache state
    get_settings.cache_clear()


@pytest.fixture
def api_key():
    """Fixture for test API key."""
    return "test-api-key"


@pytest.fixture
def mock_tos_client():
    """Fixture for mocked TOS client."""
    with patch("app.tos_client.get_tos_client") as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client
        yield mock_client
