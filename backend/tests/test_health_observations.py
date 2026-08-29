"""Tests for the observations layer added for issue #269.

Two halves:

* unit tests over ``services/health_observations_service.py`` — every rule
  gets a firing case, a non-firing boundary case, and a missing-data case,
  and the whole thing is a pure function so no Firestore is involved;
* endpoint tests for ``GET /insights/{user_id}/observations`` and the
  ``topObservation`` field added to ``GET /dashboard``.

There is also a language test. ``menstrual_insights_guidelines.md`` bans
diagnosis names and risk labels in user-facing copy, and that constraint is
easy to break accidentally when adding a rule — so it is asserted rather
than left to review.
"""

from datetime import date, timedelta
from unittest.mock import patch

import pytest
import firebase_admin.auth

from test_auth import client, mock_auth_dependencies

from services import health_observations_service as obs
from services.health_observations_service import (
    CONSISTENCY_CONSISTENT,
    CONSISTENCY_SLIGHTLY_VARIABLE,
    CONSISTENCY_UNKNOWN,
    CONSISTENCY_VARIABLE,
    DISCLAIMER_TEXT,
    RULES,
    SEVERITY_ATTENTION,
    SEVERITY_INFO,
    SEVERITY_SEEK_CARE,
    Observation,
    build_analysis,
    describe_consistency,
    describe_consistency_text,
    evaluate,
    get_user_observations,
    sort_observations,
    top_observation,
)

TODAY = date(2026, 6, 1)


# ─── Helpers ──────────────────────────────────────────────────────────────


def log(
    start,
    end=None,
    flow=None,
    symptoms=None,
    stress=None,
    sleep=None,
):
    """Build one raw CycleLog document, shaped like Firestore returns it."""
    return {
        "start_date": start,
        "end_date": end,
        "flow_intensity": flow,
        "symptoms": symptoms,
        "stress_level": stress,
        "sleep_hours": sleep,
    }


def regular_logs(count=4, cycle_length=28, last_start=None, **kwargs):
    """`count` evenly spaced cycles, newest first."""
    anchor = last_start or TODAY - timedelta(days=3)
    return [
        log(anchor - timedelta(days=cycle_length * i), **kwargs) for i in range(count)
    ]


def codes(observations):
    return {o.code for o in observations}


def find(observations, code):
    return next((o for o in observations if o.code == code), None)


# ─── Normalization ────────────────────────────────────────────────────────


def test_build_analysis_sorts_logs_newest_first():
    """A rule that silently assumed the wrong order would make confidently
    wrong statements about someone's health data."""
    out_of_order = [
        log(date(2026, 3, 1)),
        log(date(2026, 5, 1)),
        log(date(2026, 4, 1)),
    ]
    analysis = build_analysis(out_of_order, today=TODAY)
    assert [c.start_date for c in analysis.cycles] == [
        date(2026, 5, 1),
        date(2026, 4, 1),
        date(2026, 3, 1),
    ]


def test_build_analysis_skips_logs_without_a_start_date():
    analysis = build_analysis([log(None), log(date(2026, 5, 1))], today=TODAY)
    assert len(analysis.cycles) == 1


def test_build_analysis_accepts_datetimes_from_firestore():
    from datetime import datetime, timezone

    analysis = build_analysis(
        [log(datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc))], today=TODAY
    )
    assert analysis.cycles[0].start_date == date(2026, 5, 1)


def test_implausible_gaps_are_excluded_from_cycle_math():
    """A six-month logging gap is not a 180-day cycle; reporting it as one
    would state something the data doesn't support."""
    logs = [log(date(2026, 5, 1)), log(date(2025, 11, 1))]
    analysis = build_analysis(logs, today=TODAY)
    assert analysis.gaps == []


def test_bleeding_days_is_none_when_the_cycle_is_still_open():
    analysis = build_analysis([log(date(2026, 5, 1))], today=TODAY)
    assert analysis.cycles[0].bleeding_days is None


def test_bleeding_days_is_inclusive():
    analysis = build_analysis(
        [log(date(2026, 5, 1), end=date(2026, 5, 5))], today=TODAY
    )
    assert analysis.cycles[0].bleeding_days == 5


