"""Tests for the shared period-start extraction (issue #518).

The bug these guard against is not an exception — it is a plausible-looking
wrong number. ``start_date`` is stamped on every logged day, not only on
period starts, so the arithmetic that turns logs into cycle lengths has to
say which gaps it is willing to call a cycle. ``compute_cycle_stats`` did
not, and reported a 4.2-day average for a user whose cycles were 22 and 28
days.

The fixtures below therefore lean on the shape that produced it: a couple
of real period starts, plus a run of consecutive days from the Home
screen's quick-log tiles.
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from services.cycle_periods import (
    MAX_PLAUSIBLE_CYCLE_DAYS,
    MIN_PLAUSIBLE_CYCLE_DAYS,
    all_gaps,
    as_date,
    bleed_durations,
    cycle_gaps,
    cycle_history,
    is_plausible_bleed,
    is_plausible_cycle,
    partition_gaps,
    period_starts,
)
from services.scoring_service import compute_cycle_stats


def log(start, end=None, **extra):
    """One cycle_logs document, in the shape Firestore hands back."""
    entry = {"start_date": start}
    if end is not None:
        entry["end_date"] = end
    entry.update(extra)
    return entry


def quick_logs(last_day, count):
    """`count` consecutive daily logs ending on `last_day`, newest first.

    What tapping a mood or a sleep figure on the Home screen produces: one
    document per day, each carrying a `start_date` that is not a period
    start.
    """
    return [log(last_day - timedelta(days=offset)) for offset in range(count)]


# ─── as_date ──────────────────────────────────────────────────────────────


def test_as_date_passes_through_a_plain_date():
    assert as_date(date(2026, 5, 4)) == date(2026, 5, 4)


def test_as_date_drops_the_time_component_from_a_datetime():
    # Firestore returns datetimes. Two logs written at 23:00 and 01:00 are
    # one day apart, not zero, and only the date part may take part in the
    # subtraction.
    value = datetime(2026, 5, 4, 23, 30, tzinfo=timezone.utc)
    assert as_date(value) == date(2026, 5, 4)


@pytest.mark.parametrize("value", [None, "2026-05-04", 17, [], {}])
def test_as_date_returns_none_for_anything_that_is_not_a_date(value):
    assert as_date(value) is None


# ─── The band ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("days", [15, 21, 28, 35, 45, 60])
def test_plausible_cycle_lengths_are_accepted(days):
    assert is_plausible_cycle(days)


@pytest.mark.parametrize("days", [None, 0, 1, 2, 14, 61, 90, 365])
def test_implausible_cycle_lengths_are_rejected(days):
    assert not is_plausible_cycle(days)


def test_the_band_is_inclusive_at_both_ends():
    # A 15-day and a 60-day cycle are both real. The band excludes what is
    # outside it, and an off-by-one here silently discards real cycles from
    # the users whose cycles are least typical.
    assert is_plausible_cycle(MIN_PLAUSIBLE_CYCLE_DAYS)
    assert is_plausible_cycle(MAX_PLAUSIBLE_CYCLE_DAYS)
    assert not is_plausible_cycle(MIN_PLAUSIBLE_CYCLE_DAYS - 1)
    assert not is_plausible_cycle(MAX_PLAUSIBLE_CYCLE_DAYS + 1)


@pytest.mark.parametrize("days", [1, 5, 15])
def test_plausible_bleed_lengths_are_accepted(days):
    assert is_plausible_bleed(days)


@pytest.mark.parametrize("days", [None, 0, -3, 16, 40])
def test_implausible_bleed_lengths_are_rejected(days):
    assert not is_plausible_bleed(days)


# ─── period_starts ────────────────────────────────────────────────────────


def test_period_starts_are_returned_newest_first():
    logs = [log(date(2026, 4, 1)), log(date(2026, 6, 1)), log(date(2026, 5, 1))]
    assert period_starts(logs) == [
        date(2026, 6, 1),
        date(2026, 5, 1),
        date(2026, 4, 1),
    ]


def test_period_starts_ignores_the_order_it_was_given():
    # Callers pass `CycleService.get_logs_for_user` output, which is
    # newest-first — but every figure downstream depends on that holding,
    # and a reversed list would produce confident nonsense rather than an
    # error.
    ascending = [log(date(2026, 4, 1)), log(date(2026, 5, 1))]
    descending = list(reversed(ascending))
    assert period_starts(ascending) == period_starts(descending)


def test_period_starts_deduplicates_the_same_day():
    logs = [log(date(2026, 5, 1)), log(date(2026, 5, 1)), log(date(2026, 4, 1))]
    assert period_starts(logs) == [date(2026, 5, 1), date(2026, 4, 1)]


def test_period_starts_skips_logs_with_no_usable_start_date():
    logs = [log(date(2026, 5, 1)), {"start_date": None}, {"mood": "calm"}]
    assert period_starts(logs) == [date(2026, 5, 1)]


def test_period_starts_normalizes_firestore_datetimes():
    logs = [log(datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc))]
    assert period_starts(logs) == [date(2026, 5, 1)]


def test_period_starts_of_nothing_is_empty():
    assert period_starts([]) == []
    assert period_starts(None) == []


# ─── Gaps ─────────────────────────────────────────────────────────────────


def test_all_gaps_reports_every_gap_including_the_implausible_ones():
    logs = [log(date(2026, 6, 1)), log(date(2026, 5, 31)), log(date(2026, 5, 4))]
    assert all_gaps(logs) == [1, 27]


def test_cycle_gaps_keeps_only_what_could_be_a_cycle():
    logs = [log(date(2026, 6, 1)), log(date(2026, 5, 31)), log(date(2026, 5, 4))]
    assert cycle_gaps(logs) == [27]


def test_consecutive_quick_logs_produce_no_cycles_at_all():
    # The headline case. Fourteen days of tapping a mood is not fourteen
    # cycles, and it is not one either.
    assert cycle_gaps(quick_logs(date(2026, 8, 24), 14)) == []


def test_a_run_of_quick_logs_does_not_hide_the_real_cycles_around_it():
    logs = quick_logs(date(2026, 8, 24), 14) + [
        log(date(2026, 7, 20)),
        log(date(2026, 6, 22)),
    ]
    # 11 Aug (the oldest quick-log) back to 20 July is 22 days; 20 July back
    # to 22 June is 28.
    assert cycle_gaps(logs) == [22, 28]


def test_a_missed_month_of_logging_is_not_a_cycle():
    logs = [log(date(2026, 6, 1)), log(date(2026, 1, 1))]
    assert cycle_gaps(logs) == []


def test_partition_reports_both_sides():
    logs = quick_logs(date(2026, 8, 24), 3) + [log(date(2026, 7, 20))]
    kept, discarded = partition_gaps(logs)
    # 22 Aug (the oldest quick-log) back to 20 July is 33 days; the two
    # gaps between the three consecutive quick-logs are 1 day each.
    assert kept == [33]
    assert discarded == [1, 1]


def test_partition_accounts_for_every_gap():
    logs = quick_logs(date(2026, 8, 24), 6) + [
        log(date(2026, 7, 20)),
        log(date(2026, 6, 22)),
    ]
    kept, discarded = partition_gaps(logs)
    assert len(kept) + len(discarded) == len(all_gaps(logs))


# ─── Bleed durations ──────────────────────────────────────────────────────


def test_bleed_duration_is_inclusive_of_both_ends():
    assert bleed_durations([log(date(2026, 5, 1), date(2026, 5, 5))]) == [5]


def test_a_log_without_an_end_date_contributes_nothing():
    # "She hasn't logged an end date yet" and "the period lasted one day"
    # are different facts. Defaulting would invent the difference.
    assert bleed_durations([log(date(2026, 5, 1))]) == []


def test_an_inverted_range_is_discarded_rather_than_clamped():
    assert bleed_durations([log(date(2026, 5, 5), date(2026, 5, 1))]) == []


def test_an_implausibly_long_bleed_is_discarded():
    # A mis-entered end_date a year out would otherwise drag the average
    # bleeding duration onto a doctor's copy of the PDF report.
    assert bleed_durations([log(date(2026, 5, 1), date(2027, 5, 1))]) == []


# ─── cycle_history ────────────────────────────────────────────────────────


def test_cycle_history_is_oldest_first():
    logs = [log(date(2026, 6, 1)), log(date(2026, 5, 4)), log(date(2026, 4, 6))]
    history = cycle_history(logs)
    assert [entry["start_date"] for entry in history] == ["2026-05-04", "2026-06-01"]


def test_cycle_history_dates_each_entry_by_the_later_period():
    logs = [log(date(2026, 6, 1)), log(date(2026, 5, 4))]
    assert cycle_history(logs) == [{"start_date": "2026-06-01", "cycle_length": 28}]


def test_cycle_history_omits_the_one_day_entries_quick_logs_used_to_produce():
    logs = quick_logs(date(2026, 8, 24), 5) + [log(date(2026, 7, 20))]
    lengths = [entry["cycle_length"] for entry in cycle_history(logs)]
    assert lengths == [31]
    assert 1 not in lengths


def test_cycle_history_of_a_single_log_is_empty():
    assert cycle_history([log(date(2026, 6, 1))]) == []


# ─── compute_cycle_stats, end to end ──────────────────────────────────────


def test_quick_logs_no_longer_collapse_the_average_cycle_length():
    """The exact scenario from the issue.

    Two real cycles of 22 and 28 days, buried under a fortnight of daily
    quick-logs. Before the fix this returned an average of 4.2 and a
    shortest cycle of 1.
    """
    logs = quick_logs(date(2026, 8, 24), 14) + [
        log(date(2026, 7, 20), date(2026, 7, 24)),
        log(date(2026, 6, 22), date(2026, 6, 26)),
    ]
    stats = compute_cycle_stats(logs)

    assert stats["average_cycle_length"] == 25.0
    assert stats["shortest_cycle_length"] == 22
    assert stats["longest_cycle_length"] == 28
    assert stats["analyzed_cycle_count"] == 2
    assert stats["excluded_gap_count"] == 13


def test_the_stats_agree_with_the_observations_engine():
    """The contradiction #518 is really about.

    Both figures ship in the same ``/dashboard`` response. Whatever the
    right answer is, there cannot be two of it.
    """
    from services.health_observations_service import get_user_observations

    logs = quick_logs(date(2026, 8, 24), 14) + [
        log(date(2026, 7, 20)),
        log(date(2026, 6, 22)),
    ]
    stats = compute_cycle_stats(logs)
    observations = get_user_observations(logs, profile={}, today=date(2026, 8, 25))

    assert round(stats["average_cycle_length"]) == observations["averageCycleLength"]


def test_stats_are_none_when_no_gap_could_be_a_cycle():
    # Not zero, and not a 28-day default dressed up as a measurement.
    stats = compute_cycle_stats(quick_logs(date(2026, 8, 24), 4))

    assert stats["average_cycle_length"] is None
    assert stats["shortest_cycle_length"] is None
    assert stats["longest_cycle_length"] is None
    assert stats["analyzed_cycle_count"] == 0
    assert stats["excluded_gap_count"] == 3


def test_stats_of_an_empty_history_are_all_none():
    stats = compute_cycle_stats([])
    assert stats["average_cycle_length"] is None
    assert stats["average_bleeding_duration"] is None
    assert stats["analyzed_cycle_count"] == 0
    assert stats["excluded_gap_count"] == 0


def test_a_clean_history_is_unchanged_by_the_filter():
    # The regression guard on the other side: a user who only logs period
    # starts must get exactly what she got before.
    logs = [
        log(date(2026, 6, 1), date(2026, 6, 5)),
        log(date(2026, 5, 4), date(2026, 5, 8)),
        log(date(2026, 4, 6), date(2026, 4, 10)),
    ]
    stats = compute_cycle_stats(logs)

    assert stats["average_cycle_length"] == 28.0
    assert stats["shortest_cycle_length"] == 28
    assert stats["longest_cycle_length"] == 28
    assert stats["average_bleeding_duration"] == 5.0
    assert stats["excluded_gap_count"] == 0


def test_stats_do_not_depend_on_the_order_of_the_logs():
    logs = [
        log(date(2026, 6, 1)),
        log(date(2026, 5, 4)),
        log(date(2026, 4, 6)),
    ]
    assert compute_cycle_stats(logs) == compute_cycle_stats(list(reversed(logs)))


# ─── The /dashboard response, end to end ──────────────────────────────────
#
# The unit tests above prove the extraction. These two prove the wiring:
# that every figure in the response which is derived from cycle lengths now
# comes through it, and that one response cannot carry two answers.

import firebase_admin.auth  # noqa: E402
from unittest.mock import patch  # noqa: E402

from test_auth import client, mock_auth_dependencies  # noqa: E402,F401


@pytest.fixture(autouse=True)
def _clear_client_state():
    client.cookies.clear()


@pytest.fixture
def auth_headers(mock_auth_dependencies):
    firebase_admin.auth.verify_id_token.return_value = {
        "phone_number": "+1234567890",
        "uid": "firebase_uid",
    }
    response = client.post("/api/v1/auth/firebase-login", json={"id_token": "valid_token"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_dashboard_does_not_report_two_average_cycle_lengths(auth_headers):
    logs = quick_logs(date(2026, 8, 24), 14) + [
        log(date(2026, 7, 20), date(2026, 7, 24)),
        log(date(2026, 6, 22), date(2026, 6, 26)),
    ]

    with patch("services.scoring_service.CycleService") as mock_service:
        mock_service.get_logs_for_user.return_value = logs
        response = client.get("/api/v1/dashboard", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()

    # Before the fix this was 4.2, next to a cycle ring reading 4 and a
    # consistency sentence describing 25-day cycles.
    assert body["insights"]["averageCycleLength"] == 25.0
    assert body["insights"]["shortestCycleLength"] == 22
    assert body["cycle"]["total"] == 25
    assert body["insights"]["analyzedCycleCount"] == 2
    assert body["insights"]["excludedGapCount"] == 13


def test_dashboard_cycle_history_has_no_one_day_cycles(auth_headers):
    logs = quick_logs(date(2026, 8, 24), 14) + [
        log(date(2026, 7, 20)),
        log(date(2026, 6, 22)),
    ]

    with patch("services.scoring_service.CycleService") as mock_service:
        mock_service.get_logs_for_user.return_value = logs
        response = client.get("/api/v1/dashboard", headers=auth_headers)

    lengths = [entry["cycle_length"] for entry in response.json()["cycleHistory"]]

    # The trend chart used to plot thirteen consecutive 1s.
    assert lengths == [28, 22]
    assert all(is_plausible_cycle(length) for length in lengths)
