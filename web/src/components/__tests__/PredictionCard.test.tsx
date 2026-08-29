import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';

import { PredictionCard } from '../PredictionCard';
import { predictionFixture, renderWithProviders } from '../../test/utils';
import type { DashboardPrediction } from '../../api/endpoints';

// The case worth the most here is `overdue`. The dashboard's legacy
// `nextPeriodDays` is `max(avg - day, 0)`, so four days late and due today
// were the same rendered number — the app could not say the one thing a
// tracker exists to say.

function render(prediction: unknown, fallbackDays: number | null = 16) {
  return renderWithProviders(
    <PredictionCard
      prediction={prediction as DashboardPrediction | null}
      fallbackDays={fallbackDays}
    />,
  );
}

describe('a period that is late', () => {
  it('says how many days late instead of showing zero', () => {
    render(predictionFixture({ isOverdue: true, daysOverdue: 4, daysUntilNextPeriod: -4 }));

    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText(/4 days late/i)).toBeInTheDocument();
  });

  it('does not label the count as "next period in"', () => {
    render(predictionFixture({ isOverdue: true, daysOverdue: 2, daysUntilNextPeriod: -2 }));

    expect(screen.queryByText(/next period in/i)).not.toBeInTheDocument();
    expect(screen.getByText(/period is late/i)).toBeInTheDocument();
  });
});

describe('a period that is not late', () => {
  it('counts down the days', () => {
    render(predictionFixture({ daysUntilNextPeriod: 16 }));

    expect(screen.getByText('16')).toBeInTheDocument();
    expect(screen.getByText(/next period in/i)).toBeInTheDocument();
  });

  it('distinguishes due today from a countdown of zero days', () => {
    render(predictionFixture({ daysUntilNextPeriod: 0 }));

    expect(screen.getByText(/expected today/i)).toBeInTheDocument();
  });

  it('shows an em dash rather than a number it does not have', () => {
    render(predictionFixture({ daysUntilNextPeriod: null, nextPeriodDate: null }));

    expect(screen.getByText('—')).toBeInTheDocument();
  });
});

describe('uncertainty', () => {
  it('shows the earliest-to-latest range', () => {
    render(predictionFixture());

    expect(screen.getByText(/Between .* and .*/)).toBeInTheDocument();
  });

  it('omits the range when both ends are the same day', () => {
    // A "range" of one day is a point estimate wearing a range's clothes.
    render(
      predictionFixture({
        predictedRange: { earliest: '2026-05-29', latest: '2026-05-29' },
      }),
    );

    expect(screen.queryByText(/Between/)).not.toBeInTheDocument();
  });

  it('labels the confidence tier', () => {
    render(predictionFixture({ confidence: 'low' }));

    expect(screen.getByText(/low confidence/i)).toBeInTheDocument();
  });

  it('says when the estimate is just the population default', () => {
    // A brand-new user is otherwise looking at 28 days with no way to
    // tell it is an average and not anything about her.
    render(predictionFixture({ estimateSource: 'population_default' }));

    expect(screen.getByText(/typical 28-day cycle/i)).toBeInTheDocument();
  });

  it('says when the estimate comes from her own logs', () => {
    render(predictionFixture({ estimateSource: 'logged_history' }));

    expect(screen.getByText(/your logged cycles/i)).toBeInTheDocument();
  });
});

describe('phase and fertile window', () => {
  it('names the current phase', () => {
    render(predictionFixture({ phase: 'ovulation' }));

    expect(screen.getByText('Ovulation')).toBeInTheDocument();
  });

  it('reports a cycle running long rather than a phase that stopped being true', () => {
    render(predictionFixture({ phase: 'late' }));

    expect(screen.getByText(/running long/i)).toBeInTheDocument();
  });

  it('gives the fertile window real dates', () => {
    // Home previously showed the fixed string "Fertile window + High
    // energy" on every cycle day, which is a claim rather than a reading.
    render(predictionFixture());

    expect(screen.getByText(/Fertile window .* – .*/)).toBeInTheDocument();
    expect(screen.queryByText(/High energy/)).not.toBeInTheDocument();
  });

  it('omits the fertile window when the server did not compute one', () => {
    render(
      predictionFixture({
        fertileWindow: { start: null, end: null, isEstimate: true, notForContraception: true },
      }),
    );

    expect(screen.queryByText(/Fertile window/)).not.toBeInTheDocument();
  });

  it('always carries the not-contraception disclaimer', () => {
    render(predictionFixture());

    expect(screen.getByText(/not medical or contraceptive advice/i)).toBeInTheDocument();
  });
});

describe('a backend without predictions', () => {
  it('falls back to the legacy number rather than showing nothing', () => {
    // A backend from before #272 is still a working backend.
    render(null, 9);

    expect(screen.getByText('9')).toBeInTheDocument();
    expect(screen.getByText(/next period in/i)).toBeInTheDocument();
  });

  it('still carries the disclaimer on the fallback', () => {
    render(null, 9);

    expect(screen.getByText(/not medical or contraceptive advice/i)).toBeInTheDocument();
  });

  it('shows an em dash when there is no fallback either', () => {
    render(null, null);

    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
