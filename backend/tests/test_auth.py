import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

# Ensure backend directory is on the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

# ─── Mock firebase_admin ──────────────────────────────────────────────────
sys.modules["firebase_admin"] = MagicMock()
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()

# ─── Import main after mocks ──────────────────────────────────────────────
from main import app
client = TestClient(app)


# ─── Fixture to mock UserService and verify_password ──────────────────────
@pytest.fixture(autouse=True)
def mock_auth_dependencies():
    # Reset the rate-limit trackers before every test. These are
    # module-level dicts in core.auth_router (mirroring the same
    # in-memory pattern used by sms.py), so without this reset, any two
    # tests that hit the same rate-limit key (e.g. every register test
    # shares TestClient's default IP) silently share a rate-limit budget
    # depending on test execution order — a test run later in the file
    # can get an unexpected 429 because an earlier test already used up
    # part of its allowance.
    import core.auth_router as auth_router_module
    auth_router_module.login_attempts.clear()
    auth_router_module.register_attempts.clear()

    # IMPORTANT: patch these where `core.auth_router` looks them up, not
    # where they're originally defined. `auth_router.py` does
    # `from services.firestore_service import UserService` and
    # `from core.auth import verify_password` — those `from ... import`
    # statements copy a reference into auth_router's own namespace at
    # import time, so patching `services.firestore_service.UserService`
    # or `core.auth.verify_password` after that has already happened has
    # no effect on the names `auth_router` actually calls. Patching
    # `core.auth_router.UserService` / `core.auth_router.verify_password`
    # replaces the exact reference the route code uses.
    with patch("core.auth_router.UserService") as MockUserService1, \
         patch("core.auth.UserService") as MockUserService2, \
         patch("api.sms.UserService") as MockUserService3, \
         patch("core.auth_router.verify_password") as mock_verify:

        # Define mock user data
        test_user_data = {
            "id": "test-user-id-123",
            "username": "testuser",
            "email": "testuser@example.com",
            "full_name": "Test User",
            "password": "dummy_hash",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z"
        }

        rate_limiter_user = {
            "id": "rate-limiter-id",
            "username": "ratelimiter",
            "email": "ratelimiter@example.com",
            "full_name": "Rate Limiter",
            "password": "dummy_hash",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z"
        }

        def get_by_username(username):
            if username == "testuser":
                return test_user_data.copy()
            if username == "ratelimiter":
                return rate_limiter_user.copy()
            return None

        def get_by_email(email):
            # A known "existing" email, distinct from testuser's own email,
            # so tests can exercise an email-only collision (fresh username,
            # colliding email) independently of the username-only collision
            # case (colliding username, fresh email).
            if email == "existing_email_only@example.com":
                return test_user_data.copy()
            return None

        def get_by_id(user_id):
            if user_id == "test-user-id-123":
                return test_user_data
            if user_id == "rate-limiter-id":
                return rate_limiter_user
            return None

        def create_user(user_dict):
            # Return a new user ID (ignore the actual data)
            return "test-user-id-123"

        def update_user(user_id, update_data):
            if user_id == "test-user-id-123":
                test_user_data.update(update_data)
                return True
            if user_id == "rate-limiter-id":
                rate_limiter_user.update(update_data)
                return True
            return False

        # UserService's methods are @staticmethods, called directly on the
        # class (e.g. `UserService.get_user_by_username(...)`) — never
        # instantiated. So the side effects go on the mocked classes.
        for mock_us in [MockUserService1, MockUserService2, MockUserService3]:
            mock_us.get_user_by_username.side_effect = get_by_username
            mock_us.get_user_by_email.side_effect = get_by_email
            mock_us.get_user_by_id.side_effect = get_by_id
            mock_us.create_user.side_effect = create_user
            mock_us.update_user.side_effect = update_user

        # Mock verify_password: return True for correct password
        def verify_pw(plain, hashed):
            # For testuser and ratelimiter, treat "testpass123" as correct
            if plain == "testpass123":
                return True
            return False

        mock_verify.side_effect = verify_pw

        yield


# ─── Tests ──────────────────────────────────────────────────────────────────

