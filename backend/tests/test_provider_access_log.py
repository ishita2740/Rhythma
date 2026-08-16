"""Provider access to patient records is recorded (issue #350).

#267 built the consent gate: no read of a patient's data happens without
an active consent. What was missing is the other half — a patient could
see *who had permission* and never *whether anyone used it*. The consent
was checked and then discarded, so after a clinician opened a full cycle
history the only trace was an operator-only HTTP log line.

Three properties carry most of the weight here, and each has tests named
after it:

1. A read that happens is recorded (``patient_detail``, ``patient_list``).
2. A read that is *refused* is not — otherwise a provider without consent
   could write rows into any patient's history just by guessing her id.
3. The record cannot break the read. An audit write that fails is a
   missing record; an audit write that raises is a broken dashboard, and
   the second is much worse.

Seeded through the real ``ConsentService`` and read back through the real
routes, following ``test_provider.py``.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
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
from core.auth import get_current_user  # noqa: E402
from services import access_log_service  # noqa: E402
from services import data_privacy_service as privacy  # noqa: E402
from services import firestore_service as fs  # noqa: E402
from services.access_log_service import (  # noqa: E402
    ACCESS_LOG_COLLECTION,
    VIEW_PATIENT_DETAIL,
    VIEW_PATIENT_LIST,
)
from services.provider_service import ConsentService  # noqa: E402

client = TestClient(app)

PATIENT_ID = "audit-patient"
OTHER_PATIENT_ID = "audit-other-patient"
PROVIDER_ID = "audit-provider"
PROVIDER_EMAIL = "dr.rao@clinic.in"

ACCESS_LOG_URL = "/api/v1/provider/access-log"
CONSENTS_URL = "/api/v1/provider/consents"


def _identity(user_id: str, role: str) -> dict:
    return {"id": user_id, "role": role, "username": user_id, "email": f"{user_id}@x.in"}


def _act_as(user_id: str, role: str) -> None:
    app.dependency_overrides[get_current_user] = lambda: _identity(user_id, role)


@pytest.fixture(autouse=True)
def _clean_db():
    collections = getattr(fs.db, "_collections", None)
    counters = getattr(fs.db, "_counters", None)
    if collections is not None:
        collections.clear()
    if counters is not None:
        counters.clear()

    fs.db.collection("users").document(PATIENT_ID).set(
        {"email": "asha@example.com", "full_name": "Asha Rao", "role": "patient"}
    )
    fs.db.collection("users").document(OTHER_PATIENT_ID).set(
        {"email": "meera@example.com", "full_name": "Meera S", "role": "patient"}
    )
    fs.db.collection("users").document(PROVIDER_ID).set(
        {"email": PROVIDER_EMAIL, "full_name": "Dr. Priya Rao", "role": "provider"}
    )

    yield

    app.dependency_overrides.clear()
    if collections is not None:
        collections.clear()


def _grant(patient_id=PATIENT_ID):
    return ConsentService.grant(patient_id, PROVIDER_EMAIL)


def _records():
    return list((getattr(fs.db, "_collections", {}).get(ACCESS_LOG_COLLECTION) or {}).values())


# ─── A read that happens is recorded ───────────────────────────────────────


def test_opening_a_patient_record_is_recorded():
    """The headline gap: this left no trace a patient could ever see."""
    consent = _grant()
    _act_as(PROVIDER_ID, "provider")

    response = client.get(f"/api/v1/provider/patients/{PATIENT_ID}")
    assert response.status_code == 200

    records = _records()
    assert len(records) == 1
    assert records[0]["patient_id"] == PATIENT_ID
    assert records[0]["provider_id"] == PROVIDER_ID
    assert records[0]["view"] == VIEW_PATIENT_DETAIL
    assert records[0]["consent_id"] == consent["id"]


def test_the_dashboard_list_is_recorded_per_patient():
    """One row per patient, not one for the request.

    "Was my data looked at?" is asked by each patient about herself; a
    single "the provider opened her dashboard" row would be
    unattributable to any of them.
    """
    _grant(PATIENT_ID)
    _grant(OTHER_PATIENT_ID)
    _act_as(PROVIDER_ID, "provider")

    client.get("/api/v1/provider/patients")

    records = _records()
    assert len(records) == 2
    assert {r["patient_id"] for r in records} == {PATIENT_ID, OTHER_PATIENT_ID}
    assert all(r["view"] == VIEW_PATIENT_LIST for r in records)


def test_repeated_views_accumulate():
    """An audit trail is a history, not a last-seen flag."""
    _grant()
    _act_as(PROVIDER_ID, "provider")

    for _ in range(3):
        client.get(f"/api/v1/provider/patients/{PATIENT_ID}")

    assert len(_records()) == 3


def test_the_provider_name_is_stamped_on_the_record():
    """Resolved at write time so a closed provider account still reads.

    Joining on provider id at read time would leave the patient with an
    unresolvable id where a name used to be.
    """
    _grant()
    _act_as(PROVIDER_ID, "provider")

    client.get(f"/api/v1/provider/patients/{PATIENT_ID}")

    assert _records()[0]["provider_name"] == "Dr. Priya Rao"


# ─── A refused read is not recorded ────────────────────────────────────────


def test_a_read_without_consent_writes_nothing():
    """Otherwise the endpoint is a way to write into anyone's history.

    A provider with no consent could otherwise spray rows into arbitrary
    patients' access logs just by requesting their ids — turning a
    transparency feature into a nuisance channel.
    """
    _act_as(PROVIDER_ID, "provider")

    response = client.get(f"/api/v1/provider/patients/{PATIENT_ID}")

    assert response.status_code == 403
    assert _records() == []


def test_a_revoked_consent_writes_nothing():
    consent = _grant()
    ConsentService.revoke(PATIENT_ID, consent["id"])
    _act_as(PROVIDER_ID, "provider")

    assert client.get(f"/api/v1/provider/patients/{PATIENT_ID}").status_code == 403
    assert _records() == []


def test_a_patient_hitting_the_provider_route_writes_nothing():
    _act_as(PATIENT_ID, "patient")

    assert client.get(f"/api/v1/provider/patients/{PATIENT_ID}").status_code == 403
    assert _records() == []


def test_a_missing_patient_writes_nothing():
    """404 is not an access — nothing was read."""
    _grant()
    fs.db.collection("users").document(PATIENT_ID).delete()
    _act_as(PROVIDER_ID, "provider")

    assert client.get(f"/api/v1/provider/patients/{PATIENT_ID}").status_code == 404
    assert _records() == []


# ─── The record cannot break the read ──────────────────────────────────────


def test_a_failing_audit_write_does_not_break_the_dashboard():
    """A missing record beats a 500 in front of a clinician.

    This is the property that makes the feature safe to bolt onto a
    working endpoint at all. The failure is injected at the *storage*
    layer rather than by stubbing ``record`` itself, so what is asserted
    is that the real function swallows — stubbing ``record`` to raise
    would only test whether the caller happens to catch, which is not
    where the guarantee is supposed to live.
    """
    _grant()
    _act_as(PROVIDER_ID, "provider")

    with patch.object(
        access_log_service, "_db", side_effect=RuntimeError("firestore down")
    ):
        response = client.get(f"/api/v1/provider/patients/{PATIENT_ID}")

    assert response.status_code == 200
    assert response.json()["patient"]["id"] == PATIENT_ID
    assert _records() == [], "the write failed, as the test arranged"


def test_the_dashboard_list_survives_a_failing_audit_write():
    _grant()
    _act_as(PROVIDER_ID, "provider")

    with patch.object(
        access_log_service, "_db", side_effect=RuntimeError("firestore down")
    ):
        response = client.get("/api/v1/provider/patients")

    assert response.status_code == 200
    assert len(response.json()["patients"]) == 1


def test_record_swallows_a_storage_failure():
    """`record` itself never raises. That is the whole contract."""
    with patch.object(access_log_service, "_db", side_effect=RuntimeError("no db")):
        access_log_service.record(
            provider_id=PROVIDER_ID,
            patient_id=PATIENT_ID,
            view=VIEW_PATIENT_DETAIL,
        )  # must not raise


def test_an_unknown_view_type_is_refused_without_raising():
    """A typo'd view would produce rows the patient screen cannot label."""
    access_log_service.record(
        provider_id=PROVIDER_ID, patient_id=PATIENT_ID, view="peeked"
    )

    assert _records() == []


