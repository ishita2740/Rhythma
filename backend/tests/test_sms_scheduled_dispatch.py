"""The weekly SMS summary actually gets sent (issue #532).

``sms_enabled`` was a write-only flag. ``POST /sms/settings`` stored it,
``GET /sms/settings`` read it back to the screen that set it, the privacy
export listed it, and nothing else in the repository ever looked at it.
There was no scheduler, no background task and no dispatch path — so a
user who switched on "weekly SMS summaries", and watched the toggle stay
on across restarts, waited for a message no code existed to send.

Two things are under test here, and they are deliberately separated.

**The scheduling rule** is a pure function of ``(user document, now)``.
Those tests pass plain dicts and explicit instants, so a week of behaviour
is exercised without freezing a clock or seeding a database, and a
regression in the rule is reported as a rule failure rather than as a
mysterious batch that sent nothing.

**The batch** is tested through the real endpoint against the in-memory
Firestore mock, with Twilio replaced by a recorder. The assertions are on
**who was texted and what they were sent**, not on the response's `sent`
count: a count of 1 does not say it went to the right person, and getting
that wrong is the whole failure mode of a fan-out that reads a shared
collection.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
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
from api import sms as sms_api  # noqa: E402
from core.auth import create_access_token, get_password_hash  # noqa: E402
from services import sms_dispatch_service as dispatch  # noqa: E402
from services.firestore_service import MockFirestoreClient, UserService  # noqa: E402
from services.rate_limit_service import RateLimitService  # noqa: E402

import services.firestore_service as _fs_mod  # noqa: E402
import services.rate_limit_service as _rl_mod  # noqa: E402

client = TestClient(app)

_mock_db = None

DISPATCH_URL = "/api/v1/sms/dispatch-due"
PREVIEW_URL = "/api/v1/sms/preview"
SEND_URL = "/api/v1/sms/send-summary"
SETTINGS_URL = "/api/v1/sms/settings"

DISPATCH_TOKEN = "test-dispatch-secret"

NOW = datetime(2026, 8, 26, 9, 0, tzinfo=timezone.utc)


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


@pytest.fixture
def dispatch_token(monkeypatch):
    monkeypatch.setenv("SMS_DISPATCH_TOKEN", DISPATCH_TOKEN)
    return {"X-SMS-Dispatch-Token": DISPATCH_TOKEN}


class Recorder:
    """Stands in for Twilio, and remembers what it was asked to send.

    A list of ``(destination, body)`` rather than a bare call count,
    because "one message went out" is not the property that matters — "it
    went to *her* number, with *her* summary in it" is.
    """

    def __init__(self, fail_for=()):
        self.sent = []
        self.fail_for = set(fail_for)

    def __call__(self, destination, body):
        if destination in self.fail_for:
            raise RuntimeError(f"Twilio refused {destination}")
        self.sent.append((destination, body))
        return f"sid-{len(self.sent)}"

    @property
    def destinations(self):
        return [destination for destination, _ in self.sent]


def _seed_user(
    *,
    phone="+919876500001",
    enabled=True,
    last_sent=None,
    **extra,
):
    data = {
        "email": f"user{phone[-4:]}@example.com",
        "password": get_password_hash("Wintergreen!Harbour42"),
        "phone": phone,
        "sms_phone_number": phone,
        "sms_enabled": enabled,
    }
    if last_sent is not None:
        data[dispatch.LAST_SENT_FIELD] = (
            last_sent.isoformat() if isinstance(last_sent, datetime) else last_sent
        )
    data.update(extra)
    return UserService.create_user(data)


def _auth(user_id):
    return {"Authorization": f"Bearer {create_access_token(data={'sub': user_id})}"}


def _stored(user_id):
    return UserService.get_user_by_id(user_id) or {}


# ─── The scheduling rule, as a pure function ──────────────────────────────


def test_a_subscriber_who_has_never_been_sent_to_is_due_now():
    """She switched it on; she should not wait a week to learn it works."""
    user = {"sms_enabled": True, "phone": "+919876500001"}
    assert dispatch.is_due(user, NOW) is True
    assert dispatch.next_due_at(user) is None


def test_a_user_with_the_toggle_off_is_never_due():
    user = {"sms_enabled": False, "phone": "+919876500001"}
    assert dispatch.is_due(user, NOW) is False
    assert dispatch.skip_reason(user, NOW) == dispatch.SKIP_DISABLED


def test_a_missing_toggle_is_treated_as_off():
    """Absent means "never asked for this", which is not consent to be texted."""
    assert dispatch.is_due({"phone": "+919876500001"}, NOW) is False


def test_a_subscriber_with_no_number_is_reported_as_such():
    """Reachable: a later profile edit can clear `phone`."""
    user = {"sms_enabled": True, "phone": ""}
    assert dispatch.skip_reason(user, NOW) == dispatch.SKIP_NO_PHONE


def test_disabled_is_reported_ahead_of_no_phone():
    """The first answer should be the one that explains the situation."""
    user = {"sms_enabled": False, "phone": ""}
    assert dispatch.skip_reason(user, NOW) == dispatch.SKIP_DISABLED


@pytest.mark.parametrize("days_ago", [0, 1, 3, 6])
def test_a_user_texted_within_the_interval_is_not_due(days_ago):
    user = {
        "sms_enabled": True,
        "phone": "+919876500001",
        dispatch.LAST_SENT_FIELD: (NOW - timedelta(days=days_ago)).isoformat(),
    }
    assert dispatch.is_due(user, NOW) is False
    assert dispatch.skip_reason(user, NOW) == dispatch.SKIP_NOT_DUE


@pytest.mark.parametrize("days_ago", [7, 8, 30, 365])
def test_a_user_texted_longer_ago_than_the_interval_is_due(days_ago):
    user = {
        "sms_enabled": True,
        "phone": "+919876500001",
        dispatch.LAST_SENT_FIELD: (NOW - timedelta(days=days_ago)).isoformat(),
    }
    assert dispatch.is_due(user, NOW) is True


def test_the_boundary_is_the_interval_exactly():
    """Seven days is due; a second short of it is not.

    Pinned because a cron that fires at a slightly different minute each
    week would otherwise drift a user's summary later and later, one
    missed run at a time.
    """
    last = NOW - timedelta(days=dispatch.SMS_SUMMARY_INTERVAL_DAYS)
    user = {"sms_enabled": True, "phone": "+91987", dispatch.LAST_SENT_FIELD: last.isoformat()}

    assert dispatch.is_due(user, NOW) is True
    assert dispatch.is_due(user, NOW - timedelta(seconds=1)) is False


def test_next_due_at_is_the_stamp_plus_the_interval():
    last = NOW - timedelta(days=2)
    user = {"sms_enabled": True, "phone": "+91987", dispatch.LAST_SENT_FIELD: last.isoformat()}

    assert dispatch.next_due_at(user) == last + timedelta(
        days=dispatch.SMS_SUMMARY_INTERVAL_DAYS
    )


# ─── as_utc: the shapes a stored timestamp actually arrives in ────────────


def test_as_utc_accepts_an_iso_string():
    assert dispatch.as_utc("2026-08-26T09:00:00+00:00") == NOW


def test_as_utc_accepts_a_trailing_z():
    assert dispatch.as_utc("2026-08-26T09:00:00Z") == NOW


def test_as_utc_accepts_a_datetime_and_normalises_the_zone():
    aware = datetime(2026, 8, 26, 14, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    assert dispatch.as_utc(aware) == NOW


def test_as_utc_assumes_utc_for_a_naive_datetime():
    """Assumed rather than rejected.

    Everything in this codebase writes `datetime.now(timezone.utc)`, and
    raising on one legacy document would stop a batch mid-run — a worse
    failure than the assumption.
    """
    assert dispatch.as_utc(datetime(2026, 8, 26, 9, 0)) == NOW


@pytest.mark.parametrize("junk", [None, "", "   ", "not-a-date", 42, [], {}])
def test_as_utc_returns_none_for_anything_unusable(junk):
    assert dispatch.as_utc(junk) is None


def test_an_unparseable_stamp_makes_a_user_due_rather_than_crashing():
    """A corrupt field must not make her unreachable forever."""
    user = {"sms_enabled": True, "phone": "+91987", dispatch.LAST_SENT_FIELD: "garbage"}
    assert dispatch.is_due(user, NOW) is True


# ─── Selecting the batch ──────────────────────────────────────────────────


def test_due_users_returns_only_subscribers_and_tallies_the_rest():
    due_user = _seed_user(phone="+919876500001", enabled=True)
    _seed_user(phone="+919876500002", enabled=False)
    _seed_user(phone="", enabled=True)
    _seed_user(phone="+919876500004", enabled=True, last_sent=NOW - timedelta(days=1))

    due, skipped = dispatch.due_users(NOW)

    assert [user["id"] for user in due] == [due_user]
    assert skipped[dispatch.SKIP_DISABLED] == 1
    assert skipped[dispatch.SKIP_NO_PHONE] == 1
    assert skipped[dispatch.SKIP_NOT_DUE] == 1


def test_the_skip_tally_counts_every_non_due_user_not_just_a_page():
    """A caller needs the shape of the whole collection, not of the page.

    Otherwise "nobody is subscribed" and "the batch size is too small"
    look identical.
    """
    for index in range(5):
        _seed_user(phone=f"+91987650100{index}", enabled=False)
    _seed_user(phone="+919876502000", enabled=True)

    _, skipped = dispatch.due_users(NOW, limit=1)

    assert skipped[dispatch.SKIP_DISABLED] == 5


def test_limit_bounds_the_batch():
    for index in range(4):
        _seed_user(phone=f"+91987650300{index}", enabled=True)

    due, _ = dispatch.due_users(NOW, limit=2)

    assert len(due) == 2


def test_limit_is_clamped_to_the_ceiling():
    _seed_user(phone="+919876504001", enabled=True)
    due, _ = dispatch.due_users(NOW, limit=10_000_000)
    assert len(due) == 1


def test_the_scan_is_ordered_so_nobody_is_permanently_unlucky():
    """An unordered scan makes `limit` mean "an arbitrary hundred".

    A user at the wrong end of an arbitrary order could be passed over
    week after week while the batch reported a full hundred sends each
    time.
    """
    for index in range(6):
        _seed_user(phone=f"+91987650500{index}", enabled=True)

    first, _ = dispatch.due_users(NOW, limit=3)
    again, _ = dispatch.due_users(NOW, limit=3)

    assert [user["id"] for user in first] == [user["id"] for user in again]


def test_an_empty_collection_is_a_quiet_no_op():
    due, skipped = dispatch.due_users(NOW)
    assert due == []
    assert sum(skipped.values()) == 0


# ─── Running the batch ────────────────────────────────────────────────────


def test_dispatch_sends_to_each_due_subscriber():
    _seed_user(phone="+919876500001", enabled=True)
    _seed_user(phone="+919876500002", enabled=True)
    _seed_user(phone="+919876500003", enabled=False)
    recorder = Recorder()

    report = dispatch.dispatch_due(
        now=NOW, send=recorder, build_body=lambda uid: f"summary for {uid}"
    )

    assert report.sent == 2
    assert sorted(recorder.destinations) == ["+919876500001", "+919876500002"]


def test_each_user_is_sent_her_own_summary():
    """The fan-out failure mode: one body built once and mailed to everyone."""
    first = _seed_user(phone="+919876500001", enabled=True)
    second = _seed_user(phone="+919876500002", enabled=True)
    recorder = Recorder()

    dispatch.dispatch_due(
        now=NOW, send=recorder, build_body=lambda uid: f"summary for {uid}"
    )

    bodies = dict(recorder.sent)
    assert bodies["+919876500001"] == f"summary for {first}"
    assert bodies["+919876500002"] == f"summary for {second}"


def test_a_successful_send_stamps_the_user():
    user = _seed_user(phone="+919876500001", enabled=True)

    dispatch.dispatch_due(now=NOW, send=Recorder(), build_body=lambda uid: "body")

    assert dispatch.as_utc(_stored(user)[dispatch.LAST_SENT_FIELD]) == NOW


def test_running_the_batch_twice_does_not_text_anyone_twice():
    """The property that makes this endpoint safe for a real cron.

    A cron that double-fires, a retry after a timeout, two overlapping
    runs — all of them call this more often than the cadence, and none of
    them may produce two texts.
    """
    _seed_user(phone="+919876500001", enabled=True)
    recorder = Recorder()

    dispatch.dispatch_due(now=NOW, send=recorder, build_body=lambda uid: "body")
    second = dispatch.dispatch_due(
        now=NOW + timedelta(minutes=5), send=recorder, build_body=lambda uid: "body"
    )

    assert len(recorder.sent) == 1
    assert second.sent == 0
    assert second.skipped[dispatch.SKIP_NOT_DUE] == 1


def test_the_next_week_sends_again():
    _seed_user(phone="+919876500001", enabled=True)
    recorder = Recorder()

    dispatch.dispatch_due(now=NOW, send=recorder, build_body=lambda uid: "body")
    dispatch.dispatch_due(
        now=NOW + timedelta(days=7), send=recorder, build_body=lambda uid: "body"
    )

    assert len(recorder.sent) == 2


def test_one_failure_does_not_stop_the_batch():
    """One unreachable number must not cost everybody else her summary."""
    _seed_user(phone="+919876500001", enabled=True)
    _seed_user(phone="+919876500002", enabled=True)
    _seed_user(phone="+919876500003", enabled=True)
    recorder = Recorder(fail_for={"+919876500002"})

    report = dispatch.dispatch_due(
        now=NOW, send=recorder, build_body=lambda uid: "body"
    )

    assert report.sent == 2
    assert report.failed == 1
    assert sorted(recorder.destinations) == ["+919876500001", "+919876500003"]


def test_a_failed_send_is_not_stamped():
    """Stamping a failure would silently consume her week.

    She would be recorded as having been told, and would not be due again
    for seven days.
    """
    user = _seed_user(phone="+919876500002", enabled=True)
    recorder = Recorder(fail_for={"+919876500002"})

    dispatch.dispatch_due(now=NOW, send=recorder, build_body=lambda uid: "body")

    assert dispatch.LAST_SENT_FIELD not in _stored(user)
    assert dispatch.is_due(_stored(user), NOW) is True


def test_a_failure_while_building_the_body_is_caught_per_user():
    _seed_user(phone="+919876500001", enabled=True)
    _seed_user(phone="+919876500002", enabled=True)
    recorder = Recorder()

    attempts = []

    def build(user_id):
        attempts.append(user_id)
        if len(attempts) == 1:
            raise RuntimeError("scoring blew up")
        return "body"

    report = dispatch.dispatch_due(now=NOW, send=recorder, build_body=build)

    assert report.failed == 1
    assert report.sent == 1


def test_the_report_names_the_user_and_never_her_number():
    """A batch report is not a place to accumulate women's phone numbers."""
    user = _seed_user(phone="+919876500001", enabled=True)

    report = dispatch.dispatch_due(
        now=NOW, send=Recorder(), build_body=lambda uid: "body"
    )
    payload = report.to_dict()

    assert payload["outcomes"][0]["userId"] == user
    assert "+919876500001" not in str(payload)