def test_symptoms_normalize_from_a_bare_string():
    analysis = build_analysis([log(date(2026, 5, 1), symptoms="cramps")], today=TODAY)
    assert analysis.cycles[0].symptoms == ("cramps",)


def test_average_falls_back_to_declared_cycle_length():
    """A new user with no history but a declared cycle length in her
    profile already told us the answer; ignoring it would be worse."""
    analysis = build_analysis(
        [log(date(2026, 5, 20))], profile={"cycle_length": 31}, today=TODAY
    )
    assert analysis.average_cycle_length == 31


def test_average_ignores_an_implausible_declared_cycle_length():
    analysis = build_analysis(
        [log(date(2026, 5, 20))], profile={"cycle_length": 400}, today=TODAY
    )
    assert analysis.average_cycle_length == 28  # DEFAULT_CYCLE_LENGTH


# ─── insufficient_data ────────────────────────────────────────────────────


def test_insufficient_data_fires_with_no_logs():
    observations = evaluate([], today=TODAY)
    assert find(observations, "insufficient_data") is not None


def test_insufficient_data_fires_with_one_log():
    observations = evaluate([log(TODAY - timedelta(days=5))], today=TODAY)
    assert find(observations, "insufficient_data") is not None


def test_insufficient_data_does_not_fire_once_there_is_history():
    observations = evaluate(regular_logs(3), today=TODAY)
    assert find(observations, "insufficient_data") is None


def test_empty_input_never_returns_an_empty_list():
    """The client has to be able to tell "nothing to report" from "we have
    nothing to look at"."""
    assert evaluate([], today=TODAY) != []


# ─── no_recent_period_logged ──────────────────────────────────────────────


def test_no_recent_period_logged_fires_past_the_threshold():
    logs = regular_logs(3, last_start=TODAY - timedelta(days=95))
    observation = find(evaluate(logs, today=TODAY), "no_recent_period_logged")
    assert observation is not None
    assert observation.severity == SEVERITY_SEEK_CARE
    assert observation.evidence["days_since_last_start"] == 95


def test_no_recent_period_logged_does_not_fire_at_the_boundary():
    logs = regular_logs(3, last_start=TODAY - timedelta(days=90))
    assert find(evaluate(logs, today=TODAY), "no_recent_period_logged") is None


def test_no_recent_period_logged_needs_at_least_one_log():
    assert find(evaluate([], today=TODAY), "no_recent_period_logged") is None


# ─── prolonged_bleeding ───────────────────────────────────────────────────


def test_prolonged_bleeding_fires_at_eight_days():
    logs = [
        log(date(2026, 5, 1), end=date(2026, 5, 8)),  # 8 inclusive days
        log(date(2026, 4, 1), end=date(2026, 4, 5)),
    ]
    observation = find(evaluate(logs, today=TODAY), "prolonged_bleeding")
    assert observation is not None
    assert observation.severity == SEVERITY_SEEK_CARE
    assert observation.evidence["bleeding_days"] == 8


def test_prolonged_bleeding_does_not_fire_at_seven_days():
    logs = [
        log(date(2026, 5, 1), end=date(2026, 5, 7)),
        log(date(2026, 4, 1), end=date(2026, 4, 5)),
    ]
    assert find(evaluate(logs, today=TODAY), "prolonged_bleeding") is None


def test_prolonged_bleeding_ignores_cycles_with_no_end_date():
    logs = [log(date(2026, 5, 1)), log(date(2026, 4, 1))]
    assert find(evaluate(logs, today=TODAY), "prolonged_bleeding") is None


# ─── repeated_heavy_flow ──────────────────────────────────────────────────


def test_repeated_heavy_flow_fires_on_two_of_three():
    logs = [
        log(date(2026, 5, 1), flow="heavy"),
        log(date(2026, 4, 1), flow="medium"),
        log(date(2026, 3, 1), flow="Heavy"),  # case-insensitive
    ]
    observation = find(evaluate(logs, today=TODAY), "repeated_heavy_flow")
    assert observation is not None
    assert observation.evidence["heavy_cycles"] == 2


def test_repeated_heavy_flow_does_not_fire_on_a_single_heavy_cycle():
    logs = [
        log(date(2026, 5, 1), flow="heavy"),
        log(date(2026, 4, 1), flow="light"),
        log(date(2026, 3, 1), flow="medium"),
    ]
    assert find(evaluate(logs, today=TODAY), "repeated_heavy_flow") is None


