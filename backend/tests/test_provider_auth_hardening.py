"""Provider account security parity with the patient auth flow (issue #346).

The bug this file exists to prevent coming back is an *asymmetry*, not a
missing feature in isolation: ``/auth/register`` refused a one-character
password while ``/provider/register`` accepted it, and ``/auth/login`` was
metered on two keys while ``/provider/login`` was metered on one with
hardcoded numbers. So a good number of the tests below assert the two
routes behave the *same*, driving both with identical input and comparing
outcomes. A test that only pinned down the provider route's behaviour
would pass just as happily if the patient route later regressed to match
it, which is the wrong direction to converge.

Rate-limit tests set their own ceilings with ``monkeypatch.setenv`` rather
than firing the default number of requests. The defaults are a product
decision that should be tunable without rewriting this suite; what is
asserted is the shape — N allowed, N+1 refused, with a usable
``Retry-After`` — following the convention established in
``test_auth_rate_limits.py``.
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
from core.auth import get_password_hash  # noqa: E402
from core.auth_router import normalize_email  # noqa: E402
from core.password_policy import validate_password  # noqa: E402
from core.rate_limits import (  # noqa: E402
    LOGIN_ACCOUNT,
    LOGIN_IP,
    PROVIDER_REGISTER_IP,
    REGISTER_IP,
)
from services.rate_limit_service import RateLimitService  # noqa: E402

client = TestClient(app)

REGISTER_URL = "/api/v1/provider/register"
LOGIN_URL = "/api/v1/provider/login"
PATIENT_REGISTER_URL = "/api/v1/auth/register"
PATIENT_LOGIN_URL = "/api/v1/auth/login"

STRONG_PASSWORD = "Wintergreen!Harbour42"
PROVIDER_EMAIL = "dr.mehta@clinic.in"
PATIENT_EMAIL = "asha@example.com"

#: Passwords the policy exists to refuse. Every entry breaks at least one
#: rule in ``core/password_policy.py``; several break more than one, which
#: is deliberate — the error carries all failures and callers should not
#: depend on which one is listed first.
WEAK_PASSWORDS = [
    "a",
    "",
    "        ",
    "1234567",
    "password",
    "aaaaaaaaaaaa",
    "abcdefghijkl",
    "qwertyuiop",
]


# ─── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_state():
    """Every test starts with empty buckets and no cookies."""

    def _reset():
        client.cookies.clear()
        RateLimitService.clear_all()

    _reset()
    yield
    _reset()


class _FakeUserStore:
    """The smallest user store both routes can be driven against.

    Keyed on the *normalised* address, and canonicalising on both read and
    write, because that is what the real ``UserService`` does since #380.

    It did not always. This fake used to match byte-exactly, on the
    reasoning that "a store that matched case-insensitively on its own
    would hide a missing ``normalize_email`` call in the route" — correct
    while the routes were the only place canonicalisation happened. It
    stopped being correct when #380 moved that responsibility down into
    ``UserService.create_user`` / ``get_user_by_email``, precisely so that
    no route could forget it. A fake that is stricter than the thing it
    stands in for does not test the routes harder; it fails on behaviour
    the real store handles.

    The route-level assertions below are unchanged, and they are what
    actually pins the behaviour down: a case-variant registration is still
    a 409, a case-variant login still succeeds. Those pass or fail on what
    a caller sees, not on which layer performed the fold.
    """

    def __init__(self):
        self.users = {}
        self.next_id = 1

    def seed(self, email, password, role="provider", **extra):
        user_id = f"seeded-{role}-{self.next_id}"
        self.next_id += 1
        key = normalize_email(email)
        self.users[key] = {
            "id": user_id,
            "email": key,
            "password": get_password_hash(password),
            "email_verified": True,
            "role": role,
            **extra,
        }
        return user_id

    def get_user_by_email(self, email):
        found = self.users.get(normalize_email(email))
        return dict(found) if found else None

    def get_user_by_id(self, user_id):
        for user in self.users.values():
            if user["id"] == user_id:
                return dict(user)
        return None

    def create_user(self, data):
        user_id = f"created-{self.next_id}"
        self.next_id += 1
        key = normalize_email(data.get("email"))
        self.users[key] = {**data, "email": key, "id": user_id}
        return user_id

    def update_user(self, user_id, updates):
        return None


@pytest.fixture
def store():
    """Patch the user store seen by *both* routers.

    ``api/provider.py`` and ``core/auth_router.py`` each import
    ``UserService`` into their own namespace, so patching one module does
    not affect the other. Both are patched onto a single shared instance
    so a cross-route test (register as a provider, then try the patient
    login) sees one consistent set of accounts.
    """
    fake = _FakeUserStore()
    with patch("api.provider.UserService", fake), patch(
        "core.auth_router.UserService", fake
    ):
        yield fake


@pytest.fixture
def generous_limits(monkeypatch):
    """Lift every limit these tests are not specifically about.

    Without this, a test that registers four accounts to check something
    else trips ``PROVIDER_REGISTER_IP`` (default 3/hour) and fails for a
    reason that has nothing to do with what it asserts.
    """
    for policy in (REGISTER_IP, PROVIDER_REGISTER_IP, LOGIN_IP, LOGIN_ACCOUNT):
        monkeypatch.setenv(f"{policy.env_prefix}_MAX", "10000")
    yield


# ─── Password policy: the asymmetry itself ─────────────────────────────────


@pytest.mark.parametrize("password", WEAK_PASSWORDS)
def test_provider_register_refuses_weak_passwords(store, generous_limits, password):
    """The headline bug: ``{"password": "a"}`` used to return 201."""
    response = client.post(
        REGISTER_URL,
        json={"email": f"weak-{len(password)}@clinic.in", "password": password},
    )

    assert response.status_code == 422, (
        f"password {password!r} was accepted; policy failures: "
        f"{validate_password(password)}"
    )
    assert response.json()["error"]["code"] == "weak_password"
    assert store.users == {}, "a rejected registration must not create an account"


@pytest.mark.parametrize("password", WEAK_PASSWORDS)
def test_provider_and_patient_registration_agree_on_weak_passwords(
    store, generous_limits, password
):
    """Both routes must refuse the same password, with the same error code.

    This is the assertion that actually encodes issue #346. If either
    route is later loosened, the two stop agreeing and this fails.
    """
    provider = client.post(
        REGISTER_URL, json={"email": "sym-a@clinic.in", "password": password}
    )
    patient = client.post(
        PATIENT_REGISTER_URL, json={"email": "sym-b@example.com", "password": password}
    )

    assert provider.status_code == patient.status_code == 422
    assert (
        provider.json()["error"]["code"] == patient.json()["error"]["code"]
    ), "the two registration routes disagree about what a weak password is"


def test_provider_register_accepts_a_strong_password(store, generous_limits):
    response = client.post(
        REGISTER_URL,
        json={
            "email": PROVIDER_EMAIL,
            "password": STRONG_PASSWORD,
            "full_name": "Dr. Priya Mehta",
            "specialty": "Gynaecology",
            "license_number": "MH-2019-44821",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "provider"
    assert body["email"] == PROVIDER_EMAIL

    stored = store.users[PROVIDER_EMAIL]
    assert stored["role"] == "provider"
    assert stored["specialty"] == "Gynaecology"
    assert stored["license_number"] == "MH-2019-44821"


def test_password_containing_the_provider_email_is_refused(store, generous_limits):
    """The identifier rule must receive the email, not just the password."""
    response = client.post(
        REGISTER_URL,
        json={"email": "drmehta@clinic.in", "password": "drmehta@clinic.in!99X"},
    )

    assert response.status_code == 422
    codes = {d["code"] for d in response.json()["error"]["details"]}
    assert "contains_identifier" in codes


def test_password_containing_the_provider_username_is_refused(store, generous_limits):
    response = client.post(
        REGISTER_URL,
        json={
            "email": "someone@clinic.in",
            "password": "PriyaMehta!Winter42",
            "username": "PriyaMehta",
        },
    )

    assert response.status_code == 422
    codes = {d["code"] for d in response.json()["error"]["details"]}
    assert "contains_identifier" in codes


def test_the_password_is_never_echoed_in_a_rejection(store, generous_limits):
    """A 422 body must not carry the password it just refused.

    Error responses land in client logs and bug reports; the rejected
    password is very often a near-miss of the one finally chosen.
    """
    secret = "hunter2hunter2"
    response = client.post(
        REGISTER_URL, json={"email": "echo@clinic.in", "password": secret}
    )

    assert secret not in response.text


# ─── Free-text field bounds ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "field,length",
    [
        ("full_name", 500),
        ("username", 500),
        ("specialty", 500),
        ("license_number", 500),
    ],
)
def test_over_long_profile_fields_are_refused(store, generous_limits, field, length):
    response = client.post(
        REGISTER_URL,
        json={
            "email": f"long-{field}@clinic.in",
            "password": STRONG_PASSWORD,
            field: "x" * length,
        },
    )

    assert response.status_code == 422
    assert store.users == {}


def test_whitespace_only_profile_fields_are_stored_as_absent(store, generous_limits):
    """``full_name="   "`` must not become the provider's display name.

    ``provider_service`` renders ``full_name or username or email``; a
    blank string is truthy enough to win that chain and shows the patient
    an unnamed provider on her sharing screen.
    """
    response = client.post(
        REGISTER_URL,
        json={
            "email": "blank@clinic.in",
            "password": STRONG_PASSWORD,
            "full_name": "   ",
            "specialty": "\t\n ",
        },
    )

    assert response.status_code == 201
    stored = store.users["blank@clinic.in"]
    assert stored["full_name"] is None
    assert stored["specialty"] is None


def test_profile_fields_are_trimmed(store, generous_limits):
    client.post(
        REGISTER_URL,
        json={
            "email": "trim@clinic.in",
            "password": STRONG_PASSWORD,
            "full_name": "  Dr. Priya Mehta  ",
        },
    )

    assert store.users["trim@clinic.in"]["full_name"] == "Dr. Priya Mehta"


# ─── Email normalisation ───────────────────────────────────────────────────


def test_normalize_email_casefolds_and_strips():
    assert normalize_email("  Dr.Mehta@Clinic.IN ") == "dr.mehta@clinic.in"
    assert normalize_email("") == ""
    assert normalize_email(None) == ""


def test_registration_stores_the_normalised_address(store, generous_limits):
    response = client.post(
        REGISTER_URL, json={"email": "Dr.Mehta@Clinic.IN", "password": STRONG_PASSWORD}
    )

    assert response.status_code == 201
    assert response.json()["email"] == "dr.mehta@clinic.in"
    assert "dr.mehta@clinic.in" in store.users


def test_case_variant_registration_is_a_conflict_not_a_second_account(
    store, generous_limits
):
    """``Doc@Clinic.in`` and ``doc@clinic.in`` are one clinician."""
    first = client.post(
        REGISTER_URL, json={"email": "doc@clinic.in", "password": STRONG_PASSWORD}
    )
    second = client.post(
        REGISTER_URL, json={"email": "DOC@CLINIC.IN", "password": STRONG_PASSWORD}
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert len(store.users) == 1


def test_login_accepts_a_differently_cased_address(store, generous_limits):
    store.seed(PROVIDER_EMAIL, STRONG_PASSWORD)

    response = client.post(
        LOGIN_URL, json={"email": "Dr.Mehta@Clinic.IN", "password": STRONG_PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["role"] == "provider"


# ─── Login: rate limiting on two keys ──────────────────────────────────────


def test_provider_login_is_limited_per_account(store, generous_limits, monkeypatch):
    store.seed(PROVIDER_EMAIL, STRONG_PASSWORD)
    monkeypatch.setenv(f"{LOGIN_ACCOUNT.env_prefix}_MAX", "3")

    codes = [
        client.post(
            LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "WrongPassword!1"}
        ).status_code
        for _ in range(4)
    ]

    assert codes[:3] == [401, 401, 401]
    assert codes[3] == 429


def test_provider_login_is_limited_per_ip_across_different_accounts(
    store, generous_limits, monkeypatch
):
    """Per-account alone would miss a walk through the whole user table."""
    monkeypatch.setenv(f"{LOGIN_IP.env_prefix}_MAX", "3")

    codes = [
        client.post(
            LOGIN_URL, json={"email": f"victim{i}@clinic.in", "password": "Guess!1234"}
        ).status_code
        for i in range(4)
    ]

    assert codes[3] == 429, "a different address each time should still trip per-IP"


def test_rate_limited_login_carries_a_usable_retry_after(
    store, generous_limits, monkeypatch
):
    store.seed(PROVIDER_EMAIL, STRONG_PASSWORD)
    monkeypatch.setenv(f"{LOGIN_ACCOUNT.env_prefix}_MAX", "1")
    monkeypatch.setenv(f"{LOGIN_ACCOUNT.env_prefix}_WINDOW", "600")

    client.post(LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Wrong!12345"})
    blocked = client.post(
        LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Wrong!12345"}
    )

    assert blocked.status_code == 429
    retry_after = int(blocked.headers["Retry-After"])
    assert 0 < retry_after <= 600


def test_provider_and_patient_login_share_one_account_bucket(
    store, generous_limits, monkeypatch
):
    """Switching routes must not hand an attacker a fresh budget.

    Before #346 the provider route used its own unhashed ``login:{ip}``
    key, so a caller who exhausted patient login could simply continue
    against provider login with a full allowance.
    """
    store.seed(PROVIDER_EMAIL, STRONG_PASSWORD)
    monkeypatch.setenv(f"{LOGIN_ACCOUNT.env_prefix}_MAX", "2")

    client.post(LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Wrong!12345"})
    client.post(LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Wrong!12345"})

    spillover = client.post(
        PATIENT_LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Wrong!12345"}
    )

    assert spillover.status_code == 429


def test_provider_and_patient_login_share_one_ip_bucket(
    store, generous_limits, monkeypatch
):
    monkeypatch.setenv(f"{LOGIN_IP.env_prefix}_MAX", "2")

    client.post(LOGIN_URL, json={"email": "a@clinic.in", "password": "Wrong!12345"})
    client.post(LOGIN_URL, json={"email": "b@clinic.in", "password": "Wrong!12345"})

    spillover = client.post(
        PATIENT_LOGIN_URL, json={"email": "c@example.com", "password": "Wrong!12345"}
    )

    assert spillover.status_code == 429


def test_a_successful_login_clears_the_account_bucket(
    store, generous_limits, monkeypatch
):
    """Three typos then the right password must not leave her near lockout."""
    store.seed(PROVIDER_EMAIL, STRONG_PASSWORD)
    monkeypatch.setenv(f"{LOGIN_ACCOUNT.env_prefix}_MAX", "5")

    for _ in range(3):
        client.post(LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Nope!12345"})

    success = client.post(
        LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": STRONG_PASSWORD}
    )
    assert success.status_code == 200

    # The budget is whole again: five more wrong attempts are each answered
    # on their merits rather than the fourth being refused outright.
    after = [
        client.post(
            LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Nope!12345"}
        ).status_code
        for _ in range(5)
    ]
    assert after == [401] * 5


def test_a_successful_login_does_not_clear_the_ip_bucket(
    store, generous_limits, monkeypatch
):
    """One success says nothing about the other accounts being worked through."""
    store.seed(PROVIDER_EMAIL, STRONG_PASSWORD)
    monkeypatch.setenv(f"{LOGIN_IP.env_prefix}_MAX", "3")

    client.post(LOGIN_URL, json={"email": "x@clinic.in", "password": "Nope!12345"})
    client.post(LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": STRONG_PASSWORD})
    client.post(LOGIN_URL, json={"email": "y@clinic.in", "password": "Nope!12345"})

    assert (
        client.post(
            LOGIN_URL, json={"email": "z@clinic.in", "password": "Nope!12345"}
        ).status_code
        == 429
    )


def test_a_patient_hitting_the_provider_form_keeps_her_budget_intact(
    store, generous_limits, monkeypatch
):
    """A correct password on the wrong form is still a 403, not a reset.

    The account bucket is cleared only after the role check passes. If it
    were cleared on password success alone, a caller who knew one valid
    patient password could reset that account's bucket at will and use the
    provider form as an unlimited oracle.
    """
    store.seed(PATIENT_EMAIL, STRONG_PASSWORD, role="patient")
    monkeypatch.setenv(f"{LOGIN_ACCOUNT.env_prefix}_MAX", "3")

    codes = [
        client.post(
            LOGIN_URL, json={"email": PATIENT_EMAIL, "password": STRONG_PASSWORD}
        ).status_code
        for _ in range(4)
    ]

    assert codes[:3] == [403, 403, 403]
    assert codes[3] == 429


# ─── Registration rate limiting ────────────────────────────────────────────


def test_provider_registration_is_rate_limited(store, monkeypatch):
    """Thirty registrations from one address used to be thirty 201s."""
    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_MAX", "3")
    monkeypatch.setenv(f"{REGISTER_IP.env_prefix}_MAX", "10000")

    codes = [
        client.post(
            REGISTER_URL,
            json={"email": f"bulk{i}@clinic.in", "password": STRONG_PASSWORD},
        ).status_code
        for i in range(4)
    ]

    assert codes[:3] == [201, 201, 201]
    assert codes[3] == 429


def test_provider_registration_also_counts_against_the_shared_ceiling(
    store, monkeypatch
):
    """Switching to the provider form must not reset the account-creation budget."""
    monkeypatch.setenv(f"{REGISTER_IP.env_prefix}_MAX", "2")
    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_MAX", "10000")

    client.post(
        PATIENT_REGISTER_URL,
        json={"email": "p1@example.com", "password": STRONG_PASSWORD},
    )
    client.post(
        REGISTER_URL, json={"email": "d1@clinic.in", "password": STRONG_PASSWORD}
    )

    third = client.post(
        REGISTER_URL, json={"email": "d2@clinic.in", "password": STRONG_PASSWORD}
    )
    assert third.status_code == 429


def test_registration_is_metered_before_the_existence_check(store, monkeypatch):
    """The 409/201 split is an enumeration oracle; it must be metered.

    A caller probing which addresses are already registered gets the same
    429 as anyone else once the budget is gone — the limit is not spent
    only on *successful* registrations.
    """
    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_MAX", "2")
    monkeypatch.setenv(f"{REGISTER_IP.env_prefix}_MAX", "10000")
    store.seed("taken@clinic.in", STRONG_PASSWORD)

    first = client.post(
        REGISTER_URL, json={"email": "taken@clinic.in", "password": STRONG_PASSWORD}
    )
    second = client.post(
        REGISTER_URL, json={"email": "taken@clinic.in", "password": STRONG_PASSWORD}
    )
    third = client.post(
        REGISTER_URL, json={"email": "taken@clinic.in", "password": STRONG_PASSWORD}
    )

    assert first.status_code == second.status_code == 409
    assert third.status_code == 429


def test_a_weak_password_still_consumes_registration_budget(store, monkeypatch):
    """Rate limits run before the policy, so probing is not free."""
    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_MAX", "2")
    monkeypatch.setenv(f"{REGISTER_IP.env_prefix}_MAX", "10000")

    client.post(REGISTER_URL, json={"email": "w1@clinic.in", "password": "a"})
    client.post(REGISTER_URL, json={"email": "w2@clinic.in", "password": "a"})

    third = client.post(
        REGISTER_URL, json={"email": "w3@clinic.in", "password": STRONG_PASSWORD}
    )
    assert third.status_code == 429


# ─── Policy wiring ─────────────────────────────────────────────────────────


def test_provider_register_policy_is_tunable_from_the_environment(monkeypatch):
    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_MAX", "7")
    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_WINDOW", "120")

    assert PROVIDER_REGISTER_IP.limit == 7
    assert PROVIDER_REGISTER_IP.window_seconds == 120


def test_a_zero_limit_falls_back_rather_than_opening_the_gate(monkeypatch):
    """A typo in a deploy config must not disable the protection."""
    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_MAX", "0")
    assert PROVIDER_REGISTER_IP.limit == PROVIDER_REGISTER_IP.default_limit

    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_MAX", "-4")
    assert PROVIDER_REGISTER_IP.limit == PROVIDER_REGISTER_IP.default_limit

    monkeypatch.setenv(f"{PROVIDER_REGISTER_IP.env_prefix}_MAX", "not-a-number")
    assert PROVIDER_REGISTER_IP.limit == PROVIDER_REGISTER_IP.default_limit


def test_the_provider_register_bucket_is_distinct_from_the_shared_one():
    """Two policies, two namespaces — otherwise one would consume the other."""
    assert PROVIDER_REGISTER_IP.key_for("1.2.3.4") != REGISTER_IP.key_for("1.2.3.4")


def test_provider_bucket_keys_do_not_contain_the_identifier():
    """An address must not land in a Firestore document id in plaintext."""
    key = PROVIDER_REGISTER_IP.key_for("dr.mehta@clinic.in")
    assert "dr.mehta@clinic.in" not in key
    assert key.startswith("provider_register_ip:")


def test_login_buckets_are_case_insensitive_for_one_account():
    """Otherwise capitalisation alone would mint a fresh login budget."""
    assert LOGIN_ACCOUNT.key_for("Dr.Mehta@Clinic.IN") == LOGIN_ACCOUNT.key_for(
        "dr.mehta@clinic.in"
    )


def _bucket_ids():
    """Document ids currently in the mock Firestore rate-limit collection.

    Read through ``rate_limit_service.db`` rather than
    ``firestore_service.db``. The two are usually the same object, but
    ``services/rate_limit_service.py`` binds ``db`` at import time while
    other test modules reassign ``firestore_service.db`` to a fresh mock.
    Once that has happened the service is still writing to the handle it
    captured, so reading the other one finds an empty collection and this
    helper reports "no buckets written" for a request that wrote two.
    """
    from services import rate_limit_service as rls

    collections = getattr(rls.db, "_collections", None)
    if not collections:
        return set()
    return set((collections.get(RateLimitService.COLLECTION) or {}).keys())


def test_the_old_inline_login_key_is_no_longer_written(store, generous_limits):
    """The route used ``login:{ip}`` — an unhashed key in a shared namespace.

    Asserting its absence is what proves the migration actually happened,
    rather than a policy being added alongside the old call and both
    running.
    """
    store.seed(PROVIDER_EMAIL, STRONG_PASSWORD)
    client.post(LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Wrong!12345"})

    written = _bucket_ids()
    assert written, "the login attempt recorded no bucket at all"
    assert not any(
        key.startswith("login:") for key in written
    ), f"the inline login:{{ip}} key is still being written: {written}"


def test_provider_login_writes_both_policy_buckets(store, generous_limits):
    """One attempt should leave a record under each of the two keys."""
    store.seed(PROVIDER_EMAIL, STRONG_PASSWORD)
    client.post(LOGIN_URL, json={"email": PROVIDER_EMAIL, "password": "Wrong!12345"})

    written = _bucket_ids()
    assert LOGIN_IP.key_for("testclient") in written or any(
        key.startswith("login_ip:") for key in written
    )
    assert LOGIN_ACCOUNT.key_for(PROVIDER_EMAIL) in written