def test_the_report_carries_the_run_time_and_the_interval():
    report = dispatch.dispatch_due(
        now=NOW, send=Recorder(), build_body=lambda uid: "body"
    )
    payload = report.to_dict()

    assert payload["ranAt"] == NOW.isoformat()
    assert payload["intervalDays"] == dispatch.SMS_SUMMARY_INTERVAL_DAYS


# ─── POST /sms/dispatch-due ───────────────────────────────────────────────


def test_the_endpoint_sends_a_batch(dispatch_token):
    _seed_user(phone="+919876500001", enabled=True)
    recorder = Recorder()

    with patch.object(sms_api, "send_sms", recorder), patch.object(
        sms_api, "generate_cycle_sms_summary", lambda uid: "Rhythma Summary: ..."
    ):
        response = client.post(DISPATCH_URL, headers=dispatch_token)

    assert response.status_code == 200
    assert response.json()["sent"] == 1
    assert recorder.destinations == ["+919876500001"]


def test_the_endpoint_reports_skips_by_reason(dispatch_token):
    _seed_user(phone="+919876500001", enabled=False)
    _seed_user(phone="+919876500002", enabled=True, last_sent=datetime.now(timezone.utc))

    with patch.object(sms_api, "send_sms", Recorder()):
        body = client.post(DISPATCH_URL, headers=dispatch_token).json()

    assert body["skipped"]["disabled"] == 1
    assert body["skipped"]["not_due"] == 1
    assert body["sent"] == 0