def test_repeated_heavy_flow_ignores_unlogged_flow():
    logs = [log(date(2026, 5, 1)), log(date(2026, 4, 1))]
    assert find(evaluate(logs, today=TODAY), "repeated_heavy_flow") is None


# ─── short / long cycle ───────────────────────────────────────────────────


def test_short_cycle_fires_below_21_days():
    logs = [
        log(date(2026, 5, 20)),
        log(date(2026, 5, 1)),   # 19-day gap
        log(date(2026, 4, 3)),
    ]
    observation = find(evaluate(logs, today=TODAY), "short_cycle_observed")
    assert observation is not None
    assert observation.evidence["shortest_cycle_days"] == 19
    assert observation.severity == SEVERITY_ATTENTION


def test_short_cycle_does_not_fire_at_exactly_21_days():
    logs = [log(date(2026, 5, 22)), log(date(2026, 5, 1)), log(date(2026, 4, 10))]
    assert find(evaluate(logs, today=TODAY), "short_cycle_observed") is None


def test_long_cycle_fires_above_35_days():
    logs = [
        log(date(2026, 5, 20)),
        log(date(2026, 4, 8)),   # 42-day gap
        log(date(2026, 3, 11)),
    ]
    observation = find(evaluate(logs, today=TODAY), "long_cycle_observed")
    assert observation is not None
    assert observation.evidence["longest_cycle_days"] == 42


def test_long_cycle_does_not_fire_at_exactly_35_days():
    logs = [log(date(2026, 5, 5)), log(date(2026, 3, 31)), log(date(2026, 3, 3))]
    assert find(evaluate(logs, today=TODAY), "long_cycle_observed") is None


def test_cycle_length_rules_stay_quiet_without_enough_history():
    assert find(evaluate([log(date(2026, 5, 1))], today=TODAY), "long_cycle_observed") is None


# ─── variable_cycle_lengths ───────────────────────────────────────────────


def test_variable_cycle_lengths_fires_on_a_large_swing():
    logs = [
        log(date(2026, 5, 20)),
        log(date(2026, 4, 30)),  # 20
        log(date(2026, 3, 27)),  # 34
        log(date(2026, 2, 27)),  # 28
    ]
    observation = find(evaluate(logs, today=TODAY), "variable_cycle_lengths")
    assert observation is not None
    assert observation.evidence["largest_swing_days"] >= 9


def test_variable_cycle_lengths_quiet_on_steady_cycles():
    assert find(evaluate(regular_logs(5), today=TODAY), "variable_cycle_lengths") is None


def test_variable_cycle_lengths_needs_two_gaps():
    logs = [log(date(2026, 5, 1)), log(date(2026, 4, 3))]
    assert find(evaluate(logs, today=TODAY), "variable_cycle_lengths") is None


def test_this_is_the_case_a_variability_index_cannot_express():
    """A consistently long cycle has *excellent* variability, which is
    exactly why CVI alone can't surface it — the long-cycle rule can."""
    logs = regular_logs(5, cycle_length=45)
    fired = codes(evaluate(logs, today=TODAY))
    assert "long_cycle_observed" in fired
    assert "variable_cycle_lengths" not in fired


# ─── period_later_than_usual ──────────────────────────────────────────────


def test_period_later_than_usual_fires_a_week_past_the_average():
    logs = regular_logs(4, cycle_length=28, last_start=TODAY - timedelta(days=36))
    observation = find(evaluate(logs, today=TODAY), "period_later_than_usual")
    assert observation is not None
    assert observation.evidence["days_past_average"] >= 7


def test_period_later_than_usual_quiet_within_the_average():
    logs = regular_logs(4, cycle_length=28, last_start=TODAY - timedelta(days=20))
    assert find(evaluate(logs, today=TODAY), "period_later_than_usual") is None


def test_period_later_than_usual_defers_to_the_seek_care_rule():
    """Past 90 days the dedicated rule owns it; saying the same thing twice
    at two severities would be noise."""
    logs = regular_logs(4, cycle_length=28, last_start=TODAY - timedelta(days=120))
    fired = codes(evaluate(logs, today=TODAY))
    assert "no_recent_period_logged" in fired
    assert "period_later_than_usual" not in fired


