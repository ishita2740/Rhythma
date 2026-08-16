"""Period-over-period trends in sleep, stress and symptoms.

``GET /dashboard/trends`` described itself as comparing "the most-recent
logged period with the immediately prior period". What it did was::

    logs = CycleService.get_logs_for_user(user_id)
    recent = logs[0]
    prev = logs[1]

``get_logs_for_user`` returns **per-day documents** — ``upsert_log`` keys
them ``{user_id}_{YYYY-MM-DD}``, one per calendar day. So ``logs[0]`` and
``logs[1]`` were two adjacent *days*, usually yesterday and the day
before, and the endpoint reported::

    "Average sleep has decreased (8h → 6h)."

That sentence is wrong twice over (issue #484). It is not an average — it
is one reading. And it is not a period-over-period comparison — it is
last night against the night before. A user who slept badly once was told
her sleep had declined across the cycle.

A third defect sat next to it: an ``avg()`` helper was defined in the
route and never called. Somebody meant to average over a window, wrote
the helper, never wrote the call site, and the word "Average" reached the
user anyway.

What this module does instead
-----------------------------

**It finds periods, then compares windows between them.** There is no
"this document is a period start" flag in the data — every day-document
carries its own date as ``start_date`` — so a period is reconstructed the
only way the data allows: from logged flow. A run of consecutive bleeding
days is a period; the first day of that run starts a cycle; a cycle
window runs from one start to the day before the next.

**It averages over the window.** Every value in a window contributes.
``previousSamples``/``currentSamples`` travel with each statement so a
reader can tell a fourteen-night average from a single night.

**It says what it compared.** ``basis`` is ``cycle`` when real cycle
windows were found and ``recent_logs`` when they were not — see
``BASIS_RECENT_LOGS`` for why that fallback exists rather than a flat
refusal.

**It emits keys, not just prose.** ``services/health_observations_service``
already established the convention in this codebase: a stable key plus a
structured ``evidence`` dict, with English as a fallback rather than as
the only option. ``ObservationModel``'s docstring states it outright.
Trends predate that convention; this adopts it, so a Tamil user's trends
card can be Tamil.

Everything here is a pure function of ``(logs, today)``. ``today`` is
injectable so tests never depend on the wall clock.

**Not a diagnosis.** These are descriptions of logged values, following
``menstrual_insights_guidelines.md``: no scores, no risk labels, no
condition named.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Sequence

from services.scoring_service import as_date

# ─── Tunables ─────────────────────────────────────────────────────────────

#: Flow values that mean bleeding happened. ``none`` is a value the user
#: chose — "I checked, there was nothing" — and is deliberately not here;
#: treating it as bleeding would invent a period out of a negative answer.
BLEEDING_FLOWS = frozenset({"spotting", "light", "medium", "heavy", "very_heavy"})

#: A missed day inside a period should not split it into two periods. One
#: day of tolerance covers the common "forgot to log on Tuesday" case
#: without merging two genuinely separate bleeds.
PERIOD_RUN_GAP_TOLERANCE_DAYS = 1

#: Two period starts closer together than this are not two cycles. Mid-cycle
#: spotting is the case this guards against: without it, one logged
#: spotting day would end the current cycle and start a phantom short one.
#: Matches ``prediction_service.MIN_PLAUSIBLE_CYCLE_DAYS``.
MIN_DAYS_BETWEEN_PERIOD_STARTS = 15

#: How many logged values a window needs before its mean is called an
#: average in the English fallback. One reading is a reading.
MIN_SAMPLES_FOR_AVERAGE = 2

#: Changes smaller than this are reported as unchanged rather than as a
#: trend. Without it, 7.0h against 7.05h reads as "sleep has increased",
#: which is noise presented as a finding.
SLEEP_MEANINGFUL_DELTA_HOURS = 0.3
STRESS_MEANINGFUL_DELTA = 0.5

#: A symptom has to move by more than this share of days in the window to
#: count as a change. 0.2 means "at least one day in five".
SYMPTOM_MEANINGFUL_DELTA = 0.2

#: The symptoms the dashboard reports on, matching the canonical set
#: ``api/dashboard.py`` already uses for ``symptomFrequency``.
CANONICAL_SYMPTOMS = ("cramps", "headache", "bloating", "acne")

#: When no cycle windows can be found, the logged days are split in half
#: by count instead. See ``BASIS_RECENT_LOGS``.
MIN_LOGS_FOR_RECENT_SPLIT = 2

DIRECTION_INCREASED = "increased"
DIRECTION_DECREASED = "decreased"
DIRECTION_UNCHANGED = "unchanged"

#: Real cycle windows, reconstructed from logged flow.
BASIS_CYCLE = "cycle"

#: No period could be reconstructed — the user logs sleep and mood but has
#: never logged flow, which is a normal way to use this app. Rather than
#: refusing to say anything, the logged days are split in half by count
#: and compared, and ``basis`` reports that this is what happened. The
#: distinction matters: "your last cycle vs the one before" and "your
#: recent logs vs your earlier ones" are different claims, and the old
#: endpoint made the first while doing something closer to the second.
BASIS_RECENT_LOGS = "recent_logs"

DISCLAIMER_KEY = "insights.disclaimer"

DISCLAIMER = (
    "These are descriptions of what you logged, not medical advice."
)


# ─── Types ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DayRecord:
    """One day-document, normalized."""

    day: date
    flow_intensity: Optional[str]
    sleep_hours: Optional[float]
    stress_level: Optional[int]
    symptoms: frozenset

    @property
    def is_bleeding(self) -> bool:
        return self.flow_intensity in BLEEDING_FLOWS


@dataclass(frozen=True)
class Window:
    """A span of days being compared, and the records inside it."""

    start: date
    end: date
    records: List[DayRecord] = field(default_factory=list)

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def values(self, attribute: str) -> List[float]:
        return [
            float(getattr(record, attribute))
            for record in self.records
            if getattr(record, attribute) is not None
        ]

    def mean(self, attribute: str) -> Optional[float]:
        """The average of ``attribute`` across this window, or ``None``.

        This is the call site the route's orphaned ``avg()`` helper never
        got. Every logged value in the window contributes, which is what
        makes the word "average" true.
        """
        values = self.values(attribute)
        return statistics.fmean(values) if values else None

    def symptom_rate(self, symptom: str) -> Optional[float]:
        """Share of *logged* days in this window carrying ``symptom``.

        Denominator is days that recorded a symptom list at all, not
        calendar days: a user who logs on four days out of twenty-eight
        has not thereby reported "no cramps" on the other twenty-four.
        """
        logged = [record for record in self.records if record.symptoms is not None]
        if not logged:
            return None
        return sum(1 for record in logged if symptom in record.symptoms) / len(logged)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "days": self.days,
            "loggedDays": len(self.records),
        }


@dataclass(frozen=True)
class TrendStatement:
    """One comparison, as a key plus the numbers behind it.

    ``text`` is an English fallback, exactly as ``Observation.title``/
    ``body`` are. A client with a translation should render ``key`` and
    interpolate ``evidence`` — which is why every number in the sentence
    is also in the dict.
    """

    metric: str
    direction: str
    key: str
    text: str
    evidence: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "direction": self.direction,
            "key": self.key,
            "text": self.text,
            "evidence": self.evidence,
        }


# ─── Normalization ────────────────────────────────────────────────────────


def _normalize_symptoms(value: Any) -> frozenset:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(
        str(item).strip().lower() for item in value if str(item).strip()
    )


def to_day_records(logs: Sequence[Dict[str, Any]]) -> List[DayRecord]:
    """Normalize raw log documents into ``DayRecord``s, oldest first.

    Sorted here rather than trusting the caller: every window boundary
    below depends on the order, and a silently reversed list would
    produce confidently inverted trends ("sleep has decreased" when it
    increased) rather than an error.
    """
    records: List[DayRecord] = []
    for log in logs or []:
        day = as_date(log.get("start_date"))
        if day is None:
            continue

        sleep = log.get("sleep_hours")
        stress = log.get("stress_level")
        records.append(
            DayRecord(
                day=day,
                flow_intensity=(log.get("flow_intensity") or "").strip().lower() or None,
                sleep_hours=float(sleep) if isinstance(sleep, (int, float)) else None,
                stress_level=int(stress) if isinstance(stress, (int, float)) else None,
                symptoms=_normalize_symptoms(log.get("symptoms")),
            )
        )

    # Deduplicate by day, keeping the last seen. Two documents for one day
    # should not exist — `upsert_log` uses a deterministic id — but a
    # legacy document written by `create_log` could produce one, and
    # double-counting a day would quietly weight it twice in the mean.
    by_day: Dict[date, DayRecord] = {record.day: record for record in records}
    return sorted(by_day.values(), key=lambda record: record.day)


# ─── Finding periods ──────────────────────────────────────────────────────


def period_starts(records: Sequence[DayRecord]) -> List[date]:
    """First day of each logged period, oldest first.

    There is no period-start flag in the data, so this reconstructs one
    from logged flow: a run of bleeding days (tolerating a single missed
    day) is a period, and its first day starts a cycle.

    Starts closer together than ``MIN_DAYS_BETWEEN_PERIOD_STARTS`` are
    merged into the earlier one. Mid-cycle spotting is why: without that
    rule a single logged spotting day would close the current cycle and
    open a phantom one a few days long, which would then be compared
    against a full cycle as though the two were alike.
    """
    bleeding = [record.day for record in records if record.is_bleeding]
    if not bleeding:
        return []

    starts = [bleeding[0]]
    for previous, current in zip(bleeding, bleeding[1:]):
        if (current - previous).days > PERIOD_RUN_GAP_TOLERANCE_DAYS + 1:
            starts.append(current)

    merged = [starts[0]]
    for start in starts[1:]:
        if (start - merged[-1]).days >= MIN_DAYS_BETWEEN_PERIOD_STARTS:
            merged.append(start)
    return merged


def cycle_windows(records: Sequence[DayRecord], today: date) -> List[Window]:
    """Closed cycle windows, oldest first.

    A window runs from one period start to the day before the next. The
    cycle currently in progress is deliberately excluded: it is partial,
    and averaging four days of a new cycle against twenty-eight of the
    last one compares a sample to a population and calls the difference a
    trend.
    """
    starts = period_starts(records)
    if len(starts) < 2:
        return []

    windows: List[Window] = []
    for start, next_start in zip(starts, starts[1:]):
        end = next_start - timedelta(days=1)
        windows.append(
            Window(
                start=start,
                end=end,
                records=[r for r in records if start <= r.day <= end],
            )
        )
    return windows


def recent_log_windows(records: Sequence[DayRecord]) -> List[Window]:
    """Fallback: split the logged days in half by count, older half first.

    For a user who logs sleep and mood but never flow — a normal way to
    use this app — no period can be reconstructed, and refusing to say
    anything at all would be a worse answer than a correctly-labelled
    one. ``basis`` reports that this is what happened, so the response
    never claims a cycle comparison it did not make.
    """
    if len(records) < MIN_LOGS_FOR_RECENT_SPLIT:
        return []

    midpoint = len(records) // 2
    older, newer = records[:midpoint], records[midpoint:]
    if not older or not newer:
        return []

    return [
        Window(start=older[0].day, end=older[-1].day, records=list(older)),
        Window(start=newer[0].day, end=newer[-1].day, records=list(newer)),
    ]


# ─── Building statements ──────────────────────────────────────────────────


def _direction(previous: float, current: float, threshold: float) -> str:
    if abs(current - previous) < threshold:
        return DIRECTION_UNCHANGED
    return DIRECTION_INCREASED if current > previous else DIRECTION_DECREASED


def _numeric_statement(
    metric: str,
    previous_window: Window,
    current_window: Window,
    attribute: str,
    threshold: float,
    unit: str,
    noun: str,
) -> Optional[TrendStatement]:
    """One sleep- or stress-shaped comparison, or ``None`` if unanswerable."""
    previous = previous_window.mean(attribute)
    current = current_window.mean(attribute)
    if previous is None or current is None:
        return None

    previous_samples = len(previous_window.values(attribute))
    current_samples = len(current_window.values(attribute))
    direction = _direction(previous, current, threshold)

    previous_display = round(previous, 1)
    current_display = round(current, 1)

    # "Average" only when it is one. With a single reading in either
    # window the mean *is* that reading, and calling it an average is the
    # specific untruth this issue is about.
    averaged = (
        previous_samples >= MIN_SAMPLES_FOR_AVERAGE
        and current_samples >= MIN_SAMPLES_FOR_AVERAGE
    )
    subject = f"Average {noun}" if averaged else f"Logged {noun}"

    if direction == DIRECTION_UNCHANGED:
        text = f"{subject} is about the same ({current_display}{unit})."
    else:
        text = (
            f"{subject} has {direction} "
            f"({previous_display}{unit} → {current_display}{unit})."
        )

    return TrendStatement(
        metric=metric,
        direction=direction,
        key=f"trends.{metric}.{direction}",
        text=text,
        evidence={
            "previous": previous_display,
            "current": current_display,
            "delta": round(current - previous, 1),
            "unit": unit or None,
            "previousSamples": previous_samples,
            "currentSamples": current_samples,
            "averaged": averaged,
        },
    )


def _symptom_statement(
    symptom: str, previous_window: Window, current_window: Window
) -> Optional[TrendStatement]:
    """How often ``symptom`` was logged, this window against the last.

    A rate, not a yes/no. The predecessor asked "was it present in this
    single document?", which for a symptom logged on three days of a
    seven-day period is a coin flip on which day happened to be newest.
    """
    previous = previous_window.symptom_rate(symptom)
    current = current_window.symptom_rate(symptom)
    if previous is None or current is None:
        return None
    if previous == 0 and current == 0:
        return None

    direction = _direction(previous, current, SYMPTOM_MEANINGFUL_DELTA)
    previous_pct = round(previous * 100)
    current_pct = round(current * 100)

    if direction == DIRECTION_UNCHANGED:
        text = f"Logged on a similar share of days ({current_pct}%)."
    else:
        text = f"Logged on {previous_pct}% of days, now {current_pct}%."

    return TrendStatement(
        metric=symptom,
        direction=direction,
        key=f"trends.symptom.{direction}",
        text=text,
        evidence={
            "symptom": symptom,
            "previousRate": round(previous, 2),
            "currentRate": round(current, 2),
            "previousDays": previous_window.days,
            "currentDays": current_window.days,
        },
    )


# ─── Public API ───────────────────────────────────────────────────────────


def build_trends(
    logs: Sequence[Dict[str, Any]], today: Optional[date] = None
) -> Dict[str, Any]:
    """Compare the two most recent comparable windows of a user's logs.

    Returns the response body for ``GET /dashboard/trends``. The legacy
    ``sleep`` / ``stress`` / ``symptoms`` / ``notEnoughData`` fields are
    preserved exactly where they were so clients written against the old
    shape keep working; everything else is additive.
    """
    resolved_today = today or date.today()
    records = to_day_records(logs)

    windows = cycle_windows(records, resolved_today)
    basis = BASIS_CYCLE
    if len(windows) < 2:
        windows = recent_log_windows(records)
        basis = BASIS_RECENT_LOGS

    if len(windows) < 2:
        return {
            "sleep": None,
            "stress": None,
            "symptoms": {},
            "notEnoughData": True,
            "basis": None,
            "comparedWindows": None,
            "trends": [],
            "disclaimer": DISCLAIMER,
            "disclaimerKey": DISCLAIMER_KEY,
        }

    previous_window, current_window = windows[-2], windows[-1]

    sleep = _numeric_statement(
        "sleep", previous_window, current_window,
        attribute="sleep_hours",
        threshold=SLEEP_MEANINGFUL_DELTA_HOURS,
        unit="h",
        noun="sleep",
    )
    stress = _numeric_statement(
        "stress", previous_window, current_window,
        attribute="stress_level",
        threshold=STRESS_MEANINGFUL_DELTA,
        unit="",
        noun="stress",
    )

    symptom_statements = [
        statement
        for statement in (
            _symptom_statement(symptom, previous_window, current_window)
            for symptom in CANONICAL_SYMPTOMS
        )
        if statement is not None
    ]

    statements = [s for s in (sleep, stress) if s is not None] + symptom_statements

    # Nothing comparable in either window — two windows exist but neither
    # recorded a value for anything. Saying "not enough data" is more use
    # than an empty object that looks like a successful answer.
    if not statements:
        return {
            "sleep": None,
            "stress": None,
            "symptoms": {},
            "notEnoughData": True,
            "basis": basis,
            "comparedWindows": {
                "previous": previous_window.to_dict(),
                "current": current_window.to_dict(),
            },
            "trends": [],
            "disclaimer": DISCLAIMER,
            "disclaimerKey": DISCLAIMER_KEY,
        }

    return {
        "sleep": sleep.text if sleep else None,
        "stress": stress.text if stress else None,
        "symptoms": {s.metric: s.text for s in symptom_statements},
        "notEnoughData": False,
        "basis": basis,
        "comparedWindows": {
            "previous": previous_window.to_dict(),
            "current": current_window.to_dict(),
        },
        "trends": [statement.to_dict() for statement in statements],
        "disclaimer": DISCLAIMER,
        "disclaimerKey": DISCLAIMER_KEY,
    }


__all__ = [
    "BASIS_CYCLE",
    "BASIS_RECENT_LOGS",
    "BLEEDING_FLOWS",
    "CANONICAL_SYMPTOMS",
    "DIRECTION_DECREASED",
    "DIRECTION_INCREASED",
    "DIRECTION_UNCHANGED",
    "DISCLAIMER",
    "DISCLAIMER_KEY",
    "MIN_DAYS_BETWEEN_PERIOD_STARTS",
    "DayRecord",
    "TrendStatement",
    "Window",
    "build_trends",
    "cycle_windows",
    "period_starts",
    "recent_log_windows",
    "to_day_records",
]
