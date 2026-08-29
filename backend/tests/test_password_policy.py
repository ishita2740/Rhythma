"""Password policy on registration and reset (issue #330).

The rule-level tests are plain function calls — no HTTP, no mocks — so a
failure points at the rule rather than at a route. The endpoint tests then
check the two things only integration can: that a rejection is a 422 whose
body carries *every* broken rule, and that `/register` and `/reset-password`
enforce the identical policy. That last one is the whole reason the rules
live in one module, so it is asserted rather than assumed.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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


sys.modules.setdefault("google.generativeai", MockGemini())

os.environ["JWT_SECRET"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GEMINI_API_KEY"] = "mock-key"
os.environ["COOKIE_SECURE"] = "false"

_existing = sys.modules.get("firebase_admin")
if isinstance(_existing, MagicMock):
    mock_firebase_admin = _existing
else:
    mock_firebase_admin = MagicMock(_apps={})
    sys.modules["firebase_admin"] = mock_firebase_admin
    sys.modules["firebase_admin.auth"] = mock_firebase_admin.auth
    sys.modules["firebase_admin.credentials"] = MagicMock()
    sys.modules["firebase_admin.firestore"] = MagicMock()

from main import app  # noqa: E402
from core.password_policy import (  # noqa: E402
    DEFAULT_MIN_LENGTH,
    MAX_PASSWORD_BYTES,
    WeakPasswordError,
    enforce_password_policy,
    min_length,
    requirements,
    validate_password,
)
from core.auth import generate_reset_token, get_password_hash  # noqa: E402
from services.rate_limit_service import RateLimitService  # noqa: E402

client = TestClient(app)

GOOD_PASSWORD = "kolkata-monsoon-77"
USER_EMAIL = "sana@example.com"


def codes(password, **kwargs):
    return {failure.code for failure in validate_password(password, **kwargs)}


@pytest.fixture(autouse=True)
def _clean_state():
    client.cookies.clear()
    RateLimitService.clear_all()
    yield
    RateLimitService.clear_all()


@pytest.fixture(autouse=True)
def _mock_user_service():
    stored = {
        "id": "policy-user",
        "email": USER_EMAIL,
        "username": "sanakumari",
        "password": get_password_hash(GOOD_PASSWORD),
        "email_verified": True,
        "created_at": "2026-01-01T00:00:00Z",
    }

    with patch("core.auth_router.UserService") as mock_service:
        mock_service.get_user_by_email.side_effect = (
            lambda email: stored.copy() if email == USER_EMAIL else None
        )
        mock_service.get_user_by_id.return_value = stored.copy()
        mock_service.create_user.return_value = "created-user-id"
        mock_service.update_user.return_value = None
        yield mock_service


# ─── The rules ────────────────────────────────────────────────────────────


def test_a_reasonable_password_passes():
    assert validate_password(GOOD_PASSWORD, email=USER_EMAIL) == []


@pytest.mark.parametrize(
    "password",
    [
        "kolkata-monsoon-77",
        "chai without sugar",
        "9-cycles-and-counting",
        "MyDogIsCalledLaddoo",
    ],
)
def test_ordinary_good_passwords_are_not_rejected(password):
    """The policy has to stay usable, not just strict.

    Every one of these is something a real person might pick, and none of
    them satisfies a classic "uppercase + digit + symbol" rule. If a change
    to the rules starts rejecting these, the change is wrong.
    """
    assert validate_password(password, email=USER_EMAIL, username="sanakumari") == []


def test_an_empty_password_reports_one_thing_not_eight():
    """An empty box breaks every rule; saying so eight times is noise."""
    assert codes("") == {"password_required"}


def test_a_password_of_only_spaces_is_rejected():
    assert codes("        ") == {"password_blank"}


def test_short_passwords_are_rejected():
    assert "too_short" in codes("abc1")
    assert "too_short" in codes("a" * (DEFAULT_MIN_LENGTH - 1))


def test_a_password_exactly_at_the_minimum_is_accepted():
    """Off-by-one at the boundary would be invisible and annoying."""
    assert "too_short" not in codes("hibiscus")


def test_passwords_beyond_bcrypts_72_bytes_are_rejected():
    """bcrypt ignores everything past 72 bytes — that must not pass silently."""
    assert "too_long" in codes("a" * 73)
    assert "too_long" not in codes("a1b2c3d4" + "z" * 60)


def test_the_byte_ceiling_is_measured_in_bytes_not_characters():
    """A 25-character Hindi passphrase is already over the line.

    Most Devanagari characters cost three UTF-8 bytes, so an
    Indian-language passphrase hits bcrypt's limit at roughly a third of
    the character count an English one does. Truncating it silently would
    hand the user a password that isn't the one she typed — for an app
    built for Indian languages first, that is the case that matters.
    """
    hindi = "सुरक्षितपासवर्डहैयहबहुतअच्छा"

    assert len(hindi) < MAX_PASSWORD_BYTES
    assert len(hindi.encode("utf-8")) > MAX_PASSWORD_BYTES
    assert "too_long" in codes(hindi)


def test_a_short_indian_language_password_is_still_fine():
    assert "too_long" not in codes("पासवर्ड२०२६")


@pytest.mark.parametrize("password", ["password", "PASSWORD", "Password", "qwerty123", "iloveyou"])
def test_common_passwords_are_rejected_regardless_of_case(password):
    assert "too_common" in codes(password)


def test_a_password_containing_the_email_local_part_is_rejected():
    assert "contains_identifier" in codes("sana-loves-mangoes", email="sana@example.com")


def test_a_password_containing_the_email_domain_is_rejected():
    assert "contains_identifier" in codes("example-2026-pass", email="sana@example.com")


def test_a_password_containing_the_username_is_rejected():
    assert "contains_identifier" in codes("sanakumari2026", username="sanakumari")


def test_the_identifier_check_ignores_case():
    assert "contains_identifier" in codes("SANA-loves-mangoes", email="sana@example.com")


def test_short_identifier_fragments_do_not_trigger_false_positives():
    """`k@example.com` must not make every password containing `k` illegal."""
    assert "contains_identifier" not in codes("kolkata-monsoon-77", email="k@example.com")


def test_repetitive_passwords_are_rejected():
    assert "not_varied_enough" in codes("aaaaaaaa")
    assert "not_varied_enough" in codes("abababababab")


@pytest.mark.parametrize(
    "password",
    ["abcdefgh", "12345678", "qwertyuiop", "87654321", "my-password-12345"],
)
def test_sequential_runs_are_rejected(password):
    assert "sequential" in codes(password)


def test_an_ordinary_word_containing_three_sequential_letters_is_fine():
    """`rst` in `first` is not a keyboard walk; the run threshold is 5."""
    assert "sequential" not in codes("first-monsoon-rain")


def test_every_broken_rule_is_reported_together():
    """One complaint per submission is how users end up at `Password1!`."""
    found = codes("123456", email=USER_EMAIL)
    assert {"too_short", "too_common", "sequential"} <= found


# ─── Configuration ────────────────────────────────────────────────────────


def test_min_length_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("PASSWORD_MIN_LENGTH", raising=False)
    assert min_length() == DEFAULT_MIN_LENGTH


def test_min_length_can_be_raised(monkeypatch):
    monkeypatch.setenv("PASSWORD_MIN_LENGTH", "12")
    assert min_length() == 12
    assert "too_short" in codes("hibiscus")


def test_min_length_cannot_be_lowered_below_the_default(monkeypatch):
    """Weakening a password policy by environment variable is not a feature."""
    monkeypatch.setenv("PASSWORD_MIN_LENGTH", "3")
    assert min_length() == DEFAULT_MIN_LENGTH


def test_an_unparseable_min_length_falls_back(monkeypatch):
    monkeypatch.setenv("PASSWORD_MIN_LENGTH", "eight")
    assert min_length() == DEFAULT_MIN_LENGTH


# ─── enforce_password_policy ──────────────────────────────────────────────


def test_enforce_is_silent_for_a_good_password():
    enforce_password_policy(GOOD_PASSWORD, email=USER_EMAIL)


def test_enforce_raises_with_every_failure_attached():
    with pytest.raises(WeakPasswordError) as exc:
        enforce_password_policy("123456", email=USER_EMAIL)

    assert exc.value.status_code == 422
    assert exc.value.code == "weak_password"
    reported = {item["code"] for item in exc.value.details}
    assert {"too_short", "too_common", "sequential"} <= reported


def test_the_error_never_echoes_the_password_back():
    """A rejected password must not end up in a response body or a log line."""
    with pytest.raises(WeakPasswordError) as exc:
        enforce_password_policy("qwerty123", email=USER_EMAIL)

    rendered = str(exc.value.details) + exc.value.message
    assert "qwerty123" not in rendered


# ─── Endpoints ────────────────────────────────────────────────────────────


def test_register_rejects_a_weak_password():
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "123456"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "weak_password"
    reported = {item["code"] for item in body["error"]["details"]}
    assert {"too_short", "too_common"} <= reported


def test_register_rejects_a_password_containing_the_email(_mock_user_service):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "sana@example.com", "password": "sana-loves-mangoes"},
    )

    assert response.status_code == 422
    assert "contains_identifier" in {
        item["code"] for item in response.json()["error"]["details"]
    }


def test_register_checks_the_password_before_touching_the_user_store(_mock_user_service):
    client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "123456"},
    )
    _mock_user_service.create_user.assert_not_called()


def test_register_still_accepts_a_good_password():
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": GOOD_PASSWORD},
    )

    assert response.status_code == 200
    assert response.json()["email"] == "new@example.com"


def test_reset_password_rejects_a_weak_new_password():
    token = generate_reset_token(USER_EMAIL)

    response = client.post(
        "/api/v1/auth/reset-password",
        json={"email": USER_EMAIL, "token": token, "new_password": "abc"},
    )

    assert response.status_code == 422
    assert "too_short" in {item["code"] for item in response.json()["error"]["details"]}


def test_reset_password_does_not_write_a_rejected_password(_mock_user_service):
    token = generate_reset_token(USER_EMAIL)

    client.post(
        "/api/v1/auth/reset-password",
        json={"email": USER_EMAIL, "token": token, "new_password": "password"},
    )

    _mock_user_service.update_user.assert_not_called()


def test_reset_password_checks_the_token_before_the_policy():
    """An invalid token is a 400 — the policy must not answer first.

    If the weak-password 422 came back before the token check, this route
    would tell an unauthenticated caller which passwords are acceptable and
    confirm the account exists, which is exactly what the token is for.
    """
    response = client.post(
        "/api/v1/auth/reset-password",
        json={"email": USER_EMAIL, "token": "wrong-token", "new_password": "abc"},
    )

    assert response.status_code == 400


def test_reset_password_accepts_a_good_new_password(_mock_user_service):
    token = generate_reset_token(USER_EMAIL)

    response = client.post(
        "/api/v1/auth/reset-password",
        json={
            "email": USER_EMAIL,
            "token": token,
            "new_password": "chennai-rain-2026",
        },
    )

    assert response.status_code == 200
    _mock_user_service.update_user.assert_called_once()


@pytest.mark.parametrize(
    "password", ["a", "password", "12345678", "aaaaaaaa", "qwertyuiop"]
)
def test_register_and_reset_enforce_the_same_policy(password):
    """The two paths must not drift — that's why the rules live in one module."""
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": "parity@example.com", "password": password},
    )

    token = generate_reset_token(USER_EMAIL)
    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"email": USER_EMAIL, "token": token, "new_password": password},
    )

    assert registered.status_code == 422
    assert reset.status_code == 422


