import { describe, expect, it } from 'vitest';

import type { CyclePhase, DashboardPrediction } from '../api/endpoints';
import {
  PHASE_LABEL_KEY,
  PHASE_TONE,
  cycleLengthDisplay,
  cycleLengthLabelKey,
  phaseLabelKey,
  phaseOf,
  phaseTone,
} from './phase';
import { dashboardFixture, predictionFixture } from '../test/utils';

const prediction = (phase: CyclePhase) =>
  predictionFixture({ phase }) as unknown as DashboardPrediction;

describe('phaseOf', () => {
  it.each<CyclePhase>([
    'period',
    'follicular',
    'ovulation',
    'luteal',
    'late',
    'unknown',
  ])('passes %s through from the server unchanged', (phase) => {
    expect(phaseOf(prediction(phase))).toBe(phase);
  });

  it('reports unknown when the dashboard has not loaded', () => {
    expect(phaseOf(null)).toBe('unknown');
    expect(phaseOf(undefined)).toBe('unknown');
  });

  it('reports unknown for a server that predates the prediction block', () => {
    // An older backend returns `prediction: null`, or one without `phase`.
    // Rendering `undefined` into the pill would be worse than saying so.
    expect(phaseOf({} as DashboardPrediction)).toBe('unknown');
  });

  it('reports unknown for a phase name this client does not know', () => {
    // A phase added server-side before this client ships must not render
    // a raw string like "menopausal" into the pill.
    expect(phaseOf({ phase: 'something_new' } as unknown as DashboardPrediction)).toBe(
      'unknown',
    );
  });
});

describe('phase labels', () => {
  it('has a label key and a tone for every phase the server can return', () => {
    // Typed as a total Record, so this is really asserting that the type
    // and the runtime map have not drifted — a partial map plus an
    // `?? fallback` is how `late` would quietly render as "Luteal" again.
    const phases: CyclePhase[] = [
      'period',
      'follicular',
      'ovulation',
      'luteal',
      'late',
      'unknown',
    ];
    for (const phase of phases) {
      expect(PHASE_LABEL_KEY[phase]).toBeTruthy();
      expect(PHASE_TONE[phase]).toBeTruthy();
    }
  });

  it('gives late its own label rather than folding it into luteal', () => {
    // The bug: `return t('profile.luteal')` was the fallthrough, so day
    // 20, day 40 and day 200 all read "Luteal Phase".
    expect(phaseLabelKey(prediction('late'))).not.toBe(
      phaseLabelKey(prediction('luteal')),
    );
    expect(phaseLabelKey(prediction('late'))).toBe('profile.late');
  });

  it('gives unknown its own label rather than a bare dash', () => {
    expect(phaseLabelKey(null)).toBe('profile.unknown');
  });

  it('styles late and unknown neutrally, not as a warning', () => {
    // Both mean "we cannot tell you where you are", which is about our
    // confidence and not about her health.
    expect(phaseTone(prediction('late'))).toBe('phase-neutral');
    expect(phaseTone(null)).toBe('phase-neutral');
    expect(phaseTone(prediction('ovulation'))).not.toBe('phase-neutral');
  });

  it('maps the serverphase `period` onto the existing menstrual key', () => {
    // The key is named `profile.menstrual` and seven locale files already
    // translate it; the server calls the phase `period`.
    expect(phaseLabelKey(prediction('period'))).toBe('profile.menstrual');
  });
});

describe('cycleLengthDisplay', () => {
  it('prefers the average computed from logged history', () => {
    const display = cycleLengthDisplay(
      dashboardFixture({
        insights: { averageCycleLength: 33, averageBleedingDuration: 5 },
      }) as never,
      { cycle_length: 28 } as never,
    );

    expect(display).toEqual({ days: 33, measured: true });
    expect(cycleLengthLabelKey(display)).toBe('profile.avgCycleLength');
  });

  it('falls back to the declared length and says that is what it is', () => {
    // The bug: a user who declared 28 while logging cycles averaging 33
    // saw "Avg cycle length: 28 days" under a label reading "average".
    const display = cycleLengthDisplay(
      dashboardFixture({ insights: { averageCycleLength: null } }) as never,
      { cycle_length: 30 } as never,
    );

    expect(display).toEqual({ days: 30, measured: false });
    expect(cycleLengthLabelKey(display)).toBe('profile.declaredCycleLength');
  });

  it('never falls through to cycle.total, which defaults to 28', () => {
    // `dashboard.cycle.total` is 28 for a user with no history at all.
    // Showing it in a tile labelled as her average would put a population
    // constant behind a personal label.
    const display = cycleLengthDisplay(
      dashboardFixture({
        insights: { averageCycleLength: null },
        cycle: { day: 3, total: 28, nextPeriodDays: 25 },
      }) as never,
      {} as never,
    );

    expect(display).toEqual({ days: null, measured: false });
  });

  it('shows nothing rather than a number when neither source exists', () => {
    expect(cycleLengthDisplay(null, null)).toEqual({ days: null, measured: false });
  });

  it('ignores a non-finite average rather than rendering NaN', () => {
    const display = cycleLengthDisplay(
      dashboardFixture({ insights: { averageCycleLength: NaN } }) as never,
      { cycle_length: 29 } as never,
    );

    expect(display).toEqual({ days: 29, measured: false });
  });
});
