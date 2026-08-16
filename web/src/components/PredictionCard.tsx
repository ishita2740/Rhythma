import { useTranslation } from 'react-i18next';
import type { DashboardPrediction } from '../api/endpoints';

/**
 * "When is my next period?", answered with what the server actually knows.
 *
 * The Home screen used to render `cycle.nextPeriodDays`, which the
 * dashboard computes as:
 *
 *     next_period_days = max(avg_cycle_length - cycle_day, 0)
 *
 * The clamp is the problem. Four days late and due today are both "0", so
 * the app could not say the one thing a tracker exists to say. #272 built
 * `prediction_service.py` to replace that line and `/dashboard` has
 * returned its output as `prediction` ever since; nothing rendered it.
 *
 * What this component adds over a single number:
 *
 * - **Overdue is a state, not a zero.** `daysUntilNextPeriod` is negative
 *   when late and `isOverdue`/`daysOverdue` say so explicitly.
 * - **A range, not a point.** Someone with 28/28/29-day cycles and
 *   someone with 21/34/30-day cycles were shown the same thing with the
 *   same apparent precision. `predictedRange` is as wide as her own
 *   spread.
 * - **Where the number came from.** `estimateSource` distinguishes an
 *   estimate from her logs, one from the length she declared at
 *   onboarding, and the population default — which is what a brand-new
 *   user is looking at without being told.
 * - **The fertile window, with dates.** Home previously showed the fixed
 *   string "Fertile window + High energy" regardless of cycle day, which
 *   is a claim rather than a reading.
 */

/** Rendered when the prediction is absent, e.g. an older backend. */
interface PredictionCardProps {
  prediction: DashboardPrediction | null | undefined;
  /** `cycle.nextPeriodDays`, used only when `prediction` is missing. */
  fallbackDays: number | null;
}

function formatDate(value: string | null, locale: string): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed.toLocaleDateString(locale, { day: 'numeric', month: 'short' });
}

export function PredictionCard({ prediction, fallbackDays }: PredictionCardProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;

  // No prediction: fall back to the legacy number rather than showing
  // nothing. A backend from before #272 is still a working backend.
  if (!prediction) {
    return (
      <div className="prediction-card-body">
        <p className="card-label">{t('home.nextPeriod')}</p>
        <p className="cycle-next-number">{fallbackDays == null ? '—' : fallbackDays}</p>
        <p className="card-sub">{t('home.days')}</p>
        {/* Still an estimate, so it still carries the disclaimer. */}
        <p className="fertile-window-disclaimer">{t('home.fertileWindowDisclaimer')}</p>
      </div>
    );
  }

  const { isOverdue, daysOverdue, daysUntilNextPeriod, phase, confidence, estimateSource } =
    prediction;
  const nextDate = formatDate(prediction.nextPeriodDate, locale);
  const earliest = formatDate(prediction.predictedRange?.earliest ?? null, locale);
  const latest = formatDate(prediction.predictedRange?.latest ?? null, locale);
  const fertileStart = formatDate(prediction.fertileWindow?.start ?? null, locale);
  const fertileEnd = formatDate(prediction.fertileWindow?.end ?? null, locale);

  return (
    <div className="prediction-card-body">
      {isOverdue ? (
        <>
          <p className="card-label">{t('prediction.overdueLabel')}</p>
          <p className="cycle-next-number is-overdue">{daysOverdue}</p>
          <p className="card-sub">{t('prediction.daysLate', { count: daysOverdue })}</p>
        </>
      ) : (
        <>
          <p className="card-label">{t('home.nextPeriod')}</p>
          <p className="cycle-next-number">
            {daysUntilNextPeriod == null ? '—' : daysUntilNextPeriod}
          </p>
          <p className="card-sub">
            {daysUntilNextPeriod === 0 ? t('prediction.dueToday') : t('home.days')}
          </p>
        </>
      )}

      {nextDate ? <p className="prediction-date">{nextDate}</p> : null}

      {/* The range is the honest part of the estimate — a single date
          claims a precision that logged history rarely supports. */}
      {earliest && latest && earliest !== latest ? (
        <p className="prediction-range">{t('prediction.range', { from: earliest, to: latest })}</p>
      ) : null}

      <div className="prediction-tags">
        <span className={`status-pill phase-${phase}`}>{t(`prediction.phase.${phase}`)}</span>
        <span className={`status-pill confidence-${confidence}`}>
          {t(`prediction.confidence.${confidence}`)}
        </span>
      </div>

      {/* Said plainly rather than hidden behind the word "estimate": a
          new user is otherwise looking at 28 days with no way to tell it
          is a population average and not anything about her. */}
      <p className="prediction-source">{t(`prediction.source.${estimateSource}`)}</p>

      {fertileStart && fertileEnd ? (
        <p className="fertile-window">
          {t('prediction.fertileWindow', { from: fertileStart, to: fertileEnd })}
        </p>
      ) : null}

      <p className="fertile-window-disclaimer">{t('home.fertileWindowDisclaimer')}</p>
    </div>
  );
}
