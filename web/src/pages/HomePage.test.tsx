import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const fetchDashboard = vi.fn();
const submitCycleLog = vi.fn();

vi.mock('../api/endpoints', () => ({
  fetchDashboard: (...args: unknown[]) => fetchDashboard(...args),
  submitCycleLog: (...args: unknown[]) => submitCycleLog(...args),
}));

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({
    user: { id: 'u1', username: 'asha', email: 'asha@example.com' },
    loading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock('../auth/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import { HomePage } from './HomePage';
import { dashboardFixture, predictionFixture, renderWithProviders } from '../test/utils';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('HomePage loading and error states', () => {
  it('fetches the dashboard once on mount', async () => {
    fetchDashboard.mockResolvedValue(dashboardFixture());

    renderWithProviders(<HomePage />);

    await waitFor(() => expect(fetchDashboard).toHaveBeenCalledTimes(1));
  });

  it('shows an error message when the dashboard cannot be loaded', async () => {
    // Rendering a blank screen is the failure mode users report as "the
    // app is broken" with nothing actionable attached.
    fetchDashboard.mockRejectedValue(new Error('500'));

    renderWithProviders(<HomePage />);

    expect(await screen.findByText(/fail|error|could ?n.t/i)).toBeInTheDocument();
  });

  it('does not leave a spinner up forever after a failure', async () => {
    fetchDashboard.mockRejectedValue(new Error('500'));

    renderWithProviders(<HomePage />);

    await waitFor(() =>
      expect(screen.queryByText(/^loading/i)).not.toBeInTheDocument(),
    );
  });
});

describe('HomePage with data', () => {
  it('renders the cycle day from the response', async () => {
    fetchDashboard.mockResolvedValue(dashboardFixture());

    renderWithProviders(<HomePage />);

    await waitFor(() => expect(fetchDashboard).toHaveBeenCalled());
    expect(await screen.findByText(/12/)).toBeInTheDocument();
  });

  it('shows the fertile window disclaimer', async () => {
    fetchDashboard.mockResolvedValue(dashboardFixture());

    renderWithProviders(<HomePage />);

    await waitFor(() => expect(fetchDashboard).toHaveBeenCalled());
    expect(await screen.findByText(/not medical or contraceptive advice/i)).toBeInTheDocument();
  });

  it('handles a brand-new account with no cycle data', async () => {
    // Every numeric field is nullable in DashboardResponse; a component
    // that assumes otherwise crashes on the very first session.
    fetchDashboard.mockResolvedValue(
      dashboardFixture({
        cycle: { day: null, total: 28, nextPeriodDays: null },
        insights: { averageCycleLength: null, shortestCycleLength: null, longestCycleLength: null, averageBleedingDuration: null, sleepHours: null },
        hasEnoughDataForInsights: false,
        loggedCycleCount: 0,
        cycleHistory: [],
        symptomFrequency: {},
        recentStressLevel: null,
      }),
    );

    renderWithProviders(<HomePage />);

    await waitFor(() => expect(fetchDashboard).toHaveBeenCalled());
    expect(screen.queryByText(/fail|error/i)).not.toBeInTheDocument();
  });

  it('renders without a chart when there is no history', async () => {
    fetchDashboard.mockResolvedValue(dashboardFixture({ cycleHistory: [] }));

    renderWithProviders(<HomePage />);

    await waitFor(() => expect(fetchDashboard).toHaveBeenCalled());
    expect(screen.queryByText(/fail|error/i)).not.toBeInTheDocument();
  });
});

describe('quick log', () => {
  async function openTile(name: RegExp) {
    fetchDashboard.mockResolvedValue(dashboardFixture());
    renderWithProviders(<HomePage />);
    await waitFor(() => expect(fetchDashboard).toHaveBeenCalled());
    await userEvent.click(screen.getByRole('button', { name }));
    return screen.getByRole('dialog');
  }

  it('opens a dialog of options for the tapped tile', async () => {
    const dialog = await openTile(/flow/i);
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: /light/i })).toBeInTheDocument();
  });

  it('posts a flow value with an ISO start date', async () => {
    // The backend's CycleLog model parses start_date as a date; a Date
    // object or a locale-formatted string 422s at runtime while
    // type-checking perfectly.
    submitCycleLog.mockResolvedValue({ id: 'log-1', message: 'ok' });

    const dialog = await openTile(/flow/i);
    await userEvent.click(within(dialog).getByRole('button', { name: /light/i }));

    await waitFor(() => expect(submitCycleLog).toHaveBeenCalledTimes(1));
    const payload = submitCycleLog.mock.calls[0][0];
    expect(payload.flow_intensity).toBe('light');
    expect(payload.start_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('sends sleep as a number, not the option string', async () => {
    // sleep_hours is a float on the backend and stress_level an int;
    // posting "8" as a string is the kind of thing only a runtime test
    // catches.
    submitCycleLog.mockResolvedValue({ id: 'log-1', message: 'ok' });

    const dialog = await openTile(/sleep/i);
    await userEvent.click(within(dialog).getByRole('button', { name: /8/ }));

    await waitFor(() => expect(submitCycleLog).toHaveBeenCalled());
    expect(typeof submitCycleLog.mock.calls[0][0].sleep_hours).toBe('number');
  });

  it('closes the dialog and confirms after a successful log', async () => {
    submitCycleLog.mockResolvedValue({ id: 'log-1', message: 'ok' });

    const dialog = await openTile(/flow/i);
    await userEvent.click(within(dialog).getByRole('button', { name: /light/i }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('reloads the dashboard after logging, so the ring reflects the new entry', async () => {
    submitCycleLog.mockResolvedValue({ id: 'log-1', message: 'ok' });

    const dialog = await openTile(/flow/i);
    await userEvent.click(within(dialog).getByRole('button', { name: /light/i }));

    await waitFor(() => expect(fetchDashboard).toHaveBeenCalledTimes(2));
  });

  it('tells the user rather than failing silently when the save fails', async () => {
    submitCycleLog.mockRejectedValue(new Error('offline'));

    const dialog = await openTile(/flow/i);
    await userEvent.click(within(dialog).getByRole('button', { name: /light/i }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(await screen.findByText(/couldn.t reach the server/i)).toBeInTheDocument();
  });

  it('can be dismissed without logging anything', async () => {
    const dialog = await openTile(/flow/i);
    await userEvent.click(within(dialog).getByRole('button', { name: /cancel/i }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(submitCycleLog).not.toHaveBeenCalled();
  });

  it('does not submit anything on the initial render', async () => {
    fetchDashboard.mockResolvedValue(dashboardFixture());

    renderWithProviders(<HomePage />);
    await waitFor(() => expect(fetchDashboard).toHaveBeenCalled());

    expect(submitCycleLog).not.toHaveBeenCalled();
  });
});

describe('the next-period answer (issue #419)', () => {
  it('reports a late period rather than the clamped zero', async () => {
    // `cycle.nextPeriodDays` is `max(avg - day, 0)`, so it is 0 here —
    // the same value it would carry on the day the period is due. The
    // prediction is what carries the difference.
    fetchDashboard.mockResolvedValue(
      dashboardFixture({
        cycle: { day: 32, total: 28, nextPeriodDays: 0 },
        prediction: predictionFixture({
          isOverdue: true,
          daysOverdue: 4,
          daysUntilNextPeriod: -4,
        }),
      }),
    );

    renderWithProviders(<HomePage />);

    expect(await screen.findByText(/4 days late/i)).toBeInTheDocument();
  });

  it('shows the predicted range rather than a bare date', async () => {
    fetchDashboard.mockResolvedValue(dashboardFixture());

    renderWithProviders(<HomePage />);

    expect(await screen.findByText(/Between .* and .*/)).toBeInTheDocument();
  });

  it('replaces the fixed "High energy" string with real fertile dates', async () => {
    fetchDashboard.mockResolvedValue(dashboardFixture());

    renderWithProviders(<HomePage />);

    expect(await screen.findByText(/Fertile window .* – .*/)).toBeInTheDocument();
    expect(screen.queryByText(/High energy/)).not.toBeInTheDocument();
  });

  it('falls back to the legacy number against an older backend', async () => {
    fetchDashboard.mockResolvedValue(dashboardFixture({ prediction: null }));

    renderWithProviders(<HomePage />);

    await waitFor(() => expect(fetchDashboard).toHaveBeenCalled());
    expect(screen.getByText('16')).toBeInTheDocument();
  });
});
