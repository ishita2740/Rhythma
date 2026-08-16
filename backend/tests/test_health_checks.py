"""Liveness, readiness and the detailed health view (issue #348).

The bug was not that a check returned the wrong answer — there were no
checks. `/health` returned `{"status": "ok"}` for a process running
entirely on the in-memory mock database, silently losing every write on
restart.

So the assertion that carries the most weight in this file is
`test_the_mock_database_fails_readiness`: it is the exact deployment
failure the issue describes, and it is the one an operator would otherwise
never see.

The checks are exercised both directly and through HTTP. Directly, because
a check is a function and driving `check_firestore` through a route to
learn whether it detects a mock client only obscures what failed. Through
HTTP, because the status *code* is the entire contract with a platform
health probe, and that is a route concern.
"""

import os
import sys
import time
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
from services import firestore_service as fs  # noqa: E402
from services import health_check_service as hc  # noqa: E402
from services.health_check_service import (  # noqa: E402
    STATUS_DEGRADED,
    STATUS_DOWN,
    STATUS_OK,
    ComponentHealth,
    HealthReport,
    build_info,
    check_assistant_config,
    check_auth_config,
    check_firestore,
    check_sms_config,
    liveness,
    run_checks,
)

client = TestClient(app)


class _WorkingFirestore:
    """Stands in for a real, reachable client.

    Records the path it was asked for, so a test can assert the probe
    reads its own document rather than touching user data.
    """

    def __init__(self):
        self.read_paths = []

    def collection(self, name):
        self.read_paths.append(name)
        return self

    def document(self, doc_id):
        self.read_paths.append(doc_id)
        return self

    def get(self):
        return MagicMock(exists=False)


@pytest.fixture
def working_db(monkeypatch):
    fake = _WorkingFirestore()
    monkeypatch.setattr(fs, "db", fake)
    return fake


# ─── The failure from the issue ────────────────────────────────────────────


def test_the_mock_database_is_reported_as_down():
    """The whole reason this module exists.

    A process on the mock client is *healthy* — nothing throws, every
    write succeeds — and loses everything on restart. Only an explicit
    type check catches it; a read probe against the mock succeeds
    beautifully.
    """
    with patch.object(fs, "db", fs.MockFirestoreClient()):
        result = check_firestore()

    assert result.status == STATUS_DOWN
    assert result.required is True
    assert "mock" in result.detail.lower()
    assert "restart" in result.detail.lower()


def test_the_mock_database_fails_readiness():
    """`/health/ready` must return 503, not 200, on the mock database."""
    with patch.object(fs, "db", fs.MockFirestoreClient()):
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["ready"] is False


def test_the_old_endpoint_reported_ok_for_this_exact_state():
    """The regression guard, stated as the contrast it is.

    `/health/` still answers 200 — it is the detailed view and a 503 there
    would hide the breakdown that was asked for — but `status` is no
    longer `ok`, and `ready` is false.
    """
    with patch.object(fs, "db", fs.MockFirestoreClient()):
        response = client.get("/api/v1/health/")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == STATUS_DOWN
    assert body["ready"] is False
    assert body["service"] == "Rhythma API"


# ─── Firestore check ───────────────────────────────────────────────────────


def test_a_reachable_client_is_ok(working_db):
    assert check_firestore().status == STATUS_OK


def test_the_probe_reads_its_own_document_not_user_data(working_db):
    check_firestore()

    assert hc.HEALTH_PROBE_COLLECTION in working_db.read_paths
    assert hc.HEALTH_PROBE_DOCUMENT in working_db.read_paths
    assert "users" not in working_db.read_paths
    assert "cycle_logs" not in working_db.read_paths


def test_a_missing_probe_document_is_still_healthy(working_db):
    """The round trip is the signal; whether the document exists is not."""
    assert check_firestore().status == STATUS_OK


def test_a_missing_client_is_down(monkeypatch):
    monkeypatch.setattr(fs, "db", None)
    result = check_firestore()

    assert result.status == STATUS_DOWN
    assert result.required is True


