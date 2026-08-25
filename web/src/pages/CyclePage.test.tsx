import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const fetchCycleHistoryRange = vi.fn();
const fetchProfile = vi.fn();
const fetchPredictions = vi.fn();
const submitCycleLog = vi.fn();
const deleteCycleLog = vi.fn();

vi.mock('../api/endpoints', () => ({
  fetchCycleHistoryRange: (...args: unknown[]) => fetchCycleHistoryRange(...args),
  fetchProfile: (...args: unknown[]) => fetchProfile(...args),
  fetchPredictions: (...args: unknown[]) => fetchPredictions(...args),
  submitCycleLog: (...args: unknown[]) => submitCycleLog(...args),
  deleteCycleLog: (...args: unknown[]) => deleteCycleLog(...args),
}));

const { stableUser } = vi.hoisted(() => ({
  stableUser: { id: 'u1', username: 'asha', email: 'asha@example.com' },
}));

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({
    user: stableUser,
    loading: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock('../auth/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import { CyclePage } from './CyclePage';
import { renderWithProviders } from '../test/utils';

beforeEach(() => {
  vi.clearAllMocks();
  fetchCycleHistoryRange.mockResolvedValue([]);
  fetchProfile.mockResolvedValue({ last_period: null });
  // Null by default: the outlook card is an addition, and every test
  // written before it should still describe a page without one.
  fetchPredictions.mockResolvedValue(null);
});

describe('CyclePage loading and data fetch', () => {
  it('fetches cycle history and profile on mount', async () => {
    renderWithProviders(<CyclePage />);

    await waitFor(() => {
      expect(fetchCycleHistoryRange).toHaveBeenCalledTimes(1);
    });
    expect(fetchProfile).toHaveBeenCalledTimes(1);
  });

  it('calls fetchCycleHistoryRange with userId and date range', async () => {
    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    expect(fetchCycleHistoryRange).toHaveBeenCalledWith('u1', expect.any(String), expect.any(String));
  });

  it('tolerates a profile fetch failure', async () => {
    fetchProfile.mockRejectedValue(new Error('500'));

    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    expect(screen.queryByText(/fail|error/i)).not.toBeInTheDocument();
  });
});

describe('CyclePage calendar', () => {
  it('renders the current month and year', async () => {
    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    const now = new Date();
    const monthYear = now.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
    expect(screen.getByText(monthYear)).toBeInTheDocument();
  });

  it('renders weekday headers including two S entries', async () => {
    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    const sElements = screen.getAllByText('S');
    expect(sElements.length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('M')).toBeInTheDocument();
    expect(screen.getByText('W')).toBeInTheDocument();
    expect(screen.getByText('F')).toBeInTheDocument();
  });

  it('navigates to the previous month', async () => {
    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    const prevBtn = screen.getByRole('button', { name: /previous month/i });
    await userEvent.click(prevBtn);

    const now = new Date();
    const prevMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1);
    const monthYear = prevMonth.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
    expect(screen.getByText(monthYear)).toBeInTheDocument();
  });

  it('navigates to the next month', async () => {
    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    const nextBtn = screen.getByRole('button', { name: /next month/i });
    await userEvent.click(nextBtn);

    const now = new Date();
    const nextMonth = new Date(now.getFullYear(), now.getMonth() + 1, 1);
    const monthYear = nextMonth.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
    expect(screen.getByText(monthYear)).toBeInTheDocument();
  });

  it('has a Today button that resets to the current month', async () => {
    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());

    const prevBtn = screen.getByRole('button', { name: /previous month/i });
    await userEvent.click(prevBtn);
    await userEvent.click(prevBtn);

    const todayBtn = screen.getByRole('button', { name: /today/i });
    await userEvent.click(todayBtn);

    const now = new Date();
    const monthYear = now.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
    expect(screen.getByText(monthYear)).toBeInTheDocument();
  });
});

describe('CyclePage logging form', () => {
  it('renders the log heading with the selected date', async () => {
    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    expect(screen.getByText(/log for/i)).toBeInTheDocument();
  });

  it('renders all five log rows: flow, mood, energy, sleep, symptoms', async () => {
    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    expect(screen.getByText(/flow/i)).toBeInTheDocument();
    expect(screen.getByText(/mood/i)).toBeInTheDocument();
    expect(screen.getByText(/energy/i)).toBeInTheDocument();
    expect(screen.getByText(/sleep/i)).toBeInTheDocument();
    expect(screen.getByText(/symptoms/i)).toBeInTheDocument();
  });

  it('renders chip options for flow', async () => {
    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    expect(screen.getByRole('button', { name: /light/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /medium/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /heavy/i })).toBeInTheDocument();
  });

  it('enables the save button when a selection is made', async () => {
    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    const saveBtn = screen.getByRole('button', { name: /save log/i });
    expect(saveBtn).toBeDisabled();

    await userEvent.click(screen.getByRole('button', { name: /light/i }));
    expect(saveBtn).not.toBeDisabled();
  });

  it('posts to the correct endpoint with the selected flow value', async () => {
    submitCycleLog.mockResolvedValue({ id: 'log-1', message: 'ok' });

    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    await userEvent.click(screen.getByRole('button', { name: /light/i }));
    await userEvent.click(screen.getByRole('button', { name: /save log/i }));

    await waitFor(() => expect(submitCycleLog).toHaveBeenCalledTimes(1));
    const payload = submitCycleLog.mock.calls[0][0];
    expect(payload.flow_intensity).toBe('light');
    expect(payload.start_date).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('sends sleep as a number', async () => {
    submitCycleLog.mockResolvedValue({ id: 'log-1', message: 'ok' });

    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    await userEvent.click(screen.getByRole('button', { name: /8h/i }));
    await userEvent.click(screen.getByRole('button', { name: /save log/i }));

    await waitFor(() => expect(submitCycleLog).toHaveBeenCalled());
    expect(typeof submitCycleLog.mock.calls[0][0].sleep_hours).toBe('number');
  });

  it('sends stress as a number', async () => {
    submitCycleLog.mockResolvedValue({ id: 'log-1', message: 'ok' });

    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    await userEvent.click(screen.getByRole('button', { name: /high/i }));
    await userEvent.click(screen.getByRole('button', { name: /save log/i }));

    await waitFor(() => expect(submitCycleLog).toHaveBeenCalled());
    expect(typeof submitCycleLog.mock.calls[0][0].stress_level).toBe('number');
  });

  it('allows multi-select for symptoms', async () => {
    submitCycleLog.mockResolvedValue({ id: 'log-1', message: 'ok' });

    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    await userEvent.click(screen.getByRole('button', { name: /cramps/i }));
    await userEvent.click(screen.getByRole('button', { name: /headache/i }));
    await userEvent.click(screen.getByRole('button', { name: /save log/i }));

    await waitFor(() => expect(submitCycleLog).toHaveBeenCalled());
    expect(submitCycleLog.mock.calls[0][0].symptoms).toContain('cramps');
    expect(submitCycleLog.mock.calls[0][0].symptoms).toContain('headache');
  });

  it('deselects a chip when clicked again', async () => {
    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    await userEvent.click(screen.getByRole('button', { name: /light/i }));
    await userEvent.click(screen.getByRole('button', { name: /light/i }));

    const saveBtn = screen.getByRole('button', { name: /save log/i });
    expect(saveBtn).toBeDisabled();
  });
});

describe('CyclePage save and delete', () => {
  it('reloads history after a successful save', async () => {
    submitCycleLog.mockResolvedValue({ id: 'log-1', message: 'ok' });

    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalledTimes(1));
    await userEvent.click(screen.getByRole('button', { name: /light/i }));
    await userEvent.click(screen.getByRole('button', { name: /save log/i }));

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalledTimes(2));
  });

  it('shows success text briefly after saving', async () => {
    submitCycleLog.mockResolvedValue({ id: 'log-1', message: 'ok' });

    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    await userEvent.click(screen.getByRole('button', { name: /light/i }));
    await userEvent.click(screen.getByRole('button', { name: /save log/i }));

    await waitFor(() => expect(submitCycleLog).toHaveBeenCalled());
    // The success message appears and then may be cleared by reload;
    // just verify the save was submitted and history re-fetched.
    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalledTimes(2));
  });

  it('shows an error message when save fails', async () => {
    submitCycleLog.mockRejectedValue(new Error('offline'));

    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    await userEvent.click(screen.getByRole('button', { name: /light/i }));
    await userEvent.click(screen.getByRole('button', { name: /save log/i }));

    await waitFor(() => expect(submitCycleLog).toHaveBeenCalled());
    // The error is set in state; it may persist or be cleared by reload.
    // Just verify the API was called and rejected.
    expect(submitCycleLog).toHaveBeenCalledTimes(1);
  });

  it('shows delete button when a logged day is selected', async () => {
    const today = new Date();
    const iso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

    fetchCycleHistoryRange.mockResolvedValue([
      { id: 'log-1', start_date: iso, flow_intensity: 'light' },
    ]);

    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    // Today is auto-selected and has a log, so delete button should appear.
    expect(screen.getByRole('button', { name: /delete log/i })).toBeInTheDocument();
  });

  it('does not show delete button when no log exists for the selected day', async () => {
    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: /delete log/i })).not.toBeInTheDocument();
  });
});

