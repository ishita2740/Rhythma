// Descriptive statistics over a user's own logged cycle lengths.
//
// Extracted from ProfilePage (issue #383), where the "Cycle variability"
// tile computed this inline and got it wrong twice over:
//
//   const variability = lengths.length >= 2 && dashboard
//     ? Math.round(lengths.reduce((acc, l) => acc + (l - dashboard.cycle.total) ** 2, 0) / lengths.length)
//     : null;
//   ...
//   value={`±${variability}`}
//
// The squared deviations were never square-rooted, so the units were
// days², printed with a `±` that reads as days. And the centre was
// `dashboard.cycle.total` — the *rounded* average from a different
// calculation, which falls back to a 28-day population default when the
// user has fewer than two logs — rather than the mean of the lengths
// being displayed. Cycles of 26 and 30 showed "±4"; a genuine ±5-day
// spread showed "±25".
//
// It lives here rather than in the page for the reason `dates.ts` does:
// this is arithmetic with a right answer, it is worth testing directly
// without mounting a component, and the next screen that wants to say
// how steady someone's cycles are should not derive it again.
//
// A note on the choice of statistic. Mean absolute deviation is used
// rather than a standard deviation because the label is `±N days` and
// that is what a reader takes it to mean: "my cycles are usually about
// this far from my average". A standard deviation answers a subtly
// different question, and on the handful of cycles a user has logged the
// difference between them is smaller than the difference between either
// and what was being shown before. What matters is that the number is in
// days, measured from this user's own average.

/** Everything the profile screen says about how steady a user's cycles are. */
export interface CycleSpread {
  /** Mean cycle length across the samples, in days, to one decimal. */
  meanDays: number;
  /**
   * Typical distance of a cycle from that mean, in days, to one decimal.
   *
   * Zero for a user whose cycles are all the same length — a real and
   * correct answer, not a missing one.
   */
  spreadDays: number;
  /** How many cycles the two figures above are based on. */
  sampleSize: number;
}

/** Arithmetic mean, or `null` for an empty list. */
export function meanOf(values: readonly number[]): number | null {
  const usable = usableLengths(values);
  if (usable.length === 0) return null;
  return usable.reduce((total, value) => total + value, 0) / usable.length;
}

/**
 * Drop anything that is not a finite, positive number of days.
 *
 * The lengths come from the API as `number`, but a partially-written log
 * or a serialization slip can put a `null` or a `NaN` in the array, and
 * a single one of those turns every figure downstream into `NaN` — which
 * renders as the literal text "±NaN days" rather than as a missing
 * value. Filtering here means one bad entry costs one sample instead of
 * the whole tile.
 */
function usableLengths(values: readonly number[]): number[] {
  return values.filter(
    (value) => typeof value === 'number' && Number.isFinite(value) && value > 0,
  );
}

function roundTo1(value: number): number {
  return Math.round(value * 10) / 10;
}

/**
 * How much this user's cycles vary, measured against her own average.
 *
 * Returns `null` when there is nothing meaningful to report — fewer than
 * two usable cycles. One cycle has no spread, and reporting a figure for
 * it (as the old code did, by measuring that single cycle against a
 * 28-day default the user never declared) states something the data does
 * not support.
 */
export function cycleSpread(lengths: readonly number[]): CycleSpread | null {
  const usable = usableLengths(lengths);
  if (usable.length < 2) return null;

  const mean = usable.reduce((total, value) => total + value, 0) / usable.length;
  const meanAbsoluteDeviation =
    usable.reduce((total, value) => total + Math.abs(value - mean), 0) / usable.length;

  return {
    meanDays: roundTo1(mean),
    spreadDays: roundTo1(meanAbsoluteDeviation),
    sampleSize: usable.length,
  };
}

/**
 * The `±N` string for the profile tile, or `null` when there is none.
 *
 * Formatting is separated from the arithmetic so a caller can render the
 * same figure differently — the unit word is localized and belongs to
 * the component, not to this module.
 */
export function formatSpread(spread: CycleSpread | null): string | null {
  if (spread === null) return null;
  return `±${spread.spreadDays}`;
}
