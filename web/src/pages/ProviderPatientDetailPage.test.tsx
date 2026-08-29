/**
 * The patient detail screen says how much history it is showing (#557).
 *
 * `summary.loggedCycleCount` used to be `len(logs)` over the server's
 * ten-log analysis window, so it agreed with the number of rows in the
 * table below it by construction — and neither number said anything true
 * about how much the patient had actually logged.
 *
 * Now that the count is a real total, the two can disagree, and the
 * screen has to say why. A clinician reading ten rows under a card
 * saying "300 cycles" would otherwise be left to work out which of the
 * two is lying.
 */

import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor, within } from '@testing-library/react';

import { ProviderPatientDetailPage } from './ProviderPatientDetailPage';
import { renderWithProviders } from '../test/utils';

vi.mock('../api/endpoints', () => ({
  fetchProviderPatientDetail: vi.fn(),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useParams: () => ({ patientId: 'p-1' }) };
});

import { fetchProviderPatientDetail } from '../api/endpoints';

const mockedFetch = vi.mocked(fetchProviderPatientDetail);

function log(day: number) {
  return {
    id: `log-${day}`,
    start_date: `2026-01-${String(day).padStart(2, '0')}`,
    end_date: null,
    flow_intensity: 'medium',
    mood: 'neutral',
    symptoms: ['cramps'],
    sleep_hours: 7,
    stress_level: 2,
    notes: null,
  };
}

function detail({
  loggedCycleCount,
  analyzedCycleCount,
  rows = analyzedCycleCount,
}: {
  loggedCycleCount: number;
  analyzedCycleCount: number;
  rows?: number;
}) {
  return {
    patient: {
      id: 'p-1',
      name: 'Asha Devi',
      age: 29,
      city: 'Nashik',
      state: 'Maharashtra',
      cycle_length: 29,
      period_duration: 5,
      cycle_regular: true,
      last_period: '2026-01-10',
    },
    summary: {
      mhs: 72,
      cvi: 'Low',
      cvi_raw: 18,
      loggedCycleCount,
      analyzedCycleCount,
      hasEnoughDataForInsights: true,
      avgSleepHours: 7.1,
    },
    cycleLogs: Array.from({ length: rows }, (_, index) => log(index + 1)),
    consent: { grantedAt: '2026-01-01T00:00:00Z', status: 'active' },
  };
}

beforeEach(() => {
  mockedFetch.mockReset();
});

describe('how much history the detail page is showing', () => {
  it('says the table is a recent window when the patient has logged more', async () => {
    mockedFetch.mockResolvedValue(
      detail({ loggedCycleCount: 300, analyzedCycleCount: 10 }) as never,
    );

    renderWithProviders(<ProviderPatientDetailPage />);

    // "Showing the most recent 10 of 300 logged entries."
    const note = await screen.findByText(/most recent 10 of 300/i);
    expect(note).toBeInTheDocument();
  });

  it('shows the real total, not the window, as the logged-cycles stat', async () => {
    mockedFetch.mockResolvedValue(
      detail({ loggedCycleCount: 300, analyzedCycleCount: 10 }) as never,
    );

    renderWithProviders(<ProviderPatientDetailPage />);

    await waitFor(() => expect(mockedFetch).toHaveBeenCalled());
    expect(screen.getByText('300')).toBeInTheDocument();
  });

  it('says nothing when the window is the whole history', async () => {
    // Eight logs, eight analysed. There is no window to explain, and a
    // note saying "showing the most recent 8 of 8" is noise on a screen
    // a clinician is scanning.
    mockedFetch.mockResolvedValue(
      detail({ loggedCycleCount: 8, analyzedCycleCount: 8 }) as never,
    );

    renderWithProviders(<ProviderPatientDetailPage />);

    await waitFor(() => expect(mockedFetch).toHaveBeenCalled());
    expect(screen.queryByText(/most recent/i)).not.toBeInTheDocument();
  });

  it('says nothing for a patient who has logged nothing at all', async () => {
    // `analyzedCycleCount` of 0 is not a window either. Without the
    // explicit guard this would read "showing the most recent 0 of 0".
    mockedFetch.mockResolvedValue(
      detail({ loggedCycleCount: 0, analyzedCycleCount: 0, rows: 0 }) as never,
    );

    renderWithProviders(<ProviderPatientDetailPage />);

    expect(await screen.findByText(/no cycle logs shared yet/i)).toBeInTheDocument();
    expect(screen.queryByText(/most recent/i)).not.toBeInTheDocument();
  });

  it('renders one table row per shared log, independently of either count', async () => {
    mockedFetch.mockResolvedValue(
      detail({ loggedCycleCount: 300, analyzedCycleCount: 10, rows: 10 }) as never,
    );

    renderWithProviders(<ProviderPatientDetailPage />);

    await waitFor(() => expect(mockedFetch).toHaveBeenCalled());
    const table = screen.getByRole('table');
    // One header row plus ten data rows.
    expect(within(table).getAllByRole('row')).toHaveLength(11);
  });
});
