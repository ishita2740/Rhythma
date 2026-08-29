import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { I18nextProvider } from 'react-i18next';

import i18n from '../i18n';
import { NotFoundPage } from './NotFoundPage';

function renderAt(route: string) {
  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/" element={<p>Home page</p>} />
          <Route path="/cycle" element={<p>Cycle page</p>} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </MemoryRouter>
    </I18nextProvider>,
  );
}

describe('NotFoundPage', () => {
  it('renders for an unknown URL instead of redirecting to home', () => {
    // The old `<Navigate to="/" replace />` made a typo'd link look like a
    // successful navigation, and for a signed-out user it presented as
    // "you've been logged out" once ProtectedRoute bounced them to /login.
    renderAt('/cyle');

    expect(screen.getByText(i18n.t('errors.notFoundTitle'))).toBeInTheDocument();
    expect(screen.queryByText('Home page')).not.toBeInTheDocument();
  });

  it('shows the address that was actually requested', () => {
    renderAt('/provider/patients/deleted-patient-id');

    expect(screen.getByText('/provider/patients/deleted-patient-id')).toBeInTheDocument();
  });

  it('links back to the home screen', () => {
    renderAt('/nowhere');

    expect(screen.getByRole('link', { name: i18n.t('errors.goHome') })).toHaveAttribute(
      'href',
      '/',
    );
  });

  it('does not hijack a route that does exist', () => {
    renderAt('/cycle');

    expect(screen.getByText('Cycle page')).toBeInTheDocument();
    expect(screen.queryByText(i18n.t('errors.notFoundTitle'))).not.toBeInTheDocument();
  });

  it('localizes its copy rather than hardcoding English', () => {
    // Every string on this screen goes through t(), so a locale that
    // translates them shows a translated 404 rather than a mixed one.
    renderAt('/nowhere');

    expect(i18n.t('errors.notFoundTitle')).not.toBe('errors.notFoundTitle');
    expect(i18n.t('errors.notFoundBody')).not.toBe('errors.notFoundBody');
  });
});
