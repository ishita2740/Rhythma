import { NavLink, Outlet } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/useAuth';
import { MAIN_CONTENT_ID } from './SkipToContent';

interface NavLinkDef {
  to: string;
  key: string;
  end?: boolean;
}

const LINKS: NavLinkDef[] = [
  { to: '/', key: 'nav.home', end: true },
  { to: '/cycle', key: 'nav.cycle' },
  { to: '/assistant', key: 'nav.assistant' },
  { to: '/insights', key: 'nav.insights' },
  { to: '/profile', key: 'nav.profile' },
  { to: '/sharing', key: 'nav.sharing' },
  { to: '/settings', key: 'nav.settings' },
];

export function AppLayout() {
  const { t } = useTranslation();
  const { logout } = useAuth();

  return (
    <div className="app-layout">
      <header className="app-header">
        <span className="app-brand" aria-hidden>
          Rhythma
        </span>
        <button type="button" className="ghost-btn" onClick={() => void logout()}>
          {t('nav.logout')}
        </button>
      </header>

      <nav className="app-nav" aria-label="Main">
        {LINKS.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.end}
            className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
          >
            {t(link.key)}
          </NavLink>
        ))}
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
