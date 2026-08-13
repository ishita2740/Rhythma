import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/useAuth';
import {
  deleteCycleLog,
  fetchCycleHistoryRange,
  fetchPredictions,
  fetchProfile,
  submitCycleLog,
  type CycleLogEntry,
  type CycleLogInput,
  type PredictionResponse,
} from '../api/endpoints';
import {
  addMonths,
  formatDayMonth,
  formatMonthYear,
  isSameDay,
  monthWindow,
  parseISODate,
  PHASE_COLORS,
  phaseFor,
  startOfMonth,
  toISODate,
  type CyclePhase,
} from '../lib/dates';
import { useDocumentMeta } from '../lib/useDocumentMeta';

interface OptionDef {
  value: string;
  labelKey: string;
}

const FLOW_OPTIONS: OptionDef[] = [
  { value: 'none', labelKey: 'quickLog.none' },
  { value: 'light', labelKey: 'quickLog.light' },
  { value: 'medium', labelKey: 'quickLog.medium' },
  { value: 'heavy', labelKey: 'quickLog.heavy' },
];

const MOOD_OPTIONS: OptionDef[] = [
  { value: 'happy', labelKey: 'quickLog.happy' },
  { value: 'neutral', labelKey: 'quickLog.neutral' },
  { value: 'sad', labelKey: 'quickLog.sad' },
  { value: 'frustrated', labelKey: 'quickLog.frustrated' },
  { value: 'loved', labelKey: 'quickLog.loved' },
];

const STRESS_OPTIONS: OptionDef[] = [
  { value: '1', labelKey: 'quickLog.stress1' },
  { value: '3', labelKey: 'quickLog.stress3' },
  { value: '5', labelKey: 'quickLog.stress5' },
];

const SLEEP_OPTIONS: OptionDef[] = [
  { value: '4', labelKey: 'quickLog.sleep4' },
  { value: '6', labelKey: 'quickLog.sleep6' },
  { value: '8', labelKey: 'quickLog.sleep8' },
  { value: '9.5', labelKey: 'quickLog.sleep9_5' },
];

const SYMPTOM_OPTIONS: OptionDef[] = [
  { value: 'cramps', labelKey: 'cycle.cramps' },
  { value: 'headache', labelKey: 'cycle.headache' },
  { value: 'bloating', labelKey: 'cycle.bloating' },
  { value: 'fatigue', labelKey: 'cycle.fatigue' },
  { value: 'nausea', labelKey: 'cycle.nausea' },
  { value: 'acne', labelKey: 'cycle.acne' },
  { value: 'back pain', labelKey: 'cycle.backPain' },
];

const WEEKDAYS = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

function phaseLabel(t: (k: string) => string, phase: CyclePhase): string {
  switch (phase) {
    case 'period':
      return t('cycle.period');
    case 'follicular':
      return t('cycle.follicular');
    case 'ovulation':
      return t('cycle.ovulation');
    default:
      return t('cycle.luteal');
  }
}

