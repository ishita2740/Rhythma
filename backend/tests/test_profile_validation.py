"""What ``last_period`` is allowed to be (issue #501).

Three layers, because the bug had three layers.

The normaliser is tested directly: the shapes a client legitimately sends,
the shapes it should be told about, and the two bounds.

``UserProfileUpdate`` is tested as a model, because a rule that lives in a
module and is not wired into the schema protects nothing.

And ``PATCH /auth/profile`` is driven through the real app, because the
point of the change is that a bad value never reaches Firestore and
therefore never reaches ``prediction_service`` — which is where the
silence used to happen. The last group closes that loop by feeding the
rejected values straight to ``predict()`` and showing what they do there.
"""

import os
import sys
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ─── Mocks, matching the other route tests in this suite ──────────────────


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

from fastapi.testclient import TestClient  # noqa: E402

from core.profile_validation import (  # noqa: E402
    FUTURE_GRACE_DAYS,
    MAX_LAST_PERIOD_AGE_DAYS,
    normalize_last_period,
)
from main import app  # noqa: E402
from models.user import UserProfileUpdate  # noqa: E402
from services import prediction_service  # noqa: E402

client = TestClient(app)


def _today() -> date:
    return datetime.now(timezone.utc).date()


# ─── Shapes a client legitimately sends ───────────────────────────────────


def test_a_bare_date_is_accepted_unchanged():
    assert normalize_last_period("2026-06-01") == "2026-06-01"


def test_surrounding_whitespace_does_not_change_the_answer():
    assert normalize_last_period("  2026-06-01 ") == "2026-06-01"


@pytest.mark.parametrize(
    "sent",
    [
        "2026-06-01T00:00:00",
        "2026-06-01T09:30:00Z",
        "2026-06-01T09:30:00z",
        "2026-06-01T09:30:00+05:30",
        "2026-06-01T09:30:00.123456Z",
    ],
)
def test_a_timestamp_is_reduced_to_its_date(sent):
    """A client that formats a DateTime rather than a date means the same day."""
    assert normalize_last_period(sent) == "2026-06-01"


def test_the_basic_iso_form_is_accepted():
    """`20260601` is ISO-8601 too, and `date.fromisoformat` reads it.

    Listed explicitly rather than left to chance: it is the form a client
    that strips separators would send, and it means the same day.
    """
    assert normalize_last_period("20260601") == "2026-06-01"


def test_a_date_object_is_accepted():
    """Firestore hands back dates; a caller re-saving one should not be refused."""
    assert normalize_last_period(date(2026, 6, 1)) == "2026-06-01"


def test_a_datetime_object_is_reduced_to_its_date():
    assert normalize_last_period(datetime(2026, 6, 1, 9, 30)) == "2026-06-01"


def test_today_is_accepted():
    today = _today()
    assert normalize_last_period(today.isoformat()) == today.isoformat()


# ─── Omission is not the same as nonsense ─────────────────────────────────


def test_none_passes_through():
    assert normalize_last_period(None) is None


def test_an_empty_string_is_read_as_clearing_the_field():
    """Storing "" would be worse than storing nothing.

    `prediction_service` guards with `isinstance(declared, str)`, which is
    true of the empty string, so it would reach `date.fromisoformat` and
    fail there — the exact silent path this change closes.
    """
    assert normalize_last_period("") is None
    assert normalize_last_period("   ") is None


# ─── Shapes a client should be told about ─────────────────────────────────


@pytest.mark.parametrize(
    "sent",
    [
        "yesterday",
        "01/06/2026",
        "2026-13-01",
        "2026-02-30",
        "2026-6-1",
        "2026-06-01-garbage",
        "null",
        "0",
    ],
)
def test_something_that_is_not_a_date_is_refused(sent):
    with pytest.raises(ValueError) as exc:
        normalize_last_period(sent)
    assert "last_period" in str(exc.value)


def test_a_trailing_suffix_is_not_quietly_truncated():
    """`declared[:10]` downstream would have accepted this. Here it does not."""
    with pytest.raises(ValueError):
        normalize_last_period("2026-06-01-garbage")


def test_a_value_that_is_not_text_is_refused():
    for sent in (42, 3.5, True, ["2026-06-01"], {"date": "2026-06-01"}):
        with pytest.raises(ValueError):
            normalize_last_period(sent)


def test_an_absurdly_long_value_is_refused_before_parsing():
    with pytest.raises(ValueError):
        normalize_last_period("2026-06-01" + "x" * 5000)


# ─── The two bounds ───────────────────────────────────────────────────────


def test_a_date_in_the_future_is_refused():
    ahead = (_today() + timedelta(days=30)).isoformat()

    with pytest.raises(ValueError) as exc:
        normalize_last_period(ahead)

    assert "future" in str(exc.value)


def test_tomorrow_is_within_the_timezone_grace():
    """A picker offering "today" east of UTC sends a date the server has not reached.

    Refusing it would reject the most common answer there is, for users in
    exactly the timezones this app is built for.
    """
    tomorrow = (_today() + timedelta(days=FUTURE_GRACE_DAYS)).isoformat()

    assert normalize_last_period(tomorrow) == tomorrow


def test_the_grace_does_not_extend_to_a_genuinely_wrong_answer():
    beyond = (_today() + timedelta(days=FUTURE_GRACE_DAYS + 1)).isoformat()

    with pytest.raises(ValueError):
        normalize_last_period(beyond)