def test_the_endpoint_refuses_without_a_token(dispatch_token):
    _seed_user(phone="+919876500001", enabled=True)
    response = client.post(DISPATCH_URL)
    assert response.status_code == 401


def test_the_endpoint_refuses_a_wrong_token(dispatch_token):
    response = client.post(
        DISPATCH_URL, headers={"X-SMS-Dispatch-Token": "not-the-secret"}
    )
    assert response.status_code == 401


def test_the_endpoint_is_unavailable_when_no_secret_is_configured(monkeypatch):
    """A deployment that has not configured a secret must not expose an
    unauthenticated way to make the project send SMS."""
    monkeypatch.delenv("SMS_DISPATCH_TOKEN", raising=False)

    response = client.post(DISPATCH_URL, headers={"X-SMS-Dispatch-Token": "anything"})

    assert response.status_code == 503


def test_a_user_session_cannot_run_the_batch(dispatch_token):
    """It is an operational endpoint, not a user one."""
    user = _seed_user(phone="+919876500001", enabled=True)

    response = client.post(DISPATCH_URL, headers=_auth(user))

    assert response.status_code == 401


def test_the_batch_limit_is_validated(dispatch_token):
    assert client.post(f"{DISPATCH_URL}?limit=0", headers=dispatch_token).status_code == 422
    assert (
        client.post(f"{DISPATCH_URL}?limit=100000", headers=dispatch_token).status_code
        == 422
    )


