"""Cycle prediction: next period, fertile window, phase, confidence.

"When is my next period?" is the most-used feature of any cycle tracker.
Before this module, Rhythma answered it with three lines inside a route
handler (``api/dashboard.py``)::

    if cycle_day is not None:
        next_period_days = max(avg_cycle_length - cycle_day, 0)

where ``avg_cycle_length`` was an unweighted mean of every gap in the last
ten logs. That has five distinct problems, each fixed here:

1. ``max(..., 0)`` means "due today" and "five days late" are the same
   number. Being late is *the* signal a tracker exists to surface, and the
   API could not express it. Here ``days_until_next_period`` goes negative
   and ``is_overdue`` / ``days_overdue`` say so explicitly.
2. An unweighted mean over ten cycles anchors predictions to cycles that
   may be ten months stale. Here recent cycles are weighted higher.
3. One outlier — a missed log, an illness — shifted the mean by ~3 days
   and kept doing so for ten cycles. Here outliers are rejected by median
   absolute deviation before the mean is taken.
4. A point estimate with no uncertainty tells a user with 28/28/29-day
   cycles and a user with 21/34/30-day cycles the same thing with the same
   apparent precision. Here every prediction carries a confidence tier and
   an explicit date range whose width comes from that user's own spread.
5. Onboarding collects ``cycle_length`` and ``last_period`` and the
   estimate ignored them, so a new user with a declared 30-day cycle got
   the hardcoded 28. Here the profile is the fallback before the default.

Plus what did not exist at all: ovulation and the fertile window, and a
phase computation that scales with the user's own cycle length instead of
the fixed day-5/13/16 ladder hardcoded in the Flutter provider.

Everything is a pure function of ``(logs, profile, today)`` — ``today`` is
injectable so tests never depend on the wall clock, and so a scheduled
notification job can ask "what does this look like tomorrow?".

**Not contraceptive guidance.** The fertile window here is a statistical
estimate from logged dates. It is labelled as an estimate in every
response and must never be presented as birth control.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence

from services.scoring_service import DEFAULT_CYCLE_LENGTH, as_date

# ─── Tunables ─────────────────────────────────────────────────────────────

#: Gaps outside this band are treated as data problems (a missed month of
#: logging, a typo'd year) rather than as cycles. Including a 180-day gap
#: as a "cycle" would poison every downstream number.
MIN_PLAUSIBLE_CYCLE_DAYS = 15
MAX_PLAUSIBLE_CYCLE_DAYS = 60

#: Exponential weight decay per cycle going backwards. 0.75 means the most
#: recent cycle counts 4x the one four cycles ago — enough to track a
#: genuine shift within a few months, not so aggressive that one cycle
#: dominates.
RECENCY_DECAY = 0.75

#: Outlier rejection threshold, in scaled median-absolute-deviations.
#: 3.0 is the conventional choice; MAD is used instead of standard
#: deviation precisely because the mean and SD are themselves dragged by
#: the outlier being tested for.
OUTLIER_MAD_THRESHOLD = 3.0

#: 1.4826 scales MAD to be a consistent estimator of the standard
#: deviation for normally distributed data, so the threshold above reads
#: as "three sigma" rather than as an arbitrary constant.
MAD_TO_SIGMA = 1.4826

#: Outlier rejection needs enough points to have a meaningful median.
MIN_CYCLES_FOR_OUTLIER_REJECTION = 4

#: The luteal phase is the stable part of the cycle; nearly all the
#: variation lives in the follicular phase. So ovulation is anchored
#: backwards from the *next* period rather than forwards from the last one.
DEFAULT_LUTEAL_DAYS = 14
MIN_LUTEAL_DAYS = 10

#: Cycles shorter than this get a proportionally shorter luteal phase,
#: otherwise a 21-day cycle would put ovulation on day 7.
SHORT_CYCLE_LUTEAL_THRESHOLD = 25

#: Sperm survive up to ~5 days; the ovum ~24 hours. Hence a window that
#: opens 5 days before ovulation and closes the day after.
FERTILE_DAYS_BEFORE_OVULATION = 5
FERTILE_DAYS_AFTER_OVULATION = 1

#: Confidence tiers. `high` needs both a decent sample and tight spread —
#: a long history of erratic cycles is not high confidence.
HIGH_CONFIDENCE_MIN_CYCLES = 5
HIGH_CONFIDENCE_MAX_SPREAD = 3.0
MEDIUM_CONFIDENCE_MIN_CYCLES = 3
MEDIUM_CONFIDENCE_MAX_SPREAD = 7.0

#: Floor on the predicted-range half-width. Even a perfectly regular user
#: should not be shown a single date as if it were certain.
MIN_RANGE_HALF_WIDTH_DAYS = 2
MAX_RANGE_HALF_WIDTH_DAYS = 14

#: Default assumed bleed length when the profile doesn't say and no log
#: has an end date.
DEFAULT_PERIOD_DAYS = 5

#: How many future periods to project by default. Three is enough for a
#: calendar view and for scheduling reminders without implying we can see
#: further than we can.
DEFAULT_FORECAST_HORIZON = 3

CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"

SOURCE_HISTORY = "logged_history"
SOURCE_PROFILE = "declared_cycle_length"
SOURCE_DEFAULT = "population_default"

PHASE_PERIOD = "period"
PHASE_FOLLICULAR = "follicular"
PHASE_OVULATION = "ovulation"
PHASE_LUTEAL = "luteal"
#: Distinct from luteal on purpose. The Flutter provider's fixed ladder
#: reports "luteal" forever once the day count runs past 16 — so a stale
#: last_period leaves a user pinned in a phase that stopped being true
#: weeks ago. Saying "we don't know, this cycle is running long" is both
#: honest and actionable ("log your period").
PHASE_LATE = "late"
PHASE_UNKNOWN = "unknown"

DISCLAIMER = (
    "Predictions are estimates based on the dates you have logged. They are "
    "not a medical or contraceptive tool."
)


# ─── Types ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CycleLengthEstimate:
    """The estimated cycle length, and how much to trust it."""

    days: int
    source: str
    confidence: str
    #: Number of gaps that survived plausibility and outlier filtering.
    sample_size: int
    #: Typical deviation between the user's cycles, in days. Drives the
    #: width of the predicted range.
    spread_days: float
    #: Gaps discarded as implausible or as outliers, for transparency.
    excluded: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "days": self.days,
            "source": self.source,
            "confidence": self.confidence,
            "sampleSize": self.sample_size,
            "spreadDays": round(self.spread_days, 1),
            "excludedCycleLengths": self.excluded,
        }


@dataclass(frozen=True)
class Prediction:
    """Everything a client needs to render "when is my next period?"."""

    cycle_length: CycleLengthEstimate
    last_period_start: Optional[date]
    current_cycle_day: Optional[int]
    phase: str
    next_period_date: Optional[date]
    #: Negative when overdue. Deliberately not clamped at zero.
    days_until_next_period: Optional[int]
    is_overdue: bool
    days_overdue: int
    predicted_earliest: Optional[date]
    predicted_latest: Optional[date]
    ovulation_date: Optional[date]
    fertile_window_start: Optional[date]
    fertile_window_end: Optional[date]
    upcoming_periods: List[date]
    today: date

    def to_dict(self) -> Dict[str, Any]:
        def iso(value: Optional[date]) -> Optional[str]:
            return value.isoformat() if value else None

        return {
            "today": self.today.isoformat(),
            "cycleLength": self.cycle_length.to_dict(),
            "lastPeriodStart": iso(self.last_period_start),
            "currentCycleDay": self.current_cycle_day,
            "phase": self.phase,
            "nextPeriodDate": iso(self.next_period_date),
            "daysUntilNextPeriod": self.days_until_next_period,
            "isOverdue": self.is_overdue,
            "daysOverdue": self.days_overdue,
            "predictedRange": {
                "earliest": iso(self.predicted_earliest),
                "latest": iso(self.predicted_latest),
            },
            "ovulation": {
                "date": iso(self.ovulation_date),
                "isEstimate": True,
            },
            "fertileWindow": {
                "start": iso(self.fertile_window_start),
                "end": iso(self.fertile_window_end),
                "isEstimate": True,
                "notForContraception": True,
            },
            "upcomingPeriods": [d.isoformat() for d in self.upcoming_periods],
            "confidence": self.cycle_length.confidence,
            "disclaimer": DISCLAIMER,
        }


# ─── Cycle length estimation ──────────────────────────────────────────────


def observed_gaps(logs: Sequence[Dict[str, Any]]) -> List[int]:
    """Day counts between consecutive period starts, most recent first.

    Re-sorts defensively rather than trusting the caller's ordering: every
    number downstream depends on this, and a silently reversed list would
    produce confidently wrong predictions rather than an error.
    """
    starts = sorted(
        {d for d in (as_date(log.get("start_date")) for log in logs or []) if d},
        reverse=True,
    )
    return [(newer - older).days for newer, older in zip(starts, starts[1:])]


def reject_outliers(gaps: Sequence[int]) -> tuple[List[int], List[int]]:
    """Split gaps into (kept, rejected) using median absolute deviation.

    Why MAD and not standard deviation: the SD is itself inflated by the
    outlier you are trying to find, so a single 60-day gap widens the
    threshold enough to include itself. The median and MAD are unaffected
    by up to half the sample being extreme.
    """
    plausible = [
        gap for gap in gaps if MIN_PLAUSIBLE_CYCLE_DAYS <= gap <= MAX_PLAUSIBLE_CYCLE_DAYS
    ]
    implausible = [gap for gap in gaps if gap not in plausible]

    if len(plausible) < MIN_CYCLES_FOR_OUTLIER_REJECTION:
        # Too few points for a median to mean anything; keep them all
        # rather than discarding real data on a guess.
        return plausible, implausible

    median = statistics.median(plausible)
    deviations = [abs(gap - median) for gap in plausible]
    mad = statistics.median(deviations)

    if mad == 0:
        # Every cycle identical apart from possibly one. Fall back to a
        # small absolute tolerance so a lone 40 among 28s is still caught.
        kept = [gap for gap in plausible if abs(gap - median) <= MIN_RANGE_HALF_WIDTH_DAYS]
        rejected = [gap for gap in plausible if gap not in kept]
        return kept, implausible + rejected

    limit = OUTLIER_MAD_THRESHOLD * mad * MAD_TO_SIGMA
    kept = [gap for gap in plausible if abs(gap - median) <= limit]
    rejected = [gap for gap in plausible if abs(gap - median) > limit]
    return kept, implausible + rejected


def weighted_mean(values: Sequence[float], decay: float = RECENCY_DECAY) -> float:
    """Exponentially weighted mean, ``values[0]`` being the most recent."""
    if not values:
        raise ValueError("weighted_mean requires at least one value")
    weights = [decay**index for index in range(len(values))]
    return sum(v * w for v, w in zip(values, weights)) / sum(weights)


def spread_of(values: Sequence[float]) -> float:
    """A robust dispersion measure, in days.

    Scaled MAD rather than the standard deviation, for the same reason as
    in :func:`reject_outliers`, and it degrades sensibly on tiny samples:
    two cycles give half their difference, one gives zero.

    MAD alone is *too* robust for this particular job. It is a median of
    deviations, so for a genuinely erratic user — 21, 34, 24, 22 — it
    reports ~2 days, because three of the four cycles sit close together.
    That would hand a user whose cycles range across two weeks the same
    narrow prediction window as a perfectly regular one, which is the
    false-precision problem this whole module exists to fix.

    So the result is the larger of the robust estimate and a quarter of
    the observed range. For a health prediction, erring wide is the right
    direction: a window that turns out to be conservative is far less
    harmful than a date presented with unearned confidence.
    """
    if len(values) < 2:
        return 0.0
    median = statistics.median(values)
    mad = statistics.median([abs(value - median) for value in values])
    quarter_range = (max(values) - min(values)) / 4

    if mad == 0:
        # Identical (or near-identical) cycles: MAD says nothing, so fall
        # back to the range alone.
        return (max(values) - min(values)) / 2

    return max(mad * MAD_TO_SIGMA, quarter_range)


def _confidence_for(sample_size: int, spread: float) -> str:
    if sample_size >= HIGH_CONFIDENCE_MIN_CYCLES and spread <= HIGH_CONFIDENCE_MAX_SPREAD:
        return CONFIDENCE_HIGH
    if (
        sample_size >= MEDIUM_CONFIDENCE_MIN_CYCLES
        and spread <= MEDIUM_CONFIDENCE_MAX_SPREAD
    ):
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_LOW


def estimate_cycle_length(
    logs: Sequence[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
) -> CycleLengthEstimate:
    """Best available cycle-length estimate, with its provenance.

    Falls back in a defined order — weighted history, then the length the
    user declared during onboarding, then the population default — and
    reports which one was used, so the UI can say "based on your last 6
    cycles" rather than presenting a guess and a measurement identically.
    """
    profile = profile or {}
    gaps = observed_gaps(logs)
    kept, rejected = reject_outliers(gaps)

    if kept:
        spread = spread_of(kept)
        return CycleLengthEstimate(
            days=max(
                MIN_PLAUSIBLE_CYCLE_DAYS,
                min(MAX_PLAUSIBLE_CYCLE_DAYS, round(weighted_mean(kept))),
            ),
            source=SOURCE_HISTORY,
            confidence=_confidence_for(len(kept), spread),
            sample_size=len(kept),
            spread_days=spread,
            excluded=sorted(rejected),
        )

    declared = profile.get("cycle_length")
    if (
        isinstance(declared, (int, float))
        and MIN_PLAUSIBLE_CYCLE_DAYS <= declared <= MAX_PLAUSIBLE_CYCLE_DAYS
    ):
        return CycleLengthEstimate(
            days=int(declared),
            source=SOURCE_PROFILE,
            # Self-reported and unverified — never better than low.
            confidence=CONFIDENCE_LOW,
            sample_size=0,
            spread_days=0.0,
            excluded=sorted(rejected),
        )

    return CycleLengthEstimate(
        days=DEFAULT_CYCLE_LENGTH,
        source=SOURCE_DEFAULT,
        confidence=CONFIDENCE_LOW,
        sample_size=0,
        spread_days=0.0,
        excluded=sorted(rejected),
    )


# ─── Derived dates ────────────────────────────────────────────────────────


def luteal_length_for(cycle_length: int) -> int:
    """Luteal phase length, shortened proportionally for short cycles.

    A flat 14 days would place ovulation on day 7 of a 21-day cycle, which
    is earlier than is plausible. Below the threshold the luteal phase is
    scaled down instead, with a floor.
    """
    if cycle_length >= SHORT_CYCLE_LUTEAL_THRESHOLD:
        return DEFAULT_LUTEAL_DAYS
    return max(MIN_LUTEAL_DAYS, cycle_length - 11)


def range_half_width(estimate: CycleLengthEstimate) -> int:
    """How wide the "earliest to latest" window should be, in days.

    Derived from the user's own spread, so an erratic history produces a
    visibly wider window rather than a falsely precise date. Bounded at
    both ends: never a single certain-looking day, never so wide as to be
    useless.
    """
    derived = round(estimate.spread_days) if estimate.spread_days else 0
    if estimate.source != SOURCE_HISTORY:
        # No logged history to measure spread from — be visibly uncertain.
        derived = max(derived, 4)
    return max(MIN_RANGE_HALF_WIDTH_DAYS, min(MAX_RANGE_HALF_WIDTH_DAYS, derived))


def phase_for(
    cycle_day: Optional[int],
    cycle_length: int,
    period_days: int,
    ovulation_day: int,
) -> str:
    """Phase name, with boundaries scaled to this user's cycle length.

    The Flutter provider hardcodes 5/13/16 regardless of cycle length,
    which places ovulation about a week early for a 35-day cycle. These
    boundaries are derived from the estimate instead.
    """
    if cycle_day is None or cycle_day < 1:
        return PHASE_UNKNOWN
    if cycle_day <= period_days:
        return PHASE_PERIOD
    if cycle_day < ovulation_day - 1:
        return PHASE_FOLLICULAR
    if cycle_day <= ovulation_day + 1:
        return PHASE_OVULATION
    if cycle_day <= cycle_length:
        return PHASE_LUTEAL
    return PHASE_LATE


def _period_days_from(
    logs: Sequence[Dict[str, Any]], profile: Dict[str, Any]
) -> int:
    """Typical bleed length: from logs if available, then profile, then default."""
    durations = []
    for log in logs or []:
        start = as_date(log.get("start_date"))
        end = as_date(log.get("end_date"))
        if start and end:
            span = (end - start).days + 1
            if 1 <= span <= 15:
                durations.append(span)

    if durations:
        return round(statistics.median(durations))

    declared = profile.get("period_duration")
    if isinstance(declared, (int, float)) and 1 <= declared <= 15:
        return int(declared)

    return DEFAULT_PERIOD_DAYS


def _last_period_start(
    logs: Sequence[Dict[str, Any]], profile: Dict[str, Any]
) -> Optional[date]:
    """Most recent logged start, falling back to the onboarding answer.

    A user who completed onboarding but has not logged anything yet still
    told us when her last period was; ignoring that would leave the whole
    Home screen empty on day one.
    """
    starts = [as_date(log.get("start_date")) for log in logs or []]
    starts = [start for start in starts if start]
    if starts:
        return max(starts)

    declared = profile.get("last_period")
    if isinstance(declared, str):
        try:
            return date.fromisoformat(declared[:10])
        except ValueError:
            return None
    return as_date(declared)


# ─── Public API ───────────────────────────────────────────────────────────


def predict(
    logs: Sequence[Dict[str, Any]],
    profile: Optional[Dict[str, Any]] = None,
    today: Optional[date] = None,
    horizon: int = DEFAULT_FORECAST_HORIZON,
) -> Prediction:
    """Full prediction for a user, from her logs and profile."""
    profile = dict(profile or {})
    today = today or date.today()

    estimate = estimate_cycle_length(logs, profile)
    last_start = _last_period_start(logs, profile)
    period_days = _period_days_from(logs, profile)

    if last_start is None:
        # Nothing to anchor on. Return the estimate and be explicit that
        # every date is unknown, rather than inventing an anchor.
        return Prediction(
            cycle_length=estimate,
            last_period_start=None,
            current_cycle_day=None,
            phase=PHASE_UNKNOWN,
            next_period_date=None,
            days_until_next_period=None,
            is_overdue=False,
            days_overdue=0,
            predicted_earliest=None,
            predicted_latest=None,
            ovulation_date=None,
            fertile_window_start=None,
            fertile_window_end=None,
            upcoming_periods=[],
            today=today,
        )

    cycle_day = (today - last_start).days + 1
    next_period = last_start + timedelta(days=estimate.days)
    days_until = (next_period - today).days
    # No clamping: negative means late, and that is the single most useful
    # thing this endpoint can say.
    is_overdue = days_until < 0
    days_overdue = -days_until if is_overdue else 0

    half_width = range_half_width(estimate)
    luteal = luteal_length_for(estimate.days)
    ovulation = next_period - timedelta(days=luteal)

    upcoming: List[date] = []
    cursor = next_period
    for _ in range(max(0, horizon)):
        upcoming.append(cursor)
        cursor = cursor + timedelta(days=estimate.days)

    return Prediction(
        cycle_length=estimate,
        last_period_start=last_start,
        current_cycle_day=cycle_day if cycle_day >= 1 else None,
        phase=phase_for(
            cycle_day,
            estimate.days,
            period_days,
            ovulation_day=(ovulation - last_start).days + 1,
        ),
        next_period_date=next_period,
        days_until_next_period=days_until,
        is_overdue=is_overdue,
        days_overdue=days_overdue,
        predicted_earliest=next_period - timedelta(days=half_width),
        predicted_latest=next_period + timedelta(days=half_width),
        ovulation_date=ovulation,
        fertile_window_start=ovulation - timedelta(days=FERTILE_DAYS_BEFORE_OVULATION),
        fertile_window_end=ovulation + timedelta(days=FERTILE_DAYS_AFTER_OVULATION),
        upcoming_periods=upcoming,
        today=today,
    )


def dashboard_summary(prediction: Prediction) -> Dict[str, Any]:
    """The compact subset the Home screen needs.

    Kept separate from ``Prediction.to_dict()`` so the dashboard payload
    doesn't grow a three-cycle forecast and an exclusion list it never
    renders.
    """
    def iso(value: Optional[date]) -> Optional[str]:
        return value.isoformat() if value else None

    return {
        "nextPeriodDate": iso(prediction.next_period_date),
        "daysUntilNextPeriod": prediction.days_until_next_period,
        "isOverdue": prediction.is_overdue,
        "daysOverdue": prediction.days_overdue,
        "phase": prediction.phase,
        "confidence": prediction.cycle_length.confidence,
        "estimateSource": prediction.cycle_length.source,
        "predictedRange": {
            "earliest": iso(prediction.predicted_earliest),
            "latest": iso(prediction.predicted_latest),
        },
        "fertileWindow": {
            "start": iso(prediction.fertile_window_start),
            "end": iso(prediction.fertile_window_end),
            "isEstimate": True,
            "notForContraception": True,
        },
    }


__all__ = [
    "CONFIDENCE_HIGH",
    "CONFIDENCE_LOW",
    "CONFIDENCE_MEDIUM",
    "DISCLAIMER",
    "PHASE_FOLLICULAR",
    "PHASE_LATE",
    "PHASE_LUTEAL",
    "PHASE_OVULATION",
    "PHASE_PERIOD",
    "PHASE_UNKNOWN",
    "SOURCE_DEFAULT",
    "SOURCE_HISTORY",
    "SOURCE_PROFILE",
    "CycleLengthEstimate",
    "Prediction",
    "dashboard_summary",
    "estimate_cycle_length",
    "luteal_length_for",
    "observed_gaps",
    "phase_for",
    "predict",
    "range_half_width",
    "reject_outliers",
    "spread_of",
    "weighted_mean",
]
