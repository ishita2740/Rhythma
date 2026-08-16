import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from './ProtectedRoute';

// Drive the gate directly through a stubbed useAuth: the point here is the
// control flow, not the session bootstrap (covered in AuthContext.test.tsx).
const authState = { user: null as { id: string } | null, loading: false };

vi.mock('./useAuth', () => ({
  useAuth: () => authState,
}));

function renderGate() {
  return render(
    <MemoryRouter initialEntries={['/private']}>
      <Routes>
        <Route
          path="/private"
          element={
            <ProtectedRoute>
              <div>secret content</div>
            </ProtectedRoute>
          }
        />
        <Route path="/login" element={<div>login page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ProtectedRoute', () => {
  it('renders the children for a signed-in user', () => {
    authState.user = { id: 'u1' };
    authState.loading = false;

    renderGate();

    expect(screen.getByText('secret content')).toBeInTheDocument();
  });

  it('redirects an anonymous visitor to /login', () => {
    authState.user = null;
    authState.loading = false;

    renderGate();

    expect(screen.getByText('login page')).toBeInTheDocument();
    expect(screen.queryByText('secret content')).not.toBeInTheDocument();
  });

  it('waits while the session is still being validated', () => {
    // Redirecting during validation would flash the login page at every
    // already-signed-in user on every full page load.
    authState.user = null;
    authState.loading = true;

    renderGate();

    expect(screen.queryByText('login page')).not.toBeInTheDocument();
    expect(screen.queryByText('secret content')).not.toBeInTheDocument();
  });

  it('does not leak protected content during validation even if a user is set', () => {
    authState.user = { id: 'u1' };
    authState.loading = true;

    renderGate();

    expect(screen.queryByText('secret content')).not.toBeInTheDocument();
  });
});
