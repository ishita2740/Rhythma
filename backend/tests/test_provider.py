"""Tests for the provider dashboard and data-sharing consents (issue #267).

These run against the in-memory mock Firestore that
``firestore_service.initialize_firebase()`` falls back to, seeded directly.
The authenticated identity is faked by overriding the ``get_current_user``
dependency, so each test can act as a patient or a provider without going
through the Firebase login mock.
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_auth import client  # noqa: E402

from main import app  # noqa: E402
from core.auth import get_current_user, get_password_hash  # noqa: E402
from services import firestore_service as fs  # noqa: E402
from services.provider_service import ConsentService  # noqa: E402
from services.rate_limit_service import RateLimitService  # noqa: E402

PATIENT_ID = "patient-123"
OTHER_PATIENT_ID = "other-patient-456"
PROVIDER_ID = "provider-789"

PROVIDER_EMAIL = "doctor@clinic.in"

_pw_hash = get_password_hash("SecurePass123")


def _identity(user_id: str, role: str, email: str, username: str) -> dict:
    return {
        "id": user_id,
        "role": role,
        "phone": "+911234567890",
        "username": username,
        "email": email,
    }


def _reset_collections():
    collections = getattr(fs.db, "_collections", None)
    if collections is not None:
        collections.clear()
    counters = getattr(fs.db, "_counters", None)
    if counters is not None:
        counters.clear()


def _seed_users():
    fs.db.collection("users").document(PATIENT_ID).set(
        {
            "phone": "+911234567890",
            "email": "asha@example.com",
            "username": "asha",
            "full_name": "Asha Rao",
            "age": 28,
            "city": "Pune",
            "state": "Maharashtra",
            "cycle_length": 29,
            "role": "patient",
            "password": _pw_hash,
        }
    )
    fs.db.collection("users").document(OTHER_PATIENT_ID).set(
        {
            "phone": "+919876543210",
            "email": "priya@example.com",
            "username": "priya",
            "full_name": "Priya Nair",
            "role": "patient",
            "password": _pw_hash,
        }
    )
    fs.db.collection("users").document(PROVIDER_ID).set(
        {
            "phone": "+918123456780",
            "email": PROVIDER_EMAIL,
            "username": "doctor_sharma",
            "full_name": "Dr. Sharma",
            "specialty": "Gynecology",
            "role": "provider",
            "password": _pw_hash,
        }
    )


def _seed_cycle_logs():
    for index, day in enumerate((1, 29, 57)):
        fs.db.collection("cycle_logs").document(f"log-{index}").set(
            {
                "user_id": PATIENT_ID,
                "start_date": datetime(2026, 3, 1, tzinfo=timezone.utc)
                + timedelta(days=day),
                "end_date": datetime(2026, 3, 5, tzinfo=timezone.utc)
                + timedelta(days=day),
                "flow_intensity": "medium",
                "symptoms": ["cramps"],
                "sleep_hours": 7.5,
                "notes": "mild cramps",
            }
        )


@pytest.fixture(autouse=True)
def _clean_state():
    def _reset():
        client.cookies.clear()
        app.dependency_overrides.clear()
        RateLimitService.clear_all()
        _reset_collections()
        _seed_users()
        _seed_cycle_logs()

    _reset()
    yield
    client.cookies.clear()
    app.dependency_overrides.clear()
    _reset_collections()


def _act_as(identity: dict):
    app.dependency_overrides[get_current_user] = lambda: identity


# ─── Provider account ────────────────────────────────────────────────────


def test_register_provider_creates_provider_account():
    response = client.post(
        "/api/v1/provider/register",
        json={
            "email": "new-doctor@clinic.in",
            "password": "SecurePass123",
            "full_name": "Dr. Mehta",
            "specialty": "Gynecology",
            "license_number": "MH-12345",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "provider"
    created = fs.db.collection("users").document(body["id"]).get()
    assert created.to_dict()["role"] == "provider"
    assert created.to_dict()["specialty"] == "Gynecology"


def test_register_provider_rejects_duplicate_email():
    response = client.post(
        "/api/v1/provider/register",
        json={"email": PROVIDER_EMAIL, "password": "SecurePass123"},
    )
    assert response.status_code == 409


def test_provider_login_success():
    response = client.post(
        "/api/v1/provider/login",
        json={"email": PROVIDER_EMAIL, "password": "SecurePass123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "provider"
    assert "access_token" in body


def test_provider_login_rejects_patient_account():
    response = client.post(
        "/api/v1/provider/login",
        json={"email": "asha@example.com", "password": "SecurePass123"},
    )
    assert response.status_code == 403


def test_provider_login_rejects_wrong_password():
    response = client.post(
        "/api/v1/provider/login",
        json={"email": PROVIDER_EMAIL, "password": "wrong-password"},
    )
    assert response.status_code == 401


# ─── Consent (patient side) ──────────────────────────────────────────────


def test_patient_can_grant_consent():
    _act_as(_identity(PATIENT_ID, "patient", "asha@example.com", "asha"))
    response = client.post(
        "/api/v1/provider/consents", json={"provider_email": PROVIDER_EMAIL}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "active"
    assert body["provider_email"] == PROVIDER_EMAIL

    consent = fs.db.collection("consents").document(body["id"]).get()
    assert consent.to_dict()["provider_id"] == PROVIDER_ID


def test_provider_account_cannot_grant_consent():
    _act_as(_identity(PROVIDER_ID, "provider", PROVIDER_EMAIL, "doctor_sharma"))
    response = client.post(
        "/api/v1/provider/consents", json={"provider_email": PROVIDER_EMAIL}
    )
    assert response.status_code == 403


def test_grant_consent_unknown_provider_returns_404():
    _act_as(_identity(PATIENT_ID, "patient", "asha@example.com", "asha"))
    response = client.post(
        "/api/v1/provider/consents", json={"provider_email": "nobody@nowhere.in"}
    )
    assert response.status_code == 404


def test_patient_lists_their_consents():
    ConsentService.grant(PATIENT_ID, PROVIDER_EMAIL)
    _act_as(_identity(PATIENT_ID, "patient", "asha@example.com", "asha"))
    response = client.get("/api/v1/provider/consents")
    assert response.status_code == 200
    consents = response.json()["consents"]
    assert len(consents) == 1
    assert consents[0]["provider_id"] == PROVIDER_ID


def test_patient_can_revoke_consent():
    consent = ConsentService.grant(PATIENT_ID, PROVIDER_EMAIL)
    _act_as(_identity(PATIENT_ID, "patient", "asha@example.com", "asha"))
    response = client.delete(f"/api/v1/provider/consents/{consent['id']}")
    assert response.status_code == 200
    assert response.json()["status"] == "revoked"


def test_patient_cannot_revoke_another_patients_consent():
    consent = ConsentService.grant(PATIENT_ID, PROVIDER_EMAIL)
    _act_as(_identity(OTHER_PATIENT_ID, "patient", "priya@example.com", "priya"))
    response = client.delete(f"/api/v1/provider/consents/{consent['id']}")
    assert response.status_code == 404


# ─── Provider view ───────────────────────────────────────────────────────


def test_provider_sees_only_consented_patients():
    ConsentService.grant(PATIENT_ID, PROVIDER_EMAIL)
    _act_as(_identity(PROVIDER_ID, "provider", PROVIDER_EMAIL, "doctor_sharma"))
    response = client.get("/api/v1/provider/patients")
    assert response.status_code == 200
    patients = response.json()["patients"]
    assert [p["patient_id"] for p in patients] == [PATIENT_ID]
    assert patients[0]["loggedCycleCount"] == 3


def test_provider_sees_no_patients_without_any_consent():
    _act_as(_identity(PROVIDER_ID, "provider", PROVIDER_EMAIL, "doctor_sharma"))
    response = client.get("/api/v1/provider/patients")
    assert response.status_code == 200
    assert response.json()["patients"] == []


def test_patient_cannot_use_provider_patients_endpoint():
    _act_as(_identity(PATIENT_ID, "patient", "asha@example.com", "asha"))
    response = client.get("/api/v1/provider/patients")
    assert response.status_code == 403


def test_provider_patient_detail_requires_consent():
    _act_as(_identity(PROVIDER_ID, "provider", PROVIDER_EMAIL, "doctor_sharma"))
    response = client.get(f"/api/v1/provider/patients/{PATIENT_ID}")
    assert response.status_code == 403


def test_provider_patient_detail_returns_shared_data_only():
    ConsentService.grant(PATIENT_ID, PROVIDER_EMAIL)
    _act_as(_identity(PROVIDER_ID, "provider", PROVIDER_EMAIL, "doctor_sharma"))
    response = client.get(f"/api/v1/provider/patients/{PATIENT_ID}")
    assert response.status_code == 200
    body = response.json()

    assert body["patient"]["name"] == "Asha Rao"
    assert body["patient"]["age"] == 28
    assert len(body["cycleLogs"]) == 3
    assert body["summary"]["loggedCycleCount"] == 3
    assert body["summary"]["hasEnoughDataForInsights"] is True

    # Consent gates out identity/contact fields a patient was not asked about.
    assert "phone" not in body["patient"]
    assert "email" not in body["patient"]
    assert "password" not in json.dumps(body)


def test_revoked_consent_blocks_provider_access():
    ConsentService.grant(PATIENT_ID, PROVIDER_EMAIL)
    ConsentService.revoke(PATIENT_ID, f"{PATIENT_ID}::{PROVIDER_ID}")
    _act_as(_identity(PROVIDER_ID, "provider", PROVIDER_EMAIL, "doctor_sharma"))
    response = client.get(f"/api/v1/provider/patients/{PATIENT_ID}")
    assert response.status_code == 403
    assert client.get("/api/v1/provider/patients").json()["patients"] == []


# ─── Privacy integration ─────────────────────────────────────────────────


def test_purge_removes_consents_regardless_of_side():
    from services.data_privacy_service import purge_user_data

    ConsentService.grant(PATIENT_ID, PROVIDER_EMAIL)
    ConsentService.grant(OTHER_PATIENT_ID, PROVIDER_EMAIL)

    # Purging a patient removes her own consents but leaves the provider's
    # relationship with the other patient intact.
    counts = purge_user_data(PATIENT_ID)
    assert counts["consents"] == 1

    # Purging the provider removes every consent where they were the
    # provider side.
    counts = purge_user_data(PROVIDER_ID)
    assert counts["consents"] == 1


def test_summary_reports_consents():
    from services.data_privacy_service import build_data_summary

    ConsentService.grant(PATIENT_ID, PROVIDER_EMAIL)
    summary = build_data_summary(PATIENT_ID)
    by_key = {c["key"]: c for c in summary["categories"]}
    assert by_key["consents"]["recordCount"] == 1
    assert "provider_email" in by_key["consents"]["storedFields"]