# ─── The patient-facing endpoint ───────────────────────────────────────────


def test_a_patient_can_read_her_own_access_history():
    _grant()
    _act_as(PROVIDER_ID, "provider")
    client.get(f"/api/v1/provider/patients/{PATIENT_ID}")

    _act_as(PATIENT_ID, "patient")
    response = client.get(ACCESS_LOG_URL)

    assert response.status_code == 200
    entries = response.json()["entries"]
    assert len(entries) == 1
    assert entries[0]["providerName"] == "Dr. Priya Rao"
    assert entries[0]["view"] == VIEW_PATIENT_DETAIL


def test_a_provider_cannot_read_the_access_log():
    """Letting the subject of an audit trail read it defeats the point."""
    _act_as(PROVIDER_ID, "provider")

    assert client.get(ACCESS_LOG_URL).status_code == 403


def test_a_patient_sees_only_her_own_history():
    _grant(PATIENT_ID)
    _grant(OTHER_PATIENT_ID)
    _act_as(PROVIDER_ID, "provider")
    client.get(f"/api/v1/provider/patients/{OTHER_PATIENT_ID}")

    _act_as(PATIENT_ID, "patient")
    response = client.get(ACCESS_LOG_URL)

    assert response.json()["entries"] == []


def test_entries_are_newest_first():
    _grant()
    now = datetime.now(timezone.utc)
    for index, offset in enumerate([3, 1, 2]):
        fs.db.collection(ACCESS_LOG_COLLECTION).add(
            {
                "provider_id": PROVIDER_ID,
                "patient_id": PATIENT_ID,
                "provider_name": "Dr. Priya Rao",
                "view": VIEW_PATIENT_DETAIL,
                "consent_id": "c",
                "accessed_at": now - timedelta(days=offset),
            }
        )

    _act_as(PATIENT_ID, "patient")
    stamps = [e["accessedAt"] for e in client.get(ACCESS_LOG_URL).json()["entries"]]

    assert stamps == sorted(stamps, reverse=True)


