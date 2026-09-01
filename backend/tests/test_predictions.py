"""Tests for the cycle prediction service (issue #272).

Everything here injects ``today``, so no assertion depends on the wall
clock and the suite behaves identically in January and in December.
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest
import firebase_admin.auth

from test_auth import client, mock_auth_dependencies

from services.prediction_service import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    DEFAULT_CYCLE_LENGTH,
    PHASE_FOLLICULAR,
    PHASE_LATE,
    PHASE_LUTEAL,
    PHASE_OVULATION,
    PHASE_PERIOD,
    PHASE_UNKNOWN,
    SOURCE_DEFAULT,
    SOURCE_HISTORY,
    SOURCE_PROFILE,
    estimate_cycle_length,
    luteal_length_for,
    observed_gaps,
    phase_for,
    predict,
    range_half_width,
    reject_outliers,
    spread_of,
    weighted_mean,
)

TODAY = date(2026, 6, 1)


def logs_from_starts(starts, end_offset=4):
    """Cycle logs from a list of start dates, newest first."""
    return [
        {
            "start_date": start,
            "end_date": start + timedelta(days=end_offset),
        }
        for start in starts
    ]


def evenly_spaced(count, cycle_length, last_start):
    return [last_start - timedelta(days=cycle_length * i) for i in range(count)]


# ─── Gap extraction ───────────────────────────────────────────────────────


def test_observed_gaps_are_newest_first():
    starts = evenly_spaced(4, 28, date(2026, 5, 20))
    assert observed_gaps(logs_from_starts(starts)) == [28, 28, 28]


def test_observed_gaps_resorts_scrambled_input():
    """Every number downstream depends on ordering; a silently reversed
    list would produce confidently wrong predictions."""
    starts = [date(2026, 3, 1), date(2026, 5, 1), date(2026, 4, 1)]
    assert observed_gaps(logs_from_starts(starts)) == [30, 31]


def test_observed_gaps_dedupes_same_day_logs():
    starts = [date(2026, 5, 1), date(2026, 5, 1), date(2026, 4, 1)]
    assert observed_gaps(logs_from_starts(starts)) == [30]


def test_observed_gaps_ignores_logs_without_a_start():
    logs = [{"start_date": None}, {"start_date": date(2026, 5, 1)}]
    assert observed_gaps(logs) == []


def test_observed_gaps_of_nothing():
    assert observed_gaps([]) == []
    assert observed_gaps(None) == []


# ─── Outlier rejection ────────────────────────────────────────────────────


def test_implausible_gaps_are_excluded():
    """A six-month logging gap is not a 180-day cycle."""
    kept, rejected = reject_outliers([28, 29, 180, 27, 28])
    assert 180 in rejected
    assert 180 not in kept


def test_a_single_outlier_is_rejected_from_a_regular_history():
    kept, rejected = reject_outliers([28, 29, 28, 45, 28, 29])
    assert 45 in rejected
    assert sorted(kept) == [28, 28, 28, 29, 29]


def test_outlier_rejection_needs_enough_points():
    """With three cycles there is no basis to call one of them wrong."""
    kept, rejected = reject_outliers([28, 45, 29])
    assert kept == [28, 45, 29]
    assert rejected == []


def test_identical_cycles_still_catch_a_lone_outlier():
    # MAD is zero here, so the scaled threshold would be zero and reject
    # nothing (or everything); the absolute fallback handles it.
    kept, rejected = reject_outliers([28, 28, 28, 28, 40])
    assert 40 in rejected


def test_genuinely_variable_cycles_are_not_all_rejected():
    kept, _ = reject_outliers([26, 31, 28, 33, 27])
    assert len(kept) == 5


# ─── Weighting ────────────────────────────────────────────────────────────


def test_weighted_mean_favours_recent_cycles():
    """A user whose cycle shortened from 34 to 27 should not be predicted
    from cycles ten months stale."""
    recent_first = [27, 28, 33, 34, 34]
    assert weighted_mean(recent_first) < sum(recent_first) / len(recent_first)


def test_weighted_mean_of_identical_values_is_that_value():
    assert weighted_mean([28, 28, 28]) == pytest.approx(28)


def test_weighted_mean_of_one_value():
    assert weighted_mean([30]) == 30


def test_weighted_mean_rejects_empty_input():
    with pytest.raises(ValueError):
        weighted_mean([])


def test_spread_is_zero_for_a_single_cycle():
    assert spread_of([28]) == 0.0


def test_spread_grows_with_variability():
    assert spread_of([28, 28, 29]) < spread_of([21, 34, 30])


# ─── Cycle length estimation ──────────────────────────────────────────────


def test_estimate_uses_logged_history_when_available():
    estimate = estimate_cycle_length(logs_from_starts(evenly_spaced(6, 30, TODAY)))
    assert estimate.days == 30
    assert estimate.source == SOURCE_HISTORY
    assert estimate.sample_size == 5


def test_a_single_outlier_does_not_move_the_estimate_materially():
    regular = evenly_spaced(6, 28, date(2026, 5, 1))
    with_outlier = list(regular)
    with_outlier[3] = with_outlier[3] - timedelta(days=25)  # one very long gap

    clean = estimate_cycle_length(logs_from_starts(regular)).days
    noisy = estimate_cycle_length(logs_from_starts(with_outlier)).days

    assert abs(noisy - clean) <= 1


def test_estimate_falls_back_to_the_declared_cycle_length():
    """Onboarding already asked; ignoring the answer and using 28 is worse
    than using what she told us."""
    estimate = estimate_cycle_length([], profile={"cycle_length": 31})
    assert estimate.days == 31
    assert estimate.source == SOURCE_PROFILE
    assert estimate.confidence == CONFIDENCE_LOW


def test_estimate_ignores_an_implausible_declared_length():
    estimate = estimate_cycle_length([], profile={"cycle_length": 400})
    assert estimate.days == DEFAULT_CYCLE_LENGTH
    assert estimate.source == SOURCE_DEFAULT


def test_estimate_falls_back_to_the_population_default():
    estimate = estimate_cycle_length([], profile={})
    assert estimate.days == DEFAULT_CYCLE_LENGTH
    assert estimate.source == SOURCE_DEFAULT


def test_history_beats_a_declared_length():
    estimate = estimate_cycle_length(
        logs_from_starts(evenly_spaced(4, 26, TODAY)), profile={"cycle_length": 35}
    )
    assert estimate.days == 26
    assert estimate.source == SOURCE_HISTORY


def test_excluded_cycles_are_reported():
    """The estimate should be auditable: which cycles were dropped, and
    therefore why the number is what it is."""
    starts = evenly_spaced(6, 28, date(2026, 5, 1))
    starts[3] = starts[3] - timedelta(days=200)
    estimate = estimate_cycle_length(logs_from_starts(starts))
    assert estimate.excluded


def test_confidence_is_high_for_a_long_regular_history():
    estimate = estimate_cycle_length(logs_from_starts(evenly_spaced(8, 28, TODAY)))
    assert estimate.confidence == CONFIDENCE_HIGH


def test_confidence_is_not_high_for_a_long_erratic_history():
    """A long history of erratic cycles is not high confidence — this is
    exactly what the old point estimate obscured."""
    starts = [date(2026, 5, 20)]
    for gap in (21, 34, 24, 38, 22, 35, 26):
        starts.append(starts[-1] - timedelta(days=gap))
    estimate = estimate_cycle_length(logs_from_starts(starts))
    assert estimate.confidence != CONFIDENCE_HIGH


def test_confidence_is_medium_for_a_short_tidy_history():
    estimate = estimate_cycle_length(logs_from_starts(evenly_spaced(4, 28, TODAY)))
    assert estimate.confidence in (CONFIDENCE_MEDIUM, CONFIDENCE_HIGH)


def test_confidence_is_low_with_almost_no_data():
    estimate = estimate_cycle_length(logs_from_starts(evenly_spaced(2, 28, TODAY)))
    assert estimate.confidence == CONFIDENCE_LOW


# ─── Range width ──────────────────────────────────────────────────────────


def test_regular_cycles_get_a_narrow_range():
    estimate = estimate_cycle_length(logs_from_starts(evenly_spaced(6, 28, TODAY)))
    assert range_half_width(estimate) <= 3


def test_erratic_cycles_get_a_visibly_wider_range():
    """28/28/29 and 21/34/30 both average ~28. Presenting them with the
    same apparent precision is the misleading part."""
    starts = [date(2026, 5, 20)]
    for gap in (21, 34, 24, 38, 22):
        starts.append(starts[-1] - timedelta(days=gap))
    erratic = estimate_cycle_length(logs_from_starts(starts))
    regular = estimate_cycle_length(logs_from_starts(evenly_spaced(6, 28, TODAY)))

    assert range_half_width(erratic) > range_half_width(regular)


def test_range_is_never_a_single_certain_looking_day():
    estimate = estimate_cycle_length(logs_from_starts(evenly_spaced(8, 28, TODAY)))
    assert range_half_width(estimate) >= 2


def test_a_profile_only_estimate_is_visibly_uncertain():
    estimate = estimate_cycle_length([], profile={"cycle_length": 30})
    assert range_half_width(estimate) >= 4


# ─── Luteal phase and ovulation ───────────────────────────────────────────


@pytest.mark.parametrize("cycle_length,expected", [(28, 14), (35, 14), (45, 14), (25, 14)])
def test_luteal_is_flat_for_normal_and_long_cycles(cycle_length, expected):
    assert luteal_length_for(cycle_length) == expected


def test_luteal_shortens_for_short_cycles():
    """A flat 14 would put ovulation on day 7 of a 21-day cycle."""
    assert luteal_length_for(21) < 14
    assert luteal_length_for(21) >= 10


def test_ovulation_is_anchored_backwards_from_the_next_period():
    prediction = predict(
        logs_from_starts(evenly_spaced(6, 28, date(2026, 5, 20))), today=TODAY
    )
    assert (prediction.next_period_date - prediction.ovulation_date).days == 14


def test_fertile_window_spans_the_sperm_and_ovum_lifespan():
    prediction = predict(
        logs_from_starts(evenly_spaced(6, 28, date(2026, 5, 20))), today=TODAY
    )
    assert (prediction.ovulation_date - prediction.fertile_window_start).days == 5
    assert (prediction.fertile_window_end - prediction.ovulation_date).days == 1


def test_fertile_window_is_labelled_as_not_contraceptive_guidance():
    payload = predict(
        logs_from_starts(evenly_spaced(4, 28, date(2026, 5, 20))), today=TODAY
    ).to_dict()
    assert payload["fertileWindow"]["notForContraception"] is True
    assert payload["fertileWindow"]["isEstimate"] is True
    assert payload["ovulation"]["isEstimate"] is True
    assert "not a medical or contraceptive tool" in payload["disclaimer"]


# ─── Phase ────────────────────────────────────────────────────────────────


def test_phase_boundaries_scale_with_cycle_length():
    """The Flutter provider hardcodes 5/13/16 regardless of cycle length,
    which places ovulation about a week early for a 35-day cycle."""
    # Day 17 is past ovulation in a 28-day cycle, but still follicular in
    # a 35-day one. A fixed ladder cannot express both.
    assert phase_for(17, cycle_length=28, period_days=5, ovulation_day=14) == PHASE_LUTEAL
    assert (
        phase_for(17, cycle_length=35, period_days=5, ovulation_day=21)
        == PHASE_FOLLICULAR
    )


@pytest.mark.parametrize(
    "day,expected",
    [
        (1, PHASE_PERIOD),
        (5, PHASE_PERIOD),
        (6, PHASE_FOLLICULAR),
        (12, PHASE_FOLLICULAR),
        (13, PHASE_OVULATION),
        (15, PHASE_OVULATION),
        (16, PHASE_LUTEAL),
        (28, PHASE_LUTEAL),
        (29, PHASE_LATE),
    ],
)
def test_phase_ladder_for_a_28_day_cycle(day, expected):
    assert phase_for(day, cycle_length=28, period_days=5, ovulation_day=14) == expected


def test_a_stale_last_period_reports_late_not_luteal_forever():
    """The Flutter provider reports "day 63, luteal" indefinitely because
    the day count is never bounded. Saying "late" is honest and tells the
    user what to do about it."""
    assert phase_for(63, cycle_length=28, period_days=5, ovulation_day=14) == PHASE_LATE


def test_phase_is_unknown_without_a_cycle_day():
    assert phase_for(None, 28, 5, 14) == PHASE_UNKNOWN
    assert phase_for(0, 28, 5, 14) == PHASE_UNKNOWN


# ─── Overdue ──────────────────────────────────────────────────────────────


def test_days_until_goes_negative_when_late():
    """The old `max(avg - day, 0)` made "due today" and "five days late"
    the same number, which is the single most useful distinction this
    endpoint can draw."""
    prediction = predict(
        logs_from_starts(evenly_spaced(4, 28, TODAY - timedelta(days=33))), today=TODAY
    )
    assert prediction.days_until_next_period < 0
    assert prediction.is_overdue is True
    assert prediction.days_overdue == 5


def test_due_today_is_distinguishable_from_late():
    prediction = predict(
        logs_from_starts(evenly_spaced(4, 28, TODAY - timedelta(days=28))), today=TODAY
    )
    assert prediction.days_until_next_period == 0
    assert prediction.is_overdue is False
    assert prediction.days_overdue == 0


def test_not_overdue_mid_cycle():
    prediction = predict(
        logs_from_starts(evenly_spaced(4, 28, TODAY - timedelta(days=10))), today=TODAY
    )
    assert prediction.days_until_next_period == 18
    assert prediction.is_overdue is False


# ─── Whole-prediction behaviour ───────────────────────────────────────────


def test_no_logs_and_no_profile_yields_no_dates_rather_than_invented_ones():
    prediction = predict([], today=TODAY)
    assert prediction.next_period_date is None
    assert prediction.ovulation_date is None
    assert prediction.phase == PHASE_UNKNOWN
    assert prediction.upcoming_periods == []


def test_a_profile_only_user_still_gets_a_prediction():
    """Onboarding collects last_period and cycle_length; a user who has
    completed it should not see an empty Home screen on day one."""
    prediction = predict(
        [], profile={"last_period": "2026-05-20", "cycle_length": 30}, today=TODAY
    )
    assert prediction.next_period_date == date(2026, 6, 19)
    assert prediction.cycle_length.source == SOURCE_PROFILE


def test_a_single_log_anchors_the_prediction_on_the_default_length():
    prediction = predict(logs_from_starts([date(2026, 5, 20)]), today=TODAY)
    assert prediction.current_cycle_day == 13
    assert prediction.cycle_length.source == SOURCE_DEFAULT


def test_cycle_day_counts_inclusively_from_the_start():
    prediction = predict(logs_from_starts([TODAY]), today=TODAY)
    assert prediction.current_cycle_day == 1


def test_upcoming_periods_are_evenly_spaced_by_the_estimate():
    prediction = predict(
        logs_from_starts(evenly_spaced(6, 30, date(2026, 5, 20))), today=TODAY, horizon=3
    )
    assert len(prediction.upcoming_periods) == 3
    first, second, third = prediction.upcoming_periods
    assert (second - first).days == 30
    assert (third - second).days == 30


def test_horizon_of_zero_returns_no_forecast():
    prediction = predict(
        logs_from_starts(evenly_spaced(4, 28, date(2026, 5, 20))), today=TODAY, horizon=0
    )
    assert prediction.upcoming_periods == []


def test_short_cycles_are_handled():
    prediction = predict(
        logs_from_starts(evenly_spaced(6, 21, date(2026, 5, 25))), today=TODAY
    )
    assert prediction.cycle_length.days == 21
    assert prediction.ovulation_date < prediction.next_period_date


def test_long_cycles_are_handled():
    prediction = predict(
        logs_from_starts(evenly_spaced(6, 45, date(2026, 5, 25))), today=TODAY
    )
    assert prediction.cycle_length.days == 45


def test_leap_day_is_crossed_correctly():
    prediction = predict(
        logs_from_starts([date(2024, 2, 15)]), today=date(2024, 3, 1)
    )
    # 2024-02-15 → 2024-03-01 is 15 days, so day 16 inclusive.
    assert prediction.current_cycle_day == 16


def test_year_boundary_is_crossed_correctly():
    prediction = predict(
        logs_from_starts([date(2025, 12, 20)]), today=date(2026, 1, 5)
    )
    assert prediction.current_cycle_day == 17
    assert prediction.next_period_date == date(2026, 1, 17)


def test_prediction_is_deterministic():
    logs = logs_from_starts(evenly_spaced(6, 29, date(2026, 5, 20)))
    assert predict(logs, today=TODAY).to_dict() == predict(logs, today=TODAY).to_dict()


def test_serialized_payload_has_iso_dates_and_no_python_objects():
    import json

    payload = predict(
        logs_from_starts(evenly_spaced(4, 28, date(2026, 5, 20))), today=TODAY
    ).to_dict()
    json.dumps(payload)  # would raise on a stray date object
    assert payload["nextPeriodDate"].startswith("2026-")


# ─── Endpoint ─────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_client_state():
    from services.rate_limit_service import RateLimitService

    def _reset():
        client.cookies.clear()
        RateLimitService.clear_all()

    _reset()
    yield
    _reset()


@pytest.fixture
def auth_headers(mock_auth_dependencies):
    firebase_admin.auth.verify_id_token.return_value = {
        "phone_number": "+1234567890",
        "uid": "firebase_uid",
    }
    token_response = client.post(
        "/api/v1/auth/firebase-login",
        json={"id_token": "valid_token"},
        headers={"X-Client-Platform": "mobile"},
    )
    return {"Authorization": f"Bearer {token_response.json()['access_token']}"}


@pytest.fixture
def mock_cycle_service():
    with patch("api.cycle.CycleService") as mock:
        yield mock


def test_predictions_endpoint_returns_the_payload(auth_headers, mock_cycle_service):
    mock_cycle_service.get_logs_for_user.return_value = logs_from_starts(
        evenly_spaced(6, 28, date.today() - timedelta(days=10))
    )
    response = client.get("/api/v1/cycle/predictions", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["cycleLength"]["days"] == 28
    assert body["cycleLength"]["source"] == SOURCE_HISTORY
    assert body["daysUntilNextPeriod"] == 18
    assert body["fertileWindow"]["notForContraception"] is True


def test_predictions_endpoint_requires_auth():
    assert client.get("/api/v1/cycle/predictions").status_code == 401


def test_predictions_endpoint_honours_the_horizon(auth_headers, mock_cycle_service):
    mock_cycle_service.get_logs_for_user.return_value = logs_from_starts(
        evenly_spaced(4, 28, date.today() - timedelta(days=5))
    )
    body = client.get(
        "/api/v1/cycle/predictions?horizon=6", headers=auth_headers
    ).json()
    assert len(body["upcomingPeriods"]) == 6


def test_predictions_endpoint_rejects_an_absurd_horizon(auth_headers):
    assert (
        client.get("/api/v1/cycle/predictions?horizon=500", headers=auth_headers).status_code
        == 422
    )


def test_predictions_endpoint_handles_a_user_with_no_logs(
    auth_headers, mock_cycle_service
):
    mock_cycle_service.get_logs_for_user.return_value = []
    body = client.get("/api/v1/cycle/predictions", headers=auth_headers).json()
    assert body["nextPeriodDate"] is None
    assert body["phase"] == PHASE_UNKNOWN


def test_predictions_route_is_not_shadowed_by_the_log_id_routes(
    auth_headers, mock_cycle_service
):
    """`/predictions` sits alongside PUT/DELETE `/{log_id}`; a GET must
    reach the prediction handler rather than 404 or match a log id."""
    mock_cycle_service.get_logs_for_user.return_value = []
    assert client.get("/api/v1/cycle/predictions", headers=auth_headers).status_code == 200


def test_predictions_endpoint_uses_onboarding_cycle_length(auth_headers, mock_cycle_service):
    """Onboarding declares cycle_length=35; the endpoint must thread it
    through UserService → predict() rather than silently dropping it and
    falling back to the 28-day population default."""
    mock_cycle_service.get_logs_for_user.return_value = []

    user_profile = {
        "id": "test-user-id-123",
        "phone": "+1234567890",
        "cycle_length": 35,
        "last_period": "2026-05-20",
    }
    with patch("api.cycle.UserService") as mock_user_service:
        mock_user_service.get_user_by_id.return_value = user_profile
        body = client.get(
            "/api/v1/cycle/predictions", headers=auth_headers
        ).json()

    assert body["cycleLength"]["days"] == 35
    assert body["cycleLength"]["source"] == SOURCE_PROFILE


def test_predictions_endpoint_ignores_implausible_onboarding_cycle_length(
    auth_headers, mock_cycle_service
):
    """An out-of-range declared value (e.g. 400 days) must not produce a
    nonsensical estimate; the endpoint should fall back to the default."""
    mock_cycle_service.get_logs_for_user.return_value = []

    user_profile = {
        "id": "test-user-id-123",
        "phone": "+1234567890",
        "cycle_length": 400,
        "last_period": "2026-05-20",
    }
    with patch("api.cycle.UserService") as mock_user_service:
        mock_user_service.get_user_by_id.return_value = user_profile
        body = client.get(
            "/api/v1/cycle/predictions", headers=auth_headers
        ).json()

    assert body["cycleLength"]["days"] == DEFAULT_CYCLE_LENGTH
    assert body["cycleLength"]["source"] == SOURCE_DEFAULT


def test_dashboard_carries_the_prediction_summary(auth_headers):
    with patch("services.scoring_service.CycleService") as scoring_cycle_service, patch(
        "services.scoring_service.predict_cvi", return_value=40.0
    ), patch("services.scoring_service.predict_mhs", return_value=70.0):
        scoring_cycle_service.get_logs_for_user.return_value = logs_from_starts(
            evenly_spaced(4, 28, date.today() - timedelta(days=33))
        )
        body = client.get("/api/v1/dashboard", headers=auth_headers).json()

    assert body["prediction"]["isOverdue"] is True
    assert body["prediction"]["daysOverdue"] == 5
    # The legacy field keeps its clamped meaning so existing clients are
    # unaffected by the addition.
    assert body["cycle"]["nextPeriodDays"] == 0


def test_dashboard_keeps_all_of_its_original_fields(auth_headers):
    with patch("services.scoring_service.CycleService") as scoring_cycle_service, patch(
        "services.scoring_service.predict_cvi", return_value=40.0
    ), patch("services.scoring_service.predict_mhs", return_value=70.0):
        scoring_cycle_service.get_logs_for_user.return_value = logs_from_starts(
            evenly_spaced(3, 28, date.today() - timedelta(days=5))
        )
        body = client.get("/api/v1/dashboard", headers=auth_headers).json()

    for key in (
        "user",
        "cycle",
        "insights",
        "hasEnoughDataForInsights",
        "loggedCycleCount",
        "cycleHistory",
        "symptomFrequency",
        "recentStressLevel",
    ):
        assert key in body
