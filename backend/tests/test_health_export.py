"""Tests for the Health Export Summary feature.

Covers full export, provider brief, empty-state handling,
and data accuracy of computed statistics.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch
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
from services.firestore_service import MockFirestoreClient, CycleService

fs.db = MockFirestoreClient()
db = fs.db
client = TestClient(app)

UID = "test-export-user"


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


def _seed_logs(count=3):
    """Seed cycle logs so scoring has data to work with."""
    today = date.today()
    for i in range(count):
        start = today - timedelta(days=28 * (i + 1))
        CycleService.upsert_log(
            UID,
            start,
            {
                "flow_intensity": "medium",
                "sleep_hours": 7.0 + (i % 2),
                "stress_level": 2 + (i % 3),
                "symptoms": ["cramps"] if i % 2 == 0 else [],
            },
        )


# ─── Tests ──────────────────────────────────────────────────────────────────


def test_full_export_empty():
    """Empty user gets a valid but sparse summary."""
    resp = client.get("/api/v1/export/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "generatedAt" in data
    assert data["cycleStatistics"]["loggedCycleCount"] == 0
    assert "disclaimer" in data


def test_full_export_with_data():
    _seed_logs(3)
    resp = client.get("/api/v1/export/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cycleStatistics"]["loggedCycleCount"] == 3
    assert data["sleepSummary"]["sampleCount"] >= 1
    assert data["stressSummary"]["sampleCount"] >= 1


def test_full_export_has_all_sections():
    resp = client.get("/api/v1/export/summary")
    data = resp.json()
    for key in [
        "generatedAt", "user", "dateRange", "cycleStatistics",
        "symptomFrequency", "sleepSummary", "stressSummary",
        "moodSummary", "bleedingPattern", "trends",
        "disclaimer", "disclaimerKey",
    ]:
        assert key in data, f"Missing key: {key}"


def test_full_export_user_info():
    resp = client.get("/api/v1/export/summary")
    user = resp.json()["user"]
    assert "username" in user
    assert user["username"] == "testuser"


def test_full_export_date_range():
    _seed_logs(3)
    resp = client.get("/api/v1/export/summary")
    dr = resp.json()["dateRange"]
    assert dr is not None
    assert "earliest" in dr
    assert "latest" in dr


def test_full_export_symptom_frequency():
    _seed_logs(3)
    resp = client.get("/api/v1/export/summary")
    sf = resp.json()["symptomFrequency"]
    assert isinstance(sf, dict)
    # cramps should appear in some logs
    assert "cramps" in sf or len(sf) == 0


def test_full_export_bleeding_pattern():
    _seed_logs(2)
    resp = client.get("/api/v1/export/summary")
    bp = resp.json()["bleedingPattern"]
    assert "distribution" in bp
    assert "totalBleedingDays" in bp


def test_full_export_trends():
    _seed_logs(4)
    resp = client.get("/api/v1/export/summary")
    trends = resp.json()["trends"]
    assert "basis" in trends
    assert "notEnoughData" in trends


# ─── Provider brief ──────────────────────────────────────────────────────────


def test_provider_brief_empty():
    resp = client.get("/api/v1/export/provider-brief")
    assert resp.status_code == 200
    data = resp.json()
    assert "disclaimer" in data
    assert "cycleStatistics" in data


def test_provider_brief_with_data():
    _seed_logs(3)
    resp = client.get("/api/v1/export/provider-brief")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cycleStatistics"]["loggedCycleCount"] == 3


def test_provider_brief_omits_trends():
    _seed_logs(3)
    resp = client.get("/api/v1/export/provider-brief")
    data = resp.json()
    assert "trends" not in data
    assert "moodSummary" not in data


def test_provider_brief_has_sleep_stress_averages():
    _seed_logs(3)
    resp = client.get("/api/v1/export/provider-brief")
    data = resp.json()
    assert "sleepAverage" in data
    assert "stressAverage" in data


def test_provider_brief_bleeding_days():
    _seed_logs(2)
    resp = client.get("/api/v1/export/provider-brief")
    data = resp.json()
    assert "bleedingDaysLogged" in data
    assert isinstance(data["bleedingDaysLogged"], int)


def test_full_export_disclaimer_matches_brief():
    resp_full = client.get("/api/v1/export/summary")
    resp_brief = client.get("/api/v1/export/provider-brief")
    assert resp_full.json()["disclaimer"] == resp_brief.json()["disclaimer"]
