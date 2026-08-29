import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

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
import { dashboardFixture, renderWithProviders } from '../test/utils';

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

// ─── Editing the profile (issue #533) ──────────────────────────────────────
//
// Two faults met in this one form. A cleared field could not actually be
// cleared — the client sends `null`, which the server used to drop — and a
// failed save was indistinguishable from a successful one, because
// `submitEdit` was `try`/`finally` with no `catch` at all.
//
// The assertions below are mostly about the *second* one: what the screen
// says when the write does not land. A user on a 2G handset whose request
// never left the device saw a modal that would not close, a button that
// flipped back from "Saving…" to "Save changes", and no message anywhere —
// which reads as "your value was rejected".

describe('editing', () => {
  async function openEditor() {
    renderWithProviders(<ProfilePage />);
    await screen.findByRole('button', { name: /edit/i });
    await userEvent.click(screen.getByRole('button', { name: /edit/i }));
    return screen.findByRole('dialog');
  }

  it('sends null for a field the user emptied', async () => {
    // `null` is how a client says "remove this". It reached a server that
    // filtered it out, so the removal silently did not happen.
    fetchProfile.mockResolvedValue({ id: 'u1', full_name: 'Asha', age: 27, cycle_length: 30 });
    patchProfile.mockResolvedValue({ id: 'u1', full_name: 'Asha', age: null, cycle_length: 30 });

    await openEditor();
    await userEvent.clear(screen.getByLabelText(/age/i));
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() =>
      expect(patchProfile).toHaveBeenCalledWith(
        expect.objectContaining({ age: null }),
      ),
    );
  });

  it('closes and adopts the server’s answer on success', async () => {
    patchProfile.mockResolvedValue({ id: 'u1', full_name: 'Asha Verma', age: 27 });

    await openEditor();
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('keeps the editor open and says something when the save fails', async () => {
    patchProfile.mockRejectedValue({ isAxiosError: true, response: undefined });

    await openEditor();
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('says the request never left the device when there is no response', async () => {
    // The ordinary failure for this app's users, and the one where "try
    // again" is genuine advice rather than a platitude.
    patchProfile.mockRejectedValue({ isAxiosError: true, response: undefined });

    await openEditor();
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    expect(await screen.findByText(/offline/i)).toBeInTheDocument();
  });

  it('shows the server’s own words for a rejected value', async () => {
    // A 422 names the field it refused, which is more useful than any
    // generic sentence this page could write.
    patchProfile.mockRejectedValue({
      isAxiosError: true,
      response: {
        status: 422,
        data: { detail: 'These fields cannot be cleared: email. Send a new value instead of null.' },
      },
    });

    await openEditor();
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    expect(await screen.findByText(/cannot be cleared/i)).toBeInTheDocument();
  });

  it('re-enables the button after a failure so she can retry', async () => {
    patchProfile.mockRejectedValue({ isAxiosError: true, response: undefined });

    await openEditor();
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /save changes/i })).toBeEnabled(),
    );
  });

  it('clears a stale error when the editor is reopened', async () => {
    patchProfile.mockRejectedValue({ isAxiosError: true, response: undefined });

    await openEditor();
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));
    await screen.findByRole('alert');

    await userEvent.click(screen.getByRole('button', { name: /cancel/i }));
    await userEvent.click(screen.getByRole('button', { name: /edit/i }));

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('does not call the server when the form itself is invalid', async () => {
    await openEditor();
    await userEvent.clear(screen.getByLabelText(/name/i));
    await userEvent.click(screen.getByRole('button', { name: /save changes/i }));

    expect(patchProfile).not.toHaveBeenCalled();
  });
});
