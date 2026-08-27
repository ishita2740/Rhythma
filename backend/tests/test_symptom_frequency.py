"""Symptom percentages on /dashboard (issue #537).

Two defects, both pushing the same way — they made the few symptoms the
Insights card drew look more dominant than the user's record supports.

**The denominator was the wrong set.** ``api/dashboard.py`` divided by
``len(logs_with_symptoms)``, the days that already carried a symptom, so a
logged day with no symptom was removed from the sample before the division
and could not pull any percentage down. Two cramp days out of ten logged
days reported 67%. The overstatement is ``len(logs) / len(logs_with_symptoms)``
and it grows the *more* diligently a user logs.

**The vocabulary was four fixed strings** while ``core/cycle_validation``
accepts nine chips and is explicit that the list is open-ended. ``fatigue``,
``nausea``, ``back pain``, ``severe pain`` and ``fainting`` were accepted at
the door and then never counted.

Most of what follows tests ``compute_symptom_frequency`` directly rather
than through the endpoint: it is arithmetic with a right answer, and the
numbers are the thing that was wrong. The endpoint tests at the bottom
check the wiring and the response schema.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from unittest.mock import patch  # noqa: E402

from test_auth import client, mock_auth_dependencies  # noqa: F401,E402

import firebase_admin.auth  # noqa: E402
from core.cycle_validation import KNOWN_SYMPTOMS  # noqa: E402
from services.scoring_service import compute_symptom_frequency  # noqa: E402


def _log(day: int, symptoms=None):
    """One log, dated so the list stays newest-first and plausibly spaced."""
    entry = {"start_date": f"2026-08-{day:02d}"}
    if symptoms is not None:
        entry["symptoms"] = symptoms
    return entry


# ─── The denominator ─────────────────────────────────────────────────────


def test_fraction_is_over_every_logged_day_not_only_symptom_days():
    """The reproduction from the issue: two cramp days in ten.

    The old expression returned 0.67 here, because seven of the ten logs
    were dropped from the sample before dividing.
    """
    logs = [
        _log(20, ["cramps"]),
        _log(19, []),
        _log(18, None),
        _log(17, ["cramps", "nausea"]),
        _log(16, []),
        _log(15, []),
        _log(14, []),
        _log(13, []),
        _log(12, []),
        _log(11, ["nausea", "fatigue"]),
    ]

    result = compute_symptom_frequency(logs)

    assert result["sample_size"] == 10
    assert result["frequencies"]["cramps"] == 0.2
    assert result["frequencies"]["cramps"] != 0.67


def test_a_symptom_free_logged_day_lowers_the_percentage():
    """The property the old denominator made impossible.

    Logging more days without cramps has to move the cramps figure down.
    Under the old code both of these returned 1.0.
    """
    one_of_one = compute_symptom_frequency([_log(20, ["cramps"])])
    one_of_four = compute_symptom_frequency(
        [_log(20, ["cramps"]), _log(19, []), _log(18, []), _log(17, [])]
    )

    assert one_of_one["frequencies"]["cramps"] == 1.0
    assert one_of_four["frequencies"]["cramps"] == 0.25


def test_single_symptom_entry_no_longer_reports_everything_at_100_percent():
    """The degenerate case, and the common one.

    A user who has logged symptoms exactly once saw every symptom in that
    entry at 100% regardless of how much else she had logged.
    """
    logs = [_log(20, ["cramps", "headache"])] + [_log(19 - n, []) for n in range(9)]

    result = compute_symptom_frequency(logs)

    assert result["sample_size"] == 10
    assert result["frequencies"]["cramps"] == 0.1
    assert result["frequencies"]["headache"] == 0.1


def test_no_fraction_can_exceed_one():
    """A symptom listed twice on one day is still one day with it."""
    result = compute_symptom_frequency(
        [_log(20, ["cramps", "cramps", "Cramps"]), _log(19, [])]
    )

    assert result["frequencies"]["cramps"] == 0.5


# ─── The vocabulary ──────────────────────────────────────────────────────


def test_every_chip_cycle_validation_accepts_is_reported():
    """Five of the nine chips were previously uncountable.

    ``fatigue``, ``nausea``, ``back pain``, ``severe pain`` and ``fainting``
    are offered by both clients and accepted by ``normalize_symptoms``, and
    none of them appeared in the response.
    """
    logs = [_log(20, ["fatigue", "nausea", "back pain", "severe pain", "fainting"])]

    frequencies = compute_symptom_frequency(logs)["frequencies"]

    for symptom in KNOWN_SYMPTOMS:
        assert symptom in frequencies, f"{symptom} missing from the response"
    assert frequencies["fatigue"] == 1.0
    assert frequencies["fainting"] == 1.0


def test_a_symptom_outside_the_chip_list_is_reported():
    """``cycle_validation`` keeps unknown symptoms on purpose.

    Its docstring: *"Choices are rejected; symptoms are not. [...] Unknown
    symptoms are therefore normalised and kept."* Something kept at write
    time and dropped at read time is stored data the user can never see.
    """
    logs = [_log(20, ["dizziness"]), _log(19, ["dizziness"]), _log(18, [])]

    frequencies = compute_symptom_frequency(logs)["frequencies"]

    assert frequencies["dizziness"] == 0.67


def test_known_chips_come_first_and_extras_are_sorted():
    """A stable order, so a client iterating the map does not reshuffle."""
    logs = [_log(20, ["zzz", "aaa", "cramps"])]

    keys = list(compute_symptom_frequency(logs)["frequencies"])

    assert keys[: len(KNOWN_SYMPTOMS)] == list(KNOWN_SYMPTOMS)
    assert keys[len(KNOWN_SYMPTOMS) :] == ["aaa", "zzz"]


def test_a_chip_never_logged_is_reported_as_zero_not_omitted():
    """"You did not report this" is an answer; a missing key is not.

    It also keeps a client that draws a fixed row of bars drawing them.
    """
    frequencies = compute_symptom_frequency([_log(20, ["cramps"])])["frequencies"]

    assert frequencies["acne"] == 0.0
    assert "acne" in frequencies


# ─── Stored values that predate normalisation ────────────────────────────


def test_casing_and_spacing_in_stored_logs_still_count():
    """A document written before the write path normalised must still count.

    An exact-match test against ``"cramps"`` silently loses ``"Cramps"``,
    and the user sees 0% for a symptom she logged.
    """
    logs = [_log(20, ["Cramps"]), _log(19, ["  CRAMPS  "]), _log(18, ["back   pain"])]

    frequencies = compute_symptom_frequency(logs)["frequencies"]

    assert frequencies["cramps"] == 0.67
    assert frequencies["back pain"] == 0.33


def test_known_alternate_spellings_fold_onto_the_chip_value():
    """The same alias table the write path uses, applied on read."""
    logs = [_log(20, ["tiredness"]), _log(19, ["tired"]), _log(18, ["fatigue"])]

    assert compute_symptom_frequency(logs)["frequencies"]["fatigue"] == 1.0


def test_non_string_entries_are_skipped_not_fatal():
    """One malformed entry costs one symptom, not the whole card."""
    logs = [_log(20, ["cramps", None, 7, {"a": 1}]), _log(19, [])]

    frequencies = compute_symptom_frequency(logs)["frequencies"]

    assert frequencies["cramps"] == 0.5


# ─── Empty states ────────────────────────────────────────────────────────


def test_nothing_logged_at_all():
    assert compute_symptom_frequency([]) == {"frequencies": {}, "sample_size": 0}


def test_logs_without_any_symptom_keep_the_empty_map_but_report_the_sample():
    """The two empty states are different and stay distinguishable.

    ``{}`` preserves the clients' "no symptoms yet" state — the Flutter
    Insights card keys off ``_symptomFrequency.isEmpty`` — while a non-zero
    ``sample_size`` records that she has in fact been logging.
    """
    result = compute_symptom_frequency([_log(20, []), _log(19, None), _log(18)])

    assert result["frequencies"] == {}
    assert result["sample_size"] == 3


# ─── Through the endpoint ────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_client_state():
    client.cookies.clear()


@pytest.fixture
def auth_headers(mock_auth_dependencies):
    firebase_admin.auth.verify_id_token.return_value = {
        "phone_number": "+1234567890",
        "uid": "firebase_uid",
    }
    response = client.post(
        "/api/v1/auth/firebase-login", json={"id_token": "valid_token"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def mock_cycle_service():
    with patch("services.scoring_service.CycleService") as mock:
        yield mock


@pytest.fixture
def _mock_models():
    with patch("services.scoring_service.predict_cvi", return_value=0.5), patch(
        "services.scoring_service.predict_mhs", return_value=8.0
    ):
        yield


def test_dashboard_serves_the_corrected_fractions_and_the_sample_size(
    auth_headers, mock_cycle_service, _mock_models
):
    mock_cycle_service.get_logs_for_user.return_value = [
        _log(20, ["cramps"]),
        _log(19, []),
        _log(18, ["nausea"]),
        _log(17, []),
    ]

    response = client.get("/api/v1/dashboard", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["symptomSampleSize"] == 4
    assert data["symptomFrequency"]["cramps"] == 0.25
    assert data["symptomFrequency"]["nausea"] == 0.25


def test_dashboard_empty_symptom_map_is_unchanged_for_a_user_with_no_symptoms(
    auth_headers, mock_cycle_service, _mock_models
):
    """The clients' empty state must not turn into a row of 0% bars."""
    mock_cycle_service.get_logs_for_user.return_value = [_log(20, []), _log(19, [])]

    data = client.get("/api/v1/dashboard", headers=auth_headers).json()

    assert data["symptomFrequency"] == {}
    assert data["symptomSampleSize"] == 2


def test_symptom_sample_size_is_published_in_the_openapi_schema():
    """Additive and documented, so a client can rely on it being there."""
    schema = client.get("/openapi.json").json()
    properties = schema["components"]["schemas"]["DashboardResponse"]["properties"]

    assert "symptomSampleSize" in properties
    assert properties["symptomSampleSize"]["default"] == 0
