import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from contextlib import contextmanager
from src.main import app

client = TestClient(app)

@contextmanager
def mock_admin_auth():
    with patch("src.admin.dependencies.decode_access_token") as mock_decode, \
         patch("src.admin.dependencies.SessionLocal") as mock_db:
        mock_decode.return_value = {"role": "admin", "sub": "admin-uuid", "email": "admin@test.com"}
        mock_session = MagicMock()
        mock_db.return_value = mock_session
        mock_admin = MagicMock(admin_id="admin-uuid", is_active=True)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_admin
        yield mock_session


@contextmanager
def mock_user_auth():
    with patch("src.admin.dependencies.decode_access_token") as mock_decode, \
         patch("src.admin.dependencies.SessionLocal") as mock_db:
        mock_decode.return_value = {"role": "user", "sub": "user-uuid", "email": "user@test.com"}
        mock_session = MagicMock()
        mock_db.return_value = mock_session
        mock_user = MagicMock(user_id="user-uuid", email_address="user@test.com", is_active=True, is_blocked=False)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_user
        yield mock_session


@contextmanager
def mock_admin_or_user_auth(role: str):
    with patch("src.admin.dependencies.decode_access_token") as mock_decode, \
         patch("src.admin.dependencies.SessionLocal") as mock_db:
        mock_decode.return_value = {"role": role, "sub": f"{role}-uuid", "email": f"{role}@test.com"}
        mock_session = MagicMock()
        mock_db.return_value = mock_session
        if role == "admin":
            mock_obj = MagicMock(admin_id="admin-uuid", is_active=True)
        else:
            mock_obj = MagicMock(user_id="user-uuid", email_address="user@test.com", is_active=True, is_blocked=False)
        mock_session.query.return_value.filter.return_value.first.return_value = mock_obj
        yield mock_session


class TestCreateUser:
    """Tests for POST /api/create_user"""

    URL = "/api/create_user"

    def test_create_user_success(self):
        payload = {"name": "New User", "email": "user@example.com", "phone_number": "9876543210"}
        with mock_admin_auth():
            with patch("src.admin.api.new_auth") as mock_new_auth:
                mock_new_auth.return_value = {"status": 201, "message": "User created successfully", "data": {}}
                response = client.post(self.URL, json=payload, headers={"Authorization": "Bearer test"})
        assert response.status_code == 200

    def test_create_user_no_auth(self):
        payload = {"name": "New User", "email": "user@example.com", "phone_number": "9876543210"}
        response = client.post(self.URL, json=payload)
        assert response.status_code == 401

    def test_create_user_missing_name(self):
        payload = {"email": "user@example.com", "phone_number": "9876543210"}
        with mock_admin_auth():
            response = client.post(self.URL, json=payload, headers={"Authorization": "Bearer test"})
        assert response.status_code == 422

    def test_create_user_missing_email(self):
        payload = {"name": "New User", "phone_number": "9876543210"}
        with mock_admin_auth():
            response = client.post(self.URL, json=payload, headers={"Authorization": "Bearer test"})
        assert response.status_code == 422

    def test_create_user_service_error(self):
        payload = {"name": "New User", "email": "user@example.com", "phone_number": "9876543210"}
        with mock_admin_auth():
            with patch("src.admin.api.new_auth", side_effect=ValueError("Email already exists")):
                response = client.post(self.URL, json=payload, headers={"Authorization": "Bearer test"})
        assert response.status_code == 400


class TestUserProfile:
    """Tests for GET /api/user_profile — uses get_current_user"""

    URL = "/api/user_profile"

    def test_user_profile_success(self):
        with mock_user_auth():
            with patch("src.admin.api.get_user") as mock_get:
                mock_get.return_value = {"name": "Test User", "email_address": "u@test.com"}
                response = client.get(self.URL, headers={"Authorization": "Bearer test"})
        assert response.status_code == 200

    def test_user_profile_no_auth(self):
        response = client.get(self.URL)
        assert response.status_code == 401

    def test_user_profile_admin_token_forbidden(self):
        with patch("src.admin.dependencies.decode_access_token") as mock_decode, \
            patch("src.admin.dependencies.SessionLocal") as mock_db:
            mock_decode.return_value = {"role": "admin", "sub": "admin-uuid", "email": "admin@test.com"}
            mock_session = MagicMock()
            mock_db.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = None
            response = client.get(self.URL, headers={"Authorization": "Bearer admin-token"})
        assert response.status_code == 403

    def test_user_profile_user_not_found(self):
        with patch("src.admin.dependencies.decode_access_token") as mock_decode, \
             patch("src.admin.dependencies.SessionLocal") as mock_db:
            mock_decode.return_value = {"role": "user", "sub": "missing-uuid", "email": "user@test.com"}
            mock_session = MagicMock()
            mock_db.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = None
            response = client.get(self.URL, headers={"Authorization": "Bearer test"})
        assert response.status_code == 403

    def test_user_profile_service_error(self):
        with mock_user_auth():
            with patch("src.admin.api.get_user", side_effect=ValueError("error")):
                response = client.get(self.URL, headers={"Authorization": "Bearer test"})
        assert response.status_code == 400


