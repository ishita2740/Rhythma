import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient


# Ensure backend directory is on the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from services.rate_limit_service import RateLimitService
# ─── Mock google.generativeai ──────────────────────────────────────────────
class MockGemini:
    def __getattr__(self, name):
        return self
    def configure(self, *args, **kwargs):
        pass
    def GenerativeModel(self, *args, **kwargs):
        class MockModel:
            def generate_content(self, *args, **kwargs):
                class MockResponse:
                    text = "Mock Gemini response"
                return MockResponse()
        return MockModel()

sys.modules["google.generativeai"] = MockGemini()

# ─── Set environment variables ─────────────────────────────────────────────
os.environ["JWT_SECRET"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GEMINI_API_KEY"] = "mock-key"
os.environ["COOKIE_SECURE"] = "false"

# ─── Mock firebase_admin ──────────────────────────────────────────────────
mock_firebase_admin = MagicMock()
mock_firebase_auth = MagicMock()
mock_firebase_admin.auth = mock_firebase_auth
sys.modules["firebase_admin"] = mock_firebase_admin
sys.modules["firebase_admin.auth"] = mock_firebase_auth
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()

# ─── Import main after mocks ──────────────────────────────────────────────
from main import app
import firebase_admin.auth
client = TestClient(
    app,
    headers={
        "X-Client-Platform": "mobile"
    }
)

import core.auth_router as _auth_router
_auth_router.firebase_admin = mock_firebase_admin

@pytest.fixture(autouse=True)
def _ensure_firebase_mock():
    import core.auth_router as _ar_mod
    _ar_mod.firebase_admin = mock_firebase_admin
    mock_firebase_admin.auth = mock_firebase_auth
    _ar_mod.COOKIE_SECURE = False
    sys.modules["firebase_admin"] = mock_firebase_admin
    sys.modules["firebase_admin.auth"] = mock_firebase_auth

from api.sms import sms_history
from core.auth import refresh_token_store, reset_token_store, verification_token_store

@pytest.fixture(autouse=True)
def clear_state():
    client.cookies.clear()

    sms_history.clear()

    refresh_token_store.clear()
    reset_token_store.clear()
    verification_token_store.clear()

    # Clear persistent Firestore-backed rate limiter state
    RateLimitService.clear_all()

# ─── Fixture to mock UserService ──────────────────────
@pytest.fixture(autouse=True)
def mock_auth_dependencies():
    import core.auth_router as auth_router_module
    with patch("core.auth_router.UserService") as MockUserService1, \
         patch("core.auth.UserService") as MockUserService2, \
         patch("api.sms.UserService") as MockUserService3:

        from core.auth import get_password_hash
        _pw_hash = get_password_hash("SecurePass123")

        test_user_data = {
            "id": "test-user-id-123",
            "phone": "+1234567890",
            "email": "test@example.com",
            "email_verified": False,
            "password": _pw_hash,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z"
        }

        def get_by_phone(phone):
            if phone == "+1234567890":
                return test_user_data.copy()
            return None

        def get_by_email(email):
            if email == "test@example.com":
                return test_user_data.copy()
            return None

        def get_by_id(user_id):
            if user_id == "test-user-id-123":
                return test_user_data
            return None

        def create_user(user_dict):
            return "test-user-id-123"

        def update_user(user_id, update_data):
            if user_id == "test-user-id-123":
                test_user_data.update(update_data)
                return True
            return False

        for mock_us in [MockUserService1, MockUserService2, MockUserService3]:
            mock_us.get_user_by_phone.side_effect = get_by_phone
            mock_us.get_user_by_email.side_effect = get_by_email
            mock_us.get_user_by_id.side_effect = get_by_id
            mock_us.create_user.side_effect = create_user
            mock_us.update_user.side_effect = update_user

        yield

# ─── Tests ──────────────────────────────────────────────────────────────────

def test_firebase_login_success():
    # Mock verify_id_token to return a valid payload
    firebase_admin.auth.verify_id_token.return_value = {"phone_number": "+1234567890", "uid": "firebase_uid"}
    
    response = client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_firebase_login_invalid_token():
    # Patch the verify_id_token in the auth_router module (where the endpoint uses it)
    with patch("core.auth_router.firebase_admin.auth.verify_id_token") as mock_verify:
        class InvalidIdTokenError(Exception):
            pass
        # Attach the exception class to the mocked module so the endpoint's except clause catches it
        import core.auth_router
        core.auth_router.firebase_admin.auth.InvalidIdTokenError = InvalidIdTokenError

        mock_verify.side_effect = InvalidIdTokenError("Invalid token")

        response = client.post(
            "/api/v1/auth/firebase-login",
            json={"id_token": "invalid_token"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid Firebase ID token"

def test_protected_endpoint_without_token():
    response = client.post(
        "/api/v1/sms/send-summary",
        json={"phone_number": "+1234567890", "message": "Test"}
    )
    assert response.status_code == 401

def test_get_profile():
    firebase_admin.auth.verify_id_token.return_value = {"phone_number": "+1234567890", "uid": "firebase_uid"}
    token_response = client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"}
    )
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/auth/profile", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["phone"] == "+1234567890"

def test_patch_profile():
    firebase_admin.auth.verify_id_token.return_value = {"phone_number": "+1234567890", "uid": "firebase_uid"}
    token_response = client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"}
    )
    token = token_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    update_payload = {
        "age": 25,
        "cycle_length": 29,
        "avatar": "assets/avatars/avatar_2.png"
    }
    response = client.patch("/api/v1/auth/profile", json=update_payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["age"] == 25
    assert data["cycle_length"] == 29
    assert data["avatar"] == "assets/avatars/avatar_2.png"
    assert data.get("username") in ["testuser", None]
    assert "password" not in data

def test_login_sets_httponly_cookie():
    firebase_admin.auth.verify_id_token.return_value = {"phone_number": "+1234567890", "uid": "firebase_uid"}
    response = client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"}
    )

    assert response.status_code == 200
    assert "rhythma_access_token" in response.cookies

    set_cookie_header = response.headers.get("set-cookie", "")
    assert "HttpOnly" in set_cookie_header

def test_cookie_only_auth_works():
    firebase_admin.auth.verify_id_token.return_value = {"phone_number": "+1234567890", "uid": "firebase_uid"}
    # Login stores the HttpOnly cookie in the TestClient cookie jar.
    client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"}
    )

    # No Authorization header is sent here.
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.status_code == 200

