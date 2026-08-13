import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';

const fetchObservations = vi.fn();

vi.mock('../api/endpoints', () => ({
  fetchObservations: (...args: unknown[]) => fetchObservations(...args),
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

import { InsightsPage } from './InsightsPage';
import { observationsFixture, renderWithProviders } from '../test/utils';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('InsightsPage loading and error states', () => {
  it('fetches observations once on mount', async () => {
    fetchObservations.mockResolvedValue(observationsFixture());

    renderWithProviders(<InsightsPage />);

    await waitFor(() => expect(fetchObservations).toHaveBeenCalledTimes(1));
  });

  it('shows an error message when observations cannot be loaded', async () => {
    fetchObservations.mockRejectedValue(new Error('500'));

    renderWithProviders(<InsightsPage />);

    expect(await screen.findByText(/fail|error|could ?n.t/i)).toBeInTheDocument();
  });

  it('does not leave a spinner up forever after a failure', async () => {
    fetchObservations.mockRejectedValue(new Error('500'));

    renderWithProviders(<InsightsPage />);

    await waitFor(() =>
      expect(screen.queryByText(/^loading/i)).not.toBeInTheDocument(),
    );
  });
});

describe('InsightsPage with observations data', () => {
  it('renders cycle stats — average cycle length and cycles analyzed', async () => {
    fetchObservations.mockResolvedValue(observationsFixture());

    renderWithProviders(<InsightsPage />);

    await waitFor(() => expect(fetchObservations).toHaveBeenCalled());
    expect(await screen.findByText('33d')).toBeInTheDocument();
    expect(screen.getByText('6')).toBeInTheDocument();
  });

  it('renders the consistency description', async () => {
    fetchObservations.mockResolvedValue(
      observationsFixture({ cycleConsistency: 'consistent' }),
    );

    renderWithProviders(<InsightsPage />);

    await waitFor(() => expect(fetchObservations).toHaveBeenCalled());
    expect(await screen.findByText(/consistent/i)).toBeInTheDocument();
  });

  it('renders observation cards with title and body text', async () => {
    fetchObservations.mockResolvedValue(observationsFixture());

    renderWithProviders(<InsightsPage />);

    await waitFor(() => expect(fetchObservations).toHaveBeenCalled());
    expect(await screen.findByText(/longer cycle than most/i)).toBeInTheDocument();
    expect(screen.getByText(/42 days/i)).toBeInTheDocument();
  });

  it('shows no-MHS/CVI anywhere on the page', async () => {
    fetchObservations.mockResolvedValue(observationsFixture());

    renderWithProviders(<InsightsPage />);

    await waitFor(() => expect(fetchObservations).toHaveBeenCalled());
    expect(screen.queryByText(/MHS|CVI|score/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/mental health score/i)).not.toBeInTheDocument();
  });

  it('renders the disclaimer text', async () => {
    fetchObservations.mockResolvedValue(observationsFixture());

    renderWithProviders(<InsightsPage />);

    await waitFor(() => expect(fetchObservations).toHaveBeenCalled());
    expect(await screen.findByText(/not a medical diagnosis/i)).toBeInTheDocument();
  });

  it('does not render observations when insufficient_data is the only observation', async () => {
    fetchObservations.mockResolvedValue(
      observationsFixture({
        observations: [
          {
            code: 'insufficient_data',
            severity: 'info',
            title: 'Keep logging to see your patterns',
            body: "You've logged 1 cycle so far.",
            titleKey: 'observations.insufficient_data.title',
            bodyKey: 'observations.insufficient_data.body',
            evidence: { logged_cycles: 1, needed: 2 },
            isMedicalAdvice: false,
            disclaimerKey: 'insights.disclaimer',
          },
        ],
        topObservation: null,
      }),
    );

    renderWithProviders(<InsightsPage />);

    await waitFor(() => expect(fetchObservations).toHaveBeenCalled());
    expect(screen.queryByText(/longer cycle/i)).not.toBeInTheDocument();
  });
});

describe('InsightsPage empty / not-enough-data state', () => {
  it('shows a not-enough-data warning when insufficient_data fires', async () => {
    fetchObservations.mockResolvedValue(
      observationsFixture({
        observations: [
          {
            code: 'insufficient_data',
            severity: 'info',
            title: 'Keep logging',
            body: "You've logged 0 cycles so far.",
            titleKey: 'observations.insufficient_data.title',
            bodyKey: 'observations.insufficient_data.body',
            evidence: { logged_cycles: 0, needed: 2 },
            isMedicalAdvice: false,
            disclaimerKey: 'insights.disclaimer',
          },
        ],
        topObservation: null,
      }),
    );

    renderWithProviders(<InsightsPage />);

    await waitFor(() => expect(fetchObservations).toHaveBeenCalled());
    expect(await screen.findByText(/log a few more cycles/i)).toBeInTheDocument();
  });
});
