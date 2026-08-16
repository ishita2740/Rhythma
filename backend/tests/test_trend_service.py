"""Trends compare periods, and say so honestly (issue #484).

``GET /dashboard/trends`` took ``logs[0]`` and ``logs[1]`` — two adjacent
*day* documents, because ``upsert_log`` writes one document per calendar
day — and reported the difference as "Average sleep has decreased". Two
untruths in one sentence: it was not an average, and it was not a
period-over-period comparison.

These tests are all against ``services/trend_service`` directly rather
than through the route. The bug was arithmetic over a badly chosen
window, and a pure function is where that can be pinned down; the route
gets its own coverage in ``test_dashboard_trends.py``.

Every test injects ``today``. One that derived a window from
``date.today()`` would change meaning every day it ran.
"""

import os
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.trend_service import (  # noqa: E402
    BASIS_CYCLE,
    BASIS_RECENT_LOGS,
    DIRECTION_DECREASED,
    DIRECTION_INCREASED,
    DIRECTION_UNCHANGED,
    MIN_DAYS_BETWEEN_PERIOD_STARTS,
    build_trends,
    cycle_windows,
    period_starts,
    recent_log_windows,
    to_day_records,
)

TODAY = date(2026, 6, 30)


def _log(day, **fields):
    """One day-document, in the shape Firestore hands back."""
    return {"start_date": day, **fields}


def _period_days(first_day, length=5, **fields):
    """A run of ``length`` consecutive bleeding days from ``first_day``."""
    return [
        _log(first_day + timedelta(days=offset), flow_intensity="medium", **fields)
        for offset in range(length)
    ]


def _statement(result, metric):
    for entry in result["trends"]:
        if entry["metric"] == metric:
            return entry
    return None


# ─── Reconstructing periods ───────────────────────────────────────────────


def test_a_run_of_bleeding_days_is_one_period_not_five():
    """The core mistake: one document is one day, not one period."""
    records = to_day_records(_period_days(date(2026, 5, 1), length=5))

    assert period_starts(records) == [date(2026, 5, 1)]


def test_a_single_missed_day_does_not_split_a_period_in_two():
    """"Forgot to log on Tuesday" is the common case, not a new period."""
    logs = [
        _log(date(2026, 5, 1), flow_intensity="medium"),
        _log(date(2026, 5, 2), flow_intensity="medium"),
        # 3 May missing
        _log(date(2026, 5, 4), flow_intensity="light"),
    ]

    assert period_starts(to_day_records(logs)) == [date(2026, 5, 1)]


def test_mid_cycle_spotting_does_not_open_a_phantom_cycle():
    """Without the minimum-gap rule this produces a 10-day "cycle".

    That phantom would then be averaged against a real 28-day window and
    the difference reported as a trend.
    """
    logs = _period_days(date(2026, 5, 1)) + [
        _log(date(2026, 5, 11), flow_intensity="spotting"),
    ] + _period_days(date(2026, 5, 29))

    starts = period_starts(to_day_records(logs))

    assert starts == [date(2026, 5, 1), date(2026, 5, 29)]
    for earlier, later in zip(starts, starts[1:]):
        assert (later - earlier).days >= MIN_DAYS_BETWEEN_PERIOD_STARTS


def test_flow_logged_as_none_is_not_bleeding():
    """`none` is an answer the user gave, not an absence of one.

    Treating it as a period would invent a cycle out of "I checked,
    there was nothing".
    """
    logs = [_log(date(2026, 5, 1), flow_intensity="none")]

    assert period_starts(to_day_records(logs)) == []


def test_a_cycle_window_runs_from_one_start_to_the_day_before_the_next():
    logs = _period_days(date(2026, 5, 1)) + _period_days(date(2026, 5, 29))

    windows = cycle_windows(to_day_records(logs), TODAY)

    assert len(windows) == 1
    assert windows[0].start == date(2026, 5, 1)
    assert windows[0].end == date(2026, 5, 28)
    assert windows[0].days == 28