export function CyclePage() {
  useDocumentMeta('meta.cycle.title', 'meta.cycle.description');
  const { t } = useTranslation();
  const { user } = useAuth();

  const today = useMemo(() => new Date(), []);
  const [selectedDate, setSelectedDate] = useState<Date>(today);
  const [displayedMonth, setDisplayedMonth] = useState<Date>(startOfMonth(today));
  const [logs, setLogs] = useState<Map<string, CycleLogEntry>>(new Map());
  const [lastPeriod, setLastPeriod] = useState<string | null>(null);
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState('');

  // Draft for the selected day, re-seeded from the server log whenever the
  // selected date (or the fetched history) changes.
  const [draft, setDraft] = useState<CycleLogInput | null>(null);

  // The window of history currently loaded. Keyed off the displayed month
  // rather than a fixed count: the calendar renders one month at a time,
  // and this page used to ask for `limit=365`, which the endpoint refuses
  // outright (its ceiling is 100). The 422 was caught below and turned
  // into an empty Map, so the calendar rendered as if the user had never
  // logged anything (#349).
  const loadedWindow = useMemo(() => monthWindow(displayedMonth), [displayedMonth]);

  // Depended on by `load`, and deliberately the id rather than the whole
  // `user` object. A context that hands back a fresh object on each render
  // would otherwise make `load` a new function every render, so the effect
  // below would re-fire, set state, and render again — an unbounded fetch
  // loop that only shows up under a re-rendering provider.
  const userId = user?.id;

  const load = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    try {
      // Predictions are fetched alongside the history and allowed to fail
      // on their own. The calendar is this page's job; the outlook card is
      // an addition to it, and losing the addition must not blank the
      // month (#419).
      const [history, profile, forecast] = await Promise.all([
        fetchCycleHistoryRange(userId, loadedWindow.start, loadedWindow.end),
        fetchProfile().catch(() => null),
        fetchPredictions().catch(() => null),
      ]);
      setPrediction(forecast);
      const map = new Map<string, CycleLogEntry>();
      for (const entry of history) {
        if (!entry.start_date) continue;
        const key = entry.start_date.slice(0, 10);
        map.set(key, { ...entry, start_date: key });
      }
      setLogs(map);
      setLastPeriod(profile?.last_period ?? null);
      setLoadError(false);
    } catch {
      // Distinguished from "no logs yet". Clearing to an empty Map without
      // saying so is what made the original bug invisible — an empty
      // calendar looks exactly like a new account.
      setLogs(new Map());
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, [userId, loadedWindow.start, loadedWindow.end]);

  // Re-runs when the displayed month changes, because `loadedWindow`
  // changes with it. Before this the whole history was fetched once and
  // any month outside it would have been blank regardless.
  useEffect(() => {
    void load();
  }, [load]);

  const selectedIso = toISODate(selectedDate);
  useEffect(() => {
    const existing = logs.get(selectedIso);
    setDraft(existing ? { ...existing } : { start_date: selectedIso });
    setSaved(false);
    setSaveError('');
  }, [selectedIso, logs]);

  const toggleSingle = (field: 'flow_intensity' | 'mood' | 'stress_level' | 'sleep_hours', value: string) => {
    const prev: CycleLogInput = draft ?? { start_date: selectedIso };
    const next: CycleLogInput = { ...prev };
    if (field === 'sleep_hours') {
      next.sleep_hours = Number(next.sleep_hours) === parseFloat(value) ? null : parseFloat(value);
    } else if (field === 'stress_level') {
      next.stress_level = Number(next.stress_level) === parseInt(value, 10) ? null : parseInt(value, 10);
    } else if (field === 'flow_intensity') {
      next.flow_intensity = next.flow_intensity === value ? null : value;
    } else {
      next.mood = next.mood === value ? null : value;
    }
    setDraft(next);
    setSaved(false);
    setSaveError('');
  };

  const toggleSymptom = (value: string) => {
    const prev: CycleLogInput = draft ?? { start_date: selectedIso };
    const next: CycleLogInput = { ...prev };
    const current = next.symptoms ?? [];
    next.symptoms = current.includes(value) ? current.filter((s) => s !== value) : [...current, value];
    setDraft(next);
    setSaved(false);
    setSaveError('');
  };

  const hasSelections = (d: CycleLogInput | null): boolean => {
    if (!d) return false;
    return Boolean(
      d.flow_intensity ||
        d.mood ||
        d.sleep_hours != null ||
        d.stress_level != null ||
        (d.symptoms && d.symptoms.length > 0),
    );
  };

  const save = async () => {
    if (!draft || saving) return;
    setSaving(true);
    setSaveError('');
    try {
      const payload: CycleLogInput = { start_date: selectedIso };
      if (draft.flow_intensity) payload.flow_intensity = draft.flow_intensity;
      if (draft.mood) payload.mood = draft.mood;
      if (draft.sleep_hours != null) payload.sleep_hours = draft.sleep_hours;
      if (draft.stress_level != null) payload.stress_level = draft.stress_level;
      if (draft.symptoms && draft.symptoms.length > 0) payload.symptoms = draft.symptoms;
      await submitCycleLog(payload);
      setSaved(true);
      void load();
    } catch {
      setSaveError(t('home.savedOffline'));
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    const existing = logs.get(selectedIso);
    if (!existing) return;
    if (!window.confirm(t('cycle.deleteConfirm'))) return;
    try {
      await deleteCycleLog(existing.id);
    } catch {
      // Best-effort delete: the local view still clears.
    }
    const next = new Map(logs);
    next.delete(selectedIso);
    setLogs(next);
    setSaved(false);
  };

  const shiftMonth = (delta: number) => setDisplayedMonth((m) => addMonths(m, delta));

  // The server's estimate, not a hardcoded 28. Falls through to the
  // library default when there is no prediction, which is what the
  // calendar did unconditionally before.
  const estimatedCycleLength = prediction?.cycleLength?.days;

  // `lastPeriodStart` from the prediction beats `last_period` from the
  // profile: the profile field is what the user typed at onboarding and
  // is never updated again, so once she has logged a period it is stale.
  const anchorPeriod = prediction?.lastPeriodStart ?? lastPeriod;

  const selectedPhase = phaseFor(selectedDate, anchorPeriod, estimatedCycleLength);

  const cells = useMemo(() => {
    const first = startOfMonth(displayedMonth);
    const offset = first.getDay();
    const daysInMonth = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
    const out: (Date | null)[] = [];
    for (let i = 0; i < offset; i++) out.push(null);
    for (let d = 1; d <= daysInMonth; d++) out.push(new Date(first.getFullYear(), first.getMonth(), d));
    return out;
  }, [displayedMonth]);

  if (loading && logs.size === 0) {
    return <div className="centered-loader">{t('common.loading')}</div>;
  }

  const selectedLog = logs.get(selectedIso);

  return (
    <div className="page">
      <header className="page-header">
        <h1>{t('cycle.title')}</h1>
      </header>

      {loadError ? (
        <p className="error-text" role="alert">
          {t('cycle.loadFailed')}{' '}
          <button type="button" className="ghost-btn" onClick={() => void load()}>
            {t('cycle.retry')}
          </button>
        </p>
      ) : null}

      {/* The outlook, from `GET /cycle/predictions` — an endpoint no
          client had ever called (#419). Everything in it is computed
          server-side from the same logs the calendar below renders. */}
      {prediction ? (
        <section className="glass-card outlook-card">
          <div className="trend-heading">
            <p className="card-label">{t('prediction.outlookLabel')}</p>
            <span className={`status-pill phase-${prediction.phase}`}>
              {t(`prediction.phase.${prediction.phase}`)}
            </span>
          </div>

          <div className="stat-row">
            <div className="stat-cell">
              <span className="stat-label">{t('prediction.cycleDay')}</span>
              <span className="stat-value">{prediction.currentCycleDay ?? '—'}</span>
            </div>
            <div className="stat-cell">
              <span className="stat-label">
                {prediction.isOverdue ? t('prediction.overdueLabel') : t('home.nextPeriod')}
              </span>
              <span className={`stat-value${prediction.isOverdue ? ' is-overdue' : ''}`}>
                {prediction.isOverdue
                  ? t('prediction.daysLate', { count: prediction.daysOverdue })
                  : (prediction.daysUntilNextPeriod ?? '—')}
              </span>
            </div>
            <div className="stat-cell">
              <span className="stat-label">{t('prediction.estimatedLength')}</span>
              <span className="stat-value">{prediction.cycleLength.days}</span>
            </div>
          </div>

          <p className="prediction-source">
            {t(`prediction.source.${prediction.cycleLength.source}`)} ·{' '}
            {t(`prediction.confidence.${prediction.cycleLength.confidence}`)}
          </p>

          {prediction.ovulation?.date ? (
            <p className="card-sub">
              {t('prediction.ovulation', {
                date: formatDayMonth(parseISODate(prediction.ovulation.date)),
              })}
            </p>
          ) : null}

          {prediction.fertileWindow?.start && prediction.fertileWindow?.end ? (
            <p className="fertile-window">
              {t('prediction.fertileWindow', {
                from: formatDayMonth(parseISODate(prediction.fertileWindow.start)),
                to: formatDayMonth(parseISODate(prediction.fertileWindow.end)),
              })}
            </p>
          ) : null}

          {prediction.upcomingPeriods?.length > 0 ? (
            <p className="card-sub">
              {t('prediction.upcoming')}:{' '}
              {prediction.upcomingPeriods
                .map((iso) => formatDayMonth(parseISODate(iso)))
                .join(' · ')}
            </p>
          ) : null}

          {/* The server's own wording. It is the sentence that has to be
              right, so it is not paraphrased here. */}
          <p className="fertile-window-disclaimer">{prediction.disclaimer}</p>
        </section>
      ) : null}

      <section className="glass-card calendar-card">
        <div className="calendar-toolbar">
          <div className="month-nav">
            <button type="button" className="icon-btn" onClick={() => shiftMonth(-1)} aria-label="Previous month">
              ‹
            </button>
            <span className="month-label">{formatMonthYear(displayedMonth)}</span>
            <button type="button" className="icon-btn" onClick={() => shiftMonth(1)} aria-label="Next month">
              ›
            </button>
          </div>
          <button type="button" className="ghost-btn" onClick={() => setDisplayedMonth(startOfMonth(today))}>
            {t('cycle.today')}
          </button>
        </div>

        <div className="weekday-row">
          {WEEKDAYS.map((d, i) => (
            <span key={i} className="weekday">
              {d}
            </span>
          ))}
        </div>

        <div className="calendar-grid">
          {cells.map((date, i) => {
            if (!date) return <span key={i} className="day-cell empty" />;
            const iso = toISODate(date);
            const phase = phaseFor(date, anchorPeriod, estimatedCycleLength);
            const isFuture = date > today;
            const isSelected = isSameDay(date, selectedDate);
            const isToday = isSameDay(date, today);
            const hasLog = logs.has(iso);
            const color = PHASE_COLORS[phase];
            return (
              <button
                key={iso}
                type="button"
                className={`day-cell${isSelected ? ' selected' : ''}${isToday ? ' today' : ''}${isFuture ? ' future' : ''}`}
                style={
                  isSelected
                    ? { background: color, borderColor: color }
                    : isToday
                      ? { borderColor: color, color: 'var(--text-h)' }
                      : { color: phase === 'period' ? color : 'var(--text)' }
                }
                disabled={isFuture}
                onClick={() => setSelectedDate(date)}
              >
                {date.getDate()}
                {hasLog ? <span className="log-dot" style={isSelected ? {} : { background: color }} /> : null}
              </button>
            );
          })}
        </div>

        <div className="phase-legend">
          {(['period', 'follicular', 'ovulation', 'luteal'] as CyclePhase[]).map((p) => (
            <span key={p} className="legend-item">
              <span className="legend-dot" style={{ background: PHASE_COLORS[p] }} />
              {phaseLabel(t, p)}
            </span>
          ))}
        </div>
      </section>

      <section className="glass-card log-card">
        <h2 className="log-heading">
          {t('cycle.logFor', { date: formatDayMonth(selectedDate) })} · {phaseLabel(t, selectedPhase)}
        </h2>

        <LogRow label={t('cycle.flow')} icon="💧" options={FLOW_OPTIONS} selected={draft?.flow_intensity ?? null} onToggle={(v) => toggleSingle('flow_intensity', v)} />
        <LogRow label={t('cycle.mood')} icon="❤️" options={MOOD_OPTIONS} selected={draft?.mood ?? null} onToggle={(v) => toggleSingle('mood', v)} />
        <LogRow label={t('cycle.energy')} icon="🌬️" options={STRESS_OPTIONS} selected={draft?.stress_level != null ? String(draft.stress_level) : null} onToggle={(v) => toggleSingle('stress_level', v)} />
        <LogRow label={t('cycle.sleep')} icon="🌙" options={SLEEP_OPTIONS} selected={draft?.sleep_hours != null ? String(draft.sleep_hours) : null} onToggle={(v) => toggleSingle('sleep_hours', v)} />
        <LogRow label={t('cycle.symptoms')} icon="🩺" options={SYMPTOM_OPTIONS} selected={draft?.symptoms ?? []} multi onToggle={(v) => toggleSymptom(v)} />

        {saved ? <p className="success-text">✓ {t('cycle.savedToAccount')}</p> : null}
        {saveError ? <p className="error-text">{saveError}</p> : null}

        <button type="button" className="primary-btn full" disabled={saving || !hasSelections(draft)} onClick={() => void save()}>
          {saving ? t('common.loading') : t('cycle.saveLog')}
        </button>

        {selectedLog ? (
          <button type="button" className="danger-btn full" onClick={() => void remove()}>
            {t('cycle.deleteLog')}
          </button>
        ) : null}
      </section>
    </div>
  );
}

interface LogRowProps {
  label: string;
  icon: string;
  options: OptionDef[];
  selected: string | string[] | null;
  multi?: boolean;
  onToggle: (value: string) => void;
}

function LogRow({ label, icon, options, selected, multi, onToggle }: LogRowProps) {
  const { t } = useTranslation();
  const selectedList = Array.isArray(selected) ? selected : selected ? [selected] : [];
  return (
    <div className="log-row">
      <span className="log-row-label">
        {icon} {label}
      </span>
      <div className="chip-row">
        {options.map((opt) => {
          const active = multi ? selectedList.includes(opt.value) : selectedList[0] === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              className={`chip${active ? ' active' : ''}`}
              onClick={() => onToggle(opt.value)}
            >
              {t(opt.labelKey)}
            </button>
          );
        })}
      </div>
    </div>
  );
}
