import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const register = vi.fn();
const navigate = vi.fn();

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({ register, user: null, loading: false, login: vi.fn(), logout: vi.fn() }),
}));

vi.mock('../auth/AuthContext', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>(
    'react-router-dom',
  );
  return { ...actual, useNavigate: () => navigate };
});

import { RegisterPage } from './RegisterPage';
import { renderWithProviders } from '../test/utils';

beforeEach(() => {
  vi.clearAllMocks();
});

function fields() {
  const inputs = screen.getAllByRole('textbox');
  const password = document.querySelector('input[type="password"]') as HTMLInputElement;
  return {
    username: inputs[0] as HTMLInputElement,
    email: inputs[1] as HTMLInputElement,
    password,
  };
}

function rule(code: string) {
  return document.querySelector(`[data-rule="${code}"]`) as HTMLElement;
}

function weakPasswordError(messages: string[]) {
  return {
    isAxiosError: true,
    response: {
      status: 422,
      data: {
        detail: "That password doesn't meet the requirements.",
        error: {
          code: 'weak_password',
          details: messages.map((message, index) => ({ code: `rule_${index}`, message })),
        },
      },
    },
  };
}

describe('RegisterPage password requirements', () => {
  it('shows the requirements before anything is typed', async () => {
    renderWithProviders(<RegisterPage />, { route: '/register' });

    // A requirement discovered by failing is a requirement worked around,
    // not met — so it has to be on screen from the start.
    expect(rule('too_short')).toBeInTheDocument();
    expect(rule('too_common')).toBeInTheDocument();
    expect(rule('too_short').dataset.met).toBe('false');
  });

  it('ticks a requirement off as it is satisfied', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />, { route: '/register' });

    await user.type(fields().password, 'kolkata-monsoon-77');

    await waitFor(() => expect(rule('too_short').dataset.met).toBe('true'));
    expect(rule('too_common').dataset.met).toBe('true');
    expect(rule('sequential').dataset.met).toBe('true');
  });

  it('marks a common password as failing its rule', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />, { route: '/register' });

    await user.type(fields().password, 'password');

    await waitFor(() => expect(rule('too_common').dataset.met).toBe('false'));
  });

  it('reacts to the email the user typed, not just the password', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />, { route: '/register' });

    const { email, password } = fields();
    await user.type(email, 'sana@example.com');
    await user.type(password, 'sana-loves-mangoes');

    await waitFor(() => expect(rule('contains_identifier').dataset.met).toBe('false'));
  });

  it('keeps submit disabled until the password is acceptable', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />, { route: '/register' });

    const submit = screen.getByRole('button');
    expect(submit).toBeDisabled();

    await user.type(fields().password, 'abc');
    expect(submit).toBeDisabled();

    await user.type(fields().password, 'kolkata-monsoon-77');
    await waitFor(() => expect(submit).toBeEnabled());
  });

  it('does not call the API for a password it can already reject', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RegisterPage />, { route: '/register' });

    await user.type(fields().username, 'sanakumari');
    await user.type(fields().email, 'sana@example.com');
    await user.type(fields().password, '123456');
    await user.click(screen.getByRole('button'));

    expect(register).not.toHaveBeenCalled();
  });

  it('registers and navigates to login on success', async () => {
    const user = userEvent.setup();
    register.mockResolvedValueOnce(undefined);
    renderWithProviders(<RegisterPage />, { route: '/register' });

    await user.type(fields().username, 'sanakumari');
    await user.type(fields().email, 'sana@example.com');
    await user.type(fields().password, 'kolkata-monsoon-77');
    await user.click(screen.getByRole('button'));

    await waitFor(() => expect(register).toHaveBeenCalledTimes(1));
    expect(navigate).toHaveBeenCalledWith('/login', { replace: true });
  });

  it('renders the server’s own rule messages when it rejects the password', async () => {
    const user = userEvent.setup();
    register.mockRejectedValueOnce(
      weakPasswordError(['Use at least 8 characters.', 'That password is too common.']),
    );
    renderWithProviders(<RegisterPage />, { route: '/register' });

    await user.type(fields().username, 'sanakumari');
    await user.type(fields().email, 'sana@example.com');
    await user.type(fields().password, 'kolkata-monsoon-77');
    await user.click(screen.getByRole('button'));

    // The server decides, and it may enforce rules this build doesn't know
    // about — so its messages are shown verbatim rather than being mapped
    // back onto the local rule list.
    expect(await screen.findByText('Use at least 8 characters.')).toBeInTheDocument();
    expect(screen.getByText('That password is too common.')).toBeInTheDocument();
  });

  it('falls back to the generic message for a non-password failure', async () => {
    const user = userEvent.setup();
    register.mockRejectedValueOnce({
      isAxiosError: true,
      response: { status: 409, data: { detail: 'An account with this email already exists' } },
    });
    renderWithProviders(<RegisterPage />, { route: '/register' });

    await user.type(fields().username, 'sanakumari');
    await user.type(fields().email, 'sana@example.com');
    await user.type(fields().password, 'kolkata-monsoon-77');
    await user.click(screen.getByRole('button'));

    expect(
      await screen.findByText('An account with this email already exists'),
    ).toBeInTheDocument();
    expect(document.querySelector('[data-testid="server-password-errors"]')).toBeNull();
  });

  it('clears previous server errors on the next submission', async () => {
    const user = userEvent.setup();
    register
      .mockRejectedValueOnce(weakPasswordError(['That password is too common.']))
      .mockResolvedValueOnce(undefined);
    renderWithProviders(<RegisterPage />, { route: '/register' });

    await user.type(fields().username, 'sanakumari');
    await user.type(fields().email, 'sana@example.com');
    await user.type(fields().password, 'kolkata-monsoon-77');
    await user.click(screen.getByRole('button'));
    expect(await screen.findByText('That password is too common.')).toBeInTheDocument();

    await user.click(screen.getByRole('button'));

    await waitFor(() =>
      expect(screen.queryByText('That password is too common.')).not.toBeInTheDocument(),
    );
  });

  it('associates the requirements with the password field for screen readers', () => {
    renderWithProviders(<RegisterPage />, { route: '/register' });

    const password = document.querySelector('input[type="password"]') as HTMLInputElement;
    expect(password.getAttribute('aria-describedby')).toBe('password-requirements');
    expect(document.getElementById('password-requirements')).toBeInTheDocument();
  });

  it('states each requirement in words, not only in colour', () => {
    // Colour alone would carry the met/unmet state for nobody using a
    // screen reader and for anyone with a red-green colour vision
    // deficiency.
    renderWithProviders(<RegisterPage />, { route: '/register' });

    expect(rule('too_short').textContent).toMatch(/8/);
    expect(rule('too_common').textContent?.trim().length).toBeGreaterThan(10);
  });
});
