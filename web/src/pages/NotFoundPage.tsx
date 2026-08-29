import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useDocumentMeta } from '../lib/useDocumentMeta';

/**
 * Shown for any URL the router doesn't recognize.
 *
 * Replaces `<Route path="*" element={<Navigate to="/" replace />} />`,
 * which sent every unmatched URL to the home screen with no explanation.
 * That was wrong in three ways: a typo'd or stale link looked like a
 * successful navigation, `replace` destroyed the bad URL so the back
 * button couldn't return to where the user came from, and for a
 * signed-out user `/` is protected — so `ProtectedRoute` bounced them to
 * `/login` and a mistyped address presented as "you've been logged out".
 *
 * The URL is left intact and shown, so the user can see what was actually
 * requested and a bug report can quote it.
 */
export function NotFoundPage() {
  useDocumentMeta('meta.notFound.title', 'meta.notFound.description');
  const { t } = useTranslation();
  const location = useLocation();

  return (
    <div className="page not-found-page">
      <h1>{t('errors.notFoundTitle')}</h1>
      <p className="card-sub">{t('errors.notFoundBody')}</p>

      <p className="card-sub">
        <code className="not-found-path">{location.pathname}</code>
      </p>

      <div className="error-boundary-actions">
        <Link className="primary-btn" to="/">
          {t('errors.goHome')}
        </Link>
      </div>
    </div>
  );
}