def test_logout_clears_cookie():
    firebase_admin.auth.verify_id_token.return_value = {"phone_number": "+1234567890", "uid": "firebase_uid"}
    client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"}
    )

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401

def test_web_client_does_not_receive_token_in_body():
    firebase_admin.auth.verify_id_token.return_value = {"phone_number": "+1234567890", "uid": "firebase_uid"}
    response = client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"},
        headers={"X-Client-Platform": "web"},
    )
    assert response.status_code == 200
    assert "access_token" not in response.json()
    # Web client should still get the refresh cookie set
    assert "rhythma_refresh_token" in response.cookies

def test_mobile_client_still_receives_token_in_body():
    firebase_admin.auth.verify_id_token.return_value = {"phone_number": "+1234567890", "uid": "firebase_uid"}
    response = client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


# ─── Registration ─────────────────────────────────────────────────────────

def test_register_success():
    response = client.post("/api/v1/auth/register", json={
        "email": "newuser@example.com",
        "password": "SecurePass123",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["email_verified"] is False
    assert "id" in data

def test_register_duplicate_email():
    response = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "SecurePass123",
    })
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"].lower()

def test_register_invalid_email():
    response = client.post("/api/v1/auth/register", json={
        "email": "not-an-email",
        "password": "SecurePass123",
    })
    assert response.status_code == 422


# ─── Email/Password Login ─────────────────────────────────────────────────

def test_login_success():
    response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

def test_login_wrong_password():
    # The UserService mock returns the test user for test@example.com,
    # but the password stored in the mock data is empty/None, so the
    # verify_password call will fail against any real password.
    response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "WrongPassword",
    })
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()

def test_login_nonexistent_user():
    response = client.post("/api/v1/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "SomePass123",
    })
    assert response.status_code == 401
    assert "invalid" in response.json()["detail"].lower()


# ─── Refresh Token ────────────────────────────────────────────────────────

def test_refresh_token_success():
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123",
    })
    refresh_token = login_resp.json()["refresh_token"]

    response = client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["refresh_token"] != refresh_token

def test_refresh_token_invalid():
    response = client.post("/api/v1/auth/refresh", json={
        "refresh_token": "invalid-token-value"
    })
    assert response.status_code == 401

def test_refresh_token_rotation():
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123",
    })
    refresh_token = login_resp.json()["refresh_token"]

    # First refresh — succeeds
    resp1 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp1.status_code == 200

    # Second refresh with the same (now revoked) token — fails
    resp2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp2.status_code == 401


# ─── Forgot / Reset Password ─────────────────────────────────────────────

def test_forgot_password_success():
    response = client.post("/api/v1/auth/forgot-password", json={
        "email": "test@example.com"
    })
    assert response.status_code == 200
    assert "message" in response.json()

def test_forgot_password_nonexistent():
    response = client.post("/api/v1/auth/forgot-password", json={
        "email": "nonexistent@example.com"
    })
    assert response.status_code == 200
    assert "message" in response.json()