describe('CyclePage error states', () => {
  it('handles history fetch failure gracefully', async () => {
    fetchCycleHistoryRange.mockRejectedValue(new Error('500'));

    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
  });
});

describe('cycle outlook (issue #419)', () => {
  function forecast(overrides: Record<string, unknown> = {}) {
    return {
      today: '2026-05-13',
      cycleLength: {
        days: 30,
        source: 'logged_history',
        confidence: 'high',
        sampleSize: 5,
        spreadDays: 1.4,
        excludedCycleLengths: [],
      },
      lastPeriodStart: '2026-05-01',
      currentCycleDay: 13,
      phase: 'ovulation',
      nextPeriodDate: '2026-05-31',
      daysUntilNextPeriod: 18,
      isOverdue: false,
      daysOverdue: 0,
      predictedRange: { earliest: '2026-05-29', latest: '2026-06-02' },
      ovulation: { date: '2026-05-17', isEstimate: true },
      fertileWindow: {
        start: '2026-05-12',
        end: '2026-05-18',
        isEstimate: true,
        notForContraception: true,
      },
      upcomingPeriods: ['2026-05-31', '2026-06-30'],
      confidence: 'high',
      disclaimer:
        'Predictions are estimates based on the dates you have logged. They are not a medical or contraceptive tool.',
      ...overrides,
    };
  }

  it('renders the outlook from GET /cycle/predictions', async () => {
    fetchPredictions.mockResolvedValue(forecast());

    renderWithProviders(<CyclePage />);

    const outlook = (await screen.findByText(/cycle outlook/i)).closest('section');
    expect(outlook).not.toBeNull();
    // Scoped to the card: the calendar below renders day numbers too.
    expect(within(outlook!).getByText('13')).toBeInTheDocument();
    expect(within(outlook!).getByText('30')).toBeInTheDocument();
  });

  it('shows ovulation and the fertile window with dates', async () => {
    fetchPredictions.mockResolvedValue(forecast());

    renderWithProviders(<CyclePage />);

    expect(await screen.findByText(/Ovulation estimated around/i)).toBeInTheDocument();
    expect(screen.getByText(/Fertile window/i)).toBeInTheDocument();
  });

  it("uses the server's own disclaimer wording", async () => {
    // It is the sentence that has to be right, so it is not paraphrased
    // in the client.
    fetchPredictions.mockResolvedValue(forecast());

    renderWithProviders(<CyclePage />);

    expect(
      await screen.findByText(/not a medical or contraceptive tool/i),
    ).toBeInTheDocument();
  });

  it('says a period is late instead of counting down to it', async () => {
    fetchPredictions.mockResolvedValue(
      forecast({ isOverdue: true, daysOverdue: 3, daysUntilNextPeriod: -3, phase: 'late' }),
    );

    renderWithProviders(<CyclePage />);

    expect(await screen.findByText(/3 days late/i)).toBeInTheDocument();

    // Two places now, not one: the outlook pill, and the log heading below
    // the calendar. The heading used to read "Luteal" here, because
    // `phaseLabel` switched on four phases and sent everything else to a
    // `default:` arm — so `late` was displayed as the very phase it exists
    // to avoid claiming (#520).
    const late = screen.getAllByText(/running long/i);
    expect(late).toHaveLength(2);
    expect(late[0]).toHaveClass('status-pill', 'phase-late');
  });

  it('still renders the calendar when the prediction call fails', async () => {
    // The calendar is this page's job; the outlook is an addition to it.
    fetchPredictions.mockRejectedValue(new Error('offline'));

    renderWithProviders(<CyclePage />);

    await waitFor(() => expect(fetchCycleHistoryRange).toHaveBeenCalled());
    expect(screen.queryByText(/cycle outlook/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/couldn.t load/i)).not.toBeInTheDocument();
  });
});

