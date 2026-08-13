import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/useAuth';
import {
  confirmAccountDeletion,
  fetchDataExport,
  fetchDataSummary,
  requestAccountDeletion,
  type DataSummary,
  type DeletionPreview,
  type ExportFormat,
} from '../api/endpoints';

/**
 * See what is stored, download it, and delete the account (issue #418).
 *
 * The backend has had `/privacy/summary`, `/privacy/export` and the
 * two-step `/privacy/delete-account` since #270 and no client called any
 * of them. What Settings offered instead was a single `window.confirm`
 * over the legacy `DELETE /auth/me`, with an empty `catch` and a `finally`
 * that logged the user out either way — so a failed deletion looked
 * exactly like a successful one. On a menstrual-health app that is the
 * single worst thing to be wrong about.
 *
 * Three rules shape this screen:
 *
 * **Nothing is claimed that the server did not say.** Counts come from
 * the summary, the warning text comes from the deletion preview, and the
 * receipt at the end is the server's own per-collection counts.
 *
 * **Deletion is two steps, and the second one is deliberate.** The
 * preview is fetched first, so the confirmation names what will actually
 * be destroyed, and the confirm button stays disabled until the user
 * types the word. That is not friction for its own sake — this is
 * irreversible and destroys history a user may have spent years building.
 *
 * **A failure is reported.** If the delete call fails the user stays on
 * this page and is told, rather than being signed out into a screen that
 * implies it worked.
 */

/** What the user must type to arm the confirm button. */
const CONFIRMATION_WORD = 'DELETE';

type Stage = 'idle' | 'previewing' | 'confirming';

function formatDate(value: string | null | undefined, locale: string): string {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleDateString(locale);
}

/**
 * A message for the user, given whatever the API layer threw.
 *
 * Prefers the server's `detail` — a 409 saying no phone number is saved
 * is more useful than "something went wrong" — and separately names the
 * case where the request never reached the server at all, because
 * "offline" and "the server refused" call for different next steps.
 */
function friendlyError(error: unknown, fallback: string): string {
  if (error && typeof error === 'object' && 'isAxiosError' in error) {
    const axiosErr = error as {
      response?: { status?: number; data?: { detail?: string } };
    };
    if (!axiosErr.response) return fallback;
    if (axiosErr.response.data?.detail) return axiosErr.response.data.detail;
  }
  return fallback;
}