# ─── GET /auth/password-requirements ──────────────────────────────────────


def test_password_requirements_are_published():
    response = client.get("/api/v1/auth/password-requirements")

    assert response.status_code == 200
    body = response.json()
    assert body["minLength"] == min_length()
    assert body["maxBytes"] == MAX_PASSWORD_BYTES
    assert len(body["rules"]) >= 4
    assert all({"code", "message"} <= set(rule) for rule in body["rules"])


def test_published_requirements_track_the_configured_minimum(monkeypatch):
    monkeypatch.setenv("PASSWORD_MIN_LENGTH", "14")

    response = client.get("/api/v1/auth/password-requirements")

    assert response.status_code == 200
    assert response.json()["minLength"] == 14
    assert "14" in " ".join(rule["message"] for rule in response.json()["rules"])


def test_every_published_rule_can_actually_fire():
    """A rule shown to users that no code enforces is a lie in the UI."""
    published = {rule["code"] for rule in requirements()["rules"]}

    enforceable = set()
    for password, kwargs in [
        ("abc", {}),
        ("a" * 100, {}),
        ("password", {}),
        ("sana-loves-mangoes", {"email": USER_EMAIL}),
        ("aaaaaaaa", {}),
        ("12345678", {}),
    ]:
        enforceable |= codes(password, **kwargs)

    assert published <= enforceable
