import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';

// Issue #512. The assistant picker offered Bengali, the interface
// switched to Bengali, and the reply came back in English with no
// explanation — because `bn` is a complete locale here and not a language
// `POST /assistant/chat` serves.
vi.mock('../api/endpoints', () => ({
  sendChatMessage: vi.fn(),
}));

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({ user: { id: 'u1', username: 'asha' }, loading: false, logout: vi.fn() }),
}));

import { sendChatMessage } from '../api/endpoints';
import { AssistantPage } from './AssistantPage';
import i18n from '../i18n';
import { APP_LANGUAGES, ASSISTANT_LANGUAGE_CODES } from '../lib/supportedLanguages';
import { renderWithProviders } from '../test/utils';

const mockSend = sendChatMessage as unknown as ReturnType<typeof vi.fn>;

beforeEach(async () => {
  vi.clearAllMocks();
  localStorage.clear();
  mockSend.mockResolvedValue({
    response: 'An answer.',
    language: 'en',
    disclaimer: 'Please consult a healthcare professional for medical advice.',
  });
  await i18n.changeLanguage('en');
});

afterEach(async () => {
  await i18n.changeLanguage('en');
});

describe('the assistant language picker', () => {
  it('offers every locale the app ships', async () => {
    renderWithProviders(<AssistantPage />);

    const select = await screen.findByRole('combobox');
    const values = Array.from(select.querySelectorAll('option')).map((o) => o.value);

    expect(values).toEqual(APP_LANGUAGES.map((l) => l.code));
  });

  it('selects the current language when the tag carries a region', async () => {
    await i18n.changeLanguage('hi-IN');
    renderWithProviders(<AssistantPage />);

    expect(await screen.findByRole('combobox')).toHaveValue('hi');
  });

  it('selects a three-letter code without truncating it', async () => {
    // `.slice(0, 2)` turned `mai` into `ma`, which matched no option, so
    // the select silently showed the first entry instead.
    await i18n.changeLanguage('mai');
    renderWithProviders(<AssistantPage />);

    expect(await screen.findByRole('combobox')).toHaveValue('mai');
  });

  it('says so when the assistant cannot answer in this language', async () => {
    // The whole point. `isAssistantLanguageFallback` was written for this
    // and nothing imported it, so nine of the seventeen shipped locales
    // got an English reply with no explanation.
    await i18n.changeLanguage('bn');
    renderWithProviders(<AssistantPage />);

    const notice = await screen.findByRole('status');
    expect(notice).toHaveTextContent(/cannot answer in this language/i);
  });

  it('says nothing when the assistant does answer in this language', async () => {
    await i18n.changeLanguage('hi');
    renderWithProviders(<AssistantPage />);

    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  });

  it('says nothing in English, where there is no fallback to report', async () => {
    renderWithProviders(<AssistantPage />);

    await waitFor(() => expect(screen.queryByRole('status')).not.toBeInTheDocument());
  });

  it('warns for every locale the assistant does not serve', async () => {
    const unserved = APP_LANGUAGES.filter(
      (l) => !ASSISTANT_LANGUAGE_CODES.includes(l.code),
    );
    expect(unserved.length).toBeGreaterThan(0);

    for (const lang of unserved) {
      await i18n.changeLanguage(lang.code);
      const { unmount } = renderWithProviders(<AssistantPage />);

      expect(
        await screen.findByRole('status'),
        `no fallback notice for ${lang.code}`,
      ).toBeInTheDocument();

      unmount();
    }
  });
});
