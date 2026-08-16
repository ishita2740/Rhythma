"""Email addresses have one canonical form, everywhere (issue #380).

``core/auth_router.py`` already carried a ``normalize_email`` whose
docstring spelled out exactly why this matters — and no route in that
module called it. ``api/provider.py`` was its only caller, so the provider
flow normalised and the patient flow did not.

That shape is what most of this file asserts. Several tests drive the
patient and provider routes with the *same* mixed-case input and compare
the outcomes, rather than pinning down one route in isolation: a test that
only described the patient side would pass just as happily if the provider
side later regressed to match it, which is the wrong direction to
converge. It is the same reasoning ``test_provider_auth_hardening.py``
uses, and for the same class of bug.

The tests run against the real in-memory Firestore mock rather than a
stubbed ``UserService``. A hand-written store that matched
case-insensitively on its own would hide the very thing under test.
"""

import os
import sys
from unittest.mock import MagicMock

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
from core.auth import (  # noqa: E402
    generate_reset_token,
    generate_verification_token,
    get_password_hash,
    reset_token_store,
    verification_token_store,
    verify_email_token,
    verify_reset_token,
)
from core.auth_router import normalize_email as router_normalize_email  # noqa: E402
from core.email_identity import normalize_email, same_email  # noqa: E402
from services import token_store  # noqa: E402
from services.firestore_service import MockFirestoreClient, UserService  # noqa: E402
from services.rate_limit_service import RateLimitService  # noqa: E402

import services.firestore_service as _fs_mod  # noqa: E402
import services.rate_limit_service as _rl_mod  # noqa: E402

client = TestClient(app)

#: The client the test currently running is reading and writing.
#:
#: Swapped in per test by ``_isolated_db`` rather than assigned once at
#: import. The `firebase_admin` MagicMock can leave the real
#: ``firestore_service.db`` as a plain MagicMock that persists nothing, so
#: something has to stand in — but assigning a module global at import
#: time leaks: ``services.firestore_service.db`` is shared by every test
#: module in the run, several of which seed data at import and would then
#: have it wiped by this file's per-test reset. ``monkeypatch`` restores
#: whatever was there before, so nothing outside this file observes it.
_mock_db = None

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
FORGOT_URL = "/api/v1/auth/forgot-password"
RESET_URL = "/api/v1/auth/reset-password"
VERIFY_URL = "/api/v1/auth/verify-email"
RESEND_URL = "/api/v1/auth/resend-verification"
PROVIDER_REGISTER_URL = "/api/v1/provider/register"
PROVIDER_LOGIN_URL = "/api/v1/provider/login"

PASSWORD = "Wintergreen!Harbour42"

#: The same address, written the several ways a phone keyboard, a password
#: manager and a hurried human actually produce it.
CANONICAL = "sana@example.com"
VARIANTS = [
    "Sana@Example.com",
    "SANA@EXAMPLE.COM",
    "  sana@example.com  ",
    "sAnA@eXaMpLe.CoM",
]


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    """Every test gets its own empty in-memory Firestore.

    Both references are patched. ``services/rate_limit_service.py`` does
    ``from services.firestore_service import db``, so it holds a binding
    of its own that a single patch would miss — and the rate limiter is
    on the path of every route this file exercises.
    """
    global _mock_db
    _mock_db = MockFirestoreClient()
    monkeypatch.setattr(_fs_mod, "db", _mock_db)
    monkeypatch.setattr(_rl_mod, "db", _mock_db)
    yield
    _mock_db = None


@pytest.fixture(autouse=True)
def _clean_state():
    """No cookies, no outstanding tokens, no rate-limit buckets."""

    def _reset():
        client.cookies.clear()
        reset_token_store.clear()
        verification_token_store.clear()
        RateLimitService.clear_all()

    _reset()
    yield
    _reset()


def _seed_user(email, *, password=PASSWORD, role="patient", verified=False):
    """Write a user straight through the service, as registration would."""
    return UserService.create_user(
        {
            "email": email,
            "password": get_password_hash(password),
            "email_verified": verified,
            "role": role,
        }
    )