def test_the_cycle_in_progress_is_excluded():
    """It is partial.

    Averaging four days of a new cycle against twenty-eight of the last
    one compares a sample to a population and calls the gap a trend.
    """
    logs = (
        _period_days(date(2026, 4, 3))
        + _period_days(date(2026, 5, 1))
        + _period_days(date(2026, 6, 29))  # in progress on TODAY
    )

    windows = cycle_windows(to_day_records(logs), TODAY)

    assert len(windows) == 2
    assert windows[-1].end == date(2026, 6, 28)
    assert all(window.end < date(2026, 6, 29) for window in windows)


# ─── The reported bug ─────────────────────────────────────────────────────


def test_two_adjacent_days_are_no_longer_reported_as_two_periods():
    """The exact scenario from the issue.

    Two consecutive days, one bad night's sleep. The old code called this
    "Average sleep has decreased" across periods. There is no period here
    at all — no flow was logged — so the basis must say `recent_logs`,
    and the word "Average" must not appear over a single reading.
    """
    logs = [
        _log(date(2026, 6, 28), sleep_hours=8, stress_level=2),
        _log(date(2026, 6, 29), sleep_hours=6, stress_level=4),
    ]

    result = build_trends(logs, today=TODAY)

    assert result["basis"] == BASIS_RECENT_LOGS
    assert result["basis"] != BASIS_CYCLE
    assert "Average" not in result["sleep"]
    assert "Logged sleep has decreased" in result["sleep"]


def test_a_single_reading_is_never_called_an_average():
    """The specific word that made the old sentence untrue."""
    logs = [
        _log(date(2026, 6, 28), sleep_hours=8),
        _log(date(2026, 6, 29), sleep_hours=6),
    ]

    result = build_trends(logs, today=TODAY)
    sleep = _statement(result, "sleep")

    assert sleep["evidence"]["previousSamples"] == 1
    assert sleep["evidence"]["currentSamples"] == 1
    assert sleep["evidence"]["averaged"] is False
    assert "Average" not in sleep["text"]


def test_a_real_average_is_called_an_average_and_uses_every_value():
    """The call site the route's orphaned `avg()` helper never got.

    Previous cycle sleeps 5,5,5,5,5; current 8,8,8,8,8. Every value in
    each window contributes, so the means are 5.0 and 8.0 — not
    whichever single document happened to sort first.
    """
    logs = (
        _period_days(date(2026, 5, 1), sleep_hours=5)
        + _period_days(date(2026, 5, 29), sleep_hours=8)
        + _period_days(date(2026, 6, 26))
    )

    result = build_trends(logs, today=TODAY)
    sleep = _statement(result, "sleep")

    assert result["basis"] == BASIS_CYCLE
    assert sleep["evidence"]["previous"] == 5.0
    assert sleep["evidence"]["current"] == 8.0
    assert sleep["evidence"]["previousSamples"] == 5
    assert sleep["evidence"]["currentSamples"] == 5
    assert sleep["evidence"]["averaged"] is True
    assert "Average sleep has increased" in sleep["text"]


def test_one_bad_night_does_not_move_a_whole_cycle_average():
    """The user-visible consequence of averaging over the window.

    Four nights at 8h and one at 3h averages to 7.0 — not a decline. The
    old code, reading only the newest document, would have reported the
    3h night as the cycle's trend.
    """
    previous = _period_days(date(2026, 5, 1), sleep_hours=7)
    current = [
        _log(date(2026, 5, 29), flow_intensity="medium", sleep_hours=8),
        _log(date(2026, 5, 30), flow_intensity="medium", sleep_hours=8),
        _log(date(2026, 5, 31), flow_intensity="medium", sleep_hours=8),
        _log(date(2026, 6, 1), flow_intensity="medium", sleep_hours=8),
        _log(date(2026, 6, 2), sleep_hours=3),
    ]
    logs = previous + current + _period_days(date(2026, 6, 26))

    result = build_trends(logs, today=TODAY)
    sleep = _statement(result, "sleep")

    assert sleep["evidence"]["current"] == 7.0
    assert sleep["direction"] == DIRECTION_UNCHANGED


# ─── Statements ───────────────────────────────────────────────────────────


def test_noise_is_reported_as_unchanged_rather_than_as_a_trend():
    """7.0h against 7.1h is not a finding."""
    logs = (
        _period_days(date(2026, 5, 1), sleep_hours=7.0)
        + _period_days(date(2026, 5, 29), sleep_hours=7.1)
        + _period_days(date(2026, 6, 26))
    )

    result = build_trends(logs, today=TODAY)

    assert _statement(result, "sleep")["direction"] == DIRECTION_UNCHANGED
    assert "about the same" in result["sleep"]


