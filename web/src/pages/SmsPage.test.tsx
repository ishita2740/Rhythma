import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// The SMS screen used to promise something nothing delivered and refuse
// something that looked like it should work (issue #532):
//
//   - "Enable weekly SMS summaries" wrote a flag with no reader.
//   - "Send now" posted the *live input value* as the destination, so
//     typing a number and sending before saving was a 403 telling the
//     user her own number was not hers.
//   - The element whose class is `sms-preview` rendered the phone number,
//     so the destination sat where the preview belongs and the message
//     about her cycle was shown nowhere before it reached her phone.
//
// These tests are mostly about that third state — what the screen *says*
// is going to happen, as distinct from what it sends.
vi.mock('../api/endpoints', () => ({
  fetchSmsSettings: vi.fn(),
  saveSmsSettings: vi.fn(),
  sendSmsSummary: vi.fn(),
  fetchSmsPreview: vi.fn(),
}));

import {
  fetchSmsPreview,
  fetchSmsSettings,
  saveSmsSettings,
  sendSmsSummary,
} from '../api/endpoints';
import { SmsPage } from './SmsPage';
import { renderWithProviders } from '../test/utils';

const mockSettings = fetchSmsSettings as unknown as ReturnType<typeof vi.fn>;
const mockSave = saveSmsSettings as unknown as ReturnType<typeof vi.fn>;
const mockSend = sendSmsSummary as unknown as ReturnType<typeof vi.fn>;
const mockPreview = fetchSmsPreview as unknown as ReturnType<typeof vi.fn>;

const PHONE = '+919876543210';
const OTHER_PHONE = '+919000000000';

const SUMMARY =
  'Rhythma Summary: Cycle Day 12/28. Next period expected in ~16 days. Estimate only, not medical/contraceptive advice.';

function previewFixture(overrides: Record<string, unknown> = {}) {
  return {
    body: SUMMARY,
    destination: PHONE,
    characters: SUMMARY.length,
    enabled: true,
    ...overrides,
  };
}

function settingsFixture(overrides: Record<string, unknown> = {}) {
  return { phoneNumber: PHONE, enabled: true, ...overrides };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockSettings.mockResolvedValue(settingsFixture());
  mockPreview.mockResolvedValue(previewFixture());
  mockSave.mockImplementation(async (settings) => settings);
  mockSend.mockResolvedValue({ message: 'SMS sent successfully', sid: 'SM1' });
});

async function renderPage() {
  renderWithProviders(<SmsPage />);
  await waitFor(() => expect(mockSettings).toHaveBeenCalled());
  return screen.findByRole('button', { name: /send/i });
}

describe('the preview', () => {
  it('shows the message that will be sent, not the phone number', async () => {
    await renderPage();

    expect(await screen.findByText(SUMMARY)).toBeInTheDocument();
  });

  it('asks the server for it rather than composing one locally', async () => {
    // A preview assembled from different data than the send path is a
    // preview of a different message.
    await renderPage();

    await waitFor(() => expect(mockPreview).toHaveBeenCalled());
  });

  it('is not fetched when no number has been saved', async () => {
    mockSettings.mockResolvedValue(settingsFixture({ phoneNumber: '', enabled: false }));

    await renderPage();

    expect(mockPreview).not.toHaveBeenCalled();
  });

  it('survives a failed preview without breaking the settings form', async () => {
    mockPreview.mockRejectedValue(new Error('offline'));

    await renderPage();

    expect(screen.getByLabelText(/phone number/i)).toBeInTheDocument();
  });
});

