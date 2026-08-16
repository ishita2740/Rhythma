import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';

const fetchProfile = vi.fn();
const fetchDashboard = vi.fn();
const patchProfile = vi.fn();

vi.mock('../api/endpoints', () => ({
  fetchProfile: (...args: unknown[]) => fetchProfile(...args),
  fetchDashboard: (...args: unknown[]) => fetchDashboard(...args),
  patchProfile: (...args: unknown[]) => patchProfile(...args),
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

import { ProfilePage } from './ProfilePage';
import { dashboardFixture, predictionFixture, renderWithProviders } from '../test/utils';

beforeEach(() => {
  vi.clearAllMocks();
  fetchProfile.mockResolvedValue({ id: 'u1', full_name: 'Asha', age: 27 });
});

/** The rendered value of the mini-stat whose label matches `label`. */
async function statValue(label: string): Promise<string> {
  const labelNode = await screen.findByText(label);
  const tile = labelNode.closest('.mini-stat');
  expect(tile).not.toBeNull();
  const value = tile!.querySelector('.mini-stat-value');
  expect(value).not.toBeNull();
  return value!.textContent ?? '';
}

function withHistory(lengths: number[]) {
  return dashboardFixture({
    cycleHistory: lengths.map((cycle_length, i) => ({
      start_date: `2026-0${i + 1}-01`,
      cycle_length,
    })),
  });
}

// Issue #383. The tile showed a variance in days², rendered as `±N`, and
// measured against `dashboard.cycle.total` — a rounded average from a
// different calculation which falls back to 28 when the user has almost
// no history. It never crashed and it never looked obviously wrong, so
// these assert the exact rendered string rather than that the tile exists.

describe('ProfilePage — cycle variability tile', () => {
  it('reports the spread in days, not days squared', async () => {
    fetchDashboard.mockResolvedValue(withHistory([26, 30]));

    renderWithProviders(<ProfilePage />);

    await waitFor(async () =>
      expect(await statValue('Cycle variability')).toBe('±2 days'),
    );
  });

  it('does not inflate a wider spread quadratically', async () => {
    // Previously rendered as ±25 — the difference between "your cycles
    // are steady" and "something is wrong with me".
    fetchDashboard.mockResolvedValue(withHistory([23, 33]));

    renderWithProviders(<ProfilePage />);

    await waitFor(async () =>
      expect(await statValue('Cycle variability')).toBe('±5 days'),
    );
  });

  it('measures against the user\'s own average, not the 28-day default', async () => {
    // `cycle.total` stays at 28 while every logged cycle is around 35.
    // The old arithmetic measured the distance to 28 and reported ~49.
    fetchDashboard.mockResolvedValue({
      ...withHistory([34, 35, 36]),
      cycle: { day: 12, total: 28, nextPeriodDays: 16 },
    });

    renderWithProviders(<ProfilePage />);

    await waitFor(async () =>
      expect(await statValue('Cycle variability')).toBe('±0.7 days'),
    );
  });

  it('shows a dash for a single logged cycle rather than a number', async () => {
    // One cycle has no spread. The old code reported one anyway, by
    // measuring it against a default the user never entered.
    fetchDashboard.mockResolvedValue(withHistory([35]));

    renderWithProviders(<ProfilePage />);

    await waitFor(async () =>
      expect(await statValue('Cycle variability')).toBe('—'),
    );
  });

  it('shows a dash when there is no history at all', async () => {
    fetchDashboard.mockResolvedValue(withHistory([]));

    renderWithProviders(<ProfilePage />);

    await waitFor(async () =>
      expect(await statValue('Cycle variability')).toBe('—'),
    );
  });

  it('shows a real zero for perfectly regular cycles', async () => {
    fetchDashboard.mockResolvedValue(withHistory([28, 28, 28]));

    renderWithProviders(<ProfilePage />);

    await waitFor(async () =>
      expect(await statValue('Cycle variability')).toBe('±0 days'),
    );
  });

  it('never renders NaN when a length is missing', async () => {
    fetchDashboard.mockResolvedValue(
      withHistory([26, null as unknown as number, 30]),
    );

    renderWithProviders(<ProfilePage />);

    await waitFor(async () => {
      const value = await statValue('Cycle variability');
      expect(value).not.toContain('NaN');
      expect(value).toBe('±2 days');
    });
  });

  it('renders a dash when the dashboard cannot be loaded', async () => {
    // The page already tolerates a failed dashboard — the stat must not
    // be the thing that turns that into a broken tile.
    fetchDashboard.mockRejectedValue(new Error('offline'));

    renderWithProviders(<ProfilePage />);

    await waitFor(async () =>
      expect(await statValue('Cycle variability')).toBe('—'),
    );
  });
});

describe('ProfilePage — the neighbouring stats are unchanged', () => {
  it('still shows the average bleeding duration', async () => {
    fetchDashboard.mockResolvedValue(withHistory([26, 30]));

    renderWithProviders(<ProfilePage />);

    await waitFor(async () =>
      expect(await statValue('Avg bleeding')).toBe('5 days'),
    );
  });

  it('still shows the most recent cycle length', async () => {
    // `cycleHistory` arrives oldest-first from the backend, so the last
    // entry is the most recent cycle.
    fetchDashboard.mockResolvedValue(withHistory([26, 30]));

    renderWithProviders(<ProfilePage />);

    await waitFor(async () =>
      expect(await statValue('Last cycle length')).toBe('30 days'),
    );
  });
});

// Issue #486. The pill was computed on this page from a fixed day-5/13/16
// ladder — the same one #316 removed from the Flutter app — so it
// disagreed with the phase `/dashboard` already returns, and `luteal` was
// the fallthrough, meaning a period could never be shown as late.

describe('ProfilePage — the phase pill comes from the server', () => {
  /** The rendered text of the phase pill. */
  async function pillText(): Promise<string> {
    await waitFor(() => expect(fetchDashboard).toHaveBeenCalled());
    const pill = await waitFor(() => {
      const node = document.querySelector('.phase-pill');
      expect(node).not.toBeNull();
      return node!;
    });
    return pill.textContent ?? '';
  }

  it('shows the phase the dashboard reported, not one derived from the day', async () => {
    // Day 12 with a 34-day cycle. The old ladder said `day <= 13` →
    // "Follicular"; the server, scaling the boundaries to her own cycle
    // length, says luteal. Home renders the server's answer, so the two
    // screens contradicted each other for one account in one second.
    fetchDashboard.mockResolvedValue(
      dashboardFixture({
        cycle: { day: 12, total: 34, nextPeriodDays: 22 },
        prediction: predictionFixture({ phase: 'luteal' }),
      }),
    );

    renderWithProviders(<ProfilePage />);

    const text = await pillText();
    expect(text).toContain('Luteal Phase');
    expect(text).not.toContain('Follicular');
  });

  it('says a cycle is running long instead of pinning her in luteal forever', async () => {
    // The ladder returned `luteal` for day 20, day 40 and day 200 alike.
    fetchDashboard.mockResolvedValue(
      dashboardFixture({
        cycle: { day: 63, total: 28, nextPeriodDays: 0 },
        prediction: predictionFixture({
          phase: 'late',
          isOverdue: true,
          daysOverdue: 35,
          daysUntilNextPeriod: -35,
        }),
      }),
    );

    renderWithProviders(<ProfilePage />);

    const text = await pillText();
    expect(text).toContain('Cycle running long');
    expect(text).not.toContain('Luteal');
  });

  it('says so plainly when there is nothing to base a phase on', async () => {
    // This rendered a bare `—`, which told the reader nothing at all.
    fetchDashboard.mockResolvedValue(
      dashboardFixture({
        cycle: { day: null, total: 28, nextPeriodDays: null },
        prediction: predictionFixture({ phase: 'unknown' }),
      }),
    );

    renderWithProviders(<ProfilePage />);

    const text = await pillText();
    expect(text).toContain('Not enough to say yet');
    expect(text).not.toBe('—');
  });

  it('does not break on a server that returns no prediction block', async () => {
    fetchDashboard.mockResolvedValue(dashboardFixture({ prediction: null }));

    renderWithProviders(<ProfilePage />);

    expect(await pillText()).toContain('Not enough to say yet');
  });

  it('does not break when the dashboard request fails', async () => {
    // The page already tolerates a failed dashboard; the pill must not be
    // the thing that turns that into a crash.
    fetchDashboard.mockRejectedValue(new Error('offline'));

    renderWithProviders(<ProfilePage />);

    expect(await pillText()).toContain('Not enough to say yet');
  });

  it('shows the period phase during bleeding', async () => {
    fetchDashboard.mockResolvedValue(
      dashboardFixture({
        cycle: { day: 2, total: 28, nextPeriodDays: 26 },
        prediction: predictionFixture({ phase: 'period' }),
      }),
    );

    renderWithProviders(<ProfilePage />);

    expect(await pillText()).toContain('Menstrual Phase');
  });
});

describe('ProfilePage — the average cycle length tile', () => {
  it('shows the average measured from logged cycles', async () => {
    fetchProfile.mockResolvedValue({
      id: 'u1',
      full_name: 'Asha',
      age: 27,
      cycle_length: 28,
    });
    fetchDashboard.mockResolvedValue(
      dashboardFixture({
        insights: {
          averageCycleLength: 33,
          shortestCycleLength: 31,
          longestCycleLength: 35,
          averageBleedingDuration: 5,
          sleepHours: '7.4h',
        },
      }),
    );

    renderWithProviders(<ProfilePage />);

    // 33, not the 28 she typed at onboarding.
    await waitFor(async () =>
      expect(await statValue('Avg cycle length')).toBe('33 days'),
    );
  });

  it('relabels the tile when it is falling back to the declared length', async () => {
    // "Avg cycle length: 28 days" over a number the user typed is a label
    // making a claim the value does not support.
    fetchProfile.mockResolvedValue({
      id: 'u1',
      full_name: 'Asha',
      age: 27,
      cycle_length: 30,
    });
    fetchDashboard.mockResolvedValue(
      dashboardFixture({
        insights: {
          averageCycleLength: null,
          shortestCycleLength: null,
          longestCycleLength: null,
          averageBleedingDuration: 5,
          sleepHours: null,
        },
      }),
    );

    renderWithProviders(<ProfilePage />);

    await waitFor(async () =>
      expect(await statValue('Cycle length you set')).toBe('30 days'),
    );
    expect(screen.queryByText('Avg cycle length')).not.toBeInTheDocument();
  });

  it('shows a dash rather than the 28-day default when there is no data', async () => {
    fetchProfile.mockResolvedValue({ id: 'u1', full_name: 'Asha', age: 27 });
    fetchDashboard.mockResolvedValue(
      dashboardFixture({
        insights: {
          averageCycleLength: null,
          shortestCycleLength: null,
          longestCycleLength: null,
          averageBleedingDuration: null,
          sleepHours: null,
        },
        cycle: { day: 3, total: 28, nextPeriodDays: 25 },
      }),
    );

    renderWithProviders(<ProfilePage />);

    await waitFor(async () =>
      expect(await statValue('Cycle length you set')).toBe('—'),
    );
  });
});
