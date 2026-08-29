import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Issue #512, at the level the bugs were visible: a chip that never
// showed as selected, and a language that vanished when the network did.
vi.mock('../api/endpoints', () => ({
  patchProfile: vi.fn(),
}));

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({ user: { id: 'u1', username: 'asha' }, loading: false, logout: vi.fn() }),
}));

import { patchProfile } from '../api/endpoints';
import { SettingsPage } from './SettingsPage';
import i18n from '../i18n';
import { APP_LANGUAGES } from '../lib/supportedLanguages';
import { renderWithProviders } from '../test/utils';

const mockPatch = patchProfile as unknown as ReturnType<typeof vi.fn>;

beforeEach(async () => {
  vi.clearAllMocks();
  mockPatch.mockResolvedValue({});
  await i18n.changeLanguage('en');
});

describe('the language picker', () => {
  it('offers every locale the app ships', async () => {
    // It offered seven — and the seven omitted Gujarati, which the
    // backend serves and `gu.json` fully translates.
    renderWithProviders(<SettingsPage />);

    for (const lang of APP_LANGUAGES) {
      expect(
        await screen.findByRole('button', { name: lang.nativeName }),
        `no chip for ${lang.code}`,
      ).toBeInTheDocument();
    }
  });

  it('offers Gujarati with no network at all', async () => {
    // The list used to be seeded from a literal and replaced by
    // `GET /assistant/languages`; when that request failed — the
    // condition this app is built around — Gujarati was simply absent.
    // Nothing in this test mocks a successful fetch, because there is no
    // fetch any more.
    renderWithProviders(<SettingsPage />);

    expect(await screen.findByRole('button', { name: 'ગુજરાતી' })).toBeInTheDocument();
  });

  it('names every language in its own script', async () => {
    renderWithProviders(<SettingsPage />);

    // Gujarati rendered as the English string "Gujarati" because
    // `LANGUAGE_KEY` had no `gu` entry.
    expect(screen.queryByRole('button', { name: 'Gujarati' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'हिन्दी' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'اردو' })).toBeInTheDocument();
  });

  it('marks the active language when the tag carries a region', async () => {
    // The regression. `'hi-IN' === 'hi'` is false, so the screen rendered
    // in Hindi with nothing highlighted, and the user had to select a
    // language she was already using to make it admit so.
    await i18n.changeLanguage('hi-IN');
    renderWithProviders(<SettingsPage />);

    const hindi = await screen.findByRole('button', { name: 'हिन्दी' });
    expect(hindi).toHaveAttribute('aria-pressed', 'true');
    expect(hindi.className).toContain('active');
  });

  it('marks exactly one language active', async () => {
    await i18n.changeLanguage('ta-IN');
    renderWithProviders(<SettingsPage />);

    await waitFor(() => {
      const pressed = screen
        .getAllByRole('button')
        .filter((b) => b.getAttribute('aria-pressed') === 'true');
      expect(pressed).toHaveLength(1);
      expect(pressed[0]).toHaveTextContent('தமிழ்');
    });
  });

  it('switches the interface and syncs the preference', async () => {
    const user = userEvent.setup();
    renderWithProviders(<SettingsPage />);

    await user.click(await screen.findByRole('button', { name: 'मराठी' }));

    await waitFor(() => expect(i18n.language).toBe('mr'));
    expect(mockPatch).toHaveBeenCalledWith({ language: 'mr' });
  });

  it('tags each chip with its own lang so a screen reader switches voice', async () => {
    renderWithProviders(<SettingsPage />);

    const tamil = await screen.findByRole('button', { name: 'தமிழ்' });
    expect(tamil).toHaveAttribute('lang', 'ta');
  });
});