def test_an_unreachable_client_is_down_with_a_different_detail(monkeypatch):
    """"Mocked" and "unreachable" are both down and need different fixes."""
    exploding = MagicMock()
    exploding.collection.side_effect = RuntimeError("connection refused to 10.0.0.1")
    monkeypatch.setattr(fs, "db", exploding)

    report = run_checks()
    firestore = next(c for c in report.components if c.name == "firestore")

    assert firestore.status == STATUS_DOWN
    assert "mock" not in firestore.detail.lower()


def test_an_exception_message_is_not_returned_to_the_caller(monkeypatch):
    """Raw dependency errors carry project ids and index-creation URLs."""
    exploding = MagicMock()
    exploding.collection.side_effect = RuntimeError(
        "project rhythma-prod-8821 index https://console.cloud.google.com/secret"
    )
    monkeypatch.setattr(fs, "db", exploding)

    response = client.get("/api/v1/health/ready")

    assert "rhythma-prod-8821" not in response.text
    assert "console.cloud.google.com" not in response.text


# ─── Config checks ─────────────────────────────────────────────────────────


def test_auth_is_down_without_a_signing_key(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    result = check_auth_config()

    assert result.status == STATUS_DOWN
    assert result.required is True


def test_a_blank_signing_key_counts_as_missing(monkeypatch):
    """`JWT_SECRET=` in an env file is not a configured secret."""
    monkeypatch.setenv("JWT_SECRET", "   ")
    assert check_auth_config().status == STATUS_DOWN


def test_a_missing_gemini_key_is_degraded_not_down(monkeypatch):
    """The cycle-tracking product works without the assistant."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = check_assistant_config()

    assert result.status == STATUS_DEGRADED
    assert result.required is False


def test_missing_twilio_is_degraded_not_down(monkeypatch):
    for name in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER"):
        monkeypatch.delenv(name, raising=False)
    result = check_sms_config()

    assert result.status == STATUS_DEGRADED
    assert result.required is False


def test_partial_twilio_config_names_what_is_missing(monkeypatch):
    """`/sms/send-summary` currently discovers this when a user taps send."""
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_PHONE_NUMBER", raising=False)

    result = check_sms_config()

    assert result.status == STATUS_DEGRADED
    assert "TWILIO_AUTH_TOKEN" in result.detail
    assert "TWILIO_PHONE_NUMBER" in result.detail


def test_fully_configured_twilio_is_ok(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+911234567890")

    assert check_sms_config().status == STATUS_OK


def test_no_check_ever_returns_a_secret_value(monkeypatch):
    """Configured/not-configured only. Never a value or a prefix."""
    monkeypatch.setenv("JWT_SECRET", "super-secret-signing-key")
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTOTALLYSECRET")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACsecretsid")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "secrettoken")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+911234567890")

    response = client.get("/api/v1/health/")

    for secret in (
        "super-secret-signing-key",
        "AIzaSyTOTALLYSECRET",
        "ACsecretsid",
        "secrettoken",
    ):
        assert secret not in response.text


# ─── Readiness semantics ───────────────────────────────────────────────────


def test_a_degraded_optional_dependency_stays_ready(working_db, monkeypatch):
    """Pulling an instance from rotation over SMS would be the worse outage."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    for name in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_PHONE_NUMBER"):
        monkeypatch.delenv(name, raising=False)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["status"] == STATUS_DEGRADED


def test_overall_status_is_the_worst_component():
    ok = ComponentHealth("a", STATUS_OK, True, "")
    degraded = ComponentHealth("b", STATUS_DEGRADED, False, "")
    down = ComponentHealth("c", STATUS_DOWN, True, "")

    assert HealthReport(STATUS_OK, [ok]).ready is True
    assert HealthReport(STATUS_DEGRADED, [ok, degraded]).ready is True
    assert HealthReport(STATUS_DOWN, [ok, degraded, down]).ready is False


def test_a_down_optional_component_does_not_fail_readiness():
    """`required` is what gates readiness, not `status` alone."""
    optional_down = ComponentHealth("sms", STATUS_DOWN, False, "")
    assert HealthReport(STATUS_DOWN, [optional_down]).ready is True


# ─── Liveness stays independent ────────────────────────────────────────────


def test_liveness_touches_no_dependency():
    """A liveness probe that failed on a DB outage would restart-loop the fleet."""
    with patch.object(fs, "db", None):
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == STATUS_OK


