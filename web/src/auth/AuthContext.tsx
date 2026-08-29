import { useEffect, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient, setUnauthorizedHandler } from '../api/client';
import { clearAllHistories, clearLegacyHistory } from '../lib/chatHistory';
import { AuthContext, type User } from './auth-context';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  // Starts true: on first load we don't yet know if a stored token is
  // still valid, so protected routes should wait rather than flash
  // the login page.
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      // A 401 ends the session as surely as pressing Log out does, and it
      // is the *more* likely of the two to be followed by someone else
      // using the browser — an expired session is what a user walks away
      // from (#420).
      clearAllHistories();
      navigate('/login', { replace: true });
    });
  }, [navigate]);

  // The single shared `rhythma_chat_history` key every account used to
  // write to. There is no way to tell whose conversation it holds, which
  // is the whole problem with it, so it goes on first load whether or not
  // anyone is signed in.
  useEffect(() => {
    clearLegacyHistory();
  }, []);

  // On load, confirm any stored token is genuinely still valid by calling
  // /auth/me (not just checking that it exists) — same approach as the
  // Flutter app's splash-screen session validation.
  useEffect(() => {
    const validate = async () => {
      try {
        const response = await apiClient.get('/auth/me');
        setUser(response.data);
      } catch {
        // 401 is already handled by the response interceptor (clears
        // token). Any other failure (e.g. offline) just leaves the user
        // logged out for this session rather than guessing.
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
    validate();
  }, []);

  const login = async (username: string, password: string) => {
    await apiClient.post('/auth/login', { email: username, password });
    // If the token is valid, /auth/me will return the user info.
    // response body's access_token is for Flutter's benefit; web ignores it —
    // the cookie is already set by the backend.
    const me = await apiClient.get('/auth/me');
    setUser(me.data);
  };

  const register = async (
    username: string,
    email: string,
    password: string,
    fullName?: string,
    role?: string,
    specialty?: string,
    licenseNumber?: string,
  ) => {
    const body: Record<string, unknown> = {
      username,
      email,
      password,
      full_name: fullName || null,
    };
    if (role) body.role = role;
    if (specialty) body.specialty = specialty;
    if (licenseNumber) body.license_number = licenseNumber;
    await apiClient.post('/auth/register', body);
  };

  const loginProvider = async (email: string, password: string) => {
    await apiClient.post('/provider/login', { email, password });
    // Same pattern as patient login: the cookie is set by the backend, so
    // we ask /auth/me who we are rather than trusting the login response.
    const me = await apiClient.get('/auth/me');
    setUser(me.data);
  };

  const registerProvider = async (
    email: string,
    password: string,
    fullName?: string,
    specialty?: string,
    licenseNumber?: string,
  ) => {
    await apiClient.post('/provider/register', {
      email,
      password,
      full_name: fullName || null,
      specialty: specialty || null,
      license_number: licenseNumber || null,
    });
  };

  const logout = async (redirectTo = '/login') => {
    try {
      await apiClient.post('/auth/logout');
    } catch {
      // Ignore errors on logout
    } finally {
      setUser(null);
      // Here rather than in the Assistant screen, so it happens whichever
      // screen the user logged out from — and in the `finally`, so a
      // failed request to the server does not leave a health conversation
      // on a shared computer (#420).
      clearAllHistories();
      navigate(redirectTo, { replace: true });
    }
  };

  return (
    <AuthContext.Provider
      value={{ user, loading, login, register, loginProvider, registerProvider, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}
