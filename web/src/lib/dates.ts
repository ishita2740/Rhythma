// Local-time date helpers (no external date library).

export function toISODate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function parseISODate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number);
  return new Date(y, m - 1, d);
}

export function startOfMonth(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

export function addMonths(date: Date, months: number): Date {
  return new Date(date.getFullYear(), date.getMonth() + months, 1);
}

export function endOfMonth(date: Date): Date {
  // Day 0 of the *next* month is the last day of this one, which avoids
  // hardcoding month lengths or a leap-year rule.
  return new Date(date.getFullYear(), date.getMonth() + 1, 0);
}

export function addDays(date: Date, days: number): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
}

/**
 * The inclusive date window the calendar needs loaded to render `month`.
 *
 * Wider than the month itself. A user paging back and forth re-fetches
 * constantly at exact-month granularity, and a log written on the 1st or
 * the 31st sits right on the boundary. A few days of margin each side
 * makes paging feel steadier and costs nothing — the whole window is
 * still comfortably inside a single page.
 */
export function monthWindow(month: Date, marginDays = 7): { start: string; end: string } {
  return {
    start: toISODate(addDays(startOfMonth(month), -marginDays)),
    end: toISODate(addDays(endOfMonth(month), marginDays)),
  };
}

export function isSameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export function daysBetween(a: Date, b: Date): number {
  const ms = new Date(b.getFullYear(), b.getMonth(), b.getDate()).getTime() -
    new Date(a.getFullYear(), a.getMonth(), a.getDate()).getTime();
  return Math.round(ms / 86400000);
}

export function cycleDayFor(date: Date, lastPeriodIso?: string | null): number {
  if (lastPeriodIso) {
    const day = daysBetween(parseISODate(lastPeriodIso), date) + 1;
    if (day >= 1) return day;
  }
  // Fallback matches the Flutter app: day-of-month when no last period set.
  return date.getDate();
}

export type CyclePhase = 'period' | 'follicular' | 'ovulation' | 'luteal' | 'late';

/** Population default, used only when nothing better is known. */
export const DEFAULT_CYCLE_LENGTH = 28;

const DEFAULT_PERIOD_DAYS = 5;
const DEFAULT_LUTEAL_DAYS = 14;
const MIN_LUTEAL_DAYS = 10;
const SHORT_CYCLE_LUTEAL_THRESHOLD = 25;

/**
 * Luteal length, shortened proportionally for short cycles.
 *
 * Mirrors `luteal_length_for` in `backend/services/prediction_service.py`.
 * A flat 14 days would place ovulation on day 7 of a 21-day cycle, which
 * is earlier than is plausible.
 */
export function lutealLengthFor(cycleLength: number): number {
  if (cycleLength >= SHORT_CYCLE_LUTEAL_THRESHOLD) return DEFAULT_LUTEAL_DAYS;
  return Math.max(MIN_LUTEAL_DAYS, cycleLength - 11);
}

/**
 * Which phase a date falls in, scaled to the user's own cycle length.
 *
 * This used to be a fixed day-5/13/16 ladder regardless of cycle length,
 * which is the same hardcoding `prediction_service.phase_for` was written
 * to replace: it puts ovulation about a week early on a 35-day cycle, and
 * — because there was no branch past 16 — it reported `luteal` forever
 * once the count ran off the end, so a stale last period left a user
 * pinned in a phase that stopped being true weeks ago.
 *
 * `late` is that missing branch. Saying "this cycle is running long" is
 * both honest and actionable in a way that a wrong phase name is not.
 *
 * The boundaries are derived the same way the server derives them, so a
 * calendar cell and the outlook card above it cannot disagree.
 */
export function phaseFor(
  date: Date,
  lastPeriodIso?: string | null,
  cycleLength: number = DEFAULT_CYCLE_LENGTH,
  periodDays: number = DEFAULT_PERIOD_DAYS,
): CyclePhase {
  const day = cycleDayFor(date, lastPeriodIso);
  const length = cycleLength > 0 ? cycleLength : DEFAULT_CYCLE_LENGTH;
  const ovulationDay = length - lutealLengthFor(length);

  if (day <= periodDays) return 'period';
  if (day < ovulationDay - 1) return 'follicular';
  if (day <= ovulationDay + 1) return 'ovulation';
  if (day <= length) return 'luteal';
  return 'late';
}

export const PHASE_COLORS: Record<CyclePhase, string> = {
  period: '#E07AAD',
  follicular: '#AA3BFF',
  ovulation: '#52B3B0',
  luteal: '#E8946A',
  // Deliberately muted rather than alarming. Running long is a fact about
  // the log, not a warning.
  late: '#8E8E93',
};

export function formatMonthYear(date: Date): string {
  return date.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
}

export function formatDayMonth(date: Date): string {
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}
