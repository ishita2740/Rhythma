import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  fetchProviderProfile,
  fetchProviderPatientPage,
  type ProviderPatientSummary,
} from '../api/endpoints';
import { useDocumentMeta } from '../lib/useDocumentMeta';

/** Matches the server default in `provider_service.DEFAULT_PATIENTS_PAGE`. */
const PAGE_SIZE = 20;

function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString();
}

export function ProviderDashboardPage() {
  useDocumentMeta('meta.providerDashboard.title', 'meta.providerDashboard.description');
  const { t } = useTranslation();

  const [name, setName] = useState('');
  const [patients, setPatients] = useState<ProviderPatientSummary[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [profile, page] = await Promise.all([
          fetchProviderProfile(),
          fetchProviderPatientPage(PAGE_SIZE, 0),
        ]);
        if (cancelled) return;
        setName(profile.full_name || profile.username || profile.email);
        setPatients(page.patients);
        setNextOffset(page.page?.hasMore ? page.page.nextOffset : null);
      } catch {
        if (!cancelled) setError(t('providerDashboard.loadError'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [t]);

  async function loadMore() {
    if (nextOffset === null || loadingMore) return;
    setLoadingMore(true);
    try {
      const page = await fetchProviderPatientPage(PAGE_SIZE, nextOffset);
      // Appended rather than replaced, and `nextOffset` comes from the
      // server's envelope rather than being computed here — the server is
      // the only party that knows whether the page it just sent was short
      // because the roster ended or because a consent was revoked mid-scroll.
      setPatients((current) => [...current, ...page.patients]);
      setNextOffset(page.page?.hasMore ? page.page.nextOffset : null);
    } catch {
      setError(t('providerDashboard.loadError'));
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>{t('providerDashboard.title')}</h1>
      </header>

      <p className="card-sub" style={{ marginTop: -6 }}>
        {name ? t('providerDashboard.welcome', { name }) : ''}
      </p>

      {error && <p className="error-text">{error}</p>}
      {loading && <p>{t('common.loading')}</p>}

      {!loading && patients.length === 0 && (
        <div className="glass-card provider-card">
          <span>{t('providerDashboard.empty')}</span>
        </div>
      )}

      <div className="provider-grid">
        {patients.map((patient) => (
          <div key={patient.patient_id} className="glass-card provider-card">
            <span className="list-row-title">{patient.name}</span>
            <span className="list-row-sub">
              {[patient.age != null ? `${patient.age} yr` : null, patient.city, patient.state]
                .filter(Boolean)
                .join(' · ')}
            </span>
            <div className="stat-row">
              <div className="stat-cell">
                <span className="stat-label">{t('providerDashboard.cyclesLogged', { count: patient.loggedCycleCount })}</span>
                <span className="stat-value">{patient.loggedCycleCount}</span>
              </div>
              <div className="stat-cell">
                <span className="stat-label">{t('providerDashboard.mhs')}</span>
                <span className="stat-value">{patient.mhs ?? '—'}</span>
              </div>
              <div className="stat-cell">
                <span className="stat-label">{t('providerDashboard.cvi')}</span>
                <span className="stat-value">{patient.cvi ?? '—'}</span>
              </div>
            </div>
            <span className="list-row-sub">
              {t('providerPatient.grantedOn', { date: formatDate(patient.sharedSince) })}
            </span>
            <Link to={`/provider/patients/${patient.patient_id}`}>
              {t('providerDashboard.viewPatient')} →
            </Link>
          </div>
        ))}
      </div>

      {nextOffset !== null && (
        <button type="button" onClick={loadMore} disabled={loadingMore}>
          {loadingMore ? t('common.loading') : t('providerDashboard.loadMore')}
        </button>
      )}
    </div>
  );
}