def test_a_symptom_is_reported_as_a_rate_not_as_present_or_absent():
    """"Was it in the newest document?" is a coin flip on which day sorted first.

    Cramps on 1 of 5 days, then 4 of 5. That is a real change in how
    often it happened, which a presence check cannot express.
    """
    previous = [
        _log(date(2026, 5, 1), flow_intensity="medium", symptoms=["cramps"]),
        _log(date(2026, 5, 2), flow_intensity="medium", symptoms=[]),
        _log(date(2026, 5, 3), flow_intensity="medium", symptoms=[]),
        _log(date(2026, 5, 4), flow_intensity="medium", symptoms=[]),
        _log(date(2026, 5, 5), flow_intensity="medium", symptoms=[]),
    ]
    current = [
        _log(date(2026, 5, 29), flow_intensity="medium", symptoms=["cramps"]),
        _log(date(2026, 5, 30), flow_intensity="medium", symptoms=["cramps"]),
        _log(date(2026, 5, 31), flow_intensity="medium", symptoms=["cramps"]),
        _log(date(2026, 6, 1), flow_intensity="medium", symptoms=["cramps"]),
        _log(date(2026, 6, 2), flow_intensity="medium", symptoms=[]),
    ]
    logs = previous + current + _period_days(date(2026, 6, 26))

    result = build_trends(logs, today=TODAY)
    cramps = _statement(result, "cramps")

    assert cramps["direction"] == DIRECTION_INCREASED
    assert cramps["evidence"]["previousRate"] == 0.2
    assert cramps["evidence"]["currentRate"] == 0.8


def test_a_symptom_logged_in_neither_window_is_omitted_entirely():
    """Silence about acne is better than a card saying nothing changed."""
    logs = (
        _period_days(date(2026, 5, 1), symptoms=["cramps"])
        + _period_days(date(2026, 5, 29), symptoms=["cramps"])
        + _period_days(date(2026, 6, 26))
    )

    result = build_trends(logs, today=TODAY)

    assert "acne" not in result["symptoms"]
    assert _statement(result, "acne") is None
    assert _statement(result, "cramps") is not None


def test_every_statement_carries_a_key_and_its_evidence():
    """The contract `/insights/observations` already established.

    `text` is a fallback; a client with a translation renders `key` and
    interpolates `evidence`. That is only possible if every number in the
    sentence is also in the dict.
    """
    logs = (
        _period_days(date(2026, 5, 1), sleep_hours=5, stress_level=2, symptoms=["cramps"])
        + _period_days(date(2026, 5, 29), sleep_hours=8, stress_level=4, symptoms=["cramps"])
        + _period_days(date(2026, 6, 26))
    )

    result = build_trends(logs, today=TODAY)

    assert result["trends"]
    for statement in result["trends"]:
        assert statement["key"].startswith("trends.")
        assert statement["direction"] in {
            DIRECTION_INCREASED,
            DIRECTION_DECREASED,
            DIRECTION_UNCHANGED,
        }
        assert statement["evidence"], statement
        assert statement["text"]

    assert result["disclaimerKey"] == "insights.disclaimer"


def test_the_legacy_fields_still_carry_the_english_sentences():
    """Clients written against the old shape must keep working.

    `sleep`, `stress`, `symptoms` and `notEnoughData` keep their names,
    types and meanings; everything else is additive.
    """
    logs = (
        _period_days(date(2026, 5, 1), sleep_hours=5, stress_level=2, symptoms=["cramps"])
        + _period_days(date(2026, 5, 29), sleep_hours=8, stress_level=4, symptoms=["cramps"])
        + _period_days(date(2026, 6, 26))
    )

    result = build_trends(logs, today=TODAY)

    assert isinstance(result["sleep"], str)
    assert isinstance(result["stress"], str)
    assert isinstance(result["symptoms"], dict)
    assert result["notEnoughData"] is False


def test_stress_direction_follows_the_logged_values():
    logs = (
        _period_days(date(2026, 5, 1), stress_level=4)
        + _period_days(date(2026, 5, 29), stress_level=2)
        + _period_days(date(2026, 6, 26))
    )

    result = build_trends(logs, today=TODAY)

    assert _statement(result, "stress")["direction"] == DIRECTION_DECREASED


