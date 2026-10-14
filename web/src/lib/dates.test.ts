import { describe, expect, it } from 'vitest';
import {
  PHASE_COLORS,
  addDays,
  addMonths,
  cycleDayFor,
  daysBetween,
  isSameDay,
  endOfMonth,
  lutealLengthFor,
  monthWindow,
  parseISODate,
  phaseFor,
  startOfMonth,
  toISODate,
} from './dates';
import type { CyclePhase } from './dates';

// These are local-time helpers with no library behind them, so the failure
// modes are the classic ones: UTC drift, month rollover, and leap days.
// All fixtures are fixed dates — nothing here reads the clock.

describe('toISODate', () => {
  it('pads month and day', () => {
    expect(toISODate(new Date(2026, 0, 5))).toBe('2026-01-05');
  });

  it('uses local components, not UTC', () => {
    // `toISOString()` would report the previous day for anywhere west of
    // Greenwich late in the evening — the bug this helper exists to avoid.
    const lateEvening = new Date(2026, 4, 1, 23, 30);
    expect(toISODate(lateEvening)).toBe('2026-05-01');
  });

  it('handles the last day of a year', () => {
    expect(toISODate(new Date(2026, 11, 31))).toBe('2026-12-31');
  });

  it('handles a leap day', () => {
    expect(toISODate(new Date(2024, 1, 29))).toBe('2024-02-29');
  });
});

describe('parseISODate', () => {
  it('round-trips with toISODate', () => {
    for (const iso of ['2026-01-01', '2024-02-29', '2026-12-31', '2026-07-04']) {
      expect(toISODate(parseISODate(iso))).toBe(iso);
    }
  });

  it('produces a local midnight, not a UTC one', () => {
    const parsed = parseISODate('2026-05-01');
    expect(parsed.getHours()).toBe(0);
    expect(parsed.getDate()).toBe(1);
  });
});

describe('startOfMonth', () => {
  it('returns the first of the month', () => {
    expect(toISODate(startOfMonth(new Date(2026, 4, 17)))).toBe('2026-05-01');
  });

  it('is idempotent', () => {
    const first = startOfMonth(new Date(2026, 4, 17));
    expect(toISODate(startOfMonth(first))).toBe('2026-05-01');
  });
});

describe('addMonths', () => {
  it('moves forward', () => {
    expect(toISODate(addMonths(new Date(2026, 4, 15), 1))).toBe('2026-06-01');
  });

  it('rolls over the year boundary going forward', () => {
    expect(toISODate(addMonths(new Date(2026, 11, 15), 1))).toBe('2027-01-01');
  });

  it('rolls over the year boundary going back', () => {
    expect(toISODate(addMonths(new Date(2026, 0, 15), -1))).toBe('2025-12-01');
  });

  it('does not overflow from a 31-day month into the wrong month', () => {
    // Normalising to the 1st is what makes this safe; a naive
    // setMonth(+1) on Jan 31 lands in March.
    expect(toISODate(addMonths(new Date(2026, 0, 31), 1))).toBe('2026-02-01');
  });
});

describe('isSameDay', () => {
  it('ignores the time of day', () => {
    expect(isSameDay(new Date(2026, 4, 1, 0, 1), new Date(2026, 4, 1, 23, 59))).toBe(true);
  });

  it('distinguishes the same day in different months', () => {
    expect(isSameDay(new Date(2026, 4, 1), new Date(2026, 5, 1))).toBe(false);
  });

  it('distinguishes the same date in different years', () => {
    expect(isSameDay(new Date(2025, 4, 1), new Date(2026, 4, 1))).toBe(false);
  });
});

describe('daysBetween', () => {
  it('counts forward', () => {
    expect(daysBetween(new Date(2026, 4, 1), new Date(2026, 4, 8))).toBe(7);
  });

  it('counts backward as a negative', () => {
    expect(daysBetween(new Date(2026, 4, 8), new Date(2026, 4, 1))).toBe(-7);
  });

  it('is zero for the same day at different times', () => {
    expect(daysBetween(new Date(2026, 4, 1, 1), new Date(2026, 4, 1, 23))).toBe(0);
  });

  it('crosses a month boundary', () => {
    expect(daysBetween(new Date(2026, 3, 28), new Date(2026, 4, 2))).toBe(4);
  });

  it('counts a leap day', () => {
    expect(daysBetween(new Date(2024, 1, 28), new Date(2024, 2, 1))).toBe(2);
  });

  it('survives a DST transition', () => {
    // A naive (b - a) / 86400000 without rounding returns 30.958… across a
    // spring-forward, which floors to the wrong day count.
    expect(daysBetween(new Date(2026, 2, 1), new Date(2026, 3, 1))).toBe(31);
  });
});

