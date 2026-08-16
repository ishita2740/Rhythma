import { describe, expect, it } from 'vitest';
import { cycleSpread, formatSpread, meanOf, type CycleSpread } from './cycleStats';

// The bug these exist for (issue #383) was arithmetic that produced a
// plausible-looking number: a variance in days², rendered as `±N` and
// measured against a rounded average from a different calculation which
// defaults to 28 when the user has barely any history. Nothing crashed
// and nothing looked obviously wrong on screen — a woman whose cycles
// ran 26 and 30 was simply told "±4".
//
// So most of the cases below assert an exact expected value worked out
// by hand from a fixture, rather than a property like "is a number" or
// "is positive". The old code satisfied both of those.

describe('meanOf', () => {
  it('averages the values', () => {
    expect(meanOf([26, 30])).toBe(28);
  });

  it('does not round', () => {
    // The rounding that belongs to display must not happen in the
    // arithmetic — rounding the centre before measuring distance from it
    // is half of what went wrong before.
    expect(meanOf([28, 29])).toBe(28.5);
  });

  it('returns null for an empty list', () => {
    expect(meanOf([])).toBeNull();
  });

  it('ignores unusable entries', () => {
    expect(meanOf([28, Number.NaN, 30])).toBe(29);
  });
});

describe('cycleSpread', () => {
  it('reports the spread in days, not days squared', () => {
    // The headline case. Cycles of 26 and 30 sit 2 days either side of a
    // 28-day mean. The old code squared those deviations and never took
    // the root, then printed the result as `±4`.
    expect(cycleSpread([26, 30])).toEqual<CycleSpread>({
      meanDays: 28,
      spreadDays: 2,
      sampleSize: 2,
    });
  });

  it('does not grow quadratically as the real spread widens', () => {
    // A genuine ±5 displayed as ±25 under the old arithmetic. The
    // difference between "your cycles are steady" and "something is
    // wrong with me" is exactly this number.
    expect(cycleSpread([23, 33])?.spreadDays).toBe(5);
  });

  it('measures against this user\'s own mean, not a population default', () => {
    // Every one of these is far from 28, and none of them is far from
    // the others. Measured against a 28-day default the answer would be
    // about 7; measured honestly it is 1.
    const spread = cycleSpread([34, 35, 36]);
    expect(spread?.meanDays).toBe(35);
    expect(spread?.spreadDays).toBeCloseTo(0.7, 5);
  });

  it('reports zero spread for perfectly regular cycles', () => {
    // A real answer, not a missing one: this user's cycles do not vary.
    expect(cycleSpread([28, 28, 28])).toEqual<CycleSpread>({
      meanDays: 28,
      spreadDays: 0,
      sampleSize: 3,
    });
  });

  it('rounds both figures to one decimal place', () => {
    const spread = cycleSpread([27, 28, 30]);
    expect(spread?.meanDays).toBe(28.3);
    expect(spread?.spreadDays).toBe(1.1);
  });

  it('returns null for a single cycle', () => {
    // The worst case of the old behaviour: one logged cycle of 35 days
    // was measured against a 28-day default the user never entered and
    // reported as ±49, from a sample with no variability in it at all.
    expect(cycleSpread([35])).toBeNull();
  });

  it('returns null for no cycles', () => {
    expect(cycleSpread([])).toBeNull();
  });

  it('survives a null or NaN in the array', () => {
    // A partially-written log or a serialization slip puts one of these
    // in the list. One bad entry should cost one sample, not turn the
    // tile into the literal text "±NaN days".
    const withHoles = [26, Number.NaN, 30, null as unknown as number, undefined as unknown as number];
    expect(cycleSpread(withHoles)).toEqual<CycleSpread>({
      meanDays: 28,
      spreadDays: 2,
      sampleSize: 2,
    });
  });

  it('returns null when the holes leave fewer than two usable cycles', () => {
    expect(cycleSpread([Number.NaN, 28])).toBeNull();
  });

  it('ignores non-positive lengths', () => {
    // A cycle cannot be zero or negative days long; such a value is
    // corrupt data, and averaging it in would drag the mean somewhere
    // no real cycle is.
    expect(cycleSpread([0, 28, 30, -5])?.sampleSize).toBe(2);
  });

  it('does not mutate its input', () => {
    const lengths = [30, 26, 28];
    cycleSpread(lengths);
    expect(lengths).toEqual([30, 26, 28]);
  });

  it('is order-independent', () => {
    expect(cycleSpread([26, 30, 28])).toEqual(cycleSpread([30, 28, 26]));
  });

  it('handles a long history without drift', () => {
    const lengths = Array.from({ length: 24 }, (_, i) => (i % 2 === 0 ? 27 : 29));
    expect(cycleSpread(lengths)).toEqual<CycleSpread>({
      meanDays: 28,
      spreadDays: 1,
      sampleSize: 24,
    });
  });
});

describe('formatSpread', () => {
  it('prefixes the figure with a plus-minus sign', () => {
    expect(formatSpread(cycleSpread([26, 30]))).toBe('±2');
  });

  it('keeps a fractional day', () => {
    expect(formatSpread(cycleSpread([27, 28, 30]))).toBe('±1.1');
  });

  it('formats a zero spread rather than treating it as absent', () => {
    expect(formatSpread(cycleSpread([28, 28]))).toBe('±0');
  });

  it('returns null when there is nothing to report', () => {
    expect(formatSpread(null)).toBeNull();
  });

  it('leaves the unit to the caller', () => {
    // The word "days" is localized and belongs to the component. This
    // module returns the number and its sign, nothing else.
    expect(formatSpread(cycleSpread([26, 30]))).not.toContain('day');
  });
});