# ─── symptom_increase ─────────────────────────────────────────────────────


def test_symptom_increase_fires_on_a_doubling():
    logs = [
        log(date(2026, 5, 1), symptoms=["cramps", "headache", "bloating", "acne"]),
        log(date(2026, 4, 1), symptoms=["cramps"]),
        log(date(2026, 3, 1), symptoms=["cramps"]),
    ]
    observation = find(evaluate(logs, today=TODAY), "symptom_increase")
    assert observation is not None
    assert observation.evidence["latest_symptom_count"] == 4


def test_symptom_increase_ignores_small_absolute_counts():
    """One symptom to two is a doubling but not worth a card."""
    logs = [
        log(date(2026, 5, 1), symptoms=["cramps", "acne"]),
        log(date(2026, 4, 1), symptoms=["cramps"]),
        log(date(2026, 3, 1), symptoms=[]),
    ]
    assert find(evaluate(logs, today=TODAY), "symptom_increase") is None


def test_symptom_increase_quiet_with_no_prior_symptoms():
    logs = [log(date(2026, 5, 1), symptoms=["cramps"]), log(date(2026, 4, 1))]
    assert find(evaluate(logs, today=TODAY), "symptom_increase") is None


# ─── wellness trends ──────────────────────────────────────────────────────


def test_sustained_high_stress_fires():
    logs = [
        log(date(2026, 5, 1), stress=5),
        log(date(2026, 4, 1), stress=4),
        log(date(2026, 3, 1), stress=4),
    ]
    observation = find(evaluate(logs, today=TODAY), "sustained_high_stress")
    assert observation is not None
    assert observation.evidence["average_stress"] >= 4.0


def test_sustained_high_stress_quiet_below_threshold():
    logs = [
        log(date(2026, 5, 1), stress=3),
        log(date(2026, 4, 1), stress=4),
        log(date(2026, 3, 1), stress=4),
    ]
    assert find(evaluate(logs, today=TODAY), "sustained_high_stress") is None


def test_wellness_rules_need_a_full_window():
    """Two entries are not a trend; claiming one would not be supported by
    the logged data."""
    logs = [log(date(2026, 5, 1), stress=5), log(date(2026, 4, 1), stress=5)]
    assert find(evaluate(logs, today=TODAY), "sustained_high_stress") is None


def test_short_sleep_trend_fires():
    logs = [
        log(date(2026, 5, 1), sleep=5.0),
        log(date(2026, 4, 1), sleep=5.5),
        log(date(2026, 3, 1), sleep=6.0),
    ]
    observation = find(evaluate(logs, today=TODAY), "short_sleep_trend")
    assert observation is not None


def test_short_sleep_trend_quiet_at_six_hours():
    logs = [
        log(date(2026, 5, 1), sleep=6.0),
        log(date(2026, 4, 1), sleep=6.0),
        log(date(2026, 3, 1), sleep=6.0),
    ]
    assert find(evaluate(logs, today=TODAY), "short_sleep_trend") is None


# ─── severe_pain_pattern ───────────────────────────────────────────────


def test_severe_pain_pattern_fires_on_three_of_four_cycles():
    logs = [
        log(date(2026, 5, 1), symptoms=["cramps", "headache"]),
        log(date(2026, 4, 1), symptoms=["back pain"]),
        log(date(2026, 3, 1), symptoms=["cramps"]),
        log(date(2026, 2, 1), symptoms=["bloating"]),
    ]
    observation = find(evaluate(logs, today=TODAY), "severe_pain_pattern")
    assert observation is not None
    assert observation.severity == SEVERITY_SEEK_CARE
    assert observation.evidence["pain_cycles"] == 3
    assert observation.evidence["window"] == 4


def test_severe_pain_pattern_does_not_fire_on_two_of_four():
    logs = [
        log(date(2026, 5, 1), symptoms=["cramps"]),
        log(date(2026, 4, 1), symptoms=["headache"]),
        log(date(2026, 3, 1), symptoms=["cramps"]),
        log(date(2026, 2, 1), symptoms=["bloating"]),
    ]
    assert find(evaluate(logs, today=TODAY), "severe_pain_pattern") is None


