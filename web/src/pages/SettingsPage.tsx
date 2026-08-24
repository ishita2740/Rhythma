import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/useAuth';
import { patchProfile } from '../api/endpoints';
import { useDocumentMeta } from '../lib/useDocumentMeta';
import { APP_LANGUAGES, isSameLanguage } from '../lib/supportedLanguages';

export function SettingsPage() {
  useDocumentMeta('meta.settings.title', 'meta.settings.description');
  const { t, i18n } = useTranslation();
  const { logout } = useAuth();

  // The list is what this app ships, not what a request happens to
  // return. It used to be seeded from a seven-entry literal and then
  // replaced by `GET /assistant/languages` — so Gujarati, which the
  // backend serves and `gu.json` fully translates, disappeared entirely
  // whenever that request failed, which is the condition this app is
  // built around. And the `catch(() => undefined)` meant the failure was
  // not reported either (#512).
  //
  // The endpoint is still the authority on what the *assistant* answers
  // in; that is `AppLanguage.assistant`, and it belongs on the assistant
  // screen rather than here. Which language the interface is in is a
  // fact about the bundle, and the bundle is local.
  const languages = APP_LANGUAGES;

  const changeLanguage = async (code: string) => {
    await i18n.changeLanguage(code);
    // Best-effort sync so the preference follows the user across devices.
    patchProfile({ language: code }).catch(() => undefined);
  };

  return (
    <div className="page">
      <header className="page-header">
        <h1>{t('settings.title')}</h1>
      </header>

      <section className="menu-list">
        <div className="menu-item glass-card">
          <span>🌐</span>
          <div className="menu-item-body">
            <span>{t('settings.language')}</span>
            <span className="card-sub">{t('settings.languageSubtitle')}</span>
          </div>
        </div>
        <div className="language-list">
          {languages.map((lang) => {
            // `isSameLanguage`, not `===`. The browser language detector
            // reports region tags, and `'hi-IN' === 'hi'` is false — so on
            // a phone set to Hindi this screen rendered in Hindi with no
            // chip highlighted, and the user had to select a language she
            // was already using to make the screen admit it (#512).
            const active = isSameLanguage(i18n.language, lang.code);
            return (
              <button
                key={lang.code}
                type="button"
                lang={lang.code}
                className={`chip${active ? ' active' : ''}`}
                aria-pressed={active}
                onClick={() => void changeLanguage(lang.code)}
              >
                {/* The name in its own script. Every chip but Gujarati
                    used to render this way; `LANGUAGE_KEY` had no `gu`
                    entry, so the one language nobody had added a key for
                    was shown in the wrong alphabet. */}
                {lang.nativeName}
              </button>
            );
          })}
        </div>

        <Link to="/sharing" className="menu-item glass-card">
          <span>🩺</span>
          <div className="menu-item-body">
            <span>{t('settings.sharing')}</span>
            <span className="card-sub">{t('settings.sharingSubtitle')}</span>
          </div>
          <span className="chevron">›</span>
        </Link>

        <Link to="/sms" className="menu-item glass-card">
          <span>📱</span>
          <div className="menu-item-body">
            <span>{t('settings.sms')}</span>
            <span className="card-sub">{t('settings.smsSubtitle')}</span>
          </div>
          <span className="chevron">›</span>
        </Link>

        <Link to="/settings/data" className="menu-item glass-card">
          <span>🔒</span>
          <div className="menu-item-body">
            <span>{t('settings.dataPrivacy')}</span>
            <span className="card-sub">{t('settings.dataPrivacySubtitle')}</span>
          </div>
          <span className="chevron">›</span>
        </Link>

        <a href="mailto:support@rhythma.com" className="menu-item glass-card">
          <span>💬</span>
          <div className="menu-item-body">
            <span>{t('settings.contactUs')}</span>
          </div>
          <span className="chevron">›</span>
        </a>
      </section>

      <section className="menu-list">
        <button type="button" className="menu-item glass-card" onClick={() => void logout()}>
          <span>🚪</span>
          <span>{t('settings.logOut')}</span>
          <span className="chevron">›</span>
        </button>
        {/* A link, not a button that deletes.
            This used to call `DELETE /auth/me` behind a `window.confirm`
            whose message was the button's own label, with the error
            swallowed and a `finally` that logged the user out either way —
            so a failed deletion was indistinguishable from a successful
            one. Deleting now happens on its own screen, where the user is
            shown what will be destroyed before she confirms it, and where
            a failure is reported instead of hidden (issue #418). */}
        <Link to="/settings/data" className="menu-item glass-card danger">
          <span>🗑️</span>
          <span>{t('settings.deleteAccount')}</span>
          <span className="chevron">›</span>
        </Link>
      </section>
    </div>
  );
}
