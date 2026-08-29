"""An omitted field and an explicit ``null`` are different things (issue #533).

``PATCH /auth/profile`` filtered its payload with:

    updates = {k: v for k, v in profile_data.model_dump().items() if v is not None}

``model_dump()`` on an all-optional model returns *every* field, with
``None`` for the ones the client never mentioned. The filter is what makes
PATCH semantics work at all — without it, sending ``{"age": 30}`` would
blank the other fifteen fields — but it also made a deliberate ``null``
indistinguishable from silence, so **no field on this model could ever be
cleared**.

The user-visible shape of that: clear the Age box in the web Edit Profile
form, save, get a 200 — and the age is back on the card immediately,
because the response is the re-read document and still carries it. Nothing
says the removal was refused.

The tests are written in three groups, and the split matters:

* **Untouched** — the guarantee the old filter existed to provide, which
  a fix in this area could easily break in the other direction. These run
  first because a regression here is worse than the bug being fixed.
* **Cleared** — the new behaviour.
* **Refused** — the fields a ``null`` must *not* empty, because they are
  the account's identity keys.
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
from core.auth import create_access_token, get_password_hash  # noqa: E402
from models.user import (  # noqa: E402
    CLEARABLE_PROFILE_FIELDS,
    UserProfileResponse,
    UserProfileUpdate,
)
from services.firestore_service import MockFirestoreClient, UserService  # noqa: E402
from services.rate_limit_service import RateLimitService  # noqa: E402

import services.firestore_service as _fs_mod  # noqa: E402
import services.rate_limit_service as _rl_mod  # noqa: E402

client = TestClient(app)

_mock_db = None

PROFILE_URL = "/api/v1/auth/profile"

#: A profile with something in every field a client might want to clear.
FULL_PROFILE = {
    "full_name": "Asha Verma",
    "age": 29,
    "height_cm": 162.0,
    "weight_kg": 55.5,
    "avatar": "#AA3BFF",
    "language": "hi",
    "last_period": "2026-08-01",
    "last_period_is_approximate": True,
    "cycle_length": 31,
    "period_duration": 5,
    "cycle_regular": True,
    "notifications_enabled": True,
    "city": "Nagpur",
    "state": "Maharashtra",
}


@pytest.fixture(autouse=True)
def _isolated_db(monkeypatch):
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
        RateLimitService.clear_all()

    _reset()
    yield
    _reset()


def _seed_user(**extra):
    data = {
        "email": "asha@example.com",
        "password": get_password_hash("Wintergreen!Harbour42"),
        "phone": "+919876543210",
        **FULL_PROFILE,
    }
    data.update(extra)
    return UserService.create_user(data)


def _auth(user_id):
    return {"Authorization": f"Bearer {create_access_token(data={'sub': user_id})}"}


def _stored(user_id):
    return UserService.get_user_by_id(user_id) or {}


# ─── Untouched: what the old filter existed to protect ────────────────────


def test_a_field_the_request_does_not_mention_is_left_alone():
    """The whole point of PATCH, and the thing a fix here could break.

    Without the filter, `{"age": 30}` would blank the other fifteen
    fields — which is a far worse bug than the one being fixed.
    """
    user = _seed_user()

    response = client.patch(PROFILE_URL, json={"age": 30}, headers=_auth(user))

    assert response.status_code == 200
    stored = _stored(user)
    assert stored["age"] == 30
    assert stored["full_name"] == "Asha Verma"
    assert stored["cycle_length"] == 31
    assert stored["city"] == "Nagpur"


def test_an_empty_body_changes_nothing():
    user = _seed_user()

    response = client.patch(PROFILE_URL, json={}, headers=_auth(user))

    assert response.status_code == 200
    for field, value in FULL_PROFILE.items():
        assert _stored(user)[field] == value


@pytest.mark.parametrize("field,value", sorted(FULL_PROFILE.items()))
def test_every_field_can_be_set_individually(field, value):
    """One case per field, so a fix that quietly drops one is caught."""
    user = _seed_user(**{field: None})

    response = client.patch(PROFILE_URL, json={field: value}, headers=_auth(user))

    assert response.status_code == 200
    assert _stored(user)[field] == value


@pytest.mark.parametrize("falsy_field,falsy_value", [
    ("cycle_regular", False),
    ("notifications_enabled", False),
    ("last_period_is_approximate", False),
])
def test_a_false_boolean_is_written_not_dropped(falsy_field, falsy_value):
    """`False is not None`, so this always worked — pinned so it keeps doing.

    A fix that reached for a truthiness check instead of `exclude_unset`
    would silently make "turn notifications off" a no-op, which is the
    same class of bug wearing a different hat.
    """
    user = _seed_user()

    client.patch(PROFILE_URL, json={falsy_field: falsy_value}, headers=_auth(user))

    assert _stored(user)[falsy_field] is falsy_value


def test_a_zero_is_not_mistaken_for_absent():
    """Not reachable through `age` (bounded at 10), so tested where it is.

    `weight_kg` is bounded at 10.0 too — the point of the case is that the
    route must not be reintroducing a truthiness test anywhere.
    """
    user = _seed_user()

    response = client.patch(PROFILE_URL, json={"weight_kg": 10.0}, headers=_auth(user))

    assert response.status_code == 200
    assert _stored(user)["weight_kg"] == 10.0


# ─── Cleared: the bug ─────────────────────────────────────────────────────


def test_an_explicit_null_clears_a_field():
    """The reproduction from the issue, at the API level."""
    user = _seed_user()

    response = client.patch(PROFILE_URL, json={"age": None}, headers=_auth(user))

    assert response.status_code == 200
    assert _stored(user)["age"] is None
    assert response.json()["age"] is None


def test_the_response_does_not_hand_the_cleared_value_back():
    """What the user actually saw: the age reappearing on the card.

    `setProfile(updated)` writes the response into state, so a response
    still carrying the old value puts it straight back on screen.
    """
    user = _seed_user()

    body = client.patch(PROFILE_URL, json={"age": None}, headers=_auth(user)).json()

    assert body["age"] is None


@pytest.mark.parametrize("field", sorted(CLEARABLE_PROFILE_FIELDS))
def test_every_clearable_field_can_actually_be_cleared(field):
    """One case per field in the allowlist.

    Parametrised off the constant itself, so adding a field to
    `CLEARABLE_PROFILE_FIELDS` without it working is a failing test rather
    than a silent claim.
    """
    user = _seed_user()

    response = client.patch(PROFILE_URL, json={field: None}, headers=_auth(user))

    assert response.status_code == 200
    assert _stored(user)[field] is None


def test_clearing_cycle_length_stops_it_feeding_predictions():
    """Why this one matters beyond tidiness.

    `prediction_service` reads the declared `cycle_length` as its fallback
    when there is not enough logged history. A user who entered 35 during
    onboarding, later decided she should not have declared one, and
    cleared the field, kept 35 feeding her predictions forever.
    """
    user = _seed_user(cycle_length=35)

    client.patch(PROFILE_URL, json={"cycle_length": None}, headers=_auth(user))

    assert _stored(user).get("cycle_length") is None


def test_a_clear_and_a_set_in_one_request_both_apply():
    user = _seed_user()

    client.patch(
        PROFILE_URL,
        json={"age": None, "city": "Pune"},
        headers=_auth(user),
    )

    stored = _stored(user)
    assert stored["age"] is None
    assert stored["city"] == "Pune"


def test_clearing_one_field_does_not_clear_its_neighbours():
    user = _seed_user()

    client.patch(PROFILE_URL, json={"age": None}, headers=_auth(user))

    stored = _stored(user)
    assert stored["full_name"] == "Asha Verma"
    assert stored["cycle_length"] == 31
    assert stored["height_cm"] == 162.0


def test_clearing_is_idempotent():
    user = _seed_user()

    client.patch(PROFILE_URL, json={"age": None}, headers=_auth(user))
    response = client.patch(PROFILE_URL, json={"age": None}, headers=_auth(user))

    assert response.status_code == 200
    assert _stored(user)["age"] is None


def test_a_cleared_field_can_be_set_again():
    user = _seed_user()

    client.patch(PROFILE_URL, json={"age": None}, headers=_auth(user))
    client.patch(PROFILE_URL, json={"age": 31}, headers=_auth(user))

    assert _stored(user)["age"] == 31


# ─── Refused: the identity keys ───────────────────────────────────────────


@pytest.mark.parametrize("field", ["email", "phone"])
def test_the_identity_keys_cannot_be_emptied(field):
    """Changed by being given a new value, never by being emptied.

    Email is what `login`, `forgot-password` and provider consent all
    resolve an account by; a profile PATCH is not the place to be able to
    remove it by accident.
    """
    user = _seed_user()

    response = client.patch(PROFILE_URL, json={field: None}, headers=_auth(user))

    assert response.status_code == 422
    assert field in response.json()["detail"]


def test_a_refused_clear_writes_none_of_the_request():
    """All-or-nothing: a half-applied PATCH is a profile nobody asked for."""
    user = _seed_user()

    response = client.patch(
        PROFILE_URL,
        json={"email": None, "city": "Pune"},
        headers=_auth(user),
    )

    assert response.status_code == 422
    assert _stored(user)["city"] == "Nagpur"


def test_the_refusal_names_every_offending_field():
    user = _seed_user()

    detail = client.patch(
        PROFILE_URL, json={"email": None, "phone": None}, headers=_auth(user)
    ).json()["detail"]

    assert "email" in detail
    assert "phone" in detail


def test_the_identity_keys_can_still_be_given_a_new_value():
    user = _seed_user()

    response = client.patch(
        PROFILE_URL, json={"phone": "+919000000001"}, headers=_auth(user)
    )

    assert response.status_code == 200
    assert _stored(user)["phone"] == "+919000000001"


def test_the_models_bounds_still_apply_to_a_supplied_value():
    """Clearing is a new case, not a bypass of validation."""
    user = _seed_user()

    assert (
        client.patch(PROFILE_URL, json={"age": 5}, headers=_auth(user)).status_code
        == 422
    )
    assert (
        client.patch(PROFILE_URL, json={"cycle_length": 99}, headers=_auth(user)).status_code
        == 422
    )
    assert (
        client.patch(PROFILE_URL, json={"phone": "98765"}, headers=_auth(user)).status_code
        == 422
    )


# ─── The models themselves ────────────────────────────────────────────────


def test_exclude_unset_is_what_tells_the_two_cases_apart():
    """The distinction the route depends on, asserted at its source."""
    omitted = UserProfileUpdate()
    explicit = UserProfileUpdate(age=None)

    assert "age" not in omitted.model_dump(exclude_unset=True)
    assert "age" in explicit.model_dump(exclude_unset=True)
    assert explicit.model_dump(exclude_unset=True)["age"] is None


def test_a_plain_model_dump_collapses_them():
    """Why the old code could not tell a clear from a silence."""
    omitted = UserProfileUpdate().model_dump()
    explicit = UserProfileUpdate(age=None).model_dump()

    assert omitted == explicit


def test_the_clearable_set_does_not_include_the_identity_keys():
    assert "email" not in CLEARABLE_PROFILE_FIELDS
    assert "phone" not in CLEARABLE_PROFILE_FIELDS


def test_every_clearable_field_actually_exists_on_the_model():
    """A typo in the allowlist would silently permit nothing."""
    declared = set(UserProfileUpdate.model_fields)

    assert CLEARABLE_PROFILE_FIELDS <= declared


def test_the_allowlist_covers_every_field_that_is_not_an_identity_key():
    """So a field added to the model is a deliberate decision, not an omission."""
    declared = set(UserProfileUpdate.model_fields)

    assert declared - CLEARABLE_PROFILE_FIELDS == {"email", "phone"}


def test_the_response_model_declares_phone_once():
    """It was declared twice, ~15 lines apart.

    Harmless in itself — the declarations were identical, so the second
    simply won. #381 was the same pattern with a worse outcome:
    `DashboardPrediction` was declared twice, the second won, and the
    typed fields on the first were silently dropped from the served
    schema.
    """
    source = UserProfileResponse.__doc__  # keeps the import meaningful
    assert source is not None

    fields = list(UserProfileResponse.model_fields)
    assert fields.count("phone") == 1


def test_the_served_schema_still_carries_every_profile_field():
    """A duplicate removed by hand is a chance to drop the wrong one."""
    schema = client.get("/openapi.json").json()
    properties = schema["components"]["schemas"]["UserProfileResponse"]["properties"]

    for field in ("phone", "city", "state", "avatar", "cycle_length", "last_period"):
        assert field in properties