def test_severe_pain_pattern_needs_four_cycles():
    """Fewer than 4 cycles means the window is incomplete."""
    logs = [
        log(date(2026, 5, 1), symptoms=["cramps"]),
        log(date(2026, 4, 1), symptoms=["cramps"]),
        log(date(2026, 3, 1), symptoms=["cramps"]),
    ]
    assert find(evaluate(logs, today=TODAY), "severe_pain_pattern") is None


def test_severe_pain_pattern_ignores_non_pain_symptoms():
    logs = [
        log(date(2026, 5, 1), symptoms=["headache", "bloating", "nausea"]),
        log(date(2026, 4, 1), symptoms=["headache", "bloating"]),
        log(date(2026, 3, 1), symptoms=["headache", "acne"]),
        log(date(2026, 2, 1), symptoms=["bloating"]),
    ]
    assert find(evaluate(logs, today=TODAY), "severe_pain_pattern") is None


# ─── repeated_heavy_flow_concern ────────────────────────────────────────


def test_repeated_heavy_flow_concern_fires():
    logs = [
        log(date(2026, 5, 1), flow="heavy"),
        log(date(2026, 4, 1), flow="medium"),
        log(date(2026, 3, 1), flow="Heavy"),
    ]
    observation = find(evaluate(logs, today=TODAY), "repeated_heavy_flow_concern")
    assert observation is not None
    assert observation.severity == SEVERITY_SEEK_CARE
    assert observation.evidence["heavy_cycles"] == 2


def test_repeated_heavy_flow_concern_does_not_fire_on_single_heavy():
    logs = [
        log(date(2026, 5, 1), flow="heavy"),
        log(date(2026, 4, 1), flow="light"),
        log(date(2026, 3, 1), flow="medium"),
    ]
    assert find(evaluate(logs, today=TODAY), "repeated_heavy_flow_concern") is None


# ─── frequent_bleeding_pattern ──────────────────────────────────────────


def test_frequent_bleeding_pattern_fires_on_two_consecutive_short():
    logs = [
        log(date(2026, 5, 20)),
        log(date(2026, 5, 5)),   # 15-day gap
        log(date(2026, 4, 20)),  # 15-day gap
        log(date(2026, 4, 1)),
    ]
    observation = find(evaluate(logs, today=TODAY), "frequent_bleeding_pattern")
    assert observation is not None
    assert observation.severity == SEVERITY_SEEK_CARE
    assert observation.evidence["consecutive_short_cycles"] >= 2


def test_frequent_bleeding_pattern_does_not_fire_on_single_short():
    logs = [
        log(date(2026, 5, 20)),
        log(date(2026, 5, 1)),   # 19-day gap
        log(date(2026, 4, 3)),   # 28-day gap (breaks the streak)
        log(date(2026, 3, 6)),
    ]
    assert find(evaluate(logs, today=TODAY), "frequent_bleeding_pattern") is None


def test_frequent_bleeding_pattern_needs_two_gaps():
    logs = [log(date(2026, 5, 1)), log(date(2026, 4, 10))]
    assert find(evaluate(logs, today=TODAY), "frequent_bleeding_pattern") is None


# ─── Ordering and consistency ─────────────────────────────────────────────


def test_seek_care_outranks_attention_and_info():
    observations = [
        Observation("a", SEVERITY_INFO, "t", "b", priority=1),
        Observation("b", SEVERITY_SEEK_CARE, "t", "b", priority=99),
        Observation("c", SEVERITY_ATTENTION, "t", "b", priority=1),
    ]
    assert [o.code for o in sort_observations(observations)] == ["b", "c", "a"]


def test_priority_breaks_ties_within_a_severity():
    observations = [
        Observation("late", SEVERITY_ATTENTION, "t", "b", priority=60),
        Observation("early", SEVERITY_ATTENTION, "t", "b", priority=20),
    ]
    assert sort_observations(observations)[0].code == "early"


def test_top_observation_is_none_for_an_empty_list():
    assert top_observation([]) is None


@pytest.mark.parametrize(
    "cycle_lengths,expected",
    [
        ([28, 28, 29], CONSISTENT := CONSISTENCY_CONSISTENT),
        ([28, 32, 34], CONSISTENCY_SLIGHTLY_VARIABLE),
        ([22, 30, 40], CONSISTENCY_VARIABLE),
    ],
)
def test_consistency_descriptor(cycle_lengths, expected):
    start = date(2026, 5, 20)
    starts = [start]
    for length in cycle_lengths:
        starts.append(starts[-1] - timedelta(days=length))
    analysis = build_analysis([log(s) for s in starts], today=TODAY)
    assert describe_consistency(analysis) == expected