def test_the_access_log_is_paged():
    _grant()
    now = datetime.now(timezone.utc)
    for index in range(5):
        fs.db.collection(ACCESS_LOG_COLLECTION).add(
            {
                "provider_id": PROVIDER_ID,
                "patient_id": PATIENT_ID,
                "view": VIEW_PATIENT_DETAIL,
                "accessed_at": now - timedelta(minutes=index),
            }
        )

    _act_as(PATIENT_ID, "patient")
    first = client.get(ACCESS_LOG_URL, params={"limit": 2}).json()

    assert first["page"]["count"] == 2
    assert first["page"]["hasMore"] is True
    assert first["page"]["nextOffset"] == 2

    last = client.get(ACCESS_LOG_URL, params={"limit": 2, "offset": 4}).json()
    assert last["page"]["hasMore"] is False
    assert last["page"]["nextOffset"] is None


def test_an_out_of_range_page_size_is_refused():
    _act_as(PATIENT_ID, "patient")

    assert client.get(ACCESS_LOG_URL, params={"limit": 5000}).status_code == 422
    assert client.get(ACCESS_LOG_URL, params={"limit": 0}).status_code == 422
    assert client.get(ACCESS_LOG_URL, params={"offset": -1}).status_code == 422


def test_the_access_log_holds_no_health_data():
    """A privacy feature must not become a second copy of the data.

    The record says *that* a view happened. If a cycle log or a symptom
    ever appears in one of these rows, this feature has made things worse
    rather than better.
    """
    _grant()
    fs.db.collection("cycle_logs").document("l1").set(
        {
            "user_id": PATIENT_ID,
            "start_date": datetime.now(timezone.utc),
            "symptoms": ["cramps"],
            "notes": "a private note",
        }
    )
    _act_as(PROVIDER_ID, "provider")
    client.get(f"/api/v1/provider/patients/{PATIENT_ID}")

    serialized = str(_records())
    assert "cramps" not in serialized
    assert "a private note" not in serialized
    assert set(_records()[0]) == {
        "provider_id",
        "patient_id",
        "provider_name",
        "view",
        "consent_id",
        "accessed_at",
    }


