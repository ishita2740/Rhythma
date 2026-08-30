"""Rate limiting on the authentication surface (issue #329).

Two layers are covered here.

The policy layer (`core/rate_limits.py`) is tested directly: environment
overrides, the refusal to accept a limit of zero, and the fact that an
identifier never reaches storage in plaintext.

The routes are tested through the real app, driving each endpoint until it
trips. Every test sets its own limits via `monkeypatch.setenv` rather than
firing the default number of requests — the defaults are a product decision
that should be tunable without rewriting the suite, and a test that hardcodes
"the 11th login fails" would have to change every time someone adjusts a
ceiling. What is asserted is the *shape*: N allowed, N+1 refused, with a
usable `Retry-After`.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

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


sys.modules.setdefault("google.generativeai", MockGemini())

os.environ["JWT_SECRET"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GEMINI_API_KEY"] = "mock-key"
os.environ["COOKIE_SECURE"] = "false"

# The route tests below drive each endpoint from a different address by
# sending `X-Forwarded-For`, which only means anything to a deployment that
# has declared it sits behind a proxy (#498). `*` accepts the TestClient's
# own peer as one, so these tests go on exercising the per-IP buckets they
# were written for. The spoofing cases further down clear it deliberately —
# what happens *without* this line is the security property, and it has its
# own tests rather than being the ambient default here.
os.environ["TRUSTED_PROXY_IPS"] = "*"

# ─── Mock firebase_admin ──────────────────────────────────────────────────
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
from core import rate_limits  # noqa: E402
from core.client_address import (  # noqa: E402
    TRUSTED_PROXY_HOPS_ENV,
    TRUSTED_PROXY_IPS_ENV,
)
from core.rate_limits import (  # noqa: E402
    LOGIN_ACCOUNT,
    LOGIN_IP,
    RateLimitPolicy,
    client_ip,
)
from core.auth import get_password_hash  # noqa: E402
from services.firestore_service import MockFirestoreClient  # noqa: E402
from services.rate_limit_service import RateLimitService  # noqa: E402

# ─── Patch db to use in-memory mock ──────────────────────────────────────
# The firebase_admin MagicMock may cause initialize_firebase() to set `db`
# to a plain MagicMock that doesn't persist data.  Replace both references
# with a single MockFirestoreClient so rate-limit buckets survive within a
# test but are cleared between tests by _clean_state.
import services.firestore_service as _fs_mod
import services.rate_limit_service as _rl_mod

_mock_db = MockFirestoreClient()
_fs_mod.db = _mock_db
_rl_mod.db = _mock_db

client = TestClient(app)

PASSWORD = "SecurePass123"
KNOWN_EMAIL = "known@example.com"


@pytest.fixture(autouse=True)
def _clean_state():
    """Every test starts with empty buckets and no cookies."""
    def _reset():
        client.cookies.clear()
        _mock_db._collections.clear()

    _reset()
    yield
    _reset()


@pytest.fixture(autouse=True)
def _mock_user_service():
    """One known account; every other address is unknown.

    Enough to exercise both sides of the login path — correct password,
    wrong password, and an email that was never registered — without a
    database.
    """
    stored = {
        "id": "rate-limit-user",
        "email": KNOWN_EMAIL,
        "password": get_password_hash(PASSWORD),
        "email_verified": True,
        "created_at": "2026-01-01T00:00:00Z",
    }

    def get_by_email(email):
        return stored.copy() if email == KNOWN_EMAIL else None

    with patch("core.auth_router.UserService") as mock_service:
        mock_service.get_user_by_email.side_effect = get_by_email
        mock_service.get_user_by_id.return_value = stored.copy()
        mock_service.create_user.return_value = "new-user-id"
        mock_service.update_user.return_value = None
        yield mock_service


def _login(email, password=PASSWORD, ip="203.0.113.10"):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"X-Forwarded-For": ip},
    )


# ─── Policy objects ───────────────────────────────────────────────────────


def test_policy_uses_its_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_LOGIN_IP_MAX", raising=False)
    monkeypatch.delenv("RATE_LIMIT_LOGIN_IP_WINDOW", raising=False)

    assert LOGIN_IP.limit == LOGIN_IP.default_limit
    assert LOGIN_IP.window_seconds == LOGIN_IP.default_window


def test_policy_reads_overrides_from_the_environment(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "3")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_WINDOW", "60")

    assert LOGIN_IP.limit == 3
    assert LOGIN_IP.window_seconds == 60


@pytest.mark.parametrize("bad", ["0", "-5", "", "ten", "5.5"])
def test_a_bad_override_falls_back_instead_of_disabling_the_limit(monkeypatch, bad):
    """A limit of 0 would let everything through — refuse to read it that way.

    This is the failure mode worth guarding: a typo'd or empty environment
    variable in a deploy config silently turning a protection off is far
    likelier than someone genuinely wanting a zero-attempt ceiling.
    """
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", bad)
    assert LOGIN_IP.limit == LOGIN_IP.default_limit


def test_identifiers_are_hashed_before_they_become_storage_keys():
    key = LOGIN_ACCOUNT.key_for("sana@example.com")

    assert "sana@example.com" not in key
    assert "sana" not in key
    assert key.startswith("login_account:")


def test_the_same_identifier_always_maps_to_the_same_key():
    assert LOGIN_ACCOUNT.key_for("a@b.com") == LOGIN_ACCOUNT.key_for("a@b.com")


def test_identifier_matching_ignores_case_and_surrounding_space():
    """`Sana@Example.com ` and `sana@example.com` are one account, so one bucket."""
    assert LOGIN_ACCOUNT.key_for(" Sana@Example.com ") == LOGIN_ACCOUNT.key_for(
        "sana@example.com"
    )


def test_different_identifiers_map_to_different_keys():
    assert LOGIN_ACCOUNT.key_for("a@b.com") != LOGIN_ACCOUNT.key_for("c@d.com")


def test_policies_do_not_share_a_bucket():
    """The same address under two policies must not spend one budget."""
    assert LOGIN_ACCOUNT.key_for("a@b.com") != LOGIN_IP.key_for("a@b.com")


def test_enforce_allows_up_to_the_limit_then_raises_429():
    from fastapi import HTTPException

    policy = RateLimitPolicy(
        name="unit_test_bucket",
        default_limit=2,
        default_window=300,
        message="wait {seconds}",
    )

    rate_limits.enforce(policy, "someone")
    rate_limits.enforce(policy, "someone")

    with pytest.raises(HTTPException) as exc:
        rate_limits.enforce(policy, "someone")

    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"].isdigit()
    assert int(exc.value.headers["Retry-After"]) >= 1


def test_clear_frees_the_bucket_again():
    policy = RateLimitPolicy(
        name="unit_test_clear",
        default_limit=1,
        default_window=300,
        message="wait {seconds}",
    )

    rate_limits.enforce(policy, "someone")
    rate_limits.clear(policy, "someone")

    # Would raise if the earlier attempt were still counted.
    rate_limits.enforce(policy, "someone")


def test_clearing_a_bucket_that_was_never_used_is_not_an_error():
    policy = RateLimitPolicy(
        name="unit_test_never_used",
        default_limit=1,
        default_window=300,
        message="wait {seconds}",
    )
    rate_limits.clear(policy, "nobody")


# ─── client_ip ────────────────────────────────────────────────────────────


class _FakeRequest:
    def __init__(self, headers=None, host="198.51.100.7"):
        self.headers = headers or {}
        self.client = MagicMock(host=host) if host is not None else None


def test_client_ip_takes_the_last_forwarded_address_not_the_first():
    """Right to left, because that is the end a proxy writes.

    This used to assert the first entry, which is the one the *client*
    supplies: a proxy appends its view of its peer to the right, so
    everything left of that is unverified (#498). With `TRUSTED_PROXY_IPS`
    set to `*` at the top of this module, all three entries look like
    candidates and the right-most is the only one nobody downstream could
    have written.

    `core/tests/test_client_address.py` covers the resolution itself; what
    matters here is that `client_ip` is wired to it.
    """
    request = _FakeRequest({"X-Forwarded-For": "203.0.113.5, 70.41.3.18, 150.172.238.178"})
    assert client_ip(request) == "150.172.238.178"


def test_client_ip_falls_back_to_the_socket_address():
    assert client_ip(_FakeRequest(host="198.51.100.7")) == "198.51.100.7"


def test_client_ip_is_unknown_when_there_is_nothing_to_read():
    """Unattributable callers share one bucket rather than escaping the limit."""
    assert client_ip(_FakeRequest(host=None)) == "unknown"
    assert client_ip(None) == "unknown"


def test_an_empty_forwarded_header_falls_through_to_the_socket():
    request = _FakeRequest({"X-Forwarded-For": "  "}, host="198.51.100.7")
    assert client_ip(request) == "198.51.100.7"


def test_client_ip_ignores_the_header_when_no_proxy_is_declared(monkeypatch):
    """The default deployment: nothing in front, so the header is a claim."""
    monkeypatch.delenv(TRUSTED_PROXY_IPS_ENV, raising=False)

    request = _FakeRequest({"X-Forwarded-For": "203.0.113.5"}, host="198.51.100.7")
    assert client_ip(request) == "198.51.100.7"


def test_client_ip_honours_a_declared_hop_count(monkeypatch):
    """A platform balancer that appends exactly one entry of its own."""
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "*")
    monkeypatch.setenv(TRUSTED_PROXY_HOPS_ENV, "1")

    request = _FakeRequest(
        {"X-Forwarded-For": "1.1.1.1, 203.0.113.5, 169.254.8.8"},
        host="169.254.1.1",
    )
    assert client_ip(request) == "203.0.113.5"


# ─── Spoofing the bucket key ──────────────────────────────────────────────


def test_a_direct_caller_cannot_reset_a_limit_by_changing_the_header(monkeypatch):
    """The attack #498 is about, driven through a real route.

    No trusted proxy is declared, so the reset-token endpoint — which has
    no second, account-keyed bucket — must count all of these against the
    one address the requests actually came from, however many different
    ones they claim.
    """
    monkeypatch.delenv(TRUSTED_PROXY_IPS_ENV, raising=False)
    monkeypatch.setenv("RATE_LIMIT_PASSWORD_RESET_CONFIRM_IP_MAX", "2")

    payload = {
        "email": KNOWN_EMAIL,
        "token": "not-a-real-token",
        "new_password": "AnotherPass456",
    }

    statuses = [
        client.post(
            "/api/v1/auth/reset-password",
            json=payload,
            headers={"X-Forwarded-For": f"203.0.113.{n}"},
        ).status_code
        for n in range(1, 6)
    ]

    # Two guesses land, the rest are refused — the header bought nothing.
    assert statuses[:2] == [400, 400]
    assert statuses[2:] == [429, 429, 429]


def test_registration_cannot_be_sprayed_from_one_address(monkeypatch):
    """`REGISTER_IP` has no second key either, so the same property holds."""
    monkeypatch.delenv(TRUSTED_PROXY_IPS_ENV, raising=False)
    monkeypatch.setenv("RATE_LIMIT_REGISTER_IP_MAX", "2")

    statuses = [
        client.post(
            "/api/v1/auth/register",
            json={"email": f"spray{n}@example.com", "password": PASSWORD},
            headers={"X-Forwarded-For": f"198.51.100.{n}"},
        ).status_code
        for n in range(1, 5)
    ]

    assert statuses == [200, 200, 429, 429]


def test_a_caller_behind_a_declared_proxy_cannot_prepend_entries(monkeypatch):
    """Half-way case: the header *is* read, and still is not the caller's to choose.

    Every request claims a different address on the left. The TestClient's
    own peer is the only proxy, so the right-most entry is what each
    request is bucketed on — and it is the same one every time.
    """
    monkeypatch.setenv(TRUSTED_PROXY_IPS_ENV, "*")
    monkeypatch.setenv("RATE_LIMIT_EMAIL_VERIFY_IP_MAX", "2")

    payload = {"email": KNOWN_EMAIL, "token": "not-a-real-token"}

    statuses = [
        client.post(
            "/api/v1/auth/verify-email",
            json=payload,
            headers={"X-Forwarded-For": f"10.9.9.{n}, 203.0.113.200"},
        ).status_code
        for n in range(1, 5)
    ]

    assert statuses == [400, 400, 429, 429]


# ─── Login ────────────────────────────────────────────────────────────────


def test_login_is_limited_per_account(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_MAX", "3")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "50")  # keep the other key out of it

    for _ in range(3):
        assert _login(KNOWN_EMAIL, "wrong-password").status_code == 401

    blocked = _login(KNOWN_EMAIL, "wrong-password")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_the_per_account_limit_follows_the_account_across_addresses(monkeypatch):
    """A botnet spreading guesses over many IPs still spends one account budget."""
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_MAX", "3")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "50")

    for i in range(3):
        assert _login(KNOWN_EMAIL, "wrong", ip=f"203.0.113.{i}").status_code == 401

    assert _login(KNOWN_EMAIL, "wrong", ip="203.0.113.99").status_code == 429


def test_login_is_limited_per_ip_across_different_accounts(monkeypatch):
    """And one address walking the user table spends one IP budget."""
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "3")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_MAX", "50")

    for i in range(3):
        assert _login(f"victim{i}@example.com", "wrong").status_code == 401

    assert _login("victim99@example.com", "wrong").status_code == 429


def test_one_clients_limit_does_not_affect_another(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "2")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_MAX", "50")

    for _ in range(2):
        _login("a@example.com", "wrong", ip="203.0.113.1")
    assert _login("a@example.com", "wrong", ip="203.0.113.1").status_code == 429

    # A different device is unaffected.
    assert _login("a@example.com", "wrong", ip="198.51.100.1").status_code == 401


def test_a_successful_login_clears_that_accounts_attempts(monkeypatch):
    """Three typos then the right password must not leave her near a lockout."""
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_MAX", "4")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "50")

    for _ in range(3):
        assert _login(KNOWN_EMAIL, "wrong").status_code == 401

    assert _login(KNOWN_EMAIL).status_code == 200

    # Without the reset, one more wrong attempt would be the 5th and blocked.
    assert _login(KNOWN_EMAIL, "wrong").status_code == 401


def test_a_successful_login_does_not_clear_the_ip_bucket(monkeypatch):
    """A machine that guessed one account right is still suspect for the rest."""
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "3")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_MAX", "50")

    assert _login("other1@example.com", "wrong").status_code == 401
    assert _login("other2@example.com", "wrong").status_code == 401
    assert _login(KNOWN_EMAIL).status_code == 200

    assert _login("other3@example.com", "wrong").status_code == 429


def test_unknown_emails_are_counted_too(monkeypatch):
    """Otherwise being throttled would itself reveal that an account exists."""
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_MAX", "2")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "50")

    assert _login("ghost@example.com", "x").status_code == 401
    assert _login("ghost@example.com", "x").status_code == 401
    assert _login("ghost@example.com", "x").status_code == 429


def test_retry_after_is_a_usable_number_of_seconds(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_MAX", "1")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_ACCOUNT_WINDOW", "120")
    monkeypatch.setenv("RATE_LIMIT_LOGIN_IP_MAX", "50")

    _login(KNOWN_EMAIL, "wrong")
    blocked = _login(KNOWN_EMAIL, "wrong")

    assert blocked.status_code == 429
    retry_after = int(blocked.headers["Retry-After"])
    assert 1 <= retry_after <= 120
    assert str(retry_after) in blocked.json()["detail"]


# ─── The other auth routes ────────────────────────────────────────────────


def test_register_is_limited(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_REGISTER_IP_MAX", "2")

    for i in range(2):
        response = client.post(
            "/api/v1/auth/register",
            json={"email": f"new{i}@example.com", "password": PASSWORD},
            headers={"X-Forwarded-For": "203.0.113.50"},
        )
        assert response.status_code == 200

    blocked = client.post(
        "/api/v1/auth/register",
        json={"email": "new99@example.com", "password": PASSWORD},
        headers={"X-Forwarded-For": "203.0.113.50"},
    )
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_register_is_limited_before_the_email_lookup(monkeypatch, _mock_user_service):
    """The 409-vs-200 difference is an enumeration oracle; throttle it first."""
    monkeypatch.setenv("RATE_LIMIT_REGISTER_IP_MAX", "1")

    client.post(
        "/api/v1/auth/register",
        json={"email": "first@example.com", "password": PASSWORD},
        headers={"X-Forwarded-For": "203.0.113.51"},
    )
    _mock_user_service.get_user_by_email.reset_mock()

    blocked = client.post(
        "/api/v1/auth/register",
        json={"email": KNOWN_EMAIL, "password": PASSWORD},
        headers={"X-Forwarded-For": "203.0.113.51"},
    )

    assert blocked.status_code == 429
    _mock_user_service.get_user_by_email.assert_not_called()


def test_forgot_password_is_limited_per_account(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PASSWORD_RESET_REQUEST_ACCOUNT_MAX", "2")
    monkeypatch.setenv("RATE_LIMIT_PASSWORD_RESET_REQUEST_IP_MAX", "50")

    for i in range(2):
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": KNOWN_EMAIL},
            headers={"X-Forwarded-For": f"203.0.113.{i}"},
        )
        assert response.status_code == 200

    blocked = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": KNOWN_EMAIL},
        headers={"X-Forwarded-For": "198.51.100.9"},
    )
    assert blocked.status_code == 429


def test_forgot_password_is_also_limited_per_ip(monkeypatch):
    """One machine must not be able to spray reset mail across many accounts."""
    monkeypatch.setenv("RATE_LIMIT_PASSWORD_RESET_REQUEST_IP_MAX", "2")
    monkeypatch.setenv("RATE_LIMIT_PASSWORD_RESET_REQUEST_ACCOUNT_MAX", "50")

    for i in range(2):
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": f"target{i}@example.com"},
            headers={"X-Forwarded-For": "203.0.113.60"},
        )
        assert response.status_code == 200

    blocked = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "target99@example.com"},
        headers={"X-Forwarded-For": "203.0.113.60"},
    )
    assert blocked.status_code == 429


def test_reset_password_token_submissions_are_limited(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PASSWORD_RESET_CONFIRM_IP_MAX", "2")

    payload = {
        "email": KNOWN_EMAIL,
        "token": "not-a-real-token",
        "new_password": "AnotherPass456",
    }
    headers = {"X-Forwarded-For": "203.0.113.70"}

    for _ in range(2):
        assert client.post("/api/v1/auth/reset-password", json=payload, headers=headers).status_code == 400

    blocked = client.post("/api/v1/auth/reset-password", json=payload, headers=headers)
    assert blocked.status_code == 429


def test_verify_email_token_submissions_are_limited(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_EMAIL_VERIFY_IP_MAX", "2")

    payload = {"email": KNOWN_EMAIL, "token": "not-a-real-token"}
    headers = {"X-Forwarded-For": "203.0.113.80"}

    for _ in range(2):
        assert client.post("/api/v1/auth/verify-email", json=payload, headers=headers).status_code == 400

    assert client.post("/api/v1/auth/verify-email", json=payload, headers=headers).status_code == 429


def test_resend_verification_is_limited_per_account(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_VERIFICATION_RESEND_ACCOUNT_MAX", "1")
    monkeypatch.setenv("RATE_LIMIT_EMAIL_VERIFY_IP_MAX", "50")

    first = client.post(
        "/api/v1/auth/resend-verification",
        json={"email": KNOWN_EMAIL},
        headers={"X-Forwarded-For": "203.0.113.90"},
    )
    assert first.status_code == 200

    blocked = client.post(
        "/api/v1/auth/resend-verification",
        json={"email": KNOWN_EMAIL},
        headers={"X-Forwarded-For": "198.51.100.90"},
    )
    assert blocked.status_code == 429


def test_refresh_is_limited(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_TOKEN_REFRESH_IP_MAX", "2")

    payload = {"refresh_token": "not-a-real-refresh-token"}
    headers = {"X-Forwarded-For": "203.0.113.100"}

    for _ in range(2):
        assert client.post("/api/v1/auth/refresh", json=payload, headers=headers).status_code == 401

    assert client.post("/api/v1/auth/refresh", json=payload, headers=headers).status_code == 429


def test_firebase_login_keeps_its_existing_ceiling():
    """Migrating this route to a policy must not change what it enforces."""
    from core.rate_limits import FIREBASE_LOGIN_IP

    assert FIREBASE_LOGIN_IP.default_limit == 10
    assert FIREBASE_LOGIN_IP.default_window == 300


def test_every_post_route_under_auth_is_covered():
    """A new unprotected POST route should fail this, not ship quietly.

    Routes that require an authenticated caller are exempt: reaching them
    already costs a valid token, and they are bounded by whatever minted it.
    """
    import inspect

    import core.auth_router as auth_router

    authenticated_or_stateless = {"/logout", "/logout-all"}
    unprotected = []

    for route in auth_router.router.routes:
        if "POST" not in getattr(route, "methods", set()):
            continue
        if route.path in authenticated_or_stateless:
            continue
        source = inspect.getsource(route.endpoint)
        if "enforce_rate_limit" not in source:
            unprotected.append(route.path)

    assert not unprotected, f"POST routes with no rate limit: {unprotected}"