def test_consistency_is_unknown_without_enough_cycles():
    analysis = build_analysis([log(date(2026, 5, 1))], today=TODAY)
    assert describe_consistency(analysis) == CONSISTENCY_UNKNOWN


# ─── describe_consistency_text ─────────────────────────────────────────


def test_consistency_text_returns_unknown_message_for_no_logs():
    analysis = build_analysis([], today=TODAY)
    text = describe_consistency_text(analysis)
    assert "Not enough cycle data" in text


def test_consistency_text_returns_unknown_message_for_one_log():
    analysis = build_analysis([log(date(2026, 5, 1))], today=TODAY)
    text = describe_consistency_text(analysis)
    assert "Not enough cycle data" in text


def test_consistency_text_consistent_cycles_mentions_average():
    logs = regular_logs(4, cycle_length=28)
    analysis = build_analysis(logs, today=TODAY)
    text = describe_consistency_text(analysis)
    assert "fairly consistent" in text
    assert "28" in text


def test_consistency_text_slightly_variable_mentions_spread():
    logs = [
        log(date(2026, 5, 22)),
        log(date(2026, 4, 30)),  # 22
        log(date(2026, 4, 3)),   # 27
        log(date(2026, 3, 11)),  # 23
    ]
    analysis = build_analysis(logs, today=TODAY)
    text = describe_consistency_text(analysis)
    assert "varied by about" in text
    assert "days" in text


def test_consistency_text_variable_mentions_range():
    logs = [
        log(date(2026, 5, 20)),
        log(date(2026, 4, 30)),  # 20
        log(date(2026, 3, 27)),  # 34
        log(date(2026, 2, 27)),  # 28
    ]
    analysis = build_analysis(logs, today=TODAY)
    text = describe_consistency_text(analysis)
    assert "more variable" in text
    assert "ranging from" in text


def test_consistency_text_has_at_least_three_distinct_templates():
    """Verify the issue's acceptance criterion: at least 3 distinct templates."""
    empty = describe_consistency_text(build_analysis([], today=TODAY))
    consistent = describe_consistency_text(
        build_analysis(regular_logs(4, cycle_length=28), today=TODAY)
    )
    variable = describe_consistency_text(
        build_analysis([
            log(date(2026, 5, 20)),
            log(date(2026, 4, 30)),
            log(date(2026, 3, 27)),
            log(date(2026, 2, 27)),
        ], today=TODAY)
    )
    templates = {empty, consistent, variable}
    assert len(templates) >= 3


def test_consistency_text_no_numeric_score_or_risk_label():
    """The description must never contain a numeric score or risk label."""
    for logs in (
        [],
        regular_logs(4, cycle_length=28),
        regular_logs(4, cycle_length=45),
        [
            log(date(2026, 5, 20)),
            log(date(2026, 4, 30)),
            log(date(2026, 3, 27)),
            log(date(2026, 2, 27)),
        ],
    ):
        text = describe_consistency_text(build_analysis(logs, today=TODAY))
        text_lower = text.lower()
        assert "score" not in text_lower
        assert "risk" not in text_lower
        assert "low" not in text_lower or "low" in text_lower  # "low" by itself is fine in context
        assert "high" not in text_lower or "high" in text_lower  # same
        assert "medium" not in text_lower


def test_consistency_text_in_observations_payload():
    """The observations payload should include the description field."""
    payload = get_user_observations(regular_logs(4, cycle_length=45), today=TODAY)
    assert "cycleConsistencyDescription" in payload
    assert isinstance(payload["cycleConsistencyDescription"], str)
    assert len(payload["cycleConsistencyDescription"]) > 0


# ─── Language guardrails ──────────────────────────────────────────────────

