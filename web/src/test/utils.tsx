import type { ReactElement, ReactNode } from 'react';
import { render, type RenderOptions, type RenderResult } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { I18nextProvider } from 'react-i18next';
import i18n from '../i18n';
import { AuthProvider } from '../auth/AuthContext';

/**
 * Render a component inside the providers the real app mounts it under.
 *
 * Without this, every page test would repeat the same three wrappers, and
 * a test that forgot one would fail with "useAuth must be used within an
 * AuthProvider" rather than telling you anything about the component.
 */
interface RenderWithProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  /** Initial history entries for MemoryRouter, e.g. ['/login']. */
  route?: string;
  /** Set false to test a component that must not be wrapped in AuthProvider. */
  withAuth?: boolean;
}

export function renderWithProviders(
  ui: ReactElement,
  { route = '/', withAuth = true, ...options }: RenderWithProvidersOptions = {},
): RenderResult {
  function Wrapper({ children }: { children: ReactNode }) {
    const withinRouter = withAuth ? <AuthProvider>{children}</AuthProvider> : children;
    return (
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={[route]}>{withinRouter}</MemoryRouter>
      </I18nextProvider>
    );
  }

  return render(ui, { wrapper: Wrapper, ...options });
}

/**
 * A minimal axios-shaped error.
 *
 * `friendlyAuthError` branches on `isAxiosError` and on the presence of
 * `response`, so tests need to be able to build both a "server replied
 * with a status" error and a "request never reached the server" error.
 */
export function axiosError(status?: number, detail?: string) {
  return {
    isAxiosError: true,
    response:
      status === undefined
        ? undefined
        : { status, data: detail === undefined ? {} : { detail } },
  };
}

/** A minimal observations payload matching the backend's ObservationsResponse. */
export function observationsFixture(overrides: Record<string, unknown> = {}) {
  return {
    observations: [
      {
        code: 'long_cycle_observed',
        severity: 'attention',
        title: 'A longer cycle than most',
        body: 'One of your recent cycles was 42 days, longer than the 21-35 day range most cycles fall into. If this is new for you, consider mentioning it at your next check-up.',
        titleKey: 'observations.long_cycle_observed.title',
        bodyKey: 'observations.long_cycle_observed.body',
        evidence: { longest_cycle_days: 42, threshold_days: 35, occurrences: 1 },
        isMedicalAdvice: false,
        disclaimerKey: 'insights.disclaimer',
      },
      {
        code: 'sustained_high_stress',
        severity: 'info',
        title: 'Stress has been high lately',
        body: 'Your logged stress has averaged 4.2 out of 5 across your last 3 entries.',
        titleKey: 'observations.sustained_high_stress.title',
        bodyKey: 'observations.sustained_high_stress.body',
        evidence: { average_stress: 4.2, entries: 3, scale_max: 5 },
        isMedicalAdvice: false,
        disclaimerKey: 'insights.disclaimer',
      },
    ],
    topObservation: null,
    cycleConsistency: 'slightly_variable',
    averageCycleLength: 33,
    analyzedCycleCount: 6,
    disclaimer: 'These insights are based on the information you log and are intended for personal tracking only. They are not a medical diagnosis and should not replace advice from a qualified healthcare professional.',
    disclaimerKey: 'insights.disclaimer',
    ...overrides,
  };
}

/**
 * The `prediction` block `/dashboard` embeds (`dashboard_summary()`).
 *
 * Defaults describe a routine, not-late cycle. The interesting cases —
 * overdue, due today, low confidence, population default — are built by
 * overriding, so each test says in its own body which one it is about.
 */
export function predictionFixture(overrides: Record<string, unknown> = {}) {
  return {
    nextPeriodDate: '2026-05-29',
    daysUntilNextPeriod: 16,
    isOverdue: false,
    daysOverdue: 0,
    phase: 'luteal' as const,
    confidence: 'high' as const,
    estimateSource: 'logged_history' as const,
    predictedRange: { earliest: '2026-05-27', latest: '2026-05-31' },
    fertileWindow: {
      start: '2026-05-10',
      end: '2026-05-16',
      isEstimate: true,
      notForContraception: true,
    },
    ...overrides,
  };
}

/** A dashboard payload matching the backend's DashboardResponse model. */
export function dashboardFixture(overrides: Record<string, unknown> = {}) {
  return {
    user: { name: 'Asha' },
    cycle: { day: 12, total: 28, nextPeriodDays: 16 },
    prediction: predictionFixture(),
    insights: { averageCycleLength: 28, shortestCycleLength: 25, longestCycleLength: 31, averageBleedingDuration: 5, sleepHours: '7.4h' },
    hasEnoughDataForInsights: true,
    loggedCycleCount: 6,
    cycleHistory: [
      { start_date: '2026-04-01', cycle_length: 28 },
      { start_date: '2026-04-29', cycle_length: 29 },
    ],
    symptomFrequency: { cramps: 0.5, headache: 0.2, bloating: 0.3, acne: 0.1 },
    recentStressLevel: 3,
    ...overrides,
  };
}