def _seed_legacy_user(email, *, password=PASSWORD):
    """Write a user the way rows created *before* #380 look on disk.

    Deliberately bypasses ``UserService.create_user`` — that method now
    canonicalises, which is exactly what these rows never had done to
    them. This is the shape the lookup fallback exists for.
    """
    _, doc = _mock_db.collection("users").add(
        {
            "email": email,
            "password": get_password_hash(password),
            "email_verified": False,
            "role": "patient",
        }
    )
    return doc.id


def _stored_emails():
    return [
        data.get("email") for data in _mock_db._collections.get("users", {}).values()
    ]


# ─── core/email_identity ──────────────────────────────────────────────────


@pytest.mark.parametrize("variant", VARIANTS)
def test_normalize_email_collapses_every_variant(variant):
    assert normalize_email(variant) == CANONICAL


@pytest.mark.parametrize("blank", [None, "", "   ", "\t\n"])
def test_normalize_email_returns_empty_string_for_nothing(blank):
    """A missing address normalises to a miss, not to an exception.

    Callers either look the result up — where "no such account" is the
    correct answer — or store it beside a value EmailStr has already
    validated. Raising here would turn a lookup into a 500.
    """
    assert normalize_email(blank) == ""


def test_normalize_email_leaves_the_local_part_otherwise_intact():
    """No dot-stripping, no ``+tag`` removal — see the module docstring.

    Those are one provider's routing rules. Applied globally they would
    refuse two genuinely distinct addresses on a host that treats them as
    distinct, and refusing a legitimate sign-up is the worse failure.
    """
    assert normalize_email("S.ana+news@Example.com") == "s.ana+news@example.com"


@pytest.mark.parametrize("variant", VARIANTS)
def test_same_email_matches_across_capitalisation(variant):
    assert same_email(CANONICAL, variant) is True


def test_same_email_rejects_different_addresses():
    assert same_email(CANONICAL, "asha@example.com") is False


@pytest.mark.parametrize("blank", [None, "", "   "])
def test_same_email_is_false_when_either_side_is_blank(blank):
    """Two absent addresses are not "the same account"."""
    assert same_email(blank, CANONICAL) is False
    assert same_email(CANONICAL, blank) is False
    assert same_email(blank, blank) is False


def test_auth_router_still_exports_normalize_email():
    """``api/provider.py`` reaches for ``auth_router_module.normalize_email``.

    Moving the definition must not break that import, and the re-export
    must be the same function — not a second copy that could drift.
    """
    assert router_normalize_email is normalize_email


