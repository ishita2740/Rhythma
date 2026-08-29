import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { fetchProviderPatientDetail, type ProviderPatientDetail } from '../api/endpoints';
import { useDocumentMeta } from '../lib/useDocumentMeta';

function formatDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString();
}

export function ProviderPatientDetailPage() {
  useDocumentMeta('meta.providerPatient.title', 'meta.providerPatient.description');
  const { patientId } = useParams<{ patientId: string }>();
  const { t } = useTranslation();

  const [detail, setDetail] = useState<ProviderPatientDetail | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!patientId) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchProviderPatientDetail(patientId);
        if (!cancelled) setDetail(data);
      } catch {
        if (!cancelled) setError(t('providerPatient.notFound'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [patientId, t]);

  if (loading) return <p>{t('common.loading')}</p>;

  if (error || !detail) {
    return (
      <div className="page">
        <p className="error-text">{error || t('providerPatient.notFound')}</p>
        <Link to="/provider">{t('providerPatient.back')}</Link>
      </div>
    );
  }

  const { patient, summary, cycleLogs } = detail;

  return (
    <div className="page">
      <header className="page-header">
        <h1>{patient.name}</h1>
      </header>

      <Link to="/provider" className="list-row-sub">
        ← {t('providerPatient.back')}
      </Link>

      <section className="glass-card provider-card detail-section">
        <h2>{t('providerPatient.profile')}</h2>
        <div className="stat-row">
          <div className="stat-cell">
            <span className="stat-label">{t('providerPatient.age')}</span>
            <span className="stat-value">{patient.age ?? '—'}</span>
          </div>
          <div className="stat-cell">
            <span className="stat-label">{t('providerPatient.location')}</span>
            <span className="stat-value">
              {[patient.city, patient.state].filter(Boolean).join(', ') || '—'}
            </span>
          </div>
          <div className="stat-cell">
            <span className="stat-label">{t('providerPatient.cycleLength')}</span>
            <span className="stat-value">{patient.cycle_length ?? '—'}</span>
          </div>
          <div className="stat-cell">
            <span className="stat-label">{t('providerPatient.periodDuration')}</span>
            <span className="stat-value">{patient.period_duration ?? '—'}</span>
          </div>
        </div>
        <span className="list-row-sub">
          {t('providerPatient.lastPeriod')}: {formatDate(patient.last_period)}
        </span>
      </section>

      <section className="glass-card provider-card detail-section">
        <h2>{t('providerPatient.summary')}</h2>
        <div className="stat-row">
          <div className="stat-cell">
            <span className="stat-label">{t('providerDashboard.mhs')}</span>
            <span className="stat-value">{summary.mhs ?? '—'}</span>
          </div>
          <div className="stat-cell">
            <span className="stat-label">{t('providerDashboard.cvi')}</span>
            <span className="stat-value">{summary.cvi ?? '—'}</span>
          </div>
          <div className="stat-cell">
            <span className="stat-label">{t('providerPatient.sleep')}</span>
            <span className="stat-value">
              {summary.avgSleepHours != null ? `${summary.avgSleepHours}h` : '—'}
            </span>
          </div>
          <div className="stat-cell">
            <span className="stat-label">
              {t('providerDashboard.cyclesLogged', { count: summary.loggedCycleCount })}
            </span>
            <span className="stat-value">{summary.loggedCycleCount}</span>
          </div>
        </div>
      </section>

      <section className="glass-card list-card detail-section">
        <h2>{t('providerPatient.cycleLogs')}</h2>
        {/* The table below is the server's analysis window, not the
            patient's whole history. It always was — `get_user_scores`
            fetches ten logs — but the stat above it said
            `loggedCycleCount`, which until #557 was also ten, so the two
            agreed and nothing suggested anything was missing. Now that
            the count is a real total, the difference is visible and has
            to be stated: a clinician reading twelve rows under a card
            saying "300 cycles" must not be left to guess which one is
            wrong. */}
        {summary.analyzedCycleCount > 0 &&
        summary.loggedCycleCount > summary.analyzedCycleCount ? (
          <p className="card-sub">
            {t('providerPatient.showingRecent', {
              shown: summary.analyzedCycleCount,
              total: summary.loggedCycleCount,
            })}
          </p>
        ) : null}
        {cycleLogs.length === 0 ? (
          <p className="empty-note">{t('providerPatient.noLogs')}</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>{t('providerPatient.date')}</th>
                <th>{t('providerPatient.flow')}</th>
                <th>{t('providerPatient.mood')}</th>
                <th>{t('providerPatient.symptoms')}</th>
                <th>{t('providerPatient.sleepHours')}</th>
                <th>{t('providerPatient.notes')}</th>
              </tr>
            </thead>
            <tbody>
              {cycleLogs.map((log) => (
                <tr key={log.id}>
                  <td>{formatDate(log.start_date)}</td>
                  <td>{log.flow_intensity ?? '—'}</td>
                  <td>{log.mood ?? '—'}</td>
                  <td>{log.symptoms?.length ? log.symptoms.join(', ') : '—'}</td>
                  <td>{log.sleep_hours != null ? `${log.sleep_hours}h` : '—'}</td>
                  <td>{log.notes || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
