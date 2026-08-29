"""Factual, evidence-backed observations derived from a user's own logs.

Why this exists (issue #269): MHS and CVI are *summaries*. A single
scalar cannot tell a user which specific thing in her data is unusual —
and a variability index in particular is structurally blind to the case
that matters most, because a consistently 45-day cycle has excellent
variability while still being worth mentioning to a clinician.

Why it is written the way it is: ``menstrual_insights_guidelines.md``
sets the rules for health messaging in this project, and they are strict.

* "Every insight shown in the app should answer one question: *is this
  statement directly supported by the user's logged data?*" — so this is a
  rule engine over logged values, not a model. Every observation carries
  the numbers that produced it in ``evidence``.
* "The application should describe observations rather than making
  judgments." — so the copy says "your last cycle was 47 days", never
  "your cycle is abnormal", and never names a condition. Rule *codes* like
  ``no_recent_period_logged`` are internal identifiers; the user-facing
  strings never mention amenorrhea, PCOS, or any diagnosis.
* "Avoid risk scores and labels such as High/Medium/Low Risk." — so the
  severity ladder is ``info`` → ``attention`` → ``seek_care``, where the
  top rung is a prompt to talk to a professional rather than a rating.
* The guidelines' "Concerning Symptoms" section names prolonged bleeding
  and very heavy bleeding specifically, and says the app should recommend
  seeking medical advice for them instead of scoring them. Those two are
  the ``seek_care`` rules here.

Everything in this module is a pure function of ``(logs, profile, today)``.
``today`` is injectable so tests never depend on the wall clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Sequence

from services.scoring_service import DEFAULT_CYCLE_LENGTH, as_date

# ─── Thresholds ───────────────────────────────────────────────────────────
#
# Each constant is named and sourced rather than sitting inline, so the
# clinical framing behind a number is reviewable and a future change is a
# one-line edit with a visible rationale.

#: Lower bound of the commonly published normal range for cycle length.
#: Cycles shorter than this are worth *noticing*, not diagnosing.
SHORT_CYCLE_DAYS = 21

#: Upper bound of the same range.
LONG_CYCLE_DAYS = 35

#: Physiologically implausible gaps (a missed month of logging, a data
#: entry slip) are excluded from analysis entirely rather than being
#: reported as a very long cycle — reporting a logging gap as a cycle
#: would violate the "supported by logged data" principle.
MAX_PLAUSIBLE_CYCLE_DAYS = 90
MIN_PLAUSIBLE_CYCLE_DAYS = 15

#: "Bleeding lasting unusually long" from the guidelines' Concerning
#: Symptoms list. Typical periods run 3-7 days, so 8+ is the boundary.
PROLONGED_BLEEDING_DAYS = 8

#: No logged period start in this many days. Chosen at 90 rather than 35
#: so a user who simply forgot to log for a cycle isn't told to see a
#: doctor; three months without a logged start is a different signal.
NO_RECENT_PERIOD_DAYS = 90

#: Swing between two consecutive cycles. Large cycle-to-cycle variation is
#: the pattern users describe as "irregular", and it is invisible in an
#: averaged cycle length.
VARIABLE_CYCLE_SWING_DAYS = 9

#: Cycle-length spread (max - min) boundaries for the descriptive
#: consistency label the guidelines suggest as a summary card.
CONSISTENT_SPREAD_DAYS = 4
SLIGHTLY_VARIABLE_SPREAD_DAYS = 8

#: "Very heavy bleeding" is a Concerning Symptom, but a single heavy
#: cycle is normal for many people; the rule requires a repeated pattern.
HEAVY_FLOW_MIN_OCCURRENCES = 2
HEAVY_FLOW_WINDOW = 3

#: Symptom count multiplier against the prior average before it is worth
#: mentioning. 2x avoids firing on a one-symptom-to-two-symptom change.
SYMPTOM_INCREASE_MULTIPLIER = 2.0
SYMPTOM_INCREASE_MIN_COUNT = 3

#: Stress is logged on a 1-5 scale and sleep in hours; both rules look at
#: a short recent window so they describe "lately", not "ever".
RECENT_WELLNESS_WINDOW = 3
HIGH_STRESS_MEAN = 4.0
SHORT_SLEEP_MEAN_HOURS = 6.0

#: How far past the user's own average a cycle has to run before the app
#: mentions it. A week is late enough to be noticeable and short enough to
#: still be useful.
PERIOD_LATE_DAYS = 7

#: Minimum observations needed before any cycle-length rule can fire.
MIN_CYCLES_FOR_ANALYSIS = 2

# ─── Concerning-symptom thresholds ──────────────────────────────────────
#
# Rules in this group detect symptom patterns that warrant a plain
# recommendation to consult a healthcare professional.  They follow the
# same "simple, directly traceable to logged data" principle as every
# other rule — no model inference, no diagnosis.

#: Symptoms that signal pain when logged repeatedly.  Chosen from the
#: app's current symptom set; "severe pain" as a distinct chip does not
#: yet exist, so we treat frequent pain-related logging as the closest
#: available signal.
PAIN_SYMPTOMS = frozenset({"cramps", "back pain"})

#: How many of the last N cycles must contain a pain symptom before the
#: severe-pain rule fires.  3 out of 4 is a clear repeated pattern.
SEVERE_PAIN_MIN_OCCURRENCES = 3
SEVERE_PAIN_WINDOW = 4

#: Gap between consecutive period starts that is short enough to suggest
#: frequent bleeding.  Cycles shorter than this threshold on their own
#: are already caught by the short-cycle rule; this rule looks for TWO
#: consecutive short gaps, which is a different signal.
FREQUENT_BLEEDING_MAX_GAP_DAYS = 21
FREQUENT_BLEEDING_MIN_CONSECUTIVE = 2

#: Localization key for the disclaimer the guidelines require on every
#: insights surface. The English fallback below is the exact wording from
#: menstrual_insights_guidelines.md.
DISCLAIMER_KEY = "insights.disclaimer"
DISCLAIMER_TEXT = (
    "These insights are based on the information you log and are intended "
    "for personal tracking only. They are not a medical diagnosis and "
    "should not replace advice from a qualified healthcare professional."
)

#: Copy appended to seek_care observations, taken from the guidelines'
#: Concerning Symptoms example.
SEEK_CARE_SUFFIX = (
    "Consider discussing this with a qualified healthcare professional."
)

# ─── Severity ─────────────────────────────────────────────────────────────

SEVERITY_INFO = "info"
SEVERITY_ATTENTION = "attention"
SEVERITY_SEEK_CARE = "seek_care"

#: Explicit ordering, highest last. Used to pick the single observation
#: the Home screen shows. Deliberately not alphabetical and not implicit.
SEVERITY_ORDER: Dict[str, int] = {
    SEVERITY_INFO: 0,
    SEVERITY_ATTENTION: 1,
    SEVERITY_SEEK_CARE: 2,
}

# ─── Consistency descriptors ──────────────────────────────────────────────

CONSISTENCY_UNKNOWN = "unknown"
CONSISTENCY_CONSISTENT = "consistent"
CONSISTENCY_SLIGHTLY_VARIABLE = "slightly_variable"
CONSISTENCY_VARIABLE = "variable"


# ─── Data model ───────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Observation:
    """One factual statement about the user's logged data.

    ``title``/``body`` are English fallbacks; clients that have a
    translation for ``title_key``/``body_key`` should prefer it and
    interpolate ``evidence`` themselves, which is why the numbers are
    exposed structurally instead of only being baked into the string.
    """

    code: str
    severity: str
    title: str
    body: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    #: Tie-breaker within a severity band; lower sorts first.
    priority: int = 100
    is_medical_advice: bool = False
    disclaimer_key: str = DISCLAIMER_KEY

    @property
    def title_key(self) -> str:
        return f"observations.{self.code}.title"

    @property
    def body_key(self) -> str:
        return f"observations.{self.code}.body"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "title": self.title,
            "body": self.body,
            "titleKey": self.title_key,
            "bodyKey": self.body_key,
            "evidence": self.evidence,
            "isMedicalAdvice": self.is_medical_advice,
            "disclaimerKey": self.disclaimer_key,
        }


@dataclass(frozen=True)
class CycleObservationInput:
    """One normalized cycle log, with the derived fields rules need."""

    start_date: date
    end_date: Optional[date]
    bleeding_days: Optional[int]
    flow_intensity: Optional[str]
    symptoms: Sequence[str]
    stress_level: Optional[int]
    sleep_hours: Optional[float]


@dataclass(frozen=True)
class CycleAnalysis:
    """Everything the rules read, computed once.

    Building this up front keeps each rule a small pure function over
    already-normalized data instead of eleven rules each re-deriving
    cycle gaps from raw Firestore documents.
    """

    #: Newest first, matching CycleService.get_logs_for_user.
    cycles: List[CycleObservationInput]
    #: Gaps between consecutive starts, newest gap first, already filtered
    #: to physiologically plausible values.
    gaps: List[int]
    today: date
    profile: Dict[str, Any]

    @property
    def has_enough_cycles(self) -> bool:
        return len(self.gaps) >= 1 and len(self.cycles) >= MIN_CYCLES_FOR_ANALYSIS

    @property
    def average_cycle_length(self) -> int:
        if self.gaps:
            return round(sum(self.gaps) / len(self.gaps))
        declared = self.profile.get("cycle_length")
        if isinstance(declared, int) and MIN_PLAUSIBLE_CYCLE_DAYS <= declared <= MAX_PLAUSIBLE_CYCLE_DAYS:
            return declared
        return DEFAULT_CYCLE_LENGTH

    @property
    def days_since_last_start(self) -> Optional[int]:
        if not self.cycles:
            return None
        return (self.today - self.cycles[0].start_date).days


# ─── Normalization ────────────────────────────────────────────────────────


def _normalize_symptoms(raw: Any) -> Sequence[str]:
    if not raw:
        return ()
    if isinstance(raw, str):
        return (raw,)
    try:
        return tuple(str(item) for item in raw)
    except TypeError:
        return ()


def _bleeding_days(start: Optional[date], end: Optional[date]) -> Optional[int]:
    """Inclusive day count, or None when the cycle is still open.

    Returns None rather than a default so a rule can distinguish "the user
    hasn't logged an end date yet" from "the period lasted one day" — the
    guidelines' principle rules out inventing the difference.
    """
    if start is None or end is None:
        return None
    span = (end - start).days + 1
    return span if span > 0 else None


def build_analysis(
    logs: Sequence[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
    today: Optional[date] = None,
) -> CycleAnalysis:
    """Turn raw CycleLog documents into the view the rules operate on.

    ``logs`` is expected newest-first, the order
    ``CycleService.get_logs_for_user`` returns, but the function re-sorts
    defensively: a rule that silently assumed the wrong order would
    produce confidently wrong statements about the user's health data.
    """
    resolved_today = today or date.today()
    resolved_profile = dict(profile or {})

    normalized: List[CycleObservationInput] = []
    for log in logs or []:
        start = as_date(log.get("start_date"))
        if start is None:
            # Without a start date there is no cycle to describe.
            continue
        end = as_date(log.get("end_date"))
        stress = log.get("stress_level")
        sleep = log.get("sleep_hours")
        normalized.append(
            CycleObservationInput(
                start_date=start,
                end_date=end,
                bleeding_days=_bleeding_days(start, end),
                flow_intensity=(log.get("flow_intensity") or "").lower() or None,
                symptoms=_normalize_symptoms(log.get("symptoms")),
                stress_level=int(stress) if isinstance(stress, (int, float)) else None,
                sleep_hours=float(sleep) if isinstance(sleep, (int, float)) else None,
            )
        )

    normalized.sort(key=lambda c: c.start_date, reverse=True)

    gaps: List[int] = []
    for newer, older in zip(normalized, normalized[1:]):
        delta = (newer.start_date - older.start_date).days
        if MIN_PLAUSIBLE_CYCLE_DAYS <= delta <= MAX_PLAUSIBLE_CYCLE_DAYS:
            gaps.append(delta)

    return CycleAnalysis(
        cycles=normalized,
        gaps=gaps,
        today=resolved_today,
        profile=resolved_profile,
    )


# ─── Rules ────────────────────────────────────────────────────────────────
#
# Each rule takes the analysis and returns an Observation or None. They are
# registered in RULES below, in the order they should be evaluated.


def rule_insufficient_data(analysis: CycleAnalysis) -> Optional[Observation]:
    """Say "not enough yet" explicitly instead of returning nothing.

    An empty list is ambiguous — the client cannot tell "we looked and
    everything is unremarkable" from "we have nothing to look at".
    """
    if analysis.has_enough_cycles:
        return None
    logged = len(analysis.cycles)
    return Observation(
        code="insufficient_data",
        severity=SEVERITY_INFO,
        title="Keep logging to see your patterns",
        body=(
            f"You've logged {logged} "
            f"{'cycle' if logged == 1 else 'cycles'} so far. "
            "Once there are a couple of cycles to compare, this page can "
            "describe your own patterns."
        ),
        evidence={"logged_cycles": logged, "needed": MIN_CYCLES_FOR_ANALYSIS},
        priority=10,
    )


def rule_no_recent_period_logged(analysis: CycleAnalysis) -> Optional[Observation]:
    days = analysis.days_since_last_start
    if days is None or days <= NO_RECENT_PERIOD_DAYS:
        return None
    return Observation(
        code="no_recent_period_logged",
        severity=SEVERITY_SEEK_CARE,
        title="No period logged recently",
        body=(
            f"Your last logged period started {days} days ago. If a period "
            "has happened since then, it may simply need logging. "
            f"If not, {SEEK_CARE_SUFFIX[0].lower()}{SEEK_CARE_SUFFIX[1:]}"
        ),
        evidence={
            "days_since_last_start": days,
            "threshold_days": NO_RECENT_PERIOD_DAYS,
            "last_start_date": analysis.cycles[0].start_date.isoformat(),
        },
        priority=10,
    )


def rule_prolonged_bleeding(analysis: CycleAnalysis) -> Optional[Observation]:
    """Guidelines: "bleeding lasting unusually long" → recommend care."""
    for cycle in analysis.cycles:
        if cycle.bleeding_days is not None and cycle.bleeding_days >= PROLONGED_BLEEDING_DAYS:
            return Observation(
                code="prolonged_bleeding",
                severity=SEVERITY_SEEK_CARE,
                title="A longer period than usual",
                body=(
                    f"You logged {cycle.bleeding_days} days of bleeding "
                    f"starting {cycle.start_date.isoformat()}. "
                    f"{SEEK_CARE_SUFFIX}"
                ),
                evidence={
                    "bleeding_days": cycle.bleeding_days,
                    "threshold_days": PROLONGED_BLEEDING_DAYS,
                    "start_date": cycle.start_date.isoformat(),
                },
                priority=20,
            )
    return None


def rule_repeated_heavy_flow(analysis: CycleAnalysis) -> Optional[Observation]:
    window = analysis.cycles[:HEAVY_FLOW_WINDOW]
    heavy = [c for c in window if c.flow_intensity == "heavy"]
    if len(heavy) < HEAVY_FLOW_MIN_OCCURRENCES:
        return None
    return Observation(
        code="repeated_heavy_flow",
        severity=SEVERITY_ATTENTION,
        title="Heavy flow logged more than once recently",
        body=(
            f"You described your flow as heavy in {len(heavy)} of your last "
            f"{len(window)} logged cycles. If this feels different from "
            "what's normal for you, it's worth mentioning to a healthcare "
            "professional."
        ),
        evidence={
            "heavy_cycles": len(heavy),
            "window": len(window),
            "start_dates": [c.start_date.isoformat() for c in heavy],
        },
        priority=30,
    )


def rule_short_cycle_observed(analysis: CycleAnalysis) -> Optional[Observation]:
    if not analysis.has_enough_cycles:
        return None
    short = [gap for gap in analysis.gaps if gap < SHORT_CYCLE_DAYS]
    if not short:
        return None
    return Observation(
        code="short_cycle_observed",
        severity=SEVERITY_ATTENTION,
        title="A shorter cycle than most",
        body=(
            f"One of your recent cycles was {min(short)} days, shorter than "
            f"the {SHORT_CYCLE_DAYS}-{LONG_CYCLE_DAYS} day range most cycles "
            "fall into. If this is new for you, consider mentioning it at "
            "your next check-up."
        ),
        evidence={
            "shortest_cycle_days": min(short),
            "threshold_days": SHORT_CYCLE_DAYS,
            "occurrences": len(short),
        },
        priority=40,
    )


def rule_long_cycle_observed(analysis: CycleAnalysis) -> Optional[Observation]:
    if not analysis.has_enough_cycles:
        return None
    long_cycles = [gap for gap in analysis.gaps if gap > LONG_CYCLE_DAYS]
    if not long_cycles:
        return None
    return Observation(
        code="long_cycle_observed",
        severity=SEVERITY_ATTENTION,
        title="A longer cycle than most",
        body=(
            f"One of your recent cycles was {max(long_cycles)} days, longer "
            f"than the {SHORT_CYCLE_DAYS}-{LONG_CYCLE_DAYS} day range most "
            "cycles fall into. If this is new for you, consider mentioning "
            "it at your next check-up."
        ),
        evidence={
            "longest_cycle_days": max(long_cycles),
            "threshold_days": LONG_CYCLE_DAYS,
            "occurrences": len(long_cycles),
        },
        priority=40,
    )


def rule_variable_cycle_lengths(analysis: CycleAnalysis) -> Optional[Observation]:
    """Cycle-to-cycle swing, which an averaged length hides completely."""
    if len(analysis.gaps) < 2:
        return None
    swings = [abs(a - b) for a, b in zip(analysis.gaps, analysis.gaps[1:])]
    largest = max(swings)
    if largest < VARIABLE_CYCLE_SWING_DAYS:
        return None
    return Observation(
        code="variable_cycle_lengths",
        severity=SEVERITY_ATTENTION,
        title="Your cycle lengths have varied",
        body=(
            f"Your cycle length has ranged from {min(analysis.gaps)} to "
            f"{max(analysis.gaps)} days across your last "
            f"{len(analysis.gaps)} cycles. If this feels different from "
            "what is normal for you, or you have concerns, consider "
            "discussing it with a healthcare professional."
        ),
        evidence={
            "shortest_cycle_days": min(analysis.gaps),
            "longest_cycle_days": max(analysis.gaps),
            "largest_swing_days": largest,
            "cycles_compared": len(analysis.gaps),
        },
        priority=50,
    )


def rule_period_later_than_usual(analysis: CycleAnalysis) -> Optional[Observation]:
    days = analysis.days_since_last_start
    if days is None or not analysis.gaps:
        return None
    average = analysis.average_cycle_length
    overdue = days - average
    if overdue < PERIOD_LATE_DAYS:
        return None
    # The dedicated seek_care rule owns anything past the 90-day mark;
    # firing both would say the same thing twice at two severities.
    if days > NO_RECENT_PERIOD_DAYS:
        return None
    return Observation(
        code="period_later_than_usual",
        severity=SEVERITY_ATTENTION,
        title="Running later than your usual cycle",
        body=(
            f"It's day {days} of your current cycle, and your recent average "
            f"is {average} days. Cycles vary for lots of everyday reasons."
        ),
        evidence={
            "current_cycle_day": days,
            "average_cycle_days": average,
            "days_past_average": overdue,
        },
        priority=60,
    )


def rule_symptom_increase(analysis: CycleAnalysis) -> Optional[Observation]:
    if len(analysis.cycles) < MIN_CYCLES_FOR_ANALYSIS:
        return None
    latest = len(analysis.cycles[0].symptoms)
    previous = analysis.cycles[1:]
    if not previous:
        return None
    prior_average = sum(len(c.symptoms) for c in previous) / len(previous)
    if latest < SYMPTOM_INCREASE_MIN_COUNT:
        return None
    if prior_average <= 0 or latest < prior_average * SYMPTOM_INCREASE_MULTIPLIER:
        return None
    return Observation(
        code="symptom_increase",
        severity=SEVERITY_INFO,
        title="More symptoms logged this cycle",
        body=(
            f"You logged {latest} symptoms this cycle, compared with an "
            f"average of {prior_average:.1f} in your previous "
            f"{len(previous)} cycles."
        ),
        evidence={
            "latest_symptom_count": latest,
            "previous_average": round(prior_average, 1),
            "cycles_compared": len(previous),
            "symptoms": list(analysis.cycles[0].symptoms),
        },
        priority=70,
    )


def rule_sustained_high_stress(analysis: CycleAnalysis) -> Optional[Observation]:
    values = [
        c.stress_level
        for c in analysis.cycles[:RECENT_WELLNESS_WINDOW]
        if c.stress_level is not None
    ]
    if len(values) < RECENT_WELLNESS_WINDOW:
        return None
    mean = sum(values) / len(values)
    if mean < HIGH_STRESS_MEAN:
        return None
    return Observation(
        code="sustained_high_stress",
        severity=SEVERITY_INFO,
        title="Stress has been high lately",
        body=(
            f"Your logged stress has averaged {mean:.1f} out of 5 across "
            f"your last {len(values)} entries."
        ),
        evidence={
            "average_stress": round(mean, 1),
            "entries": len(values),
            "scale_max": 5,
        },
        priority=80,
    )


def rule_short_sleep_trend(analysis: CycleAnalysis) -> Optional[Observation]:
    values = [
        c.sleep_hours
        for c in analysis.cycles[:RECENT_WELLNESS_WINDOW]
        if c.sleep_hours is not None
    ]
    if len(values) < RECENT_WELLNESS_WINDOW:
        return None
    mean = sum(values) / len(values)
    if mean >= SHORT_SLEEP_MEAN_HOURS:
        return None
    return Observation(
        code="short_sleep_trend",
        severity=SEVERITY_INFO,
        title="Sleep has been on the shorter side",
        body=(
            f"You've logged an average of {mean:.1f} hours of sleep across "
            f"your last {len(values)} entries."
        ),
        evidence={"average_sleep_hours": round(mean, 1), "entries": len(values)},
        priority=90,
    )


# ─── Concerning-symptom rules ──────────────────────────────────────────
#
# These rules detect symptom patterns that warrant a plain recommendation
# to see a healthcare professional.  They follow the same interface as
# every other rule: ``CycleAnalysis`` in, ``Observation`` or ``None`` out.
# The severity is ``seek_care`` because the guidelines' Concerning
# Symptoms section says the app should recommend seeking medical advice
# for these patterns — not scoring them, not naming a condition.


def rule_severe_pain_pattern(analysis: CycleAnalysis) -> Optional[Observation]:
    """Repeated pain symptoms across recent cycles.

    The guidelines name "severe pain" as a Concerning Symptom.  The app
    does not yet offer a "severe pain" chip, so we treat frequent logging
    of pain-related symptoms (cramps, back pain) as the closest available
    signal: if 3 or more of the last 4 cycles include a pain symptom, the
    pattern is worth flagging.
    """
    window = analysis.cycles[:SEVERE_PAIN_WINDOW]
    if len(window) < SEVERE_PAIN_WINDOW:
        return None
    pain_cycles = [
        c for c in window
        if any(s in PAIN_SYMPTOMS for s in c.symptoms)
    ]
    if len(pain_cycles) < SEVERE_PAIN_MIN_OCCURRENCES:
        return None
    return Observation(
        code="severe_pain_pattern",
        severity=SEVERITY_SEEK_CARE,
        title="Pain symptoms logged repeatedly",
        body=(
            f"You logged pain-related symptoms in {len(pain_cycles)} of your "
            f"last {len(window)} cycles. If you are experiencing severe or "
            "persistent pain, please consult a qualified healthcare "
            "professional."
        ),
        evidence={
            "pain_cycles": len(pain_cycles),
            "window": len(window),
            "start_dates": [c.start_date.isoformat() for c in pain_cycles],
            "symptoms_seen": sorted(
                set(
                    s
                    for c in pain_cycles
                    for s in c.symptoms
                    if s in PAIN_SYMPTOMS
                )
            ),
        },
        priority=15,
    )


def rule_repeated_heavy_flow_seek_care(analysis: CycleAnalysis) -> Optional[Observation]:
    """Very heavy bleeding repeated across recent cycles.

    The guidelines name "very heavy bleeding" as a Concerning Symptom.
    The existing ``rule_repeated_heavy_flow`` fires at ``attention``
    severity when heavy flow is logged 2+ times in 3 cycles.  This rule
    upgrades the same pattern to ``seek_care`` when it persists, so the
    user sees a clear recommendation to talk to a professional rather
    than just a note.
    """
    window = analysis.cycles[:HEAVY_FLOW_WINDOW]
    heavy = [c for c in window if c.flow_intensity == "heavy"]
    if len(heavy) < HEAVY_FLOW_MIN_OCCURRENCES:
        return None
    return Observation(
        code="repeated_heavy_flow_concern",
        severity=SEVERITY_SEEK_CARE,
        title="Heavy bleeding may require medical attention",
        body=(
            f"You described your flow as heavy in {len(heavy)} of your last "
            f"{len(window)} logged cycles. Very heavy or prolonged bleeding "
            "can sometimes be a sign that needs checking. "
            "Please consult a qualified healthcare professional."
        ),
        evidence={
            "heavy_cycles": len(heavy),
            "window": len(window),
            "start_dates": [c.start_date.isoformat() for c in heavy],
        },
        priority=25,
    )


def rule_frequent_bleeding_pattern(analysis: CycleAnalysis) -> Optional[Observation]:
    """Two or more consecutive short cycles suggest frequent bleeding.

    A single short cycle is caught by ``rule_short_cycle_observed``; this
    rule looks for consecutive short gaps, which is a different signal
    that may warrant medical attention.
    """
    if len(analysis.gaps) < FREQUENT_BLEEDING_MIN_CONSECUTIVE:
        return None
    consecutive_short = 0
    for gap in analysis.gaps:
        if gap < FREQUENT_BLEEDING_MAX_GAP_DAYS:
            consecutive_short += 1
        else:
            consecutive_short = 0
        if consecutive_short >= FREQUENT_BLEEDING_MIN_CONSECUTIVE:
            break
    if consecutive_short < FREQUENT_BLEEDING_MIN_CONSECUTIVE:
        return None
    return Observation(
        code="frequent_bleeding_pattern",
        severity=SEVERITY_SEEK_CARE,
        title="Cycles have been shorter than usual recently",
        body=(
            f"Your last {consecutive_short} cycles have been shorter than "
            f"{FREQUENT_BLEEDING_MAX_GAP_DAYS} days. Frequent or closely "
            "spaced periods can sometimes need medical attention. "
            "Please consult a qualified healthcare professional."
        ),
        evidence={
            "consecutive_short_cycles": consecutive_short,
            "threshold_days": FREQUENT_BLEEDING_MAX_GAP_DAYS,
            "recent_gaps": analysis.gaps[:consecutive_short],
        },
        priority=35,
    )


#: Evaluation order. Ordering here does not decide what the client shows —
#: `sort_observations` does that from severity and priority — but keeping
#: it stable makes the returned list predictable and diffable in tests.
RULES = (
    rule_insufficient_data,
    rule_no_recent_period_logged,
    rule_prolonged_bleeding,
    rule_severe_pain_pattern,
    rule_repeated_heavy_flow_seek_care,
    rule_frequent_bleeding_pattern,
    rule_repeated_heavy_flow,
    rule_short_cycle_observed,
    rule_long_cycle_observed,
    rule_variable_cycle_lengths,
    rule_period_later_than_usual,
    rule_symptom_increase,
    rule_sustained_high_stress,
    rule_short_sleep_trend,
)


# ─── Public API ───────────────────────────────────────────────────────────


def sort_observations(observations: Sequence[Observation]) -> List[Observation]:
    """Highest severity first, then by explicit rule priority."""
    return sorted(
        observations,
        key=lambda o: (-SEVERITY_ORDER.get(o.severity, 0), o.priority, o.code),
    )


def describe_consistency(analysis: CycleAnalysis) -> str:
    """The descriptive summary-card label the guidelines suggest.

    A word, deliberately — not a score out of 100, and not a risk tier.
    """
    if len(analysis.gaps) < MIN_CYCLES_FOR_ANALYSIS:
        return CONSISTENCY_UNKNOWN
    spread = max(analysis.gaps) - min(analysis.gaps)
    if spread <= CONSISTENT_SPREAD_DAYS:
        return CONSISTENCY_CONSISTENT
    if spread <= SLIGHTLY_VARIABLE_SPREAD_DAYS:
        return CONSISTENCY_SLIGHTLY_VARIABLE
    return CONSISTENCY_VARIABLE


def describe_consistency_text(analysis: CycleAnalysis) -> str:
    """Plain-language description of cycle consistency from real variability data.

    Returns a sentence that references the user's actual cycle lengths and
    variability, not a numeric score or risk label.  At least three distinct
    templates exist so different users see different wording based on their
    data.
    """
    if len(analysis.cycles) < MIN_CYCLES_FOR_ANALYSIS:
        return "Not enough cycle data yet to describe your patterns."

    gaps = analysis.gaps
    if not gaps:
        return "Not enough cycle data yet to describe your patterns."

    spread = max(gaps) - min(gaps)
    count = len(gaps)
    avg = round(sum(gaps) / count)

    if spread <= CONSISTENT_SPREAD_DAYS:
        return (
            f"Your recent cycles have been fairly consistent, "
            f"averaging about {avg} days."
        )

    if spread <= SLIGHTLY_VARIABLE_SPREAD_DAYS:
        return (
            f"Your cycle length has varied by about {spread} days "
            f"over the last {count} cycles."
        )

    return (
        f"Your cycle length has become more variable recently, "
        f"ranging from {min(gaps)} to {max(gaps)} days."
    )


def evaluate(
    logs: Sequence[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
    today: Optional[date] = None,
) -> List[Observation]:
    """Run every rule and return the observations that fired, sorted."""
    analysis = build_analysis(logs, profile=profile, today=today)
    fired = [observation for rule in RULES if (observation := rule(analysis))]
    return sort_observations(fired)


def top_observation(observations: Sequence[Observation]) -> Optional[Observation]:
    """The single observation a compact surface (Home screen) should show."""
    ordered = sort_observations(observations)
    return ordered[0] if ordered else None


def get_user_observations(
    logs: Sequence[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """The full payload the API layer serializes.

    Takes already-fetched logs rather than a ``user_id`` on purpose: the
    dashboard has them in hand from ``get_user_scores()``, and re-fetching
    would double the Firestore reads on the app's hottest path.
    """
    analysis = build_analysis(logs, profile=profile, today=today)
    observations = sort_observations(
        [observation for rule in RULES if (observation := rule(analysis))]
    )
    highest = observations[0] if observations else None

    return {
        "observations": [o.to_dict() for o in observations],
        "topObservation": highest.to_dict() if highest else None,
        "cycleConsistency": describe_consistency(analysis),
        "cycleConsistencyDescription": describe_consistency_text(analysis),
        "averageCycleLength": analysis.average_cycle_length if analysis.gaps else None,
        "analyzedCycleCount": len(analysis.cycles),
        "disclaimer": DISCLAIMER_TEXT,
        "disclaimerKey": DISCLAIMER_KEY,
    }


__all__ = [
    "CONSISTENCY_CONSISTENT",
    "CONSISTENCY_SLIGHTLY_VARIABLE",
    "CONSISTENCY_UNKNOWN",
    "CONSISTENCY_VARIABLE",
    "DISCLAIMER_KEY",
    "DISCLAIMER_TEXT",
    "PAIN_SYMPTOMS",
    "RULES",
    "SEVERITY_ATTENTION",
    "SEVERITY_INFO",
    "SEVERITY_ORDER",
    "SEVERITY_SEEK_CARE",
    "CycleAnalysis",
    "CycleObservationInput",
    "Observation",
    "build_analysis",
    "describe_consistency",
    "describe_consistency_text",
    "evaluate",
    "get_user_observations",
    "sort_observations",
    "top_observation",
]