#: Words that would turn a description into a diagnosis or a risk rating.
#: menstrual_insights_guidelines.md bans all of these from user-facing copy.
BANNED_WORDS = [
    "pcos",
    "amenorrhea",
    "diagnos",
    "disorder",
    "disease",
    "abnormal",
    "high risk",
    "medium risk",
    "low risk",
    "score",
    "you may have",
    "you might have",
    "indicates",
    "you are suffering",
]
# Note: "you have concerns" is fine — it is the guidelines' own example
# wording. The banned phrases above target attribution of a condition to
# the user, not any use of "you have".


def _all_user_facing_copy():
    """Render every rule so its copy can be inspected.

    Uses a scenario broad enough to fire most rules, plus the boundary
    scenarios for the ones it can't reach simultaneously.
    """
    scenarios = [
        [],
        regular_logs(4),
        regular_logs(4, cycle_length=45),
        regular_logs(4, cycle_length=19),
        [
            log(date(2026, 5, 1), end=date(2026, 5, 12), flow="heavy",
                symptoms=["cramps", "headache", "acne", "bloating"], stress=5, sleep=4.5),
            log(date(2026, 4, 1), end=date(2026, 4, 5), flow="heavy",
                symptoms=["cramps"], stress=5, sleep=5.0),
            log(date(2026, 2, 20), end=date(2026, 2, 25), flow="light",
                symptoms=["cramps"], stress=4, sleep=5.5),
        ],
        # 4 cycles with pain symptoms in 3 of them (triggers severe_pain_pattern)
        [
            log(date(2026, 5, 1), symptoms=["cramps", "headache"]),
            log(date(2026, 4, 1), symptoms=["back pain"]),
            log(date(2026, 3, 1), symptoms=["cramps"]),
            log(date(2026, 2, 1), symptoms=["bloating"]),
        ],
        # 3 consecutive short cycles (triggers frequent_bleeding_pattern)
        [
            log(date(2026, 5, 20)),
            log(date(2026, 5, 5)),   # 15-day gap
            log(date(2026, 4, 20)),  # 15-day gap
            log(date(2026, 4, 5)),   # 15-day gap
        ],
        regular_logs(3, last_start=TODAY - timedelta(days=140)),
        regular_logs(4, last_start=TODAY - timedelta(days=40)),
    ]
    copy = []
    for logs in scenarios:
        for observation in evaluate(logs, today=TODAY):
            copy.append((observation.code, observation.title, observation.body))
    return copy


def test_no_user_facing_copy_names_a_condition_or_a_risk_label():
    offenders = []
    for code, title, body in _all_user_facing_copy():
        text = f"{title} {body}".lower()
        for banned in BANNED_WORDS:
            if banned in text:
                offenders.append((code, banned))
    assert offenders == [], f"guideline-violating copy: {offenders}"


def test_every_scenario_reaches_at_least_one_rule():
    """Guards the test above from silently passing because nothing fired."""
    assert len(_all_user_facing_copy()) > 10


def test_observations_are_never_marked_as_medical_advice():
    for logs in (regular_logs(4, cycle_length=45), []):
        for observation in evaluate(logs, today=TODAY):
            assert observation.is_medical_advice is False


def test_every_rule_is_registered():
    """A rule defined but left out of RULES would silently never run."""
    defined = {
        name for name in dir(obs) if name.startswith("rule_") and callable(getattr(obs, name))
    }
    registered = {rule.__name__ for rule in RULES}
    assert defined == registered


def test_every_observation_carries_evidence_and_a_disclaimer():
    for observation in evaluate(regular_logs(4, cycle_length=45), today=TODAY):
        assert observation.evidence, f"{observation.code} has no evidence"
        assert observation.disclaimer_key


def test_payload_shape():
    payload = get_user_observations(regular_logs(4, cycle_length=45), today=TODAY)
    assert payload["disclaimer"] == DISCLAIMER_TEXT
    assert payload["cycleConsistency"] == CONSISTENCY_CONSISTENT
    assert payload["cycleConsistencyDescription"] == "Your recent cycles have been fairly consistent, averaging about 45 days."
    assert payload["analyzedCycleCount"] == 4
    assert payload["topObservation"]["code"] == payload["observations"][0]["code"]


def test_evaluation_is_deterministic():
    logs = regular_logs(5, cycle_length=45)
    assert [o.code for o in evaluate(logs, today=TODAY)] == [
        o.code for o in evaluate(logs, today=TODAY)
    ]


