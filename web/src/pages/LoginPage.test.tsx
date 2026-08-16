import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

const login = vi.fn();
const navigate = vi.fn();

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({ login, user: null, loading: false, register: vi.fn(), logout: vi.fn() }),
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

import { LoginPage } from './LoginPage';
import { renderWithProviders, axiosError } from '../test/utils';

beforeEach(() => {
  vi.clearAllMocks();
});

function fields() {
  // The inputs are labelled by wrapping <label> text, and the password
  // input is the only one of type="password".
  const inputs = screen.getAllByRole('textbox');
  const password = document.querySelector(
    'input[type="password"]',
  ) as HTMLInputElement;
  return { username: inputs[0] as HTMLInputElement, password };
}

describe('LoginPage', () => {
  it('renders a username field, a password field and a submit button', () => {
    renderWithProviders(<LoginPage />, { route: '/login' });

    const { username, password } = fields();
    expect(username).toBeInTheDocument();
    expect(password).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /log ?in|sign ?in/i })).toBeInTheDocument();
  });

  it('submits what the user typed', async () => {
    login.mockResolvedValue(undefined);
    renderWithProviders(<LoginPage />, { route: '/login' });

    const { username, password } = fields();
    await userEvent.type(username, 'asha');
    await userEvent.type(password, 'SecurePass123');
    await userEvent.click(screen.getByRole('button', { name: /log ?in|sign ?in/i }));

    await waitFor(() => expect(login).toHaveBeenCalledWith('asha', 'SecurePass123'));
  });

  it('navigates to the dashboard on success, replacing history', async () => {
    // `replace: true` matters: without it, Back from the dashboard lands
    // on the login page of an already-signed-in user.
    login.mockResolvedValue(undefined);
    renderWithProviders(<LoginPage />, { route: '/login' });

    const { username, password } = fields();
    await userEvent.type(username, 'asha');
    await userEvent.type(password, 'pw');
    await userEvent.click(screen.getByRole('button', { name: /log ?in|sign ?in/i }));

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/', { replace: true }));
  });

  it('shows an unreachable-server message rather than blaming the password', async () => {
    // The whole reason friendlyAuthError exists — a CORS failure or a
    // stopped backend used to be reported as "invalid credentials".
    login.mockRejectedValue(axiosError(undefined));
    renderWithProviders(<LoginPage />, { route: '/login' });

    const { username, password } = fields();
    await userEvent.type(username, 'asha');
    await userEvent.type(password, 'pw');
    await userEvent.click(screen.getByRole('button', { name: /log ?in|sign ?in/i }));

    expect(await screen.findByText(/Couldn't reach the server/i)).toBeInTheDocument();
  });

  it('surfaces a rate-limit message from the server', async () => {
    login.mockRejectedValue(axiosError(429, 'Too many login attempts. Please wait 5 minutes.'));
    renderWithProviders(<LoginPage />, { route: '/login' });

    const { username, password } = fields();
    await userEvent.type(username, 'asha');
    await userEvent.type(password, 'pw');
    await userEvent.click(screen.getByRole('button', { name: /log ?in|sign ?in/i }));

    expect(await screen.findByText(/wait 5 minutes/i)).toBeInTheDocument();
  });

  it('does not navigate when login fails', async () => {
    login.mockRejectedValue(axiosError(401));
    renderWithProviders(<LoginPage />, { route: '/login' });

    const { username, password } = fields();
    await userEvent.type(username, 'asha');
    await userEvent.type(password, 'wrong');
    await userEvent.click(screen.getByRole('button', { name: /log ?in|sign ?in/i }));

    await waitFor(() => expect(login).toHaveBeenCalled());
    expect(navigate).not.toHaveBeenCalled();
  });

  it('re-enables the button after a failure so the user can retry', async () => {
    login.mockRejectedValue(axiosError(401));
    renderWithProviders(<LoginPage />, { route: '/login' });

    const { username, password } = fields();
    const button = screen.getByRole('button', { name: /log ?in|sign ?in/i });
    await userEvent.type(username, 'asha');
    await userEvent.type(password, 'wrong');
    await userEvent.click(button);

    await waitFor(() => expect(button).not.toBeDisabled());
  });

  it('clears a previous error when the form is resubmitted', async () => {
    login.mockRejectedValueOnce(axiosError(401)).mockResolvedValueOnce(undefined);
    renderWithProviders(<LoginPage />, { route: '/login' });

    const { username, password } = fields();
    const button = screen.getByRole('button', { name: /log ?in|sign ?in/i });
    await userEvent.type(username, 'asha');
    await userEvent.type(password, 'wrong');
    await userEvent.click(button);
    await screen.findByText(/invalid/i);

    await userEvent.click(button);

    await waitFor(() => expect(screen.queryByText(/invalid/i)).not.toBeInTheDocument());
  });

  it('offers a link to registration', () => {
    renderWithProviders(<LoginPage />, { route: '/login' });
    expect(screen.getByRole('link', { name: /register/i })).toHaveAttribute('href', '/register');
  });

  it('marks both credential fields as required', () => {
    // The browser-native required attribute is what stops an empty POST;
    // dropping it would send blank credentials to the backend.
    renderWithProviders(<LoginPage />, { route: '/login' });
    const { username, password } = fields();
    expect(username).toBeRequired();
    expect(password).toBeRequired();
  });
});
