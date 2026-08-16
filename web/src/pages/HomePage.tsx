import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/useAuth';
import { fetchDashboard, submitCycleLog, type CycleLogInput, type DashboardData } from '../api/endpoints';
import { ScoreRing } from '../components/charts';
import { PredictionCard } from '../components/PredictionCard';
import { toISODate } from '../lib/dates';
import { useDocumentMeta } from '../lib/useDocumentMeta';

type QuickField = 'flow_intensity' | 'mood' | 'sleep_hours' | 'stress_level';

interface QuickTileDef {
  field: QuickField;
  labelKey: string;
  emoji: string;
  options: { value: string; labelKey: string }[];
}

const QUICK_TILES: QuickTileDef[] = [
  {
    field: 'flow_intensity',
    labelKey: 'home.flow',
    emoji: '💧',
    options: [
      { value: 'none', labelKey: 'quickLog.none' },
      { value: 'light', labelKey: 'quickLog.light' },
      { value: 'medium', labelKey: 'quickLog.medium' },
      { value: 'heavy', labelKey: 'quickLog.heavy' },
    ],
  },
  {
    field: 'mood',
    labelKey: 'home.mood',
    emoji: '❤️',
    options: [
      { value: 'happy', labelKey: 'quickLog.happy' },
      { value: 'neutral', labelKey: 'quickLog.neutral' },
      { value: 'sad', labelKey: 'quickLog.sad' },
      { value: 'frustrated', labelKey: 'quickLog.frustrated' },
      { value: 'loved', labelKey: 'quickLog.loved' },
    ],
  },
  {
    field: 'sleep_hours',
    labelKey: 'home.sleep',
    emoji: '🌙',
    options: [
      { value: '4', labelKey: 'quickLog.sleep4' },
      { value: '6', labelKey: 'quickLog.sleep6' },
      { value: '8', labelKey: 'quickLog.sleep8' },
      { value: '9.5', labelKey: 'quickLog.sleep9_5' },
    ],
  },
  {
    field: 'stress_level',
    labelKey: 'home.stress',
    emoji: '🌬️',
    options: [
      { value: '1', labelKey: 'quickLog.stress1' },
      { value: '3', labelKey: 'quickLog.stress3' },
      { value: '5', labelKey: 'quickLog.stress5' },
    ],
  },
];

export function HomePage() {
  useDocumentMeta('meta.home.title', 'meta.home.description');
  const { t } = useTranslation();
  const { user } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTile, setActiveTile] = useState<QuickTileDef | null>(null);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setData(await fetchDashboard());
    } catch {
      setError(t('home.failedToLoad'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!activeTile) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setActiveTile(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeTile]);

  const handleQuickLog = async (option: { value: string; labelKey: string }) => {
    if (!activeTile || saving) return;
    setSaving(true);
    setFeedback('');
    try {
      const { field } = activeTile;
      const payload: CycleLogInput = { start_date: toISODate(new Date()) };
      if (field === 'sleep_hours') payload.sleep_hours = parseFloat(option.value);
      else if (field === 'stress_level') payload.stress_level = parseInt(option.value, 10);
      else if (field === 'flow_intensity') payload.flow_intensity = option.value;
      else payload.mood = option.value;
      await submitCycleLog(payload);
      setFeedback(`${t('home.logged', { label: t(option.labelKey) })}`);
      setActiveTile(null);
      void load();
    } catch {
      setFeedback(t('home.savedOffline'));
      setActiveTile(null);
    } finally {
      setSaving(false);
    }
  };

  const cycle = data?.cycle;
  const insights = data?.insights;
  const day = cycle?.day ?? 0;
  const total = cycle?.total ?? 28;
  const nextPeriod = cycle?.nextPeriodDays ?? null;

  if (loading && !data) {
    return <div className="centered-loader">{t('common.loading')}</div>;
  }

  return (
    <div className="home-page page">
      <header className="page-header">
        <h1>{t('home.welcome', { name: data?.user.name ?? user?.username ?? 'User' })}</h1>
      </header>

      {error ? (
        <div className="error-card">
          <p>{error}</p>
          <button type="button" className="primary-btn" onClick={() => void load()}>
            {t('common.retry')}
          </button>
        </div>
      ) : null}

      <section className="glass-card cycle-card">
        <div className="cycle-card-top">
          <ScoreRing value={total > 0 ? (day / total) * 100 : 0} size={120} label={t('home.cycleDay', { day, total })} />
          {/* Was a single clamped number and a fixed "Fertile window +
              High energy" string that showed on every cycle day whether
              or not it was true. Both now come from the server's
              `prediction` (#419). */}
          <div className="cycle-card-info">
            <PredictionCard prediction={data?.prediction} fallbackDays={nextPeriod} />
          </div>
        </div>

        <div className="stat-row">
          <div className="stat-cell">
            <span className="stat-label">{t('home.avgCycle')}</span>
            <span className="stat-value">{insights?.averageCycleLength == null ? '—' : insights.averageCycleLength}</span>
          </div>
          <div className="stat-cell">
            <span className="stat-label">{t('home.bleeding')}</span>
            <span className="stat-value">{insights?.averageBleedingDuration == null ? '—' : `${insights.averageBleedingDuration}d`}</span>
          </div>
          <div className="stat-cell">
            <span className="stat-label">{t('home.sleep')}</span>
            <span className="stat-value">{insights?.sleepHours ?? '—'}</span>
          </div>
        </div>
      </section>

      <Link to="/cycle" className="glass-card cycle-nav-card">
        <div>
          <p className="card-label">{t('cycle.title')}</p>
          <p className="insight-title">{t('home.todaysLog')}</p>
        </div>
        <span className="chevron">›</span>
      </Link>

      <Link to="/assistant" className="gradient-banner">
        <div>
          <p className="banner-title">{t('home.assistantTitle')}</p>
          <p className="banner-subtitle">{t('home.assistantSubtitle')}</p>
        </div>
        <span className="chat-pill">💬 {t('home.askRhythma')}</span>
      </Link>

      <section className="quick-log-section">
        <div className="section-heading">
          <h2>{t('home.todaysLog')}</h2>
        </div>
        <div className="quick-tiles">
          {QUICK_TILES.map((tile) => (
            <button
              key={tile.field}
              type="button"
              className="quick-tile"
              onClick={() => setActiveTile(tile)}
            >
              <span className="quick-tile-emoji">{tile.emoji}</span>
              <span>{t(tile.labelKey)}</span>
            </button>
          ))}
        </div>
        {feedback ? <p className="feedback-text">{feedback}</p> : null}
      </section>

      <Link to="/insights" className="glass-card insight-card">
        <div>
          <p className="card-label">{t('home.weeklyInsight')}</p>
          <p className="insight-title">{t('home.insightTitle')}</p>
        </div>
        <span className="chevron">›</span>
      </Link>

      {activeTile ? (
        <div className="modal-backdrop" role="presentation" onClick={() => setActiveTile(null)}>
          <div className="quick-log-panel" role="dialog" aria-label={t(activeTile.labelKey)} onClick={(e) => e.stopPropagation()}>
            <h3>
              {activeTile.emoji} {t(activeTile.labelKey)}
            </h3>
            <div className="chip-row">
              {activeTile.options.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  className="chip"
                  onClick={() => void handleQuickLog(opt)}
                >
                  {t(opt.labelKey)}
                </button>
              ))}
            </div>
            <button type="button" className="ghost-btn" onClick={() => setActiveTile(null)}>
              {t('common.cancel')}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
