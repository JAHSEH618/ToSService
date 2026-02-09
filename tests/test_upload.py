"""
Tests for upload endpoints.
"""

import base64
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytest

from app.models import UploadResult, ImageFormat


class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    def test_health_check(self, client):
        """Test health check returns correct response."""
        with patch("app.routers.health.get_tos_client") as mock_tos:
            mock_client = MagicMock()
            mock_client.check_connection.return_value = True
            mock_tos.return_value = mock_client
            
            response = client.get("/api/v1/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["tos_connection"] == "ok"


class TestBase64Upload:
    """Tests for Base64 upload endpoint."""
    
    def test_upload_base64_success(self, client, api_key):
        """Test successful Base64 image upload."""
        # Create a minimal valid JPEG (1x1 pixel)
        test_image = base64.b64encode(
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
            b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
            b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
            b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9telephones[;4telephones[;'
        ).decode()
        
        mock_result = UploadResult(
            public_url="https://test-bucket.tos-ap-southeast-1.volces.com/generated/test.jpg",
            object_key="generated/test.jpg",
            etag='"test-etag"',
            size_bytes=1234,
            content_type="image/jpeg",
            upload_time=datetime.now(timezone.utc)
        )
        
        with patch("app.routers.upload.get_tos_client") as mock_tos:
            mock_client = MagicMock()
            mock_client.upload_base64.return_value = mock_result
            mock_tos.return_value = mock_client
            
            response = client.post(
                "/api/v1/upload/base64",
                headers={"X-API-Key": api_key},
                json={
                    "image_base64": test_image,
                    "format": "jpeg",
                    "prefix": "generated/"
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["code"] == 0
            assert "public_url" in data["data"]
    
    def test_upload_base64_missing_api_key(self, client):
        """Test upload without API key returns 401."""
        response = client.post(
            "/api/v1/upload/base64",
            json={
                "image_base64": "dGVzdA==",
                "format": "jpeg"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["code"] == 40101
    
    def test_upload_base64_invalid_api_key(self, client):
        """Test upload with invalid API key returns 401."""
        response = client.post(
            "/api/v1/upload/base64",
            headers={"X-API-Key": "invalid-key"},
            json={
                "image_base64": "dGVzdA==",
                "format": "jpeg"
            }
        )
        
        assert response.status_code == 401
        data = response.json()
        assert data["success"] is False
        assert data["code"] == 40102


class TestImageUpload:
    """Tests for multipart image upload endpoint."""
    
    def test_upload_image_success(self, client, api_key):
        """Test successful image file upload."""
        # Create a minimal valid JPEG
        test_image_bytes = (
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
            b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
            b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
        )
        
        mock_result = UploadResult(
            public_url="https://test-bucket.tos-ap-southeast-1.volces.com/generated/test.jpg",
            object_key="generated/test.jpg",
            etag='"test-etag"',
            size_bytes=len(test_image_bytes),
            content_type="image/jpeg",
            upload_time=datetime.now(timezone.utc)
        )
        
        with patch("app.routers.upload.get_tos_client") as mock_tos:
            mock_client = MagicMock()
            mock_client.upload_bytes.return_value = mock_result
            mock_tos.return_value = mock_client
            
            response = client.post(
                "/api/v1/upload/image",
                headers={"X-API-Key": api_key},
                files={"file": ("test.jpg", test_image_bytes, "image/jpeg")},
                data={"prefix": "generated/"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["code"] == 0
    
    def test_upload_image_invalid_content_type(self, client, api_key):
        """Test upload with invalid content type returns 400."""
        response = client.post(
            "/api/v1/upload/image",
            headers={"X-API-Key": api_key},
            files={"file": ("test.txt", b"not an image", "text/plain")}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert data["code"] == 40001