describe('send now', () => {
  it('sends without choosing a destination or a body', async () => {
    // Neither is the client's to pick.
    await renderPage();

    await userEvent.click(screen.getByRole('button', { name: /^send$/i }));

    await waitFor(() => expect(mockSend).toHaveBeenCalledWith());
  });

  it('refuses to send an edited number that has not been saved', async () => {
    await renderPage();

    const input = screen.getByLabelText(/phone number/i);
    await userEvent.clear(input);
    await userEvent.type(input, OTHER_PHONE);

    expect(screen.getByRole('button', { name: /^send$/i })).toBeDisabled();
    expect(mockSend).not.toHaveBeenCalled();
  });

  it('says why, rather than leaving the button mysteriously dead', async () => {
    await renderPage();

    const input = screen.getByLabelText(/phone number/i);
    await userEvent.clear(input);
    await userEvent.type(input, OTHER_PHONE);

    expect(await screen.findByText(/save your settings before sending/i)).toBeInTheDocument();
  });

  it('is unavailable when summaries are switched off', async () => {
    // The server refuses this now, so offering it would be a button whose
    // only outcome is an error.
    mockSettings.mockResolvedValue(settingsFixture({ enabled: false }));

    await renderPage();

    expect(screen.getByRole('button', { name: /^send$/i })).toBeDisabled();
  });

  it('is unavailable when no number is saved', async () => {
    mockSettings.mockResolvedValue(settingsFixture({ phoneNumber: '', enabled: false }));

    await renderPage();

    expect(screen.getByRole('button', { name: /^send$/i })).toBeDisabled();
  });

  it('names the number it went to on success', async () => {
    await renderPage();

    await userEvent.click(screen.getByRole('button', { name: /^send$/i }));

    const status = await screen.findByRole('status');
    expect(status).toHaveTextContent(PHONE);
  });

  it('refreshes the preview after sending', async () => {
    // The send counts against the weekly cadence server-side, so what the
    // screen is showing has just gone stale.
    await renderPage();
    mockPreview.mockClear();

    await userEvent.click(screen.getByRole('button', { name: /^send$/i }));

    await waitFor(() => expect(mockPreview).toHaveBeenCalled());
  });

  it('reports the server’s own message when a send is refused', async () => {
    mockSend.mockRejectedValue({
      isAxiosError: true,
      response: { status: 409, data: { detail: 'SMS summaries are switched off for this account.' } },
    });

    await renderPage();
    await userEvent.click(screen.getByRole('button', { name: /^send$/i }));

    expect(await screen.findByText(/switched off/i)).toBeInTheDocument();
  });
});

describe('saving settings', () => {
  it('is offered only when something has changed', async () => {
    await renderPage();

    expect(screen.getByRole('button', { name: /save settings/i })).toBeDisabled();
  });

  it('confirms in a sentence rather than a bare tick', async () => {
    // The old screen set the success message to the string "✓" — the same
    // untranslated glyph in all seventeen locales, saying nothing about
    // what had been saved.
    await renderPage();

    const input = screen.getByLabelText(/phone number/i);
    await userEvent.clear(input);
    await userEvent.type(input, OTHER_PHONE);
    await userEvent.click(screen.getByRole('button', { name: /save settings/i }));

    expect(await screen.findByText(/settings saved/i)).toBeInTheDocument();
  });

  it('adopts the values the server echoes back', async () => {
    // The server is the authority on what is stored, and "send now" is
    // gated on that, not on what was typed.
    mockSave.mockResolvedValue({ phoneNumber: OTHER_PHONE, enabled: true });

    await renderPage();
    const input = screen.getByLabelText(/phone number/i);
    await userEvent.clear(input);
    await userEvent.type(input, OTHER_PHONE);
    await userEvent.click(screen.getByRole('button', { name: /save settings/i }));

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /^send$/i })).toBeEnabled(),
    );
  });

  it('re-fetches the preview after a save', async () => {
    await renderPage();
    mockPreview.mockClear();

    const input = screen.getByLabelText(/phone number/i);
    await userEvent.clear(input);
    await userEvent.type(input, OTHER_PHONE);
    await userEvent.click(screen.getByRole('button', { name: /save settings/i }));

    await waitFor(() => expect(mockPreview).toHaveBeenCalled());
  });

  it('rejects a number that is not E.164 before calling the server', async () => {
    await renderPage();

    const input = screen.getByLabelText(/phone number/i);
    await userEvent.clear(input);
    await userEvent.type(input, '98765');
    await userEvent.click(screen.getByRole('button', { name: /save settings/i }));

    expect(await screen.findByText(/E\.164/i)).toBeInTheDocument();
    expect(mockSave).not.toHaveBeenCalled();
  });

  it('reports a failed save instead of leaving the form looking saved', async () => {
    mockSave.mockRejectedValue({
      isAxiosError: true,
      response: { status: 500, data: { detail: 'Saving your profile failed' } },
    });

    await renderPage();
    const input = screen.getByLabelText(/phone number/i);
    await userEvent.clear(input);
    await userEvent.type(input, OTHER_PHONE);
    await userEvent.click(screen.getByRole('button', { name: /save settings/i }));

    expect(await screen.findByText(/Saving your profile failed/i)).toBeInTheDocument();
  });
});

describe('what the screen promises', () => {
  it('explains the cadence next to the toggle', async () => {
    // The toggle's label promises a weekly text. Until #532 nothing sent
    // one, and nothing on the screen said when to expect it.
    await renderPage();

    expect(screen.getByText(/once a week/i)).toBeInTheDocument();
  });
});
