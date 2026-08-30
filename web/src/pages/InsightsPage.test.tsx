import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
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
import i18n from '../i18n';
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

describe('InsightsPage observation localization (#485)', () => {
  // The page rendered `observation.title` / `.body` — the server's English
  // fallbacks — in every locale, so the chrome translated and the content
  // did not. These tests drive the real i18n instance rather than a mock,
  // because the bug was that a correct payload was being ignored, and a
  // mocked `t` would have kept passing throughout.

  afterEach(async () => {
    await i18n.changeLanguage('en');
  });

  it('renders the observation in the active language, not the English fallback', async () => {
    await i18n.changeLanguage('hi');
    fetchObservations.mockResolvedValue(observationsFixture());

    renderWithProviders(<InsightsPage />);

    // The English fallback the server sent must not be what is shown.
    await waitFor(() =>
      expect(screen.queryByText('A longer cycle than most')).not.toBeInTheDocument(),
    );
    expect(
      screen.getByText(i18n.t('observations.long_cycle_observed.title')),
    ).toBeInTheDocument();
  });

  it('interpolates the evidence into the translated body', async () => {
    await i18n.changeLanguage('hi');
    fetchObservations.mockResolvedValue(observationsFixture());

    renderWithProviders(<InsightsPage />);

    // 42 is `evidence.longest_cycle_days`. If the placeholder were dropped
    // in translation, or the evidence not passed, the number would be
    // missing from a sentence that is entirely about it.
    const body = await screen.findByText(/42/);
    expect(body).toBeInTheDocument();
    expect(body.textContent).not.toContain('{{');
  });

  it('falls back to English for a code no locale has a string for yet', async () => {
    // The normal state of the world: the backend ships a rule, the locale
    // files catch up later. The reader must see the server's English, not
    // "observations.a_new_rule.title".
    await i18n.changeLanguage('hi');
    fetchObservations.mockResolvedValue(
      observationsFixture({
        observations: [
          {
            code: 'a_rule_added_after_these_translations',
            severity: 'info',
            title: 'A brand new observation',
            body: 'Something the client has no string for yet.',
            titleKey: 'observations.a_rule_added_after_these_translations.title',
            bodyKey: 'observations.a_rule_added_after_these_translations.body',
            evidence: {},
            isMedicalAdvice: false,
            disclaimerKey: 'insights.disclaimer',
          },
        ],
        topObservation: null,
      }),
    );

    renderWithProviders(<InsightsPage />);

    expect(await screen.findByText('A brand new observation')).toBeInTheDocument();
    expect(
      screen.queryByText(/observations\.a_rule_added_after_these_translations/),
    ).not.toBeInTheDocument();
  });

  it('still renders English when English is the active language', async () => {
    fetchObservations.mockResolvedValue(observationsFixture());

    renderWithProviders(<InsightsPage />);

    expect(await screen.findByText('A longer cycle than most')).toBeInTheDocument();
  });

  it('translates a seek_care observation, which is the point of the issue', async () => {
    // `prolonged_bleeding` is one of the two rules
    // menstrual_insights_guidelines.md designates as a prompt to consult a
    // professional. A user who chose Tamil because she does not read
    // English fluently was being shown it in English.
    await i18n.changeLanguage('ta');
    fetchObservations.mockResolvedValue(
      observationsFixture({
        observations: [
          {
            code: 'prolonged_bleeding',
            severity: 'seek_care',
            title: 'A longer period than usual',
            body: 'You logged 9 days of bleeding starting 2026-05-01.',
            titleKey: 'observations.prolonged_bleeding.title',
            bodyKey: 'observations.prolonged_bleeding.body',
            evidence: { bleeding_days: 9, threshold_days: 8, start_date: '2026-05-01' },
            isMedicalAdvice: false,
            disclaimerKey: 'insights.disclaimer',
          },
        ],
        topObservation: null,
      }),
    );

    renderWithProviders(<InsightsPage />);

    await waitFor(() =>
      expect(screen.queryByText('A longer period than usual')).not.toBeInTheDocument(),
    );
    expect(
      screen.getByText(i18n.t('observations.prolonged_bleeding.title')),
    ).toBeInTheDocument();
  });
});