# ─── Registration ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("variant", VARIANTS)
def test_register_stores_the_canonical_address(variant):
    response = client.post(
        REGISTER_URL, json={"email": variant, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    assert response.json()["email"] == CANONICAL
    assert _stored_emails() == [CANONICAL]


@pytest.mark.parametrize("variant", VARIANTS)
def test_register_refuses_an_address_already_taken_in_another_case(variant):
    """The bug: both of these used to succeed, producing two accounts.

    Two user documents means two cycle histories, and which one she
    reaches at login depends on how her keyboard capitalised the field.
    """
    first = client.post(REGISTER_URL, json={"email": CANONICAL, "password": PASSWORD})
    assert first.status_code == 200, first.text

    second = client.post(REGISTER_URL, json={"email": variant, "password": PASSWORD})
    assert second.status_code == 409
    assert len(_stored_emails()) == 1


def test_register_still_allows_a_genuinely_different_address():
    """Normalisation must not collapse two distinct accounts into one."""
    assert (
        client.post(REGISTER_URL, json={"email": CANONICAL, "password": PASSWORD}).status_code
        == 200
    )
    assert (
        client.post(
            REGISTER_URL, json={"email": "asha@example.com", "password": PASSWORD}
        ).status_code
        == 200
    )
    assert sorted(_stored_emails()) == ["asha@example.com", CANONICAL]


def test_password_policy_sees_the_canonical_address():
    """A password built from the address is refused whatever its case.

    ``enforce_password_policy`` is passed the email so it can reject a
    password containing it. Handing it the raw string meant
    ``Sana@Example.com`` and the password ``sana@example.com!1`` were
    compared as different strings.
    """
    response = client.post(
        REGISTER_URL, json={"email": "Sana@Example.com", "password": "sana@example.com"}
    )
    assert response.status_code == 422


# ─── Login ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("variant", VARIANTS)
def test_login_succeeds_whatever_case_the_address_is_typed_in(variant):
    _seed_user(CANONICAL)
    response = client.post(LOGIN_URL, json={"email": variant, "password": PASSWORD})
    assert response.status_code == 200, response.text
    assert response.json()["access_token"]


def test_login_still_refuses_the_wrong_password():
    """Normalisation must not have loosened the actual credential check."""
    _seed_user(CANONICAL)
    response = client.post(
        LOGIN_URL, json={"email": "SANA@EXAMPLE.COM", "password": "not-the-password"}
    )
    assert response.status_code == 401


def test_login_still_refuses_an_unknown_address():
    response = client.post(
        LOGIN_URL, json={"email": "Nobody@Example.com", "password": PASSWORD}
    )
    assert response.status_code == 401


def test_emailstr_folds_the_domain_but_not_the_local_part():
    """Pins the assumption the rest of this file rests on.

    ``EmailStr`` already trims and lower-cases the *domain* before a route
    body ever runs, so ``SANA@EXAMPLE.COM`` arrives as
    ``SANA@example.com``. What it leaves alone is the local part — which
    is the half that actually produced the duplicate accounts, and the
    half nothing in this codebase was folding.

    Asserted here rather than assumed because it decides what a
    pre-#380 row looks like on disk: mixed-case in the local part only,
    never in the domain. If a future pydantic release changes this, the
    legacy-fallback test below is testing the wrong shape and should say
    so loudly.
    """
    from pydantic import BaseModel, EmailStr

    class _Probe(BaseModel):
        email: EmailStr

    assert _Probe(email="SANA@EXAMPLE.COM").email == "SANA@example.com"
    assert _Probe(email="  sana@example.com  ").email == CANONICAL


def test_login_finds_a_legacy_mixed_case_account():
    """Accounts written before #380 are still reachable.

    Firestore's ``==`` is byte-exact and it has no case-insensitive
    operator, so a query for the canonical form will never find a row
    stored as ``Sana@example.com``. ``get_user_by_email`` falls back to
    the exact string supplied, which is how a returning user who types
    her address the way she originally did still gets in — without a
    backfill having to complete before this change can ship.
    """
    _seed_legacy_user("Sana@example.com")

    response = client.post(
        LOGIN_URL, json={"email": "Sana@Example.com", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text


def test_the_legacy_fallback_does_not_reach_a_row_typed_differently():
    """The limit of the fallback, written down rather than assumed.

    Only the exact string supplied is tried, so a legacy row is found
    when the user types her address the way she originally did — and not
    otherwise. The alternative would be a collection scan, whose cost
    grows with the user table on every failed login. Closing this last
    gap is a one-off backfill's job, not a query's.
    """
    _seed_legacy_user("Sana@example.com")

    response = client.post(LOGIN_URL, json={"email": CANONICAL, "password": PASSWORD})
    assert response.status_code == 401


# ─── Cross-flow parity with the provider routes ───────────────────────────


def test_provider_registered_address_works_on_the_patient_login_route():
    """The asymmetry that made this a user-visible failure.

    ``/provider/register`` normalised, so ``Doc@Clinic.in`` was stored
    lower-cased. ``/auth/login`` did not, so the address she had just
    registered with came back 401 — "Invalid email or password" for a
    correct email and a correct password.
    """
    registered = client.post(
        PROVIDER_REGISTER_URL,
        json={"email": "Doc@Clinic.in", "password": PASSWORD, "full_name": "Dr Mehta"},
    )
    assert registered.status_code == 201, registered.text

    response = client.post(
        LOGIN_URL, json={"email": "Doc@Clinic.in", "password": PASSWORD}
    )
    assert response.status_code == 200, response.text


def test_patient_registered_address_works_on_the_provider_login_route():
    """The mirror image, which must fail for the *role* reason, not a 401.

    A patient signing in at the clinician form should be told this is not
    a provider account — a 403. Getting a 401 instead would mean the
    lookup missed, i.e. the two routes disagree about her address again.
    """
    assert (
        client.post(
            REGISTER_URL, json={"email": "Asha@Example.com", "password": PASSWORD}
        ).status_code
        == 200
    )

    response = client.post(
        PROVIDER_LOGIN_URL, json={"email": "Asha@Example.com", "password": PASSWORD}
    )
    assert response.status_code == 403, response.text


def test_both_register_routes_agree_an_address_is_taken():
    """One address, one account, whichever door it was created through."""
    assert (
        client.post(
            REGISTER_URL, json={"email": "shared@example.com", "password": PASSWORD}
        ).status_code
        == 200
    )
    response = client.post(
        PROVIDER_REGISTER_URL,
        json={"email": "SHARED@EXAMPLE.COM", "password": PASSWORD},
    )
    assert response.status_code == 409, response.text


# ─── Emailed tokens ───────────────────────────────────────────────────────


@pytest.mark.parametrize("variant", VARIANTS)
def test_reset_token_survives_a_case_change_between_request_and_use(variant):
    """The failure this is really about: a valid token reported as invalid.

    Requested as one capitalisation, submitted as another — because the
    mail client or password manager lower-cased it in between — and the
    store's raw-string key turned a good token into "Invalid or expired
    reset token". The token was neither.
    """
    token = generate_reset_token(variant)
    assert verify_reset_token(CANONICAL, token) is True


def test_reset_token_is_single_use_across_capitalisations():
    """Consuming it under one spelling must consume it under all of them."""
    token = generate_reset_token("Sana@Example.com")
    assert verify_reset_token(CANONICAL, token) is True
    assert verify_reset_token("SANA@EXAMPLE.COM", token) is False


def test_reset_token_still_rejects_a_wrong_token():
    generate_reset_token(CANONICAL)
    assert verify_reset_token(CANONICAL, "not-the-token") is False


def test_reset_token_still_rejects_another_accounts_token():
    token = generate_reset_token(CANONICAL)
    assert verify_reset_token("asha@example.com", token) is False


@pytest.mark.parametrize("variant", VARIANTS)
def test_verification_token_survives_a_case_change(variant):
    token = generate_verification_token(variant)
    assert verify_email_token(CANONICAL, token) is True


def test_verification_token_still_rejects_a_wrong_token():
    generate_verification_token(CANONICAL)
    assert verify_email_token(CANONICAL, "not-the-token") is False


def _reset_key(email):
    """The document id a reset token for ``email`` is filed under.

    The store keys on a hash of the canonical address rather than on the
    address itself (issue #417) — a plaintext email address in a document
    id is personal data sitting in a collection that treats none of its
    contents as personal, which is the same reason ``core/rate_limits``
    hashes its bucket keys. Hashing does not weaken this assertion: a
    differently-cased address hashes differently, so an id that matches
    proves the canonicalisation happened before the write.
    """
    return token_store.document_id(token_store.KIND_PASSWORD_RESET, email)


def _verification_key(email):
    return token_store.document_id(token_store.KIND_EMAIL_VERIFICATION, email)


def test_reset_store_is_keyed_on_the_canonical_address():
    """Asserted directly so the key format is pinned, not just its effect."""
    generate_reset_token("  SANA@Example.com  ")
    assert list(reset_token_store) == [_reset_key(CANONICAL)]


def test_reset_store_is_not_keyed_on_the_address_as_typed():
    generate_reset_token("  SANA@Example.com  ")
    assert list(reset_token_store) != [_reset_key("SANA@Example.com")]


# ─── End-to-end through the routes ────────────────────────────────────────


def test_forgot_then_reset_with_different_capitalisation():
    """The whole journey, each step spelled differently.

    ``generate_reset_token`` stores only a hash, so a route-level test
    cannot read the emailed token back out of the store. It is minted
    directly for one capitalisation — standing in for the delivery step —
    and then submitted through the route under another, which is exactly
    the sequence a mail client that lower-cases the address produces.
    """
    _seed_user(CANONICAL)
    new_password = "Marigold!Sequoia88"

    forgot = client.post(FORGOT_URL, json={"email": "Sana@Example.com"})
    assert forgot.status_code == 200
    assert list(reset_token_store) == [_reset_key(CANONICAL)]

    token = generate_reset_token("SANA@EXAMPLE.COM")

    reset = client.post(
        RESET_URL,
        json={
            "email": "  Sana@Example.COM  ",
            "token": token,
            "new_password": new_password,
        },
    )
    assert reset.status_code == 200, reset.text

    # And the new password works from yet another capitalisation.
    login = client.post(
        LOGIN_URL, json={"email": "SANA@example.com", "password": new_password}
    )
    assert login.status_code == 200, login.text


def test_reset_password_still_refuses_a_wrong_token_through_the_route():
    """So the test above passes on address handling, not a skipped check."""
    _seed_user(CANONICAL)
    client.post(FORGOT_URL, json={"email": CANONICAL})

    reset = client.post(
        RESET_URL,
        json={
            "email": CANONICAL,
            "token": "not-the-token",
            "new_password": "Marigold!Sequoia88",
        },
    )
    assert reset.status_code == 400


def test_resend_verification_accepts_any_capitalisation():
    _seed_user(CANONICAL, verified=False)
    response = client.post(RESEND_URL, json={"email": "Sana@Example.com"})
    assert response.status_code == 200
    assert list(verification_token_store) == [_verification_key(CANONICAL)]


def test_verify_email_accepts_any_capitalisation():
    _seed_user(CANONICAL, verified=False)
    token = generate_verification_token("SANA@EXAMPLE.COM")

    response = client.post(
        VERIFY_URL, json={"email": "  sana@example.com ", "token": token}
    )
    assert response.status_code == 200, response.text


def test_forgot_password_response_is_unchanged_for_an_unknown_address():
    """The deliberately identical reply must survive normalisation.

    ``/forgot-password`` answers the same whether or not the account
    exists, so the route is not an enumeration oracle. Normalising the
    address must not have introduced a difference between the two.
    """
    _seed_user(CANONICAL)
    known = client.post(FORGOT_URL, json={"email": "Sana@Example.com"})
    unknown = client.post(FORGOT_URL, json={"email": "Nobody@Example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()


# ─── Storage layer ────────────────────────────────────────────────────────


@pytest.mark.parametrize("variant", VARIANTS)
def test_create_user_canonicalises_at_the_single_write_path(variant):
    """Three routes create users; only one of them used to normalise."""
    user_id = _seed_user(variant)
    stored = UserService.get_user_by_id(user_id)
    assert stored["email"] == CANONICAL


def test_create_user_leaves_a_document_without_an_email_alone():
    """The Firebase phone flow creates users with no address at all."""
    user_id = UserService.create_user({"phone": "+919876543210"})
    stored = UserService.get_user_by_id(user_id)
    assert "email" not in stored or stored["email"] is None


@pytest.mark.parametrize("variant", VARIANTS)
def test_get_user_by_email_matches_across_capitalisation(variant):
    _seed_user(CANONICAL)
    assert UserService.get_user_by_email(variant) is not None


def test_get_user_by_email_returns_none_for_an_unknown_address():
    _seed_user(CANONICAL)
    assert UserService.get_user_by_email("nobody@example.com") is None


@pytest.mark.parametrize("blank", ["", "   "])
def test_get_user_by_email_returns_none_for_a_blank_address(blank):
    """A blank lookup must not match a document whose email is missing."""
    UserService.create_user({"phone": "+919876543210"})
    assert UserService.get_user_by_email(blank) is None


def test_get_user_by_email_finds_a_legacy_mixed_case_row():
    _seed_legacy_user("Sana@example.com")
    assert UserService.get_user_by_email("Sana@example.com") is not None


def test_get_user_by_email_costs_one_query_on_the_common_path():
    """The fallback must not double the read cost of every lookup.

    A second query only runs when the first misses *and* the supplied
    string differs from its canonical form. For everything written since
    #380 — which is everything, going forward — that is one query, the
    same as before this change.
    """
    _seed_user(CANONICAL)

    queries = []
    real_where = _mock_db.collection("users").__class__.where

    def counting_where(self, field, op, value):
        queries.append((field, value))
        return real_where(self, field, op, value)

    _mock_db.collection("users").__class__.where = counting_where
    try:
        assert UserService.get_user_by_email(CANONICAL) is not None
    finally:
        _mock_db.collection("users").__class__.where = real_where

    assert queries == [("email", CANONICAL)]


def test_update_user_canonicalises_a_changed_address():
    """A profile edit must not put a row back into the mixed-case state."""
    user_id = _seed_user(CANONICAL)
    UserService.update_user(user_id, {"email": "Sana.New@Example.COM"})
    assert UserService.get_user_by_id(user_id)["email"] == "sana.new@example.com"


def test_update_user_without_an_email_is_untouched():
    user_id = _seed_user(CANONICAL)
    UserService.update_user(user_id, {"full_name": "Sana"})
    stored = UserService.get_user_by_id(user_id)
    assert stored["email"] == CANONICAL
    assert stored["full_name"] == "Sana"


# ─── Backfill script ──────────────────────────────────────────────────────
#
# The lookup fallback above is a compatibility shim, not the fix. These
# cover the one-off migration that lets it be deleted.

from scripts import backfill_email_normalization as backfill  # noqa: E402


def test_backfill_plans_a_rewrite_for_a_legacy_row():
    _seed_legacy_user("Sana@example.com")
    rewrites, collisions = backfill.plan()

    assert collisions == []
    assert [(row["from"], row["to"]) for row in rewrites] == [
        ("Sana@example.com", CANONICAL)
    ]


def test_backfill_plans_nothing_for_rows_already_canonical():
    _seed_user(CANONICAL)
    rewrites, collisions = backfill.plan()

    assert rewrites == []
    assert collisions == []


def test_backfill_ignores_documents_with_no_address():
    """The Firebase phone flow creates users with no email at all."""
    UserService.create_user({"phone": "+919876543210"})
    rewrites, collisions = backfill.plan()

    assert rewrites == []
    assert collisions == []


def test_backfill_rewrites_when_applied():
    user_id = _seed_legacy_user("Sana@example.com")
    rewrites, _ = backfill.plan()

    assert backfill.apply(rewrites) == 1
    assert UserService.get_user_by_id(user_id)["email"] == CANONICAL

    # And the canonical lookup, which could not reach it before, now can.
    assert UserService.get_user_by_email(CANONICAL) is not None


def test_backfill_refuses_to_touch_a_duplicated_address():
    """Two accounts, one canonical address — the case it must not decide.

    Rewriting either one produces two documents with an identical email,
    after which every lookup returns whichever Firestore hands back
    first. Which of the two is "hers" is a question about months of
    logged health data, not a migration step.
    """
    _seed_legacy_user("Sana@example.com")
    _seed_user(CANONICAL)

    rewrites, collisions = backfill.plan()

    assert rewrites == []
    assert len(collisions) == 1
    assert collisions[0]["email"] == CANONICAL
    assert len(collisions[0]["documents"]) == 2


def test_backfill_still_migrates_unaffected_rows_alongside_a_collision():
    """One unresolvable pair must not block every other row."""
    _seed_legacy_user("Sana@example.com")
    _seed_user(CANONICAL)
    _seed_legacy_user("Asha@example.com")

    rewrites, collisions = backfill.plan()

    assert [row["to"] for row in rewrites] == ["asha@example.com"]
    assert len(collisions) == 1


def test_backfill_is_a_dry_run_by_default(capsys):
    user_id = _seed_legacy_user("Sana@example.com")

    exit_code = backfill.main([])

    assert exit_code == 0
    assert "Dry run" in capsys.readouterr().out
    assert UserService.get_user_by_id(user_id)["email"] == "Sana@example.com"


def test_backfill_writes_with_apply(capsys):
    user_id = _seed_legacy_user("Sana@example.com")

    exit_code = backfill.main(["--apply"])

    assert exit_code == 0
    assert "Rewrote 1/1" in capsys.readouterr().out
    assert UserService.get_user_by_id(user_id)["email"] == CANONICAL


def test_backfill_exits_non_zero_on_a_collision(capsys):
    """So a deploy pipeline notices rather than reporting success."""
    _seed_legacy_user("Sana@example.com")
    _seed_user(CANONICAL)

    assert backfill.main(["--apply"]) == 1
    assert "more than one account" in capsys.readouterr().out


def test_backfill_on_an_empty_collection_is_a_no_op(capsys):
    assert backfill.main(["--apply"]) == 0
    assert "Nothing to rewrite" in capsys.readouterr().out
