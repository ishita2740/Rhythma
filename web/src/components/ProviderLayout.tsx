import { NavLink, Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/useAuth';
import { MAIN_CONTENT_ID } from './SkipToContent';

export function ProviderLayout() {
  const { t } = useTranslation();
  const { logout } = useAuth();

  return (
    <div className="app-layout">
      <header className="app-header">
        <span className="app-brand" aria-hidden>
          Rhythma
        </span>
        <button
          type="button"
          className="ghost-btn"
          onClick={() => void logout('/provider/login')}
        >
          {t('providerNav.logout')}
        </button>
      </header>

      <nav className="app-nav" aria-label="Provider">
        <NavLink
          to="/provider"
          end
          className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
        >
          {t('providerNav.dashboard')}
        </NavLink>
      </nav>

      {/* id and tabIndex make this the skip link's target and the
          place focus lands after a route change (#409). tabIndex={-1}
          is focusable programmatically but not by Tab, so it adds no
          stop to the keyboard order. */}
      <main id={MAIN_CONTENT_ID} tabIndex={-1} className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