def test_reset_password_success():
    from core.auth import generate_reset_token
    reset_token = generate_reset_token("test@example.com")

    response = client.post("/api/v1/auth/reset-password", json={
        "email": "test@example.com",
        "token": reset_token,
        "new_password": "NewSecurePass456",
    })
    assert response.status_code == 200
    assert "reset" in response.json()["message"].lower()

def test_reset_password_invalid_token():
    response = client.post("/api/v1/auth/reset-password", json={
        "email": "test@example.com",
        "token": "invalid-token",
        "new_password": "NewSecurePass456",
    })
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


# ─── Email Verification ───────────────────────────────────────────────────

def test_verify_email_success():
    from core.auth import generate_verification_token
    verify_token = generate_verification_token("test@example.com")

    response = client.post("/api/v1/auth/verify-email", json={
        "email": "test@example.com",
        "token": verify_token,
    })
    assert response.status_code == 200
    assert "verified" in response.json()["message"].lower()

def test_verify_email_invalid_token():
    response = client.post("/api/v1/auth/verify-email", json={
        "email": "test@example.com",
        "token": "invalid-token",
    })
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()

def test_resend_verification():
    response = client.post("/api/v1/auth/resend-verification", json={
        "email": "test@example.com"
    })
    assert response.status_code == 200
    assert "message" in response.json()


# ─── Logout All ───────────────────────────────────────────────────────────

def test_logout_all_revokes_refresh_tokens():
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123",
    })
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    access_token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    logout_resp = client.post("/api/v1/auth/logout-all", headers=headers)
    assert logout_resp.status_code == 200

    refresh_resp = client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert refresh_resp.status_code == 401


# ─── Refresh Token: Cookie-Based (Web) ────────────────────────────────────

def test_refresh_token_with_cookie_success():
    """Web clients can refresh using the HttpOnly cookie without sending the token in the body."""
    firebase_admin.auth.verify_id_token.return_value = {"phone_number": "+1234567890", "uid": "firebase_uid"}
    # Login as web client — no token in body, but cookie is set
    login_resp = client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"},
        headers={"X-Client-Platform": "web"},
    )
    assert login_resp.status_code == 200
    assert "rhythma_refresh_token" in login_resp.cookies

    # Refresh without body — cookie should be used
    refresh_resp = client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 200
    data = refresh_resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # Cookie should be rotated
    assert "rhythma_access_token" in refresh_resp.cookies
    assert "rhythma_refresh_token" in refresh_resp.cookies


def test_refresh_token_cookie_rotation():
    """Refreshing with a cookie should rotate both cookies."""
    firebase_admin.auth.verify_id_token.return_value = {"phone_number": "+1234567890", "uid": "firebase_uid"}
    client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"},
        headers={"X-Client-Platform": "web"},
    )

    # First refresh
    resp1 = client.post("/api/v1/auth/refresh")
    assert resp1.status_code == 200
    old_refresh_cookie = resp1.cookies.get("rhythma_refresh_token")

    # Second refresh with the new cookie (auto-sent by TestClient)
    resp2 = client.post("/api/v1/auth/refresh")
    assert resp2.status_code == 200
    new_refresh_cookie = resp2.cookies.get("rhythma_refresh_token")

    # Cookies should be different (rotation)
    assert old_refresh_cookie != new_refresh_cookie


def test_refresh_token_body_takes_precedence_over_cookie():
    """If both body and cookie are present, body token is used."""
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "SecurePass123",
    })
    refresh_token = login_resp.json()["refresh_token"]

    # Also set a cookie by doing a web login
    firebase_admin.auth.verify_id_token.return_value = {"phone_number": "+1234567890", "uid": "firebase_uid"}
    client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"},
        headers={"X-Client-Platform": "web"},
    )

    # Refresh with explicit body token — should use body, not cookie
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200


def test_refresh_token_no_body_no_cookie_fails():
    """A request with neither body token nor cookie should 401."""
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401
    assert "No refresh token provided" in resp.json()["detail"]


# ─── Firebase Login Refresh Token ─────────────────────────────────────────

def test_firebase_login_sets_refresh_cookie():
    """Firebase login should set the refresh cookie for all clients."""
    firebase_admin.auth.verify_id_token.return_value = {"phone_number": "+1234567890", "uid": "firebase_uid"}
    response = client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"},
    )
    assert response.status_code == 200
    assert "rhythma_refresh_token" in response.cookies


def test_firebase_refresh_token_flow():
    """Full flow: firebase login → use refresh token → get new access token."""
    firebase_admin.auth.verify_id_token.return_value = {"phone_number": "+1234567890", "uid": "firebase_uid"}
    login_resp = client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]
    old_access = login_resp.json()["access_token"]

    # Use refresh token to get new tokens
    refresh_resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200
    new_access = refresh_resp.json()["access_token"]

    # New access token should be different
    assert new_access != old_access

    # Old refresh token should be revoked
    second_refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert second_refresh.status_code == 401
