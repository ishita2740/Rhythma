"""An account cannot take an address another account holds (issue #531).

``PATCH /auth/profile`` accepted an ``email`` and wrote it with no check
that another ``users`` document already carried it. ``POST /auth/register``
had always refused that collision with a 409; the profile route reached
the same collection, wrote the same field, and refused nothing.

Most of the tests below assert on **what is in the collection** and on
**what the identity lookups then return**, not merely on the status code
of the PATCH. That is deliberate. A 200 says the request was accepted; it
is ``UserService.get_user_by_email`` resolving to the wrong document that
locks a user out of her own account and binds a patient's consent to the
wrong clinician, and only a test that follows the write through to that
lookup can tell the difference. A status-code-only test would pass against
the original code as easily as against the fix.

The tests run against the real in-memory Firestore mock rather than a
stubbed ``UserService``, for the reason ``test_email_normalization.py``
gives: a hand-written store that rejected duplicates on its own would
hide the very thing under test.
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
    _email_key,
    create_access_token,
    generate_verification_token,
    get_password_hash,
    reset_token_store,
    verification_token_store,
)
from core.email_ownership import (  # noqa: E402
    EMAIL_TAKEN_DETAIL,
    EmailChangeKind,
    apply_email_change,
    classify_email_change,
    enforce_email_available,
)
from fastapi import HTTPException  # noqa: E402
from services import token_store  # noqa: E402
from services.firestore_service import MockFirestoreClient, UserService  # noqa: E402
from services.provider_service import ConsentService  # noqa: E402
from services.rate_limit_service import RateLimitService  # noqa: E402

import services.firestore_service as _fs_mod  # noqa: E402
import services.rate_limit_service as _rl_mod  # noqa: E402

client = TestClient(app)

_mock_db = None

PROFILE_URL = "/api/v1/auth/profile"
LOGIN_URL = "/api/v1/auth/login"

PASSWORD = "Wintergreen!Harbour42"
OTHER_PASSWORD = "Saltmarsh!Lantern77"

ATTACKER_EMAIL = "attacker@example.com"
VICTIM_EMAIL = "victim@example.com"
CLINICIAN_EMAIL = "dr.rao@clinic.in"


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
    """Every test gets its own empty in-memory Firestore.

    Both references are patched: ``services/rate_limit_service.py`` does
    ``from services.firestore_service import db`` and so holds a binding
    of its own that a single patch would miss.
    """
    global _mock_db
    _mock_db = MockFirestoreClient()
    monkeypatch.setattr(_fs_mod, "db", _mock_db)
    monkeypatch.setattr(_rl_mod, "db", _mock_db)
    yield
    _mock_db = None


@pytest.fixture(autouse=True)
def _clean_state():
    def _reset():
        client.cookies.clear()
        reset_token_store.clear()
        verification_token_store.clear()
        RateLimitService.clear_all()

    _reset()
    yield
    _reset()


# ─── Helpers ──────────────────────────────────────────────────────────────


def _seed_user(email, *, password=PASSWORD, role="patient", verified=True, **extra):
    """Write a user straight through the service, as registration would."""
    data = {
        "email": email,
        "password": get_password_hash(password),
        "email_verified": verified,
        "role": role,
    }
    data.update(extra)
    return UserService.create_user(data)


def _auth(user_id):
    return {"Authorization": f"Bearer {create_access_token(data={'sub': user_id})}"}


def _stored_emails():
    return [
        data.get("email")
        for data in _mock_db._collections.get("users", {}).values()
    ]


def _documents_holding(email):
    """Every user document whose stored ``email`` equals ``email``.

    Written against the raw store rather than through
    ``get_user_by_email``, because that method is ``.limit(1)`` — it
    cannot tell one match from two, which is the property that makes the
    duplicate dangerous rather than merely untidy.
    """
    return [
        doc_id
        for doc_id, data in _mock_db._collections.get("users", {}).items()
        if data.get("email") == email
    ]


# ─── The claim itself ─────────────────────────────────────────────────────


def test_claiming_another_accounts_email_is_refused():
    victim = _seed_user(VICTIM_EMAIL)
    attacker = _seed_user(ATTACKER_EMAIL, password=OTHER_PASSWORD)

    response = client.patch(
        PROFILE_URL, json={"email": VICTIM_EMAIL}, headers=_auth(attacker)
    )

    assert response.status_code == 409
    assert response.json()["detail"] == EMAIL_TAKEN_DETAIL
    assert _documents_holding(VICTIM_EMAIL) == [victim]


def test_refusal_leaves_the_collection_with_exactly_one_holder():
    """The point of the 409, stated as a property of the store.

    ``UserService.get_user_by_email`` ends in an unordered ``.limit(1)``
    query. One holder means one answer; two means the answer is whichever
    document Firestore returns first, re-decided on every call.
    """
    _seed_user(VICTIM_EMAIL)
    attacker = _seed_user(ATTACKER_EMAIL, password=OTHER_PASSWORD)

    client.patch(PROFILE_URL, json={"email": VICTIM_EMAIL}, headers=_auth(attacker))

    assert len(_documents_holding(VICTIM_EMAIL)) == 1
    assert sorted(_stored_emails()) == sorted([VICTIM_EMAIL, ATTACKER_EMAIL])


def test_refusal_is_case_insensitive():
    """``Victim@Example.COM`` is the same address and the same collision.

    Checking the raw string would let one capital letter through and
    recreate the duplicate, since ``UserService.update_user`` canonicalises
    on write — the two documents would end up byte-identical in the field
    the lookup queries.
    """
    _seed_user(VICTIM_EMAIL)
    attacker = _seed_user(ATTACKER_EMAIL, password=OTHER_PASSWORD)

    response = client.patch(
        PROFILE_URL, json={"email": "Victim@Example.COM"}, headers=_auth(attacker)
    )

    assert response.status_code == 409
    assert len(_documents_holding(VICTIM_EMAIL)) == 1


def test_refusal_does_not_name_the_holder():
    """A 409 says the address is taken, never by whom.

    The message is byte-identical to registration's, so this route is no
    better an enumeration oracle than the one that already exists.
    """
    _seed_user(VICTIM_EMAIL, full_name="Priya Nair")
    attacker = _seed_user(ATTACKER_EMAIL, password=OTHER_PASSWORD)

    body = client.patch(
        PROFILE_URL, json={"email": VICTIM_EMAIL}, headers=_auth(attacker)
    ).text

    assert "Priya" not in body
    assert VICTIM_EMAIL not in body


def test_a_rejected_email_does_not_write_the_other_fields():
    """All-or-nothing. A partial write is a profile nobody asked for."""
    _seed_user(VICTIM_EMAIL)
    attacker = _seed_user(ATTACKER_EMAIL, password=OTHER_PASSWORD, full_name="Before")

    response = client.patch(
        PROFILE_URL,
        json={"email": VICTIM_EMAIL, "full_name": "After", "age": 31},
        headers=_auth(attacker),
    )

    assert response.status_code == 409
    stored = UserService.get_user_by_id(attacker)
    assert stored["full_name"] == "Before"
    assert "age" not in stored


# ─── What the collision used to do downstream ─────────────────────────────


def test_the_victim_can_still_log_in_after_the_attempt():
    """The lockout this prevents, driven through the real login route.

    With two documents holding the address, ``get_user_by_email`` can
    return the attacker's, whose password hash does not match what the
    victim types — she gets "Invalid email or password" for credentials
    that are correct.
    """
    _seed_user(VICTIM_EMAIL, password=PASSWORD)
    attacker = _seed_user(ATTACKER_EMAIL, password=OTHER_PASSWORD)

    client.patch(PROFILE_URL, json={"email": VICTIM_EMAIL}, headers=_auth(attacker))

    response = client.post(
        LOGIN_URL, json={"email": VICTIM_EMAIL, "password": PASSWORD}
    )
    assert response.status_code == 200


def test_lookup_by_the_address_still_resolves_to_the_victim():
    victim = _seed_user(VICTIM_EMAIL)
    attacker = _seed_user(ATTACKER_EMAIL, password=OTHER_PASSWORD)

    client.patch(PROFILE_URL, json={"email": VICTIM_EMAIL}, headers=_auth(attacker))

    assert UserService.get_user_by_email(VICTIM_EMAIL)["id"] == victim


def test_consent_granted_by_email_binds_to_the_real_clinician():
    """The sharpest consequence: a patient's records going to the wrong reader.

    ``ConsentService.grant`` resolves the clinician by address and checks
    only that the account it finds has ``role == "provider"``. A second
    provider-role account holding that address is a valid answer to that
    lookup, and the consent is written against *its* id — after which
    ``GET /provider/patients/{id}`` serves that account the patient's full
    profile and cycle history, while the patient's Sharing screen shows
    the right clinician's name.
    """
    clinician = _seed_user(CLINICIAN_EMAIL, role="provider", full_name="Dr Rao")
    impostor = _seed_user(
        "someone.else@clinic.in", role="provider", password=OTHER_PASSWORD
    )
    patient = _seed_user("patient@example.com")

    claim = client.patch(
        PROFILE_URL, json={"email": CLINICIAN_EMAIL}, headers=_auth(impostor)
    )
    assert claim.status_code == 409

    consent = ConsentService.grant(patient, CLINICIAN_EMAIL)
    assert consent["provider_id"] == clinician
    assert consent["provider_id"] != impostor


# ─── Changes that must keep working ───────────────────────────────────────


def test_moving_to_an_unused_address_is_allowed():
    user = _seed_user(ATTACKER_EMAIL)

    response = client.patch(
        PROFILE_URL, json={"email": "new.address@example.com"}, headers=_auth(user)
    )

    assert response.status_code == 200
    assert response.json()["email"] == "new.address@example.com"
    assert UserService.get_user_by_id(user)["email"] == "new.address@example.com"


def test_a_new_address_is_stored_canonicalised():
    user = _seed_user(ATTACKER_EMAIL)

    client.patch(
        PROFILE_URL, json={"email": "New.Address@Example.COM"}, headers=_auth(user)
    )

    assert UserService.get_user_by_id(user)["email"] == "new.address@example.com"


def test_resubmitting_your_own_address_is_not_a_conflict():
    """The false positive a naive "is this email used?" guard produces.

    Checking availability before checking sameness finds *her own
    document* and reports the address taken — turning "save my profile"
    into a 409 for every user whose client echoes the field back.
    """
    user = _seed_user(VICTIM_EMAIL)

    response = client.patch(
        PROFILE_URL, json={"email": VICTIM_EMAIL, "age": 29}, headers=_auth(user)
    )

    assert response.status_code == 200
    assert UserService.get_user_by_id(user)["age"] == 29


@pytest.mark.parametrize(
    "variant", ["Victim@Example.com", "VICTIM@EXAMPLE.COM", "  victim@example.com  "]
)
def test_resubmitting_your_own_address_in_any_capitalisation(variant):
    user = _seed_user(VICTIM_EMAIL)

    response = client.patch(PROFILE_URL, json={"email": variant}, headers=_auth(user))

    assert response.status_code == 200
    assert UserService.get_user_by_id(user)["email"] == VICTIM_EMAIL


def test_a_patch_without_an_email_touches_neither_the_address_nor_the_flag():
    user = _seed_user(VICTIM_EMAIL, verified=True)

    response = client.patch(PROFILE_URL, json={"age": 34}, headers=_auth(user))

    assert response.status_code == 200
    stored = UserService.get_user_by_id(user)
    assert stored["email"] == VICTIM_EMAIL
    assert stored["email_verified"] is True


# ─── email_verified must not outrun what has been proven ──────────────────


def test_a_new_address_resets_the_verified_flag():
    """Registration starts every account unverified.

    An address arriving through a profile edit has had no more proof of
    control than one arriving through the registration form, and it used
    to inherit the previous address's flag — which ``POST /auth/login``
    then returns to the client as ``email_verified: true``.
    """
    user = _seed_user(ATTACKER_EMAIL, verified=True)

    response = client.patch(
        PROFILE_URL, json={"email": "moved@example.com"}, headers=_auth(user)
    )

    assert response.status_code == 200
    assert response.json().get("email_verified") is False
    assert UserService.get_user_by_id(user)["email_verified"] is False


def test_a_new_address_gets_a_verification_token():
    """Un-verifying without a way back would be a lockout, not a fix.

    The store holds only a hash of the token, so this asserts that an
    entry now exists for the new address and did not before — which is
    what "a token was issued" means from outside ``core.auth``.
    """
    user = _seed_user(ATTACKER_EMAIL, verified=True)
    new_address = "moved@example.com"

    def _pending(address):
        return token_store.get(
            token_store.KIND_EMAIL_VERIFICATION, _email_key(address)
        )

    assert _pending(new_address) is None

    client.patch(PROFILE_URL, json={"email": new_address}, headers=_auth(user))

    assert _pending(new_address) is not None


def test_no_verification_token_is_issued_for_an_unchanged_address():
    """Nothing to prove, so nothing to send."""
    user = _seed_user(VICTIM_EMAIL, verified=True)

    client.patch(
        PROFILE_URL, json={"email": "Victim@Example.com"}, headers=_auth(user)
    )

    assert (
        token_store.get(token_store.KIND_EMAIL_VERIFICATION, _email_key(VICTIM_EMAIL))
        is None
    )


def test_the_new_address_can_actually_be_verified():
    """The whole round trip, so the reset is recoverable end to end."""
    user = _seed_user(ATTACKER_EMAIL, verified=True)
    new_address = "moved@example.com"

    client.patch(PROFILE_URL, json={"email": new_address}, headers=_auth(user))
    assert UserService.get_user_by_id(user)["email_verified"] is False

    # Re-issued rather than read back: the store keeps a hash, not the
    # token. Re-issuing overwrites the pending entry for this address, so
    # what is being asserted is that /verify-email accepts a token for the
    # *new* address and flips the flag the PATCH cleared.
    token = generate_verification_token(new_address)
    response = client.post(
        "/api/v1/auth/verify-email", json={"email": new_address, "token": token}
    )

    assert response.status_code == 200
    assert UserService.get_user_by_id(user)["email_verified"] is True


def test_resaving_your_own_address_does_not_unverify_you():
    user = _seed_user(VICTIM_EMAIL, verified=True)

    client.patch(
        PROFILE_URL, json={"email": "Victim@Example.com"}, headers=_auth(user)
    )

    assert UserService.get_user_by_id(user)["email_verified"] is True


def test_a_refused_claim_does_not_touch_the_attackers_flag():
    _seed_user(VICTIM_EMAIL)
    attacker = _seed_user(ATTACKER_EMAIL, password=OTHER_PASSWORD, verified=True)

    client.patch(PROFILE_URL, json={"email": VICTIM_EMAIL}, headers=_auth(attacker))

    stored = UserService.get_user_by_id(attacker)
    assert stored["email"] == ATTACKER_EMAIL
    assert stored["email_verified"] is True


# ─── core/email_ownership, directly ───────────────────────────────────────


def test_classify_reports_absent_without_reading_anything():
    change = classify_email_change(
        user_id="nobody", requested_email=None, current_email=None
    )
    assert change.kind is EmailChangeKind.ABSENT
    assert change.normalized == ""
    assert change.is_new_address is False


@pytest.mark.parametrize("blank", ["", "   ", "\t"])
def test_classify_treats_a_blank_string_as_absent(blank):
    change = classify_email_change(
        user_id="nobody", requested_email=blank, current_email=VICTIM_EMAIL
    )
    assert change.kind is EmailChangeKind.ABSENT


def test_classify_reports_unchanged_for_the_same_address():
    user = _seed_user(VICTIM_EMAIL)
    change = classify_email_change(
        user_id=user, requested_email="VICTIM@example.com", current_email=VICTIM_EMAIL
    )
    assert change.kind is EmailChangeKind.UNCHANGED
    assert change.is_new_address is False


def test_classify_reports_available_for_a_free_address():
    user = _seed_user(VICTIM_EMAIL)
    change = classify_email_change(
        user_id=user, requested_email="free@example.com", current_email=VICTIM_EMAIL
    )
    assert change.kind is EmailChangeKind.AVAILABLE
    assert change.is_new_address is True


def test_classify_reports_taken_and_names_the_holder_internally():
    """``holder_id`` exists so a caller need not look the address up twice.

    It is never put in a response — see the 409 body test above.
    """
    victim = _seed_user(VICTIM_EMAIL)
    attacker = _seed_user(ATTACKER_EMAIL, password=OTHER_PASSWORD)

    change = classify_email_change(
        user_id=attacker, requested_email=VICTIM_EMAIL, current_email=ATTACKER_EMAIL
    )

    assert change.kind is EmailChangeKind.TAKEN
    assert change.holder_id == victim


def test_classify_reads_the_current_address_when_it_is_not_supplied():
    """The document is the authority; the argument is an optimisation."""
    user = _seed_user(VICTIM_EMAIL)

    change = classify_email_change(user_id=user, requested_email=VICTIM_EMAIL)

    assert change.kind is EmailChangeKind.UNCHANGED


def test_classify_believes_the_document_over_a_stale_current_email():
    """A caller passing the wrong ``current_email`` must not self-collide.

    Reported as available rather than taken: the only document holding the
    address *is* this account, so writing it is a no-op, not a conflict.
    """
    user = _seed_user(VICTIM_EMAIL)

    change = classify_email_change(
        user_id=user, requested_email=VICTIM_EMAIL, current_email="stale@example.com"
    )

    assert change.kind is EmailChangeKind.AVAILABLE
    assert change.holder_id is None


def test_enforce_raises_conflict_for_a_taken_address():
    _seed_user(VICTIM_EMAIL)
    attacker = _seed_user(ATTACKER_EMAIL, password=OTHER_PASSWORD)

    with pytest.raises(HTTPException) as excinfo:
        enforce_email_available(
            user_id=attacker,
            requested_email=VICTIM_EMAIL,
            current_email=ATTACKER_EMAIL,
        )

    assert excinfo.value.status_code == 409
    assert excinfo.value.detail == EMAIL_TAKEN_DETAIL


def test_enforce_returns_the_verdict_when_there_is_no_conflict():
    user = _seed_user(ATTACKER_EMAIL)

    change = enforce_email_available(
        user_id=user, requested_email="free@example.com", current_email=ATTACKER_EMAIL
    )

    assert change.kind is EmailChangeKind.AVAILABLE


def test_apply_drops_the_key_entirely_when_no_address_was_sent():
    """So a client sending ``{"email": null}`` cannot blank the identity key."""
    updates = {"email": None, "age": 30}
    change = classify_email_change(user_id="x", requested_email=None)

    apply_email_change(updates, change)

    assert "email" not in updates
    assert updates["age"] == 30


def test_apply_writes_the_canonical_form_and_unverifies_a_new_address():
    updates = {"email": "New@Example.com"}
    user = _seed_user(ATTACKER_EMAIL)
    change = classify_email_change(
        user_id=user, requested_email="New@Example.com", current_email=ATTACKER_EMAIL
    )

    apply_email_change(updates, change)

    assert updates["email"] == "new@example.com"
    assert updates["email_verified"] is False


def test_apply_leaves_the_flag_alone_for_an_unchanged_address():
    user = _seed_user(VICTIM_EMAIL)
    updates = {"email": "Victim@Example.com"}
    change = classify_email_change(
        user_id=user, requested_email="Victim@Example.com", current_email=VICTIM_EMAIL
    )

    apply_email_change(updates, change)

    assert updates["email"] == VICTIM_EMAIL
    assert "email_verified" not in updates


# ─── The route's other guarantees ─────────────────────────────────────────


def test_patching_a_deleted_account_writes_nothing():
    """The account is resolved before the write, not after.

    ``get_current_user`` already refuses a token whose account is gone, so
    from outside this is a 401 rather than the route's own 404 — the point
    of the assertion is the second half: nothing was stored against a
    document the caller no longer has.
    """
    user = _seed_user(VICTIM_EMAIL)
    _mock_db._collections["users"].pop(user)

    response = client.patch(PROFILE_URL, json={"age": 30}, headers=_auth(user))

    assert response.status_code == 401
    assert user not in _mock_db._collections.get("users", {})


def test_the_response_never_carries_the_password_hash():
    user = _seed_user(VICTIM_EMAIL)

    body = client.patch(PROFILE_URL, json={"age": 30}, headers=_auth(user)).json()

    assert "password" not in body


def test_an_unauthenticated_patch_is_rejected():
    response = client.patch(PROFILE_URL, json={"email": VICTIM_EMAIL})
    assert response.status_code in (401, 403)
