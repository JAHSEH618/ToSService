"""
Pytest configuration and fixtures.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

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
        max_file_size_mb=10
    )


@pytest.fixture
def test_settings():
    """Fixture for test settings."""
    return get_test_settings()


@pytest.fixture
def client(test_settings):
    """Fixture for test client with mocked settings."""
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


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