# ─── The toggle is honoured on the manual path too ────────────────────────


def test_send_now_is_refused_when_summaries_are_switched_off():
    """Off used to mean the same as on."""
    user = _seed_user(phone="+919876500001", enabled=False)

    response = client.post(SEND_URL, json={}, headers=_auth(user))

    assert response.status_code == 409
    assert "switched off" in response.json()["detail"]


def test_send_now_works_when_summaries_are_on():
    user = _seed_user(phone="+919876500001", enabled=True)

    with patch.object(sms_api, "send_sms", Recorder()):
        response = client.post(SEND_URL, json={}, headers=_auth(user))

    assert response.status_code == 200


def test_send_now_counts_against_the_weekly_cadence():
    """Otherwise the scheduler repeats Monday's summary on Tuesday."""
    user = _seed_user(phone="+919876500001", enabled=True)

    with patch.object(sms_api, "send_sms", Recorder()):
        client.post(SEND_URL, json={}, headers=_auth(user))

    assert dispatch.LAST_SENT_FIELD in _stored(user)
    assert dispatch.is_due(_stored(user), datetime.now(timezone.utc)) is False


def test_the_toggle_is_checked_before_the_rate_limiter():
    """A refused request costs nothing, so it must not spend her allowance."""
    user = _seed_user(phone="+919876500001", enabled=False)

    for _ in range(3):
        response = client.post(SEND_URL, json={}, headers=_auth(user))
        assert response.status_code == 409


