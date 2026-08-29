import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/useAuth';
import {
  fetchObservations,
  type CycleConsistency,
  type Observation,
  type ObservationsResponse,
} from '../api/endpoints';
import { useDocumentMeta } from '../lib/useDocumentMeta';

// No MHS/CVI score here — this page is built entirely against the factual
// /insights/{user_id}/observations endpoint (issue #320). Every number and
// sentence below comes straight from the user's own logged data.

const SEVERITY_ICON: Record<Observation['severity'], string> = {
  info: 'ℹ️',
  attention: '💡',
  seek_care: '💗',
};

const CONSISTENCY_STYLE: Record<CycleConsistency, string> = {
  unknown: 'neutral',
  consistent: 'healthy',
  slightly_variable: 'moderate',
  variable: 'attention',
};

export function InsightsPage() {
  useDocumentMeta('meta.insights.title', 'meta.insights.description');
  const { t } = useTranslation();
  const { user } = useAuth();
  const [data, setData] = useState<ObservationsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError('');
    try {
      setData(await fetchObservations(user.id));
    } catch {
      setError(t('insights.loadError'));
    } finally {
      setLoading(false);
    }
  }, [t, user]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && !data) {
    return <div className="centered-loader">{t('common.loading')}</div>;
  }

  // Everything the page renders comes straight off the observations
  // response. There is no derived score here on purpose (#320): the block
  // that used to sit in this spot computed MHS, CVI and a cycle
  // "variability" figure from fields this endpoint does not return, and
  // rendered none of them.
  const observations = data?.observations ?? [];

  // `insufficient_data` is a signal, not a card. When the backend emits it
  // the user has too few logged cycles for any pattern to mean anything,
  // so the page shows one "keep logging" note instead of an observation
  // list — showing both would be telling her there is nothing to say and
  // then saying something.
  const isInsufficient = observations.some(
    (observation) => observation.code === 'insufficient_data',
  );
  const displayObservations = observations.filter(
    (observation) => observation.code !== 'insufficient_data',
  );

  const avgCycleLength = data?.averageCycleLength ?? null;
  const analyzedCount = data?.analyzedCycleCount ?? 0;
  const consistency: CycleConsistency = data?.cycleConsistency ?? 'unknown';
  // #306 requires the disclaimer on every insights surface, so it falls
  // back to the generic key rather than rendering nothing when the
  // response omits one.
  const disclaimerKey = data?.disclaimerKey ?? 'insights.disclaimer';

  return (
    <div className="page">
      <header className="page-header">
        <h1>{t('insights.title')}</h1>
        <p className="card-sub">{t('insights.subtitle')}</p>
      </header>

      {error ? (
        <div className="error-card">
          <p>{error}</p>
          <button type="button" className="primary-btn" onClick={() => void load()}>
            {t('common.retry')}
          </button>
        </div>
      ) : isInsufficient ? (
        <div className="warning-card">⏳ {t('insights.notEnoughData')}</div>
      ) : null}

      <section className="glass-card">
        <p className="card-label">{t('insights.cycleStatsLabel')}</p>
        <div className="mini-stats">
          <div className="glass-card mini-stat">
            <span className="mini-stat-icon" style={{ background: '#AA3BFF22', color: '#AA3BFF' }}>
              ♥
            </span>
            <p className="mini-stat-label">{t('insights.avgCycleLength')}</p>
            <p className="mini-stat-value">{avgCycleLength != null ? `${avgCycleLength}d` : '—'}</p>
          </div>
          <div className="glass-card mini-stat">
            <span className="mini-stat-icon" style={{ background: '#52B3B022', color: '#52B3B0' }}>
              #
            </span>
            <p className="mini-stat-label">{t('insights.cyclesAnalyzed')}</p>
            <p className="mini-stat-value">{analyzedCount}</p>
          </div>
        </div>
      </section>

      <section className="glass-card">
        <div className="trend-heading">
          <p className="card-label">{t('insights.consistencyLabel')}</p>
          <span className={`status-pill ${CONSISTENCY_STYLE[consistency]}`}>
            {t(`insights.consistency.${consistency}.pill`)}
          </span>
        </div>
        <p className="card-sub">{t(`insights.consistency.${consistency}.description`)}</p>
      </section>

      {!isInsufficient ? (
        <section>
          <h2 className="section-title">{t('insights.observationsLabel')}</h2>
          {displayObservations.length === 0 ? (
            <div className="glass-card empty-note">{t('insights.noObservations')}</div>
          ) : (
            displayObservations.map((observation) => (
              <ObservationCard key={observation.code} observation={observation} />
            ))
          )}
        </section>
      ) : null}

      <p className="disclaimer">{t(disclaimerKey)}</p>
    </div>
  );
}

function ObservationCard({ observation }: { observation: Observation }) {
  const { t } = useTranslation();
  return (
    <div className={`glass-card observation-card severity-${observation.severity}`}>
      <div className="observation-heading">
        <span className="observation-icon" aria-hidden="true">
          {SEVERITY_ICON[observation.severity] ?? 'ℹ️'}
        </span>
        <div>
          <p className="observation-severity-label">{t(`insights.severity.${observation.severity}`)}</p>
          <p className="observation-title">{observation.title}</p>
        </div>
      </div>
      <p className="observation-body">{observation.body}</p>
    </div>
  );
}