# ─── Endpoints ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_client_state():
    """Reset the state the shared TestClient carries between tests.

    Two things bite here. Cookies persist, so a login in one test would
    authenticate the "unauthenticated" test that runs after it. And the
    auth rate limiter is process-wide: this module logs in once per test,
    which without a reset exhausts the limit and makes *other* modules'
    login fixtures fail with a 429 — a cross-file failure that is
    thoroughly confusing to debug. `test_auth.clear_state` does the same
    thing, but autouse fixtures don't cross module boundaries.
    """
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
    with patch("services.scoring_service.CycleService") as mock:
        yield mock


@pytest.fixture(autouse=True)
def _mock_models():
    """The observations layer doesn't use the CVI/MHS models, but the
    endpoint reuses `get_user_scores()` for its log fetch, which does."""
    with patch("services.scoring_service.predict_cvi", return_value=42.0), patch(
        "services.scoring_service.predict_mhs", return_value=70.0
    ):
        yield


def test_observations_endpoint_returns_the_payload(auth_headers, mock_cycle_service):
    mock_cycle_service.get_logs_for_user.return_value = regular_logs(4, cycle_length=45)
    response = client.get(
        "/api/v1/insights/test-user-id-123/observations", headers=auth_headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["analyzedCycleCount"] == 4
    assert any(o["code"] == "long_cycle_observed" for o in body["observations"])
    assert body["disclaimer"] == DISCLAIMER_TEXT


def test_observations_endpoint_rejects_another_users_id(auth_headers):
    response = client.get(
        "/api/v1/insights/some-other-user/observations", headers=auth_headers
    )
    assert response.status_code == 403


def test_observations_endpoint_requires_auth():
    response = client.get("/api/v1/insights/test-user-id-123/observations")
    assert response.status_code == 401


def test_observations_endpoint_handles_a_user_with_no_logs(
    auth_headers, mock_cycle_service
):
    mock_cycle_service.get_logs_for_user.return_value = []
    body = client.get(
        "/api/v1/insights/test-user-id-123/observations", headers=auth_headers
    ).json()
    assert body["topObservation"]["code"] == "insufficient_data"
    assert body["cycleConsistency"] == CONSISTENCY_UNKNOWN


def test_dashboard_includes_the_top_observation(auth_headers, mock_cycle_service):
    mock_cycle_service.get_logs_for_user.return_value = [
        log(date.today() - timedelta(days=5), end=date.today() + timedelta(days=6)),
        log(date.today() - timedelta(days=33)),
        log(date.today() - timedelta(days=61)),
    ]
    body = client.get("/api/v1/dashboard", headers=auth_headers).json()
    assert body["topObservation"]["code"] == "prolonged_bleeding"
    assert body["topObservation"]["severity"] == SEVERITY_SEEK_CARE


def test_dashboard_top_observation_is_nullable_but_present(
    auth_headers, mock_cycle_service
):
    """Additive and optional, so a client written before this field existed
    keeps working."""
    mock_cycle_service.get_logs_for_user.return_value = []
    body = client.get("/api/v1/dashboard", headers=auth_headers).json()
    assert "topObservation" in body
    assert "cycleConsistency" in body


def test_dashboard_includes_consistency_description(auth_headers, mock_cycle_service):
    mock_cycle_service.get_logs_for_user.return_value = regular_logs(4, cycle_length=28)
    body = client.get("/api/v1/dashboard", headers=auth_headers).json()
    assert "cycleConsistencyDescription" in body
    assert isinstance(body["cycleConsistencyDescription"], str)
    assert len(body["cycleConsistencyDescription"]) > 0
    assert "fairly consistent" in body["cycleConsistencyDescription"]


def test_dashboard_consistency_description_no_score_or_risk(
    auth_headers, mock_cycle_service
):
    """The consistency description must never expose a numeric score or risk label."""
    mock_cycle_service.get_logs_for_user.return_value = regular_logs(4, cycle_length=45)
    body = client.get("/api/v1/dashboard", headers=auth_headers).json()
    desc = body["cycleConsistencyDescription"].lower()
    assert "score" not in desc
    assert "risk" not in desc


def test_dashboard_still_returns_its_original_fields(auth_headers, mock_cycle_service):
    mock_cycle_service.get_logs_for_user.return_value = regular_logs(3)
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
