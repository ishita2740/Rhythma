"""Tests for the Cycle Comparison feature.

Covers custom date-range comparison, auto recent-vs-prior,
validation, empty states, and data accuracy.
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
from services.firestore_service import MockFirestoreClient, CycleService

fs.db = MockFirestoreClient()
db = fs.db
client = TestClient(app)

UID = "test-compare-user"


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


def _seed(start: date, count: int, sleep_base: float = 7.0):
    """Create cycle logs starting from `start`, spaced 28 days apart."""
    for i in range(count):
        day = start + timedelta(days=28 * i)
        CycleService.upsert_log(UID, day, {
            "flow_intensity": "medium",
            "sleep_hours": sleep_base + (i % 2),
            "stress_level": 2 + (i % 3),
            "symptoms": ["cramps"] if i % 2 == 0 else [],
        })


# ─── Custom comparison ───────────────────────────────────────────────────────


def test_compare_custom_basic():
    today = date.today()
    a_start = today - timedelta(days=180)
    a_end = today - timedelta(days=91)
    b_start = today - timedelta(days=90)
    b_end = today

    resp = client.post("/api/v1/cycle/compare", json={
        "period_a_start": a_start.isoformat(),
        "period_a_end": a_end.isoformat(),
        "period_b_start": b_start.isoformat(),
        "period_b_end": b_end.isoformat(),
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "periodA" in data
    assert "periodB" in data
    assert "comparisons" in data
    assert "symptomComparisons" in data
    assert "disclaimer" in data


def test_compare_custom_with_data():
    today = date.today()
    # Seed data in period B
    _seed(today - timedelta(days=60), 2)
    b_start = today - timedelta(days=90)
    b_end = today
    a_start = today - timedelta(days=180)
    a_end = today - timedelta(days=91)

    resp = client.post("/api/v1/cycle/compare", json={
        "period_a_start": a_start.isoformat(),
        "period_a_end": a_end.isoformat(),
        "period_b_start": b_start.isoformat(),
        "period_b_end": b_end.isoformat(),
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["periodB"]["stats"]["logCount"] == 2
    assert data["periodA"]["stats"]["logCount"] == 0


def test_compare_custom_invalid_date():
    resp = client.post("/api/v1/cycle/compare", json={
        "period_a_start": "not-a-date",
        "period_a_end": "2026-01-01",
        "period_b_start": "2026-01-02",
        "period_b_end": "2026-02-01",
    })
    assert resp.status_code == 422


def test_compare_custom_start_after_end():
    today = date.today()
    resp = client.post("/api/v1/cycle/compare", json={
        "period_a_start": today.isoformat(),
        "period_a_end": (today - timedelta(days=10)).isoformat(),
        "period_b_start": (today + timedelta(days=1)).isoformat(),
        "period_b_end": (today + timedelta(days=30)).isoformat(),
    })
    assert resp.status_code == 400


def test_compare_custom_overlapping():
    today = date.today()
    resp = client.post("/api/v1/cycle/compare", json={
        "period_a_start": (today - timedelta(days=90)).isoformat(),
        "period_a_end": today.isoformat(),
        "period_b_start": (today - timedelta(days=30)).isoformat(),
        "period_b_end": (today + timedelta(days=30)).isoformat(),
    })
    assert resp.status_code == 400


# ─── Auto recent vs prior ───────────────────────────────────────────────────


def test_auto_compare_basic():
    resp = client.get("/api/v1/cycle/compare/recent")
    assert resp.status_code == 200
    data = resp.json()
    assert "periodA" in data
    assert "periodB" in data


def test_auto_compare_custom_window():
    resp = client.get("/api/v1/cycle/compare/recent?window_days=90")
    assert resp.status_code == 200


def test_auto_compare_window_too_small():
    resp = client.get("/api/v1/cycle/compare/recent?window_days=5")
    assert resp.status_code == 400


def test_auto_compare_window_too_large():
    resp = client.get("/api/v1/cycle/compare/recent?window_days=400")
    assert resp.status_code == 400


# ─── Comparison structure ────────────────────────────────────────────────────


def test_comparisons_contain_direction():
    today = date.today()
    _seed(today - timedelta(days=60), 2, sleep_base=6.0)
    _seed(today - timedelta(days=180), 2, sleep_base=8.0)

    resp = client.post("/api/v1/cycle/compare", json={
        "period_a_start": (today - timedelta(days=200)).isoformat(),
        "period_a_end": (today - timedelta(days=100)).isoformat(),
        "period_b_start": (today - timedelta(days=90)).isoformat(),
        "period_b_end": today.isoformat(),
    })
    data = resp.json()
    for comp in data["comparisons"]:
        assert comp["direction"] in ("increased", "decreased", "unchanged", "unknown")
        assert "label" in comp


def test_symptom_comparisons_present():
    today = date.today()
    _seed(today - timedelta(days=60), 2)
    resp = client.post("/api/v1/cycle/compare", json={
        "period_a_start": (today - timedelta(days=180)).isoformat(),
        "period_a_end": (today - timedelta(days=91)).isoformat(),
        "period_b_start": (today - timedelta(days=90)).isoformat(),
        "period_b_end": today.isoformat(),
    })
    data = resp.json()
    assert isinstance(data["symptomComparisons"], list)