describe('cycleDayFor', () => {
  it('is day 1 on the period start date', () => {
    expect(cycleDayFor(new Date(2026, 4, 1), '2026-05-01')).toBe(1);
  });

  it('counts inclusively from the start', () => {
    expect(cycleDayFor(new Date(2026, 4, 15), '2026-05-01')).toBe(15);
  });

  // The two tests that used to sit here asserted the day-of-month
  // fallback, which is the bug in #520 rather than a behaviour worth
  // keeping: it made `phaseFor` paint a five-day period on the 1st to the
  // 5th of every month the user had not logged.

  it('returns null with no last period rather than the day of the month', () => {
    expect(cycleDayFor(new Date(2026, 4, 17), null)).toBeNull();
    expect(cycleDayFor(new Date(2026, 4, 17))).toBeNull();
    expect(cycleDayFor(new Date(2026, 4, 17), '')).toBeNull();
  });

  it('returns null for a date before the last period', () => {
    // One anchor describes the cycle that started on it and the ones
    // after. It says nothing about April.
    expect(cycleDayFor(new Date(2026, 3, 20), '2026-05-01')).toBeNull();
  });

  it('returns null for the day immediately before the anchor', () => {
    // The boundary, and the one most likely to be on screen: 30 April was
    // reported as cycle day 30 — a plausible number, in the luteal phase,
    // for a date a cycle earlier than anything logged.
    expect(cycleDayFor(new Date(2026, 3, 30), '2026-05-01')).toBeNull();
  });

  it('still counts forward across a month boundary', () => {
    expect(cycleDayFor(new Date(2026, 5, 2), '2026-05-01')).toBe(33);
  });
});