def test_a_date_from_years_ago_is_accepted():
    """Importing a history, or returning after a long gap, is legitimate."""
    old = (_today() - timedelta(days=MAX_LAST_PERIOD_AGE_DAYS - 10)).isoformat()

    assert normalize_last_period(old) == old


def test_a_date_beyond_the_age_bound_is_refused():
    ancient = (_today() - timedelta(days=MAX_LAST_PERIOD_AGE_DAYS + 10)).isoformat()

    with pytest.raises(ValueError) as exc:
        normalize_last_period(ancient)

    assert "past" in str(exc.value)


def test_a_mis_parsed_year_is_refused_by_the_age_bound():
    """`0202-06-01` parses as a date and is not one anybody meant."""
    with pytest.raises(ValueError):
        normalize_last_period("0202-06-01")


# ─── Wired into the schema ────────────────────────────────────────────────


def test_the_model_normalises_a_timestamp():
    update = UserProfileUpdate(last_period="2026-06-01T09:30:00Z")

    assert update.last_period == "2026-06-01"


def test_the_model_refuses_a_future_date():
    ahead = (_today() + timedelta(days=30)).isoformat()

    with pytest.raises(ValidationError) as exc:
        UserProfileUpdate(last_period=ahead)

    assert "last_period" in str(exc.value)


def test_the_model_refuses_a_malformed_date():
    with pytest.raises(ValidationError):
        UserProfileUpdate(last_period="not-a-date")


def test_an_update_that_omits_the_field_is_unaffected():
    """PATCH semantics: `model_dump()` must not start emitting a `None`."""
    update = UserProfileUpdate(full_name="Alice Doe")

    dump = update.model_dump()
    assert dump["last_period"] is None
    assert {k: v for k, v in dump.items() if v is not None} == {
        "full_name": "Alice Doe"
    }


# ─── Through the route ────────────────────────────────────────────────────


@pytest.fixture
def _authenticated(monkeypatch):
    """A signed-in user whose profile writes are captured rather than stored."""
    import core.auth_router as auth_router_module
    from core.auth import get_current_user

    written = {}

    def _fake_update(user_id, updates):
        written.update(updates)
        return True

    def _fake_get(user_id):
        return {
            "id": user_id,
            "email": "asha@example.com",
            "username": "ashadev",
            **written,
        }

    monkeypatch.setattr(
        auth_router_module.UserService, "update_user", staticmethod(_fake_update)
    )
    monkeypatch.setattr(
        auth_router_module.UserService, "get_user_by_id", staticmethod(_fake_get)
    )

    app.dependency_overrides[get_current_user] = lambda: {
        "id": "user-1",
        "email": "asha@example.com",
    }
    yield written
    app.dependency_overrides.pop(get_current_user, None)


def test_the_route_stores_a_normalised_date(_authenticated):
    response = client.patch(
        "/api/v1/auth/profile", json={"last_period": "2026-06-01T09:30:00Z"}
    )

    assert response.status_code == 200
    assert _authenticated["last_period"] == "2026-06-01"


def test_the_route_refuses_a_future_date_with_a_422(_authenticated):
    ahead = (_today() + timedelta(days=45)).isoformat()

    response = client.patch("/api/v1/auth/profile", json={"last_period": ahead})

    assert response.status_code == 422
    assert _authenticated == {}, "nothing should have reached the store"


def test_the_route_refuses_a_malformed_date_with_a_422(_authenticated):
    response = client.patch(
        "/api/v1/auth/profile", json={"last_period": "01/06/2026"}
    )

    assert response.status_code == 422
    assert _authenticated == {}


def test_the_422_names_the_field(_authenticated):
    response = client.patch(
        "/api/v1/auth/profile", json={"last_period": "yesterday"}
    )

    assert response.status_code == 422
    assert "last_period" in response.text


def test_other_profile_fields_still_save(_authenticated):
    """The change must not turn an ordinary update into a rejection."""
    response = client.patch(
        "/api/v1/auth/profile",
        json={"full_name": "Asha", "cycle_length": 30, "period_duration": 5},
    )

    assert response.status_code == 200
    assert _authenticated["cycle_length"] == 30
    assert "last_period" not in _authenticated


# ─── What the rejected values would have done downstream ──────────────────
#
# The reason a 422 is worth having: none of these fails loudly on its own.


def test_a_malformed_anchor_would_have_emptied_the_prediction():
    result = prediction_service.predict([], profile={"last_period": "yesterday"})

    assert result.last_period_start is None
    assert result.phase == prediction_service.PHASE_UNKNOWN
    assert result.next_period_date is None
    assert result.ovulation_date is None


def test_a_future_anchor_would_have_produced_a_fertile_window(monkeypatch):
    """Confidently wrong, which is worse than empty.

    A fertile-window date is the one output of this app that a user acts on
    away from the screen.
    """
    today = date(2026, 6, 1)
    ahead = (today + timedelta(days=30)).isoformat()

    result = prediction_service.predict(
        [], profile={"last_period": ahead, "cycle_length": 28}, today=today
    )

    assert result.last_period_start == date(2026, 7, 1)
    assert result.current_cycle_day is None  # suppressed, so nothing warns
    assert result.ovulation_date is not None  # but this is still rendered
    assert result.fertile_window_start is not None
    assert result.fertile_window_end is not None


def test_an_accepted_anchor_behaves():
    today = date(2026, 6, 15)

    result = prediction_service.predict(
        [], profile={"last_period": "2026-06-01", "cycle_length": 28}, today=today
    )

    assert result.last_period_start == date(2026, 6, 1)
    assert result.current_cycle_day == 15
    assert result.next_period_date == date(2026, 6, 29)
