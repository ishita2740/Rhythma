"""Tests for the Cycle Phase Wellness Advisor feature.

Covers all-recommendations, single-category, phases-overview,
phase detection integration, and error handling.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from datetime import date
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

UID = "test-phase-user"


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


# ─── Tests ──────────────────────────────────────────────────────────────────


def test_get_all_recommendations():
    """User with no logs gets 'unknown' phase recommendations."""
    resp = client.get("/api/v1/phase-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert data["phase"] == "unknown"
    assert "sleep" in data["categories"]
    assert "nutrition" in data["categories"]
    assert "exercise" in data["categories"]
    assert "self_care" in data["categories"]
    assert len(data["categories"]["sleep"]) >= 1
    assert "disclaimer" in data


def test_get_all_recommendations_has_keys():
    resp = client.get("/api/v1/phase-recommendations")
    data = resp.json()
    for cat_recs in data["categories"].values():
        for rec in cat_recs:
            assert "title" in rec
            assert "body" in rec
            assert "tipKey" in rec


def test_get_category_recommendations():
    resp = client.get("/api/v1/phase-recommendations/sleep")
    assert resp.status_code == 200
    data = resp.json()
    assert data["category"] == "sleep"
    assert data["phase"] == "unknown"
    assert len(data["recommendations"]) >= 1


def test_get_category_nutrition():
    resp = client.get("/api/v1/phase-recommendations/nutrition")
    assert resp.status_code == 200
    assert resp.json()["category"] == "nutrition"


def test_get_category_exercise():
    resp = client.get("/api/v1/phase-recommendations/exercise")
    assert resp.status_code == 200
    assert resp.json()["category"] == "exercise"


def test_get_category_self_care():
    resp = client.get("/api/v1/phase-recommendations/self_care")
    assert resp.status_code == 200
    assert resp.json()["category"] == "self_care"


def test_get_category_invalid():
    resp = client.get("/api/v1/phase-recommendations/invalid_cat")
    assert resp.status_code == 400
    assert "Unknown category" in resp.json()["detail"]


def test_phases_overview():
    resp = client.get("/api/v1/phase-recommendations/phases/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "period" in data["phases"]
    assert "follicular" in data["phases"]
    assert "ovulation" in data["phases"]
    assert "luteal" in data["phases"]
    assert "late" in data["phases"]
    assert "unknown" in data["phases"]
    assert len(data["phaseOrder"]) == 6


def test_phases_overview_categories():
    resp = client.get("/api/v1/phase-recommendations/phases/overview")
    data = resp.json()
    for phase_name, cats in data["phases"].items():
        assert "sleep" in cats
        assert "nutrition" in cats
        assert "exercise" in cats
        assert "self_care" in cats


def test_period_phase_recommendations():
    """Verify period phase has specific recommendations."""
    from services.prediction_service import PHASE_PERIOD
    from services import phase_recommendations_service as svc

    with patch.object(svc, "_get_user_phase", return_value=PHASE_PERIOD):
        resp = client.get("/api/v1/phase-recommendations/sleep")
        data = resp.json()
        assert data["phase"] == "period"
        # Period phase should have warm routine recommendation
        tip_keys = [r["tipKey"] for r in data["recommendations"]]
        assert any("warm_routine" in k or "rest" in k for k in tip_keys)


def test_follicular_phase_recommendations():
    from services.prediction_service import PHASE_FOLLICULAR
    from services import phase_recommendations_service as svc

    with patch.object(svc, "_get_user_phase", return_value=PHASE_FOLLICULAR):
        resp = client.get("/api/v1/phase-recommendations/exercise")
        data = resp.json()
        assert data["phase"] == "follicular"
        tip_keys = [r["tipKey"] for r in data["recommendations"]]
        assert any("high_intensity" in k for k in tip_keys)


def test_luteal_phase_recommendations():
    from services.prediction_service import PHASE_LUTEAL
    from services import phase_recommendations_service as svc

    with patch.object(svc, "_get_user_phase", return_value=PHASE_LUTEAL):
        resp = client.get("/api/v1/phase-recommendations")
        data = resp.json()
        assert data["phase"] == "luteal"
        # Luteal nutrition should mention carbohydrates
        nutri_keys = [r["tipKey"] for r in data["categories"]["nutrition"]]
        assert any("carbs" in k for k in nutri_keys)


def test_recommendations_not_empty_for_each_phase():
    """Every phase should have at least one recommendation per category."""
    from services import phase_recommendations_service as svc

    for phase in ["period", "follicular", "ovulation", "luteal", "late", "unknown"]:
        with patch.object(svc, "_get_user_phase", return_value=phase):
            resp = client.get("/api/v1/phase-recommendations")
            data = resp.json()
            for cat in ["sleep", "nutrition", "exercise", "self_care"]:
                assert len(data["categories"][cat]) >= 1, f"No {cat} recs for {phase}"
