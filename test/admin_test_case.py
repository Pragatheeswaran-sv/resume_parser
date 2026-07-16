import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from src.main import app
from src.admin.schema import AdminLoginRequest

client = TestClient(app)


class TestAdminLogin:
    """Tests for POST /api/admin/login"""

    LOGIN_URL = "/api/admin/login"

    def test_login_success(self):
        """Valid email + password returns 200 with tokens and admin profile."""
        payload = {"email": "admin@example.com", "password": "correct-password"}

        with patch("src.services.admin.service.SessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session

            # Mock admin record
            mock_admin = MagicMock()
            mock_admin.admin_id = "550e8400-e29b-41d4-a716-446655440000"
            mock_admin.email_address = "admin@example.com"
            mock_admin.name = "Admin User"
            mock_admin.password = "$2b$12$hashedpassword"  # bcrypt hash
            mock_admin.phone_number = "9876543210"

            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_admin

            with (
                patch("src.services.admin.service.verify_password", return_value=True),
                patch(
                    "src.services.admin.service.create_access_token",
                    return_value="fake-jwt-token",
                ),
                patch(
                    "src.services.admin.service.generate_refresh_token"
                ) as mock_gen_rt,
                patch(
                    "src.services.admin.service.new_family_id",
                    return_value="family-uuid",
                ),
            ):
                mock_gen_rt.return_value = (
                    "raw-refresh-token",
                    "hashed-refresh-token",
                    "expiry-date",
                )

                response = client.post(self.LOGIN_URL, json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == 200
        assert data["message"] == "Admin logged in successfully"
        assert data["data"]["access_token"] == "fake-jwt-token"
        assert data["data"]["refresh_token"] == "raw-refresh-token"
        assert data["data"]["is_admin"] is True
        assert data["data"]["email"] == "admin@example.com"
        assert data["data"]["name"] == "Admin User"

    def test_login_missing_email(self):
        payload = {"email": "", "password": "some-password"}

        with patch("src.services.admin.service.SessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session

            response = client.post(self.LOGIN_URL, json=payload)

        assert response.status_code == 400

    def test_login_missing_password(self):
        payload = {"email": "admin@example.com", "password": ""}

        with patch("src.services.admin.service.SessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session

            response = client.post(self.LOGIN_URL, json=payload)

        assert response.status_code == 400

    def test_login_admin_not_found(self):
        """Non-existent email returns 404."""
        payload = {"email": "unknown@example.com", "password": "some-password"}

        with patch("src.services.admin.service.SessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session
            mock_session.query.return_value.filter_by.return_value.first.return_value = None

            response = client.post(self.LOGIN_URL, json=payload)

        assert response.status_code == 404

    def test_login_wrong_password(self):
        """Incorrect password returns 401."""
        payload = {"email": "admin@example.com", "password": "wrong-password"}

        with patch("src.services.admin.service.SessionLocal") as mock_session_local:
            mock_session = MagicMock()
            mock_session_local.return_value = mock_session

            mock_admin = MagicMock()
            mock_admin.email_address = "admin@example.com"
            mock_admin.password = "$2b$12$hashedpassword"
            mock_session.query.return_value.filter_by.return_value.first.return_value = mock_admin

            with patch(
                "src.services.admin.service.verify_password", return_value=False
            ):
                response = client.post(self.LOGIN_URL, json=payload)

        assert response.status_code == 401