# ─── Folded into the consent list ──────────────────────────────────────────


def test_consents_carry_view_counts():
    """So the Sharing screen needs no second round trip."""
    _grant()
    _act_as(PROVIDER_ID, "provider")
    client.get(f"/api/v1/provider/patients/{PATIENT_ID}")
    client.get(f"/api/v1/provider/patients/{PATIENT_ID}")

    _act_as(PATIENT_ID, "patient")
    consents = client.get(CONSENTS_URL).json()["consents"]

    assert consents[0]["viewCount"] == 2
    assert consents[0]["lastAccessedAt"] is not None


def test_an_unused_consent_reports_zero_rather_than_null():
    """"Granted but never used" is a real, distinct answer."""
    _grant()
    _act_as(PATIENT_ID, "patient")

    consents = client.get(CONSENTS_URL).json()["consents"]

    assert consents[0]["viewCount"] == 0
    assert consents[0]["lastAccessedAt"] is None


def test_a_revoked_consent_keeps_its_history():
    """The point of revoking is knowing what was read while it was live."""
    consent = _grant()
    _act_as(PROVIDER_ID, "provider")
    client.get(f"/api/v1/provider/patients/{PATIENT_ID}")

    ConsentService.revoke(PATIENT_ID, consent["id"])

    _act_as(PATIENT_ID, "patient")
    consents = client.get(CONSENTS_URL).json()["consents"]

    assert consents[0]["status"] == "revoked"
    assert consents[0]["viewCount"] == 1


# ─── Privacy integration ───────────────────────────────────────────────────


def test_the_access_log_is_a_registered_user_data_collection():
    """Registration is what keeps export and deletion from drifting."""
    assert ACCESS_LOG_COLLECTION in privacy.USER_DATA_COLLECTIONS


def test_the_export_bundle_includes_the_access_history():
    _grant()
    _act_as(PROVIDER_ID, "provider")
    client.get(f"/api/v1/provider/patients/{PATIENT_ID}")

    bundle = privacy.build_export_bundle(PATIENT_ID)

    assert bundle["provider_access_log"]["entry_count"] == 1
    assert bundle["provider_access_log"]["entries"][0]["view"] == VIEW_PATIENT_DETAIL


def test_the_export_schema_version_was_bumped():
    """The module says to bump it whenever the shape changes."""
    assert privacy.EXPORT_SCHEMA_VERSION != "1.0"


def test_the_data_inventory_counts_access_records():
    _grant()
    _act_as(PROVIDER_ID, "provider")
    client.get(f"/api/v1/provider/patients/{PATIENT_ID}")

    summary = privacy.build_data_summary(PATIENT_ID)
    category = next(
        c for c in summary["categories"] if c["key"] == "provider_access_log"
    )

    assert category["recordCount"] == 1


def test_deleting_an_account_removes_its_access_records():
    """Deletion means deletion — the purge proof is the deletion audit."""
    _grant()
    _act_as(PROVIDER_ID, "provider")
    client.get(f"/api/v1/provider/patients/{PATIENT_ID}")
    assert len(_records()) == 1

    counts = privacy.purge_user_data(PATIENT_ID)

    assert counts[ACCESS_LOG_COLLECTION] == 1
    assert _records() == []


def test_a_provider_closing_her_account_clears_her_rows_too():
    """Otherwise her name is left in other people's histories."""
    _grant()
    _act_as(PROVIDER_ID, "provider")
    client.get(f"/api/v1/provider/patients/{PATIENT_ID}")

    counts = privacy.purge_user_data(PROVIDER_ID)

    assert counts[ACCESS_LOG_COLLECTION] == 1
    assert _records() == []


def test_a_purge_leaves_other_patients_records_alone():
    _grant(PATIENT_ID)
    _grant(OTHER_PATIENT_ID)
    _act_as(PROVIDER_ID, "provider")
    client.get(f"/api/v1/provider/patients/{PATIENT_ID}")
    client.get(f"/api/v1/provider/patients/{OTHER_PATIENT_ID}")

    privacy.purge_user_data(PATIENT_ID)

    remaining = _records()
    assert len(remaining) == 1
    assert remaining[0]["patient_id"] == OTHER_PATIENT_ID
