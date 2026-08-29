import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Issue #509. The bug this file is about is not "there is no clear
// button" — there was one, and it worked on everything except the copy
// that matters. `clearHistory()` removed a localStorage key and the screen
// emptied, while the transcript the model is given stayed on the server
// and went into the next prompt. So a user who cleared a conversation
// about a possible pregnancy asked something unrelated next and was
// answered in the context of the conversation she had just deleted.
//
// The two tests that matter here are `calls the server` and `does not
// clear the local transcript when the server call fails`. The rest
// describe the surface around them.
vi.mock('../api/endpoints', () => ({
  sendChatMessage: vi.fn(),
  clearAssistantConversation: vi.fn(),
}));

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({ user: { id: 'u1', username: 'asha' }, loading: false, logout: vi.fn() }),
}));

import { clearAssistantConversation, sendChatMessage } from '../api/endpoints';
import { AssistantPage } from './AssistantPage';
import { loadHistory, saveHistory } from '../lib/chatHistory';
import { renderWithProviders } from '../test/utils';

const mockSend = sendChatMessage as unknown as ReturnType<typeof vi.fn>;
const mockClear = clearAssistantConversation as unknown as ReturnType<typeof vi.fn>;

const USER_ID = 'u1';

function seedTranscript() {
  saveHistory(USER_ID, [
    { role: 'user', content: 'Could I be pregnant?' },
    { role: 'model', content: 'Here is what the dates suggest.' },
  ]);
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  mockClear.mockResolvedValue({ cleared: true, messagesRemoved: 2 });
  mockSend.mockResolvedValue({
    response: 'An answer.',
    language: 'en',
    disclaimer: 'Please consult a healthcare professional for medical advice.',
  });
});

async function clickClear() {
  const user = userEvent.setup();
  const button = await screen.findByRole('button', { name: /clear conversation/i });
  await user.click(button);
  return user;
}

describe('clearing the assistant conversation', () => {
  it('offers the control only once there is something to clear', async () => {
    renderWithProviders(<AssistantPage />);

    expect(
      screen.queryByRole('button', { name: /clear conversation/i }),
    ).not.toBeInTheDocument();

    localStorage.clear();
    seedTranscript();
    renderWithProviders(<AssistantPage />);

    expect(
      await screen.findByRole('button', { name: /clear conversation/i }),
    ).toBeInTheDocument();
  });

  it('asks the server to delete the stored conversation', async () => {
    seedTranscript();
    renderWithProviders(<AssistantPage />);

    await clickClear();

    await waitFor(() => expect(mockClear).toHaveBeenCalledTimes(1));
  });

  it('clears the local transcript once the server has confirmed', async () => {
    seedTranscript();
    expect(loadHistory(USER_ID)).toHaveLength(2);

    renderWithProviders(<AssistantPage />);
    await clickClear();

    await waitFor(() => expect(loadHistory(USER_ID)).toEqual([]));
  });

  it('empties the visible conversation back to the greeting', async () => {
    seedTranscript();
    renderWithProviders(<AssistantPage />);

    expect(await screen.findByText(/could i be pregnant\?/i)).toBeInTheDocument();

    await clickClear();

    await waitFor(() =>
      expect(screen.queryByText(/could i be pregnant\?/i)).not.toBeInTheDocument(),
    );
  });

  it('does not clear the local transcript when the server call fails', async () => {
    // The order is the fix. Emptying the screen first and then failing
    // would leave the user believing something untrue — which is the
    // failure this issue is about, one layer down.
    mockClear.mockRejectedValue(new Error('network'));
    seedTranscript();

    renderWithProviders(<AssistantPage />);
    await clickClear();

    await waitFor(() => expect(mockClear).toHaveBeenCalled());
    expect(loadHistory(USER_ID)).toHaveLength(2);
    expect(screen.getByText(/could i be pregnant\?/i)).toBeInTheDocument();
  });

  it('says so when the clear failed', async () => {
    mockClear.mockRejectedValue(new Error('network'));
    seedTranscript();

    renderWithProviders(<AssistantPage />);
    await clickClear();

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(/still saved/i);
  });

  it('does not send a second delete while one is in flight', async () => {
    let release: (value: unknown) => void = () => {};
    mockClear.mockImplementation(
      () => new Promise((resolve) => { release = resolve; }),
    );
    seedTranscript();

    renderWithProviders(<AssistantPage />);
    const user = await clickClear();

    const button = screen.getByRole('button', { name: /clearing/i });
    expect(button).toBeDisabled();
    await user.click(button);

    expect(mockClear).toHaveBeenCalledTimes(1);
    release({ cleared: true, messagesRemoved: 2 });
  });

  it('tells the user the conversation is saved to her account, not only on the device', async () => {
    // The old string read "kept on this device and cleared when you log
    // out", which was not true of the copy the assistant is actually
    // given.
    renderWithProviders(<AssistantPage />);

    const notice = await screen.findByText(/saved to your account/i);
    expect(notice).toBeInTheDocument();
    expect(screen.queryByText(/cleared when you log out/i)).not.toBeInTheDocument();
  });
});
