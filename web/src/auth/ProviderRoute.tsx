import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from './useAuth';

/**
 * Guards the provider dashboard. Unlike ProtectedRoute this is role-aware:
 * an anonymous visitor is sent to the provider login, and a logged-in
 * *patient* is bounced back to the patient app rather than shown provider
 * data.
 */
export function ProviderRoute({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    // Session validation (GET /auth/me) is still in flight.
    return <div className="centered-loader">Loading…</div>;
  }

  if (!user) {
    return <Navigate to="/provider/login" replace />;
  }

  if (user.role !== 'provider') {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