export function DataPrivacyPage() {
  const { t, i18n } = useTranslation();
  const { logout } = useAuth();
  const navigate = useNavigate();

  const [summary, setSummary] = useState<DataSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [downloading, setDownloading] = useState<ExportFormat | null>(null);
  const [exportError, setExportError] = useState('');
  const [exportedName, setExportedName] = useState('');

  const [stage, setStage] = useState<Stage>('idle');
  const [preview, setPreview] = useState<DeletionPreview | null>(null);
  const [typed, setTyped] = useState('');
  const [deleteError, setDeleteError] = useState('');
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setSummary(await fetchDataSummary());
    } catch (err) {
      setError(friendlyError(err, t('privacy.loadError')));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const download = async (format: ExportFormat) => {
    setDownloading(format);
    setExportError('');
    setExportedName('');
    try {
      const { blob, filename } = await fetchDataExport(format);

      // Saving is done here rather than in the API layer so that layer
      // stays testable without stubbing URL.createObjectURL.
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      // Revoked immediately: the browser has already read the blob by the
      // time click() returns, and an object URL that is never revoked
      // keeps the whole export alive in memory for the life of the tab.
      URL.revokeObjectURL(url);

      setExportedName(filename);
    } catch (err) {
      setExportError(friendlyError(err, t('privacy.exportError')));
    } finally {
      setDownloading(null);
    }
  };

  const startDeletion = async () => {
    setDeleteError('');
    setStage('previewing');
    try {
      setPreview(await requestAccountDeletion());
      setStage('confirming');
    } catch (err) {
      setDeleteError(friendlyError(err, t('privacy.deleteError')));
      setStage('idle');
    }
  };

  const cancelDeletion = () => {
    setStage('idle');
    setPreview(null);
    setTyped('');
    setDeleteError('');
  };

  const confirmDeletion = async () => {
    if (!preview) return;
    setDeleting(true);
    setDeleteError('');
    try {
      await confirmAccountDeletion(preview.confirmationToken);
    } catch (err) {
      // Deliberately *not* logging out. The previous implementation
      // signed the user out in a `finally`, so a failed deletion put her
      // on the login screen — indistinguishable from success, and she
      // would believe her health records were gone when they were not.
      setDeleteError(friendlyError(err, t('privacy.deleteError')));
      setDeleting(false);
      return;
    }

    // Only past a successful call. The server has already cleared the
    // auth cookies; `logout()` clears the client's own state and sends
    // her somewhere that exists.
    await logout('/login');
    navigate('/login', { replace: true });
  };

  if (loading && !summary) {
    return <div className="centered-loader">{t('common.loading')}</div>;
  }

  const impact = preview?.impact ?? summary;
  const canConfirm = typed.trim().toUpperCase() === CONFIRMATION_WORD && !deleting;

  return (
    <div className="page">
      <header className="page-header">
        <h1>{t('privacy.title')}</h1>
        <p className="card-sub">{t('privacy.subtitle')}</p>
      </header>

      {error ? (
        <div className="error-card">
          <p>{error}</p>
          <button type="button" className="primary-btn" onClick={() => void load()}>
            {t('common.retry')}
          </button>
        </div>
      ) : null}

      {summary ? (
        <section className="glass-card">
          <p className="card-label">{t('privacy.storedLabel')}</p>
          <p className="card-sub">
            {t('privacy.storedTotal', { count: summary.totalRecords })}
          </p>

          <ul className="data-category-list">
            {summary.categories.map((category) => (
              <li key={category.key} className="data-category">
                <div className="data-category-head">
                  <span className="data-category-label">{category.label}</span>
                  <span className="data-category-count">{category.recordCount}</span>
                </div>
                {category.earliestEntry ? (
                  <p className="card-sub">
                    {t('privacy.dateRange', {
                      from: formatDate(category.earliestEntry, i18n.language),
                      to: formatDate(category.latestEntry, i18n.language),
                    })}
                  </p>
                ) : null}
                <p className="card-sub">{category.retentionNote}</p>
                {category.storedFields.length > 0 ? (
                  <p className="data-category-fields">
                    {t('privacy.fields')}: {category.storedFields.join(', ')}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="glass-card">
        <p className="card-label">{t('privacy.exportLabel')}</p>
        <p className="card-sub">{t('privacy.exportBody')}</p>

        <div className="export-actions">
          <button
            type="button"
            className="primary-btn"
            disabled={downloading !== null}
            onClick={() => void download('json')}
          >
            {downloading === 'json' ? t('common.loading') : t('privacy.exportJson')}
          </button>
          <button
            type="button"
            className="ghost-btn"
            disabled={downloading !== null}
            onClick={() => void download('csv')}
          >
            {downloading === 'csv' ? t('common.loading') : t('privacy.exportCsv')}
          </button>
        </div>

        {exportedName ? (
          <p className="success-text">{t('privacy.exportReady', { filename: exportedName })}</p>
        ) : null}
        {exportError ? <p className="error-text">{exportError}</p> : null}
      </section>

      <section className="glass-card danger-zone">
        <p className="card-label">{t('privacy.deleteLabel')}</p>

        {stage !== 'confirming' ? (
          <>
            <p className="card-sub">{t('privacy.deleteBody')}</p>
            {deleteError ? <p className="error-text">{deleteError}</p> : null}
            <button
              type="button"
              className="danger-btn full"
              disabled={stage === 'previewing'}
              onClick={() => void startDeletion()}
            >
              {stage === 'previewing' ? t('common.loading') : t('privacy.deleteStart')}
            </button>
          </>
        ) : (
          <>
            {/* The server's own warning, not one written here. If the
                deletion cascade ever covers more, this sentence follows
                it without a client change. */}
            <p className="warning-text">{preview?.warning}</p>

            {impact ? (
              <ul className="deletion-impact">
                {impact.categories
                  .filter((category) => category.recordCount > 0)
                  .map((category) => (
                    <li key={category.key}>
                      {t('privacy.willDelete', {
                        count: category.recordCount,
                        label: category.label,
                      })}
                    </li>
                  ))}
              </ul>
            ) : null}

            <p className="card-sub">{t('privacy.exportFirst')}</p>

            <label className="confirm-field">
              {t('privacy.typeToConfirm', { word: CONFIRMATION_WORD })}
              <input
                value={typed}
                onChange={(event) => setTyped(event.target.value)}
                aria-label={t('privacy.typeToConfirm', { word: CONFIRMATION_WORD })}
                autoComplete="off"
              />
            </label>

            {deleteError ? <p className="error-text">{deleteError}</p> : null}

            <div className="export-actions">
              <button
                type="button"
                className="danger-btn"
                disabled={!canConfirm}
                onClick={() => void confirmDeletion()}
              >
                {deleting ? t('common.loading') : t('privacy.deleteConfirm')}
              </button>
              <button
                type="button"
                className="ghost-btn"
                disabled={deleting}
                onClick={cancelDeletion}
              >
                {t('common.cancel')}
              </button>
            </div>
          </>
        )}
      </section>

      <Link to="/settings" className="text-link">
        {t('privacy.backToSettings')}
      </Link>
    </div>
  );
}