# ─── Not enough data ──────────────────────────────────────────────────────


def test_no_logs_at_all_is_not_enough_data():
    result = build_trends([], today=TODAY)

    assert result["notEnoughData"] is True
    assert result["basis"] is None
    assert result["trends"] == []


def test_one_log_is_not_enough_data():
    result = build_trends([_log(date(2026, 6, 1), sleep_hours=7)], today=TODAY)

    assert result["notEnoughData"] is True


def test_two_windows_with_nothing_recorded_in_them_is_not_enough_data():
    """Two windows existing is not the same as having something to say.

    An empty `symptoms` object alongside `notEnoughData: false` would look
    like a successful answer meaning "nothing changed".
    """
    logs = (
        _period_days(date(2026, 5, 1))
        + _period_days(date(2026, 5, 29))
        + _period_days(date(2026, 6, 26))
    )

    result = build_trends(logs, today=TODAY)

    assert result["notEnoughData"] is True
    assert result["trends"] == []
    # The windows were still found, and are still reported.
    assert result["basis"] == BASIS_CYCLE
    assert result["comparedWindows"] is not None


def test_a_user_who_never_logs_flow_still_gets_a_correctly_labelled_answer():
    """Logging sleep and mood but not flow is a normal way to use this app.

    Refusing to say anything would be a worse answer than a
    correctly-labelled one — but the label is what stops it claiming a
    cycle comparison it did not make.
    """
    logs = [
        _log(date(2026, 6, 20) + timedelta(days=offset), sleep_hours=6 + (offset % 3))
        for offset in range(8)
    ]

    result = build_trends(logs, today=TODAY)

    assert result["notEnoughData"] is False
    assert result["basis"] == BASIS_RECENT_LOGS
    assert result["comparedWindows"]["previous"]["loggedDays"] == 4
    assert result["comparedWindows"]["current"]["loggedDays"] == 4


# ─── Input handling ───────────────────────────────────────────────────────


def test_logs_are_re_sorted_rather_than_trusted():
    """`get_logs_for_user` returns newest-first; windows need oldest-first.

    A silently reversed list would invert every trend — "sleep has
    decreased" when it increased — rather than raising.
    """
    ascending = (
        _period_days(date(2026, 5, 1), sleep_hours=5)
        + _period_days(date(2026, 5, 29), sleep_hours=8)
        + _period_days(date(2026, 6, 26))
    )

    forwards = build_trends(ascending, today=TODAY)
    backwards = build_trends(list(reversed(ascending)), today=TODAY)

    assert forwards["trends"] == backwards["trends"]
    assert _statement(forwards, "sleep")["direction"] == DIRECTION_INCREASED


def test_a_duplicated_day_is_not_counted_twice():
    """`upsert_log` cannot produce one, but the legacy `create_log` can.

    Double-counting a day would silently weight it twice in the mean.
    """
    logs = _period_days(date(2026, 6, 20), length=4, sleep_hours=6)
    logs.append(_log(date(2026, 6, 20), flow_intensity="medium", sleep_hours=6))

    records = to_day_records(logs)

    assert len(records) == 4
    assert len({record.day for record in records}) == 4


def test_documents_without_a_start_date_are_skipped_not_crashed_on():
    logs = [
        {"sleep_hours": 7},
        _log(date(2026, 6, 28), sleep_hours=8),
        _log(date(2026, 6, 29), sleep_hours=6),
    ]

    result = build_trends(logs, today=TODAY)

    assert result["notEnoughData"] is False


def test_non_numeric_values_are_ignored_rather_than_averaged():
    """Firestore is schemaless; a string in `sleep_hours` must not crash."""
    logs = [
        _log(date(2026, 6, 27), sleep_hours="eight"),
        _log(date(2026, 6, 28), sleep_hours=8),
        _log(date(2026, 6, 29), sleep_hours=6),
        _log(date(2026, 6, 30), sleep_hours=6),
    ]

    result = build_trends(logs, today=TODAY)

    assert result["notEnoughData"] is False


def test_recent_log_windows_needs_at_least_two_records():
    assert recent_log_windows(to_day_records([_log(date(2026, 6, 1))])) == []