class TestParticularUser:
    """Tests for GET /api/particular_user?user_id=xxx"""

    URL = "/api/particular_user"

    def test_particular_user_success(self):
        with mock_admin_auth():
            with patch("src.admin.api.get_user_by_id") as mock_get:
                mock_get.return_value = {"user_id": "some-uuid", "name": "Target User"}
                response = client.get(f"{self.URL}?user_id=some-uuid", headers={"Authorization": "Bearer test"})
        assert response.status_code == 200

    def test_particular_user_no_auth(self):
        response = client.get(f"{self.URL}?user_id=some-uuid")
        assert response.status_code == 401

    def test_particular_user_missing_id(self):
        with mock_admin_auth():
            response = client.get(self.URL, headers={"Authorization": "Bearer test"})
        assert response.status_code in (400, 422)

    def test_particular_user_not_found(self):
        with mock_admin_auth():
            with patch("src.admin.api.get_user_by_id", side_effect=ValueError("User not found")):
                response = client.get(f"{self.URL}?user_id=bad-uuid", headers={"Authorization": "Bearer test"})
        assert response.status_code == 400


class TestDeleteUser:
    """Tests for PATCH /api/delete_user/?user_id=xxx"""

    URL = "/api/delete_user/"

    def test_delete_user_success(self):
        with mock_admin_auth():
            with patch("src.admin.api.delete_user") as mock_del:
                mock_del.return_value = {"status": 200, "message": "User deleted"}
                response = client.patch(f"{self.URL}?user_id=some-uuid", headers={"Authorization": "Bearer test"})
        assert response.status_code == 200

    def test_delete_user_no_auth(self):
        response = client.patch(f"{self.URL}?user_id=some-uuid")
        assert response.status_code == 401

    def test_delete_user_missing_id(self):
        with mock_admin_auth():
            response = client.patch(self.URL, headers={"Authorization": "Bearer test"})
        assert response.status_code == 422

    def test_delete_user_service_error(self):
        with mock_admin_auth():
            with patch("src.admin.api.delete_user", side_effect=ValueError("Not found")):
                response = client.patch(f"{self.URL}?user_id=bad-id", headers={"Authorization": "Bearer test"})
        assert response.status_code == 400


class TestUpdateUser:
    """Tests for PATCH /api/update_user/?user_id=xxx
    Uses get_current_admin_or_user
    """

    URL = "/api/update_user/"

    def test_update_user_by_admin(self):
        payload = {"name": "Updated Name"}
        with mock_admin_or_user_auth("admin"):
            with patch("src.admin.api.update_user") as mock_upd:
                mock_upd.return_value = {"status": 200, "message": "User updated"}
                response = client.patch(
                    f"{self.URL}?user_id=target-uuid", json=payload,
                    headers={"Authorization": "Bearer test"}
                )
        assert response.status_code == 200

    def test_update_user_by_self(self):
        payload = {"name": "My New Name"}
        with mock_admin_or_user_auth("user"):
            with patch("src.admin.api.update_user") as mock_upd:
                mock_upd.return_value = {"status": 200, "message": "User updated"}
                response = client.patch(
                    f"{self.URL}?user_id=user-uuid", json=payload,
                    headers={"Authorization": "Bearer test"}
                )
        assert response.status_code == 200

    def test_update_user_no_auth(self):
        response = client.patch(f"{self.URL}?user_id=xxx", json={"name": "Test"})
        assert response.status_code == 401

    def test_update_user_invalid_role(self):
        with patch("src.admin.dependencies.decode_access_token") as mock_decode, \
            patch("src.admin.dependencies.SessionLocal") as mock_db:
            mock_decode.return_value = {"role": "superadmin", "sub": "x", "email": "x@test.com"}
            mock_session = MagicMock()
            mock_db.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = None
            response = client.patch(
                f"{self.URL}?user_id=xxx", json={"name": "Test"},
                headers={"Authorization": "Bearer test"}
            )
        assert response.status_code == 403

    def test_update_user_service_error(self):
        payload = {"name": "Updated"}
        with mock_admin_or_user_auth("admin"):
            with patch("src.admin.api.update_user", side_effect=ValueError("Update failed")):
                response = client.patch(
                    f"{self.URL}?user_id=bad-id", json=payload,
                    headers={"Authorization": "Bearer test"}
                )
        assert response.status_code == 400


class TestListUsers:
    """Tests for GET /api/list_users?page=1&page_size=10"""

    URL = "/api/list_users"

    def test_list_users_success(self):
        with mock_admin_auth():
            with patch("src.admin.api.list_user") as mock_list:
                mock_list.return_value = {"users": [], "total": 0, "page": 1, "page_size": 10}
                response = client.get(
                    f"{self.URL}?page=1&page_size=10",
                    headers={"Authorization": "Bearer test"}
                )
        assert response.status_code == 200

    def test_list_users_with_filters(self):
        with mock_admin_auth():
            with patch("src.admin.api.list_user") as mock_list:
                mock_list.return_value = {"users": [], "total": 0}
                response = client.get(
                    f"{self.URL}?page=1&page_size=10&sort_by=name&sort_order=asc&filter_column=email&filter_value=test@",
                    headers={"Authorization": "Bearer test"}
                )
        assert response.status_code == 200

    def test_list_users_no_auth(self):
        response = client.get(f"{self.URL}?page=1&page_size=10")
        assert response.status_code == 401

    def test_list_users_negative_page(self):
        with mock_admin_auth():
            response = client.get(
                f"{self.URL}?page=-1&page_size=10",
                headers={"Authorization": "Bearer test"}
            )
        assert response.status_code in (400, 422)

    def test_list_users_service_error(self):
        with mock_admin_auth():
            with patch("src.admin.api.list_user", side_effect=ValueError("DB error")):
                response = client.get(
                    f"{self.URL}?page=1&page_size=10",
                    headers={"Authorization": "Bearer test"}
                )
        assert response.status_code == 400