# ─── GET /sms/preview ─────────────────────────────────────────────────────


def test_preview_returns_the_body_that_would_be_sent():
    """Built by the same function, so it cannot drift from the real message."""
    user = _seed_user(phone="+919876500001", enabled=True)

    body = client.get(PREVIEW_URL, headers=_auth(user)).json()

    assert body["body"] == sms_api.generate_cycle_sms_summary(user)
    assert body["destination"] == "+919876500001"
    assert body["characters"] == len(body["body"])


def test_preview_reports_whether_summaries_are_on():
    user = _seed_user(phone="+919876500001", enabled=False)
    assert client.get(PREVIEW_URL, headers=_auth(user)).json()["enabled"] is False


def test_preview_works_with_the_toggle_off():
    """Seeing what would be sent is how a user decides whether to switch it on."""
    user = _seed_user(phone="+919876500001", enabled=False)
    assert client.get(PREVIEW_URL, headers=_auth(user)).status_code == 200


def test_preview_sends_nothing():
    user = _seed_user(phone="+919876500001", enabled=True)
    recorder = Recorder()

    with patch.object(sms_api, "send_sms", recorder):
        client.get(PREVIEW_URL, headers=_auth(user))

    assert recorder.sent == []


def test_preview_needs_a_saved_number():
    user = _seed_user(phone="", enabled=False)
    response = client.get(PREVIEW_URL, headers=_auth(user))
    assert response.status_code == 409


def test_preview_requires_authentication():
    assert client.get(PREVIEW_URL).status_code in (401, 403)


def test_the_preview_fits_one_sms_segment():
    """The summary is built to fit one segment; a preview that shows more
    than will be sent would be a preview of a different message."""
    user = _seed_user(phone="+919876500001", enabled=True)

    body = client.get(PREVIEW_URL, headers=_auth(user)).json()

    assert body["characters"] <= sms_api.SMS_MAX_CHARS


# ─── Settings still round-trip ────────────────────────────────────────────


def test_turning_the_toggle_on_makes_a_user_due():
    """End to end: the switch now has a reader."""
    user = _seed_user(phone="+919876500001", enabled=False)
    assert dispatch.is_due(_stored(user), NOW) is False

    client.post(
        SETTINGS_URL,
        json={"phoneNumber": "+919876500001", "enabled": True},
        headers=_auth(user),
    )

    assert dispatch.is_due(_stored(user), NOW) is True


def test_turning_the_toggle_off_stops_the_scheduled_send():
    user = _seed_user(phone="+919876500001", enabled=True)
    recorder = Recorder()

    client.post(
        SETTINGS_URL,
        json={"phoneNumber": "+919876500001", "enabled": False},
        headers=_auth(user),
    )
    report = dispatch.dispatch_due(
        now=NOW, send=recorder, build_body=lambda uid: "body"
    )

    assert recorder.sent == []
    assert report.skipped[dispatch.SKIP_DISABLED] == 1
