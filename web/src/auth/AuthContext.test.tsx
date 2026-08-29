import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../api/client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn() },
  setUnauthorizedHandler: vi.fn(),
  friendlyAuthError: vi.fn((_e: unknown, fallback: string) => fallback),
}));

import { apiClient, setUnauthorizedHandler } from '../api/client';
import { AuthProvider } from './AuthContext';
import { useAuth } from './useAuth';

const mockClient = apiClient as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
};

const USER = { id: 'u1', username: 'asha', email: 'asha@example.com' };

/** Exposes the context so tests can drive it without a real page. */
function Probe() {
  const { user, loading, login, register, logout } = useAuth();
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="user">{user ? user.username : 'anonymous'}</span>
      <button onClick={() => void login('asha', 'pw').catch(() => {})}>login</button>
      <button onClick={() => void register('asha', 'a@b.c', 'pw', 'Asha').catch(() => {})}>
        register
      </button>
      <button onClick={() => void logout()}>logout</button>
    </div>
  );
}

function renderProbe() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <Probe />
      </AuthProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('session bootstrap', () => {
  it('validates a stored session against /auth/me rather than assuming it', async () => {
    // Checking that a token *exists* is not the same as checking it is
    // still valid; the app deliberately asks the server.
    mockClient.get.mockResolvedValue({ data: USER });

    renderProbe();

    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'));
    expect(mockClient.get).toHaveBeenCalledWith('/auth/me');
    expect(screen.getByTestId('user')).toHaveTextContent('asha');
  });

  it('starts in a loading state so protected routes do not flash the login page', () => {
    mockClient.get.mockReturnValue(new Promise(() => {}));

    renderProbe();

    expect(screen.getByTestId('loading')).toHaveTextContent('true');
  });

  it('ends up anonymous when the stored session is rejected', async () => {
    mockClient.get.mockRejectedValue({ response: { status: 401 } });

    renderProbe();

    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'));
    expect(screen.getByTestId('user')).toHaveTextContent('anonymous');
  });

  it('ends up anonymous rather than stuck when the server is unreachable', async () => {
    // Offline must resolve loading, or ProtectedRoute renders its spinner
    // forever and the user cannot even reach the login page.
    mockClient.get.mockRejectedValue(new Error('network'));

    renderProbe();

    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'));
  });

  it('registers a handler for the 401 interceptor to call', async () => {
    mockClient.get.mockResolvedValue({ data: USER });

    renderProbe();

    await waitFor(() => expect(setUnauthorizedHandler).toHaveBeenCalled());
  });
});

describe('login', () => {
  it('posts to the endpoint the backend actually serves', async () => {
    // This is the #259 regression, locked down: the client once posted to
    // /auth/token, which does not exist. core/auth_router.py registers
    // /auth/login.
    mockClient.get.mockResolvedValue({ data: USER });
    mockClient.post.mockResolvedValue({ data: { token_type: 'bearer' } });

    renderProbe();
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'));
    await userEvent.click(screen.getByText('login'));

    await waitFor(() =>
      expect(mockClient.post).toHaveBeenCalledWith('/auth/login', {
        email: 'asha',
        password: 'pw',
      }),
    );
  });

  it('re-reads /auth/me after logging in instead of trusting the login body', async () => {
    // The web client ignores the access_token in the response body (that
    // is for Flutter); the cookie is already set, so it asks who it is.
    mockClient.get.mockResolvedValue({ data: USER });
    mockClient.post.mockResolvedValue({ data: {} });

    renderProbe();
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'));
    mockClient.get.mockClear();

    await userEvent.click(screen.getByText('login'));

    await waitFor(() => expect(mockClient.get).toHaveBeenCalledWith('/auth/me'));
  });

  it('leaves the user anonymous when the credentials are rejected', async () => {
    mockClient.get.mockResolvedValue({ data: null });
    mockClient.post.mockRejectedValue({ response: { status: 401 } });

    renderProbe();
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'));
    await userEvent.click(screen.getByText('login'));

    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('anonymous'));
  });
});

describe('register', () => {
  it('posts to /auth/register with the field names the backend model uses', async () => {
    // RegisterRequest expects full_name, not fullName.
    mockClient.get.mockResolvedValue({ data: USER });
    mockClient.post.mockResolvedValue({ data: {} });

    renderProbe();
    await waitFor(() => expect(screen.getByTestId('loading')).toHaveTextContent('false'));
    await userEvent.click(screen.getByText('register'));

    await waitFor(() =>
      expect(mockClient.post).toHaveBeenCalledWith('/auth/register', {
        username: 'asha',
        email: 'a@b.c',
        password: 'pw',
        full_name: 'Asha',
      }),
    );
  });
});

describe('logout', () => {
  it('tells the server to clear the cookie', async () => {
    // The cookie is HttpOnly, so the client cannot clear it itself —
    // skipping this call would leave the session alive on the server.
    mockClient.get.mockResolvedValue({ data: USER });
    mockClient.post.mockResolvedValue({ data: {} });

    renderProbe();
    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('asha'));
    await userEvent.click(screen.getByText('logout'));

    await waitFor(() => expect(mockClient.post).toHaveBeenCalledWith('/auth/logout'));
  });

  it('clears local state even when the logout call fails', async () => {
    mockClient.get.mockResolvedValue({ data: USER });
    mockClient.post.mockRejectedValue(new Error('offline'));

    renderProbe();
    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('asha'));
    await userEvent.click(screen.getByText('logout'));

    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('anonymous'));
  });
});

describe('useAuth guard', () => {
  it('throws a useful message outside a provider', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow(/must be used within an AuthProvider/);
    consoleError.mockRestore();
  });
});