def test_login_success():
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "testuser", "password": "testpass123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_login_failure_wrong_password():
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "testuser", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_login_failure_missing_user():
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "nonexistentuser", "password": "anything"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_login_generic_error_message():
    resp_missing = client.post(
        "/api/v1/auth/token",
        data={"username": "nonexistent", "password": "anything"}
    )
    resp_wrong = client.post(
        "/api/v1/auth/token",
        data={"username": "testuser", "password": "wrongpassword"}
    )
    assert resp_missing.json()["detail"] == resp_wrong.json()["detail"]
    assert "Invalid username or password" in resp_missing.json()["detail"]


def test_login_rate_limiting():
    username = "ratelimiter"
    for _ in range(5):
        response = client.post(
            "/api/v1/auth/token",
            data={"username": username, "password": "wrong"}
        )
        assert response.status_code == 401

    response = client.post(
        "/api/v1/auth/token",
        data={"username": username, "password": "wrong"}
    )
    assert response.status_code == 429
    assert "too many login attempts" in response.json()["detail"].lower()


def test_register_rate_limiting():
    import random
    base = f"ratetest_{random.randint(1, 100000)}"
    for i in range(10):
        username = f"{base}_{i}"
        response = client.post(
            "/api/v1/auth/register",
            json={
                "username": username,
                "email": f"{username}@example.com",
                "password": "testpass123",
                "full_name": "Test"
            }
        )
        # Since we mock, we expect 200 for all successful creations
        assert response.status_code in [200, 409]

    username11 = f"{base}_11"
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username11,
            "email": f"{username11}@example.com",
            "password": "testpass123",
            "full_name": "Test"
        }
    )
    assert response.status_code == 429
    assert "registration attempts" in response.json()["detail"].lower()


def test_register_generic_error_message():
    # Case 1: username collides ("testuser" exists), email is fresh.
    resp_username_collision = client.post(
        "/api/v1/auth/register",
        json={
            "username": "testuser",
            "email": "brandnew_email_xyz@example.com",
            "password": "testpass123",
            "full_name": "Test"
        }
    )

    # Case 2: email collides ("existing_email_only@example.com" exists),
    # username is fresh. Before the fix these two cases returned different
    # messages ("Username already exists" vs "Email already exists"),
    # letting an attacker tell exactly which field matched.
    resp_email_collision = client.post(
        "/api/v1/auth/register",
        json={
            "username": "brandnewusername123",
            "email": "existing_email_only@example.com",
            "password": "testpass123",
            "full_name": "Test"
        }
    )

    assert resp_username_collision.status_code == 409
    assert resp_email_collision.status_code == 409
    assert resp_username_collision.json()["detail"] == resp_email_collision.json()["detail"]

    # The message must not be the old field-specific wording — only that
    # some part of the submission already exists, without naming which.
    detail = resp_username_collision.json()["detail"]
    assert detail != "Username already exists"
    assert detail != "Email already exists"
    assert detail == "An account with this username or email already exists"


def test_protected_endpoint_without_token():
    response = client.post(
        "/api/v1/sms/send-summary",
        json={"phone_number": "+1234567890", "message": "Test"}
    )
    assert response.status_code == 401


def test_sms_rate_limiting():
    token_response = client.post(
        "/api/v1/auth/token",
        data={"username": "testuser", "password": "testpass123"}
    )
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response1 = client.post(
        "/api/v1/sms/send-summary",
        json={"phone_number": "+1234567890", "message": "Test"},
        headers=headers
    )
    assert response1.status_code in [200, 501, 500]

    response2 = client.post(
        "/api/v1/sms/send-summary",
        json={"phone_number": "+1234567890", "message": "Test"},
        headers=headers
    )
    assert response2.status_code == 429


def test_get_profile():
    token_response = client.post(
        "/api/v1/auth/token",
        data={"username": "testuser", "password": "testpass123"}
    )
    assert token_response.status_code == 200
    token = token_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/auth/profile", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "testuser@example.com"
    assert "password" not in data


def test_patch_profile():
    token_response = client.post(
        "/api/v1/auth/token",
        data={"username": "testuser", "password": "testpass123"}
    )
    assert token_response.status_code == 200
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
    assert data["username"] == "testuser"
    assert "password" not in data