def test_liveness_answers_even_when_everything_else_is_down(monkeypatch):
    exploding = MagicMock()
    exploding.collection.side_effect = RuntimeError("down")
    monkeypatch.setattr(fs, "db", exploding)
    monkeypatch.delenv("JWT_SECRET", raising=False)

    assert client.get("/api/v1/health/live").status_code == 200


def test_liveness_payload_shape():
    body = liveness()
    assert body["status"] == STATUS_OK
    assert body["service"] == "Rhythma API"
    assert "checkedAt" in body


# ─── Timeouts ──────────────────────────────────────────────────────────────


def test_a_hanging_check_becomes_a_result_not_a_hang(monkeypatch):
    """The endpoint must not inherit a wedged dependency's hang."""

    class _Hanging:
        def collection(self, name):
            time.sleep(5)
            return self

    monkeypatch.setattr(fs, "db", _Hanging())

    started = time.perf_counter()
    report = run_checks(timeout=0.2)
    elapsed = time.perf_counter() - started

    firestore = next(c for c in report.components if c.name == "firestore")
    assert firestore.status == STATUS_DOWN
    assert "did not respond" in firestore.detail
    assert elapsed < 3, f"run_checks inherited the hang ({elapsed:.1f}s)"


def test_a_raising_check_does_not_escape_as_an_exception():
    """An endpoint whose job is reporting failure must not fail itself."""

    def explodes():
        raise RuntimeError("boom")

    result = hc._run_one(explodes, timeout=1.0)

    assert result.status == STATUS_DOWN
    assert "boom" not in result.detail


def test_check_durations_are_recorded(working_db):
    report = run_checks()
    assert all(c.duration_ms >= 0 for c in report.components)


# ─── Build metadata ────────────────────────────────────────────────────────


def test_build_info_falls_back_gracefully(monkeypatch):
    for name in ("GIT_COMMIT", "VERCEL_GIT_COMMIT_SHA", "BUILD_TIME", "APP_ENV"):
        monkeypatch.delenv(name, raising=False)

    info = build_info()

    assert info["commit"] == "unknown"
    assert info["builtAt"] == "unknown"
    assert info["environment"] == "development"


def test_build_info_reads_the_commit_from_the_environment(monkeypatch):
    monkeypatch.setenv("GIT_COMMIT", "abcdef1234567890abcdef")
    assert build_info()["commit"] == "abcdef123456"


def test_the_root_route_no_longer_hardcodes_a_version(monkeypatch):
    """`/` returned a literal "0.1.0" that had never changed."""
    monkeypatch.setenv("APP_VERSION", "1.4.2")
    monkeypatch.setenv("GIT_COMMIT", "deadbeefcafe99")

    body = client.get("/").json()

    assert body["version"] == "1.4.2"
    assert body["commit"] == "deadbeefcafe"


# ─── Backward compatibility ────────────────────────────────────────────────


def test_the_original_response_keys_are_still_present(working_db, monkeypatch):
    """The route keeps its 200, its `service` name, and a `status` key.

    `status` is the one deliberate behaviour change: it is now the worst
    component's status rather than a constant `"ok"`. With every optional
    dependency configured it *is* `ok`, which is what this asserts —
    `test_a_degraded_optional_dependency_stays_ready` covers the other
    direction.
    """
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+911234567890")
    monkeypatch.setenv("GEMINI_API_KEY", "mock-key")

    response = client.get("/api/v1/health/")
    body = response.json()

    assert response.status_code == 200
    assert body["service"] == "Rhythma API"
    assert body["status"] == STATUS_OK
    assert body["ready"] is True


def test_the_detailed_view_lists_every_component(working_db):
    body = client.get("/api/v1/health/").json()
    names = {component["name"] for component in body["components"]}

    assert {"firestore", "auth", "assistant", "sms"} <= names


def test_the_detailed_view_reports_the_build(working_db):
    body = client.get("/api/v1/health/").json()

    assert set(body["build"]) == {"version", "commit", "builtAt", "environment"}


def test_health_routes_need_no_authentication(working_db):
    """A platform probe has no credentials to present."""
    for path in ("/api/v1/health/", "/api/v1/health/live", "/api/v1/health/ready"):
        assert client.get(path).status_code in (200, 503)