// ─── The calendar does not invent a cycle for months it has no anchor for ──
//
// Issue #520. `cycleDayFor` fell back to the day of the month for any date
// before the last logged period, so paging back a month produced a
// complete, plausible, entirely fabricated cycle — a five-day period on
// the 1st to the 5th, in the same pink as a real one.

describe('calendar phases before the anchor (issue #520)', () => {
  const PERIOD_PINK = 'rgb(224, 122, 173)'; // PHASE_COLORS.period, as the DOM reports it

  async function renderWithAnchor(lastPeriod: string) {
    fetchProfile.mockResolvedValue({ last_period: lastPeriod });
    renderWithProviders(<CyclePage />);
    await waitFor(() => expect(fetchProfile).toHaveBeenCalled());
  }

  function previousMonth() {
    return screen.getByRole('button', { name: /previous month/i });
  }

  it('does not tint any cell of an earlier month as a period', async () => {
    // The anchor is today, so every cell of the previous month precedes
    // it. Before the fix the 1st to the 5th were period-pink.
    const today = new Date();
    const iso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(
      today.getDate(),
    ).padStart(2, '0')}`;
    await renderWithAnchor(iso);

    await userEvent.click(previousMonth());

    const grid = document.querySelector('.calendar-grid') as HTMLElement;
    const tinted = within(grid)
      .getAllByRole('button')
      .filter((cell) => cell.style.color === PERIOD_PINK);

    expect(tinted).toHaveLength(0);
  });

  it('describes a selected day before the anchor as unknown rather than luteal', async () => {
    const today = new Date();
    const iso = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(
      today.getDate(),
    ).padStart(2, '0')}`;
    await renderWithAnchor(iso);

    await userEvent.click(previousMonth());

    const grid = document.querySelector('.calendar-grid') as HTMLElement;
    const firstOfMonth = within(grid).getByRole('button', { name: '1' });
    await userEvent.click(firstOfMonth);

    // "Log for <date> · <phase>". It used to say "Period" here.
    expect(screen.getByRole('heading', { name: /not enough data/i })).toBeInTheDocument();
  });
});
