"""Tests for the Symptom Pattern Analyzer feature.

Covers entry CRUD, frequency reports, severity trends,
co-occurrence analysis, trigger analysis, and authorization.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock
from datetime import date, timedelta
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Mocks ──────────────────────────────────────────────────────────────────
class MockGemini:
    def __getattr__(self, name):
        return self
    def configure(self, *args, **kwargs):
        pass
    def GenerativeModel(self, *args, **kwargs):
        class MockModel:
            def generate_content(self, *args, **kwargs):
                class R:
                    text = "mock"
                return R()
        return MockModel()

sys.modules["google.generativeai"] = MockGemini()
os.environ["JWT_SECRET"] = "test-secret"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GEMINI_API_KEY"] = "mock-key"

fa = sys.modules.get("firebase_admin")
if isinstance(fa, MagicMock) and hasattr(fa, "auth"):
    mock_fa = fa
else:
    mock_fa = MagicMock(_apps={})
    sys.modules["firebase_admin"] = mock_fa
mfa = getattr(mock_fa, "auth", None)
if not isinstance(mfa, MagicMock):
    mfa = MagicMock()
    mock_fa.auth = mfa
sys.modules["firebase_admin.auth"] = mfa
sys.modules["firebase_admin.credentials"] = MagicMock()
sys.modules["firebase_admin.firestore"] = MagicMock()

from main import app
from core.auth import get_current_user
import services.firestore_service as fs
from services.firestore_service import MockFirestoreClient

fs.db = MockFirestoreClient()
db = fs.db
client = TestClient(app)

UID = "test-symptom-user"


def _override():
    return {"id": UID, "username": "testuser"}


@pytest.fixture(autouse=True)
def deps():
    app.dependency_overrides[get_current_user] = _override
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def clean_db():
    db._collections = {}
    yield
    db._collections = {}


# ─── Helpers ────────────────────────────────────────────────────────────────

def _create(symptom="cramps", severity="moderate", d=None, triggers=None, mood_score=None):
    payload = {
        "symptom": symptom,
        "severity": severity,
        "date": (d or date.today()).isoformat(),
    }
    if triggers:
        payload["triggers"] = triggers
    if mood_score is not None:
        payload["mood_score"] = mood_score
    return client.post("/api/v1/symptom-journal/entries", json=payload)


# ─── Entry CRUD ──────────────────────────────────────────────────────────────


def test_create_entry():
    resp = _create()
    assert resp.status_code == 201
    data = resp.json()
    assert data["symptom"] == "cramps"
    assert data["severity"] == "moderate"


def test_create_with_mood():
    resp = _create(mood_score=3)
    assert resp.status_code == 201
    assert resp.json()["mood_score"] == 3


def test_create_with_triggers():
    resp = _create(triggers=["stress", "poor_sleep"])
    assert resp.status_code == 201
    assert "stress" in resp.json()["triggers"]


def test_create_invalid_symptom():
    resp = _create(symptom="unknown_pain")
    assert resp.status_code == 400


def test_create_invalid_severity():
    resp = _create(severity="extreme")
    assert resp.status_code == 400


def test_create_invalid_mood():
    resp = _create(mood_score=10)
    assert resp.status_code == 422


def test_create_invalid_date():
    payload = {"symptom": "cramps", "severity": "mild", "date": "nope"}
    resp = client.post("/api/v1/symptom-journal/entries", json=payload)
    assert resp.status_code == 422


def test_list_entries():
    _create(symptom="cramps")
    _create(symptom="headache")
    resp = client.get("/api/v1/symptom-journal/entries")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_filter_symptom():
    _create(symptom="cramps")
    _create(symptom="headache")
    resp = client.get("/api/v1/symptom-journal/entries?symptom=cramps")
    assert len(resp.json()) == 1


def test_list_filter_dates():
    today = date.today()
    yesterday = today - timedelta(days=1)
    _create(d=yesterday)
    _create(d=today)
    resp = client.get(f"/api/v1/symptom-journal/entries?start_date={yesterday.isoformat()}")
    assert len(resp.json()) == 2
    resp = client.get(f"/api/v1/symptom-journal/entries?start_date={today.isoformat()}")
    assert len(resp.json()) == 1


def test_get_entry():
    entry = _create().json()
    resp = client.get(f"/api/v1/symptom-journal/entries/{entry['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == entry["id"]


def test_get_entry_not_found():
    resp = client.get("/api/v1/symptom-journal/entries/nonexistent")
    assert resp.status_code == 404


def test_delete_entry():
    entry = _create().json()
    resp = client.delete(f"/api/v1/symptom-journal/entries/{entry['id']}")
    assert resp.status_code == 204


def test_delete_not_found():
    resp = client.delete("/api/v1/symptom-journal/entries/nonexistent")
    assert resp.status_code == 404


# ─── Reports ─────────────────────────────────────────────────────────────────


def test_frequency_report_empty():
    resp = client.get("/api/v1/symptom-journal/reports/frequency")
    assert resp.status_code == 200
    assert resp.json()["total_entries"] == 0


def test_frequency_report_with_data():
    _create(symptom="cramps")
    _create(symptom="cramps")
    _create(symptom="headache")
    resp = client.get("/api/v1/symptom-journal/reports/frequency")
    data = resp.json()
    assert data["total_entries"] == 2
    assert data["symptoms"][0]["symptom"] == "cramps"


def test_severity_trend():
    today = date.today()
    # Spread entries across weeks
    for i in range(14):
        d = today - timedelta(days=i * 2)
        _create(d=d)
    resp = client.get("/api/v1/symptom-journal/reports/severity-trend?symptom=cramps")
    assert resp.status_code == 200
    data = resp.json()
    assert data["symptom"] == "cramps"
    assert len(data["weekly_trend"]) >= 1


def test_co_occurrence_empty():
    resp = client.get("/api/v1/symptom-journal/reports/co-occurrence")
    assert resp.status_code == 200
    assert resp.json()["total_days_logged"] == 0


def test_co_occurrence_with_data():
    today = date.today()
    from services.symptom_journal_service import create_entry
    create_entry(UID, "cramps", "mild", today, triggers=["stress"])
    create_entry(UID, "headache", "moderate", today, triggers=["stress"])
    resp = client.get("/api/v1/symptom-journal/reports/co-occurrence")
    data = resp.json()
    assert data["total_days_logged"] == 1
    assert len(data["top_pairs"]) == 1
    assert data["top_pairs"][0]["co_occurring_days"] == 1


def test_trigger_analysis():
    today = date.today()
    from services.symptom_journal_service import create_entry
    create_entry(UID, "cramps", "mild", today, triggers=["stress", "caffeine"])
    create_entry(UID, "cramps", "moderate", today, triggers=["stress"])
    resp = client.get("/api/v1/symptom-journal/reports/triggers?symptom=cramps")
    data = resp.json()
    assert data["total_entries"] == 2
    assert any(t["trigger"] == "stress" for t in data["triggers"])
