"""The dashboard's prediction schema is the one that was written (issue #381).

``api/dashboard.py`` declared ``DashboardPrediction`` twice, ~40 lines
apart. Python kept the second, so the first — the one with typed
``predictedRange`` / ``fertileWindow`` sub-models and non-null
``confidence`` / ``estimateSource`` defaults — was dead code that never
reached ``DashboardResponse``. Nothing failed. The tests passed, the
route worked, and the only visible symptom was in the published OpenAPI
schema, where two nested objects appeared as untyped dicts.

That is the class of bug this file is aimed at: a change that is
invisible at runtime and only wrong in the contract. So most of the
assertions below read the **served** schema — ``app.openapi()`` — rather
than the class object. Asserting on the class would have passed happily
against the duplicate too, since whichever declaration wins is the one
imported.

``DashboardPredictionRange`` and ``DashboardFertileWindow`` were both
defined and, because of the duplicate, referenced by nothing reachable.
Several tests below exist specifically to keep them wired in.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

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
from api import dashboard as dashboard_module  # noqa: E402
from api.dashboard import (  # noqa: E402
    DashboardFertileWindow,
    DashboardPrediction,
    DashboardPredictionRange,
    DashboardResponse,
)


@pytest.fixture(scope="module")
def schema():
    """The served OpenAPI document."""
    return app.openapi()


@pytest.fixture(scope="module")
def components(schema):
    return schema["components"]["schemas"]


def _resolve(components, node):
    """Follow a ``$ref``, or an ``anyOf`` containing one, to its schema.

    Pydantic emits ``{"$ref": ...}`` for a required sub-model and
    ``{"anyOf": [{"$ref": ...}, {"type": "null"}]}`` for an optional one.
    Callers care which model is referenced, not which of the two shapes
    pydantic chose.
    """
    if "$ref" in node:
        return components[node["$ref"].rsplit("/", 1)[-1]]
    for branch in node.get("anyOf", []):
        if "$ref" in branch:
            return components[branch["$ref"].rsplit("/", 1)[-1]]
    return None


def _ref_name(node):
    if "$ref" in node:
        return node["$ref"].rsplit("/", 1)[-1]
    for branch in node.get("anyOf", []):
        if "$ref" in branch:
            return branch["$ref"].rsplit("/", 1)[-1]
    return None


# ─── The duplicate itself ─────────────────────────────────────────────────


def test_dashboard_declares_dashboard_prediction_exactly_once():
    """The direct regression test.

    A second ``class DashboardPrediction`` anywhere in the module is the
    bug, whatever it happens to contain — Python will keep one of them
    and discard the other in silence.
    """
    source = open(dashboard_module.__file__, encoding="utf-8").read()
    assert source.count("class DashboardPrediction(BaseModel)") == 1


def test_no_model_in_the_module_is_declared_twice():
    """The same mistake, generalised to every model in the file."""
    import re

    source = open(dashboard_module.__file__, encoding="utf-8").read()
    names = re.findall(r"^class (\w+)\(BaseModel\)", source, flags=re.MULTILINE)
    duplicates = {name for name in names if names.count(name) > 1}
    assert duplicates == set()


def test_dashboard_module_imports_nothing_it_does_not_use():
    """``UserService`` was imported here and never referenced."""
    source = open(dashboard_module.__file__, encoding="utf-8").read()
    assert "from services.firestore_service import UserService" not in source


# ─── The served schema ────────────────────────────────────────────────────


def test_prediction_is_a_typed_object_on_the_response(components):
    assert _ref_name(DashboardResponse.model_json_schema()["properties"]["prediction"])


def test_predicted_range_is_a_typed_model_not_a_free_dict(components):
    """It shipped as an untyped object; a generated client got a raw map."""
    node = components["DashboardPrediction"]["properties"]["predictedRange"]
    assert _ref_name(node) == "DashboardPredictionRange"

    resolved = _resolve(components, node)
    assert set(resolved["properties"]) == {"earliest", "latest"}


def test_fertile_window_is_a_typed_model_not_a_free_dict(components):
    node = components["DashboardPrediction"]["properties"]["fertileWindow"]
    assert _ref_name(node) == "DashboardFertileWindow"

    resolved = _resolve(components, node)
    assert set(resolved["properties"]) == {
        "start",
        "end",
        "isEstimate",
        "notForContraception",
    }


def test_the_contraception_warning_is_in_the_published_schema(components):
    """The flag that says this window is not contraceptive guidance.

    With ``fertileWindow`` typed as ``Dict[str, Any]`` this had no schema
    presence at all, so a client generated from ``/docs`` had no field to
    read and nothing would have noticed if the service stopped emitting
    it. It is a safety flag on a health app; it belongs in the contract.
    """
    resolved = _resolve(
        components, components["DashboardPrediction"]["properties"]["fertileWindow"]
    )
    assert resolved["properties"]["notForContraception"]["default"] is True
    assert resolved["properties"]["isEstimate"]["default"] is True


def test_both_nested_models_are_published(components):
    """Neither may be orphaned again.

    Both were defined and — because the surviving declaration referenced
    neither — reachable from nothing. An unreferenced pydantic model does
    not appear in the OpenAPI components at all.
    """
    assert "DashboardPredictionRange" in components
    assert "DashboardFertileWindow" in components


def test_days_until_next_period_keeps_its_documented_meaning(components):
    """The "not clamped" note lived only on the discarded declaration.

    It is the field's whole point: ``cycle.nextPeriodDays`` is clamped at
    zero for older clients, and this one is the honest signed value. A
    client cannot tell them apart without the description.
    """
    node = components["DashboardPrediction"]["properties"]["daysUntilNextPeriod"]
    assert "not clamped" in node.get("description", "").lower()


# ─── Defaults ─────────────────────────────────────────────────────────────


def test_confidence_defaults_to_the_most_conservative_value():
    """It became ``None`` when the duplicate won.

    A client deciding how firmly to present a predicted date reads this.
    Handing it a null means "work it out yourself"; ``"low"`` is the
    answer the author actually chose.
    """
    assert DashboardPrediction().confidence == "low"


def test_estimate_source_defaults_to_the_population_default():
    assert DashboardPrediction().estimateSource == "population_default"


def test_nested_defaults_are_real_objects_not_empty_dicts():
    prediction = DashboardPrediction()
    assert isinstance(prediction.predictedRange, DashboardPredictionRange)
    assert isinstance(prediction.fertileWindow, DashboardFertileWindow)
    assert prediction.fertileWindow.notForContraception is True
    assert prediction.fertileWindow.isEstimate is True


def test_a_default_prediction_still_serialises_every_field():
    dumped = DashboardPrediction().model_dump()
    assert dumped["predictedRange"] == {"earliest": None, "latest": None}
    assert dumped["fertileWindow"] == {
        "start": None,
        "end": None,
        "isEstimate": True,
        "notForContraception": True,
    }


# ─── Round-tripping what the service actually emits ───────────────────────


def _service_shaped_summary():
    """The exact shape ``prediction_service.dashboard_summary`` returns."""
    return {
        "nextPeriodDate": "2026-09-01",
        "daysUntilNextPeriod": -3,
        "isOverdue": True,
        "daysOverdue": 3,
        "phase": "late",
        "confidence": "medium",
        "estimateSource": "logged_history",
        "predictedRange": {"earliest": "2026-08-29", "latest": "2026-09-04"},
        "fertileWindow": {
            "start": "2026-08-15",
            "end": "2026-08-20",
            "isEstimate": True,
            "notForContraception": True,
        },
    }


def test_the_service_payload_validates_against_the_model():
    """The typed model must accept what the service already produces.

    Tightening a schema is only safe if the producer already satisfies
    it; this is the assertion that says so rather than assuming it.
    """
    prediction = DashboardPrediction(**_service_shaped_summary())

    assert prediction.predictedRange.earliest == "2026-08-29"
    assert prediction.fertileWindow.end == "2026-08-20"
    assert prediction.daysUntilNextPeriod == -3
    assert prediction.isOverdue is True


def test_a_signed_days_until_survives_serialisation():
    """Negative means late, and must not be clamped anywhere in the path."""
    prediction = DashboardPrediction(**_service_shaped_summary())
    assert prediction.model_dump()["daysUntilNextPeriod"] == -3


def test_a_new_user_with_no_anchor_date_still_validates():
    """No logged period means no dates — not a validation error."""
    prediction = DashboardPrediction(
        nextPeriodDate=None,
        daysUntilNextPeriod=None,
        phase="unknown",
        confidence="low",
        estimateSource="population_default",
        predictedRange={"earliest": None, "latest": None},
        fertileWindow={
            "start": None,
            "end": None,
            "isEstimate": True,
            "notForContraception": True,
        },
    )
    assert prediction.nextPeriodDate is None
    assert prediction.isOverdue is False
    assert prediction.daysOverdue == 0


def test_prediction_is_still_nullable_on_the_response():
    """Additive and optional, so pre-existing clients keep working."""
    node = DashboardResponse.model_json_schema()["properties"]["prediction"]
    assert any(branch.get("type") == "null" for branch in node.get("anyOf", []))


def test_the_model_matches_the_service_key_for_key():
    """The two must not drift.

    ``DashboardPrediction`` documents itself as mirroring
    ``dashboard_summary``. Comparing the key sets is what makes that
    claim checkable — a field added to one and forgotten in the other
    fails here rather than silently vanishing from the response.
    """
    from datetime import date as date_type

    from services.prediction_service import dashboard_summary, predict

    emitted = dashboard_summary(predict([], profile={}, today=date_type(2026, 8, 6)))

    assert set(emitted) == set(DashboardPrediction.model_fields)
    assert set(emitted["predictedRange"]) == set(
        DashboardPredictionRange.model_fields
    )
    assert set(emitted["fertileWindow"]) == set(DashboardFertileWindow.model_fields)
