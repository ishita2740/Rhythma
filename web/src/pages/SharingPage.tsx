import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import {
  fetchAccessLog,
  fetchConsents,
  grantConsent,
  revokeConsent,
  type AccessLogEntry,
  type Consent,
} from '../api/endpoints';
import { useDocumentMeta } from '../lib/useDocumentMeta';

/** Matches the server default in `access_log_service.DEFAULT_ACCESS_LOG_PAGE`. */
const ACCESS_LOG_PAGE_SIZE = 20;

function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString();
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString();
}

/**
 * What a consent row says about use, not just permission (issue #350).
 *
 * `viewCount` being undefined means the backend did not send the field —
 * an older server, or a client cached across a deploy. That is different
 * from a count of zero, and the row says nothing rather than claiming
 * "never viewed", which would be a statement this client cannot support.
 */
function accessSummary(
  t: (key: string, opts?: Record<string, unknown>) => string,
  consent: Consent,
): string | null {
  if (consent.viewCount == null) return null;
  if (consent.viewCount === 0) return t('sharing.neverViewed');
  return t('sharing.viewedSummary', {
    count: consent.viewCount,
    date: formatDateTime(consent.lastAccessedAt),
  });
}

export function SharingPage() {
  useDocumentMeta('meta.sharing.title', 'meta.sharing.description');
  const { t } = useTranslation();

  const [consents, setConsents] = useState<Consent[]>([]);
  const [accessLog, setAccessLog] = useState<AccessLogEntry[]>([]);
  const [accessLogNextOffset, setAccessLogNextOffset] = useState<number | null>(null);
  const [loadingMoreAccessLog, setLoadingMoreAccessLog] = useState(false);
  const [accessLogError, setAccessLogError] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  const load = async () => {
    try {
      // The access log is fetched alongside the consents but does not
      // gate them: a patient who cannot see her access history should
      // still be able to revoke, which is the more urgent action of the
      // two. `.catch` rather than a second try/except for that reason.
      const [nextConsents, log] = await Promise.all([
        fetchConsents(),
        fetchAccessLog(ACCESS_LOG_PAGE_SIZE, 0).catch(() => null),
      ]);
      setConsents(nextConsents);
      setAccessLog(log?.entries ?? []);
      // Issue #540: this page used to take `log.entries` and drop
      // `log.page`, so the list stopped at the first twenty rows with
      // nothing on screen to say so. The list is newest-first, which means
      // what fell off the end was the *oldest* history — and "has anyone
      // been looking at my records, and since when" is the question this
      // screen exists to answer.
      setAccessLogNextOffset(log?.page?.hasMore ? log.page.nextOffset : null);
      setAccessLogError('');
    } catch {
      setError(t('sharing.loadError'));
    } finally {
      setLoading(false);
    }
  };

  const loadMoreAccessLog = async () => {
    if (accessLogNextOffset === null || loadingMoreAccessLog) return;
    setLoadingMoreAccessLog(true);
    setAccessLogError('');
    try {
      const log = await fetchAccessLog(ACCESS_LOG_PAGE_SIZE, accessLogNextOffset);
      // Appended, and `nextOffset` comes off the server's envelope rather
      // than being computed from `accessLog.length` here — the server is
      // the only party that knows whether a short page means the history
      // ended or something was skipped.
      setAccessLog((current) => [...current, ...log.entries]);
      setAccessLogNextOffset(log.page?.hasMore ? log.page.nextOffset : null);
    } catch {
      // Deliberately narrow: a failed "load more" must not discard the
      // entries already on screen. A patient who can see fourteen rows and
      // cannot fetch the fifteenth should keep her fourteen.
      setAccessLogError(t('sharing.accessLogLoadMoreError'));
    } finally {
      setLoadingMoreAccessLog(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAdd = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setNotice('');
    setSubmitting(true);
    try {
      const consent = await grantConsent(email.trim());
      setEmail('');
      setNotice(t('sharing.added', { name: consent.provider_name }));
      await load();
    } catch (err) {
      if (
        err &&
        typeof err === 'object' &&
        'response' in err &&
        (err as { response?: { status?: number } }).response?.status === 404
      ) {
        setError(t('sharing.notFound'));
      } else {
        setError(t('sharing.loadError'));
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleRevoke = async (consent: Consent) => {
    if (!window.confirm(t('sharing.revokeConfirm', { name: consent.provider_name }))) return;
    setError('');
    setNotice('');
    try {
      await revokeConsent(consent.id);
      setNotice(t('sharing.revokedMsg'));
      await load();
    } catch {
      setError(t('sharing.loadError'));
    }
  };

  return (
    <div className="page">
      <header className="page-header">
        <h1>{t('sharing.title')}</h1>
      </header>

      <p className="card-sub" style={{ marginTop: -6 }}>
        {t('sharing.subtitle')}
      </p>

      {error && <p className="error-text">{error}</p>}
      {notice && <p className="card-sub">{notice}</p>}

      <section className="glass-card list-card detail-section">
        <h2>{t('sharing.addTitle')}</h2>
        <form className="auth-form" onSubmit={handleAdd} style={{ marginTop: 8 }}>
          <label>
            {t('sharing.providerEmail')}
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <button type="submit" disabled={submitting || !email.trim()}>
            {submitting ? t('sharing.adding') : t('sharing.addButton')}
          </button>
        </form>
        <p className="empty-note">{t('sharing.intro')}</p>
      </section>

      <section className="glass-card list-card detail-section">
        {loading ? (
          <p>{t('common.loading')}</p>
        ) : consents.length === 0 ? (
          <p className="empty-note">{t('sharing.empty')}</p>
        ) : (
          consents.map((consent) => (
            <div key={consent.id} className="list-row">
              <div className="list-row-main">
                <span className="list-row-title">{consent.provider_name}</span>
                <span className="list-row-sub">{consent.provider_email}</span>
                <span className="list-row-sub">
                  {t('sharing.grantedOn', { date: formatDate(consent.created_at) })}
                </span>
                {accessSummary(t, consent) ? (
                  <span className="list-row-sub">{accessSummary(t, consent)}</span>
                ) : null}
              </div>
              <span className={`badge ${consent.status}`}>
                {consent.status === 'active' ? t('sharing.active') : t('sharing.revoked')}
              </span>
              {consent.status === 'active' && (
                <button
                  type="button"
                  className="ghost-btn"
                  onClick={() => void handleRevoke(consent)}
                >
                  {t('sharing.revoke')}
                </button>
              )}
            </div>
          ))
        )}
      </section>

      <section className="glass-card list-card detail-section">
        <h2>{t('sharing.accessLogTitle')}</h2>
        <p className="card-sub">{t('sharing.accessLogSubtitle')}</p>

        {loading ? (
          <p>{t('common.loading')}</p>
        ) : accessLog.length === 0 ? (
          <p className="empty-note">{t('sharing.accessLogEmpty')}</p>
        ) : (
          <>
            {accessLog.map((entry) => (
              <div key={entry.id} className="list-row">
                <div className="list-row-main">
                  <span className="list-row-title">
                    {entry.providerName ?? t('sharing.unknownProvider')}
                  </span>
                  <span className="list-row-sub">
                    {entry.view === 'patient_detail'
                      ? t('sharing.viewedFullRecord')
                      : t('sharing.viewedSummaryCard')}
                  </span>
                </div>
                <span className="list-row-sub">{formatDateTime(entry.accessedAt)}</span>
              </div>
            ))}

            {accessLogError ? <p className="error-text">{accessLogError}</p> : null}

            {accessLogNextOffset !== null ? (
              <>
                {/* Said out loud while more remain, so the visible list is
                    never mistakable for the whole history. */}
                <p className="card-sub">
                  {t('sharing.accessLogShowing', { count: accessLog.length })}
                </p>
                <button
                  type="button"
                  className="ghost-btn"
                  disabled={loadingMoreAccessLog}
                  onClick={() => void loadMoreAccessLog()}
                >
                  {loadingMoreAccessLog
                    ? t('common.loading')
                    : t('sharing.accessLogLoadMore')}
                </button>
              </>
            ) : null}
          </>
        )}
      </section>
    </div>
  );
}