describe('phaseFor', () => {
  // Boundaries are now derived the way `prediction_service.phase_for`
  // derives them: ovulation sits at `cycleLength - lutealLength`, and the
  // ovulation phase spans one day either side of it. For a 28-day cycle
  // that is day 14, so days 13–15. The previous fixed 5/13/16 ladder did
  // not vary with cycle length at all, which put ovulation a day late on
  // a 28-day cycle and about a week early on a 35-day one.
  it.each([
    ['2026-05-01', 'period'],
    ['2026-05-05', 'period'],
    ['2026-05-06', 'follicular'],
    ['2026-05-12', 'follicular'],
    ['2026-05-13', 'ovulation'],
    ['2026-05-14', 'ovulation'],
    ['2026-05-15', 'ovulation'],
    ['2026-05-16', 'luteal'],
    ['2026-05-28', 'luteal'],
  ])('maps %s to %s on a 28-day cycle', (iso, expected) => {
    expect(phaseFor(parseISODate(iso), '2026-05-01')).toBe(expected);
  });

  it('has a colour for every phase', () => {
    for (const phase of ['period', 'follicular', 'ovulation', 'luteal', 'late'] as const) {
      expect(PHASE_COLORS[phase]).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });

  it('says a cycle is running long instead of reporting luteal forever', () => {
    // This used to return 'luteal', and the test that asserted it said so
    // outright — "documents current behaviour rather than endorsing it".
    // A stale last period pinned the user in a phase that had stopped
    // being true weeks earlier. "Running long" is both honest and
    // actionable, because the action is to log the period.
    expect(phaseFor(parseISODate('2026-07-15'), '2026-05-01')).toBe('late');
  });

  it('moves ovulation later on a longer cycle', () => {
    // Day 21 of a 35-day cycle: 35 − 14 = 21. On the old fixed ladder
    // that day was already deep into the luteal phase.
    expect(phaseFor(parseISODate('2026-05-21'), '2026-05-01', 35)).toBe('ovulation');
    expect(phaseFor(parseISODate('2026-05-14'), '2026-05-01', 35)).toBe('follicular');
  });

  it('shortens the luteal phase rather than ovulating on day 7', () => {
    // A flat 14-day luteal phase on a 21-day cycle would place ovulation
    // on day 7, which is not plausible. The floor is 10, so day 11.
    expect(lutealLengthFor(21)).toBe(10);
    expect(phaseFor(parseISODate('2026-05-11'), '2026-05-01', 21)).toBe('ovulation');
  });

  it('respects a bleed longer than the default five days', () => {
    expect(phaseFor(parseISODate('2026-05-07'), '2026-05-01', 28, 7)).toBe('period');
  });

  it('falls back to a 28-day cycle when the length is unusable', () => {
    expect(phaseFor(parseISODate('2026-05-14'), '2026-05-01', 0)).toBe('ovulation');
  });
});

// Added with #349: the Cycle calendar now loads a date window per month
// instead of asking for a fixed number of the most recent entries.
describe('month windows', () => {
  it('finds the last day of a 31-day month', () => {
    expect(toISODate(endOfMonth(parseISODate('2026-01-10')))).toBe('2026-01-31');
  });

  it('finds the last day of a 30-day month', () => {
    expect(toISODate(endOfMonth(parseISODate('2026-04-10')))).toBe('2026-04-30');
  });

  it('gets February right in a leap year', () => {
    // The reason this is `day 0 of next month` rather than a lookup table.
    expect(toISODate(endOfMonth(parseISODate('2028-02-10')))).toBe('2028-02-29');
    expect(toISODate(endOfMonth(parseISODate('2026-02-10')))).toBe('2026-02-28');
  });

  it('rolls addDays across a month boundary', () => {
    expect(toISODate(addDays(parseISODate('2026-01-31'), 1))).toBe('2026-02-01');
    expect(toISODate(addDays(parseISODate('2026-03-01'), -1))).toBe('2026-02-28');
  });

  it('rolls addDays across a year boundary', () => {
    expect(toISODate(addDays(parseISODate('2026-12-31'), 1))).toBe('2027-01-01');
  });

  it('brackets the month with margin on both sides', () => {
    const { start, end } = monthWindow(parseISODate('2026-05-14'), 7);

    expect(start).toBe('2026-04-24');
    expect(end).toBe('2026-06-07');
  });

  it('always contains the whole month it was asked for', () => {
    for (let month = 0; month < 12; month++) {
      const { start, end } = monthWindow(new Date(2026, month, 1));
      expect(start <= toISODate(new Date(2026, month, 1))).toBe(true);
      expect(end >= toISODate(endOfMonth(new Date(2026, month, 1)))).toBe(true);
    }
  });

  it('stays inside a single server page', () => {
    // A window wider than MAX_HISTORY_PAGE entries would need paging on
    // every month change, which is the cost this design avoids.
    const { start, end } = monthWindow(parseISODate('2026-01-15'));
    expect(daysBetween(parseISODate(start), parseISODate(end))).toBeLessThan(100);
  });
});

// ─── The calendar does not invent a cycle it has no anchor for (#520) ─────
//
// `cycleDayFor` fell back to `date.getDate()` for any date before the
// anchor as well as for a missing one, and a day-of-month is a perfectly
// well-formed cycle day — so `phaseFor` turned the calendar month into a
// cycle. These assert the shape of the whole rendered month, because the
// bug was not one wrong cell; it was a complete, plausible, invented cycle.

describe('phaseFor before the anchor (issue #520)', () => {
  const ANCHOR = '2026-08-10';

  it('does not paint a period on the first five days of an earlier month', () => {
    // The headline symptom. These rendered `period`, in `#E07AAD` — the
    // same pink as a real logged period, indistinguishable from one.
    for (const day of [1, 2, 3, 4, 5]) {
      const iso = `2026-07-0${day}`;
      expect(phaseFor(parseISODate(iso), ANCHOR)).toBe('unknown');
    }
  });

  it('reports unknown for every day of an earlier month', () => {
    const phases = new Set<string>();
    for (let day = 1; day <= 31; day++) {
      const iso = `2026-07-${String(day).padStart(2, '0')}`;
      phases.add(phaseFor(parseISODate(iso), ANCHOR));
    }
    // Previously this set was {period, follicular, ovulation, luteal} —
    // an entire fabricated cycle, keyed to the calendar month.
    expect([...phases]).toEqual(['unknown']);
  });

  it('reports unknown for the day immediately before the anchor', () => {
    // 9 August rendered as `follicular`, because 9 is the day of the
    // month — the boundary is wrong by a full cycle at exactly the point
    // a user is most likely to be looking.
    expect(phaseFor(parseISODate('2026-08-09'), ANCHOR)).toBe('unknown');
  });

  it('reports unknown when there is no anchor at all', () => {
    expect(phaseFor(parseISODate('2026-07-03'), null)).toBe('unknown');
    expect(phaseFor(parseISODate('2026-07-03'), undefined)).toBe('unknown');
  });

  it('is unchanged on and after the anchor', () => {
    // The regression guard. Everything from the anchor forward must keep
    // behaving exactly as it did.
    expect(phaseFor(parseISODate('2026-08-10'), ANCHOR)).toBe('period');
    expect(phaseFor(parseISODate('2026-08-14'), ANCHOR)).toBe('period');
    expect(phaseFor(parseISODate('2026-08-20'), ANCHOR)).toBe('follicular');
    expect(phaseFor(parseISODate('2026-08-23'), ANCHOR)).toBe('ovulation');
    expect(phaseFor(parseISODate('2026-08-30'), ANCHOR)).toBe('luteal');
    expect(phaseFor(parseISODate('2026-09-20'), ANCHOR)).toBe('late');
  });
});

describe('PHASE_COLORS', () => {
  it('covers every phase', () => {
    // The calendar indexes this map with whatever `phaseFor` returned. A
    // missing entry is `undefined`, which renders as an unstyled cell
    // rather than as an error.
    const phases: CyclePhase[] = [
      'period',
      'follicular',
      'ovulation',
      'luteal',
      'late',
      'unknown',
    ];
    for (const phase of phases) {
      expect(PHASE_COLORS[phase]).toMatch(/^#[0-9A-Fa-f]{6}$/);
    }
  });

  it('does not give unknown a cycle colour', () => {
    // The whole point: a cell we know nothing about must not be tinted
    // like one we do.
    const cycleColours = [
      PHASE_COLORS.period,
      PHASE_COLORS.follicular,
      PHASE_COLORS.ovulation,
      PHASE_COLORS.luteal,
    ];
    expect(cycleColours).not.toContain(PHASE_COLORS.unknown);
  });
});
