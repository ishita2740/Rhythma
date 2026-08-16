/**
 * Which cycle phase to show, and where the number beside it came from (#486).
 *
 * `ProfilePage` computed the phase itself:
 *
 *     if (day <= 5) return t('profile.menstrual');
 *     if (day <= 13) return t('profile.follicular');
 *     if (day <= 16) return t('profile.ovulation');
 *     return t('profile.luteal');
 *
 * That is the fixed day-5/13/16 ladder. #316 removed it from the Flutter
 * app; the web copy was never touched. `prediction_service.phase_for()`
 * says what is wrong with it:
 *
 * > The Flutter provider hardcodes 5/13/16 regardless of cycle length,
 * > which places ovulation about a week early for a 35-day cycle. These
 * > boundaries are derived from the estimate instead.
 *
 * Two things followed from keeping a second copy on this screen.
 *
 * **Home and Profile disagreed.** `/dashboard` already returns
 * `prediction.phase`, computed from the user's own logged cycle length,
 * bleed durations and a luteal phase scaled for short cycles. `HomePage`
 * renders it. `ProfilePage` computed its own. For a 34-day cycle on day
 * 15, Home said `follicular` and Profile said `ovulation` — same account,
 * same second, one tab apart.
 *
 * **The pill could never say a period was late.** `luteal` was the
 * fallthrough, so day 20, day 40 and day 200 all read "Luteal Phase". The
 * server has `late` for exactly this, and explains why it exists: a stale
 * `last_period` otherwise pins a user in a phase that stopped being true
 * weeks ago, and "this cycle is running long" is both honest and
 * actionable.
 *
 * So there is no ladder in this module. There is a lookup from the
 * server's answer to a translation key, and the deliberate absence of any
 * local computation is the point — a ladder here would be the third copy.
 */

import type {
  DashboardData,
  DashboardPrediction,
  CyclePhase,
  Profile,
} from '../api/endpoints';

/**
 * Translation key per phase.
 *
 * Typed `Record<CyclePhase, string>` rather than a partial map so that
 * adding a phase to `CyclePhase` is a `tsc` error here. The alternative
 * — a lookup with an `?? fallback` — is how `late` would silently render
 * as "Luteal Phase" again.
 */
export const PHASE_LABEL_KEY: Record<CyclePhase, string> = {
  // `period` maps to the existing `profile.menstrual` key rather than
  // renaming it. The server calls the phase `period`; this screen has
  // called the label "Menstrual Phase" since before the server had an
  // opinion, and renaming a key that seven locale files already translate
  // to fix a naming mismatch nobody sees is not worth the churn.
  period: 'profile.menstrual',
  follicular: 'profile.follicular',
  ovulation: 'profile.ovulation',
  luteal: 'profile.luteal',
  late: 'profile.late',
  unknown: 'profile.unknown',
};

/**
 * Pill styling per phase.
 *
 * `late` and `unknown` are deliberately neutral rather than alarming.
 * They mean "we cannot tell you where you are", which is a statement
 * about our confidence and not about her health —
 * `menstrual_insights_guidelines.md` rules out risk framing, and a red
 * pill on a cycle that is running long is exactly that.
 */
export const PHASE_TONE: Record<CyclePhase, string> = {
  period: 'phase-period',
  follicular: 'phase-follicular',
  ovulation: 'phase-ovulation',
  luteal: 'phase-luteal',
  late: 'phase-neutral',
  unknown: 'phase-neutral',
};

/**
 * The phase the server reported, or `unknown`.
 *
 * `unknown` covers three cases that are the same to a reader: the
 * dashboard has not loaded, this server predates the `prediction` block,
 * or the user has nothing to anchor a prediction on. All three mean "we
 * cannot say", and the honest label is better than the `—` this screen
 * used to render, which said nothing at all.
 */
export function phaseOf(
  prediction: DashboardPrediction | null | undefined,
): CyclePhase {
  const phase = prediction?.phase;
  return phase && phase in PHASE_LABEL_KEY ? phase : 'unknown';
}

export function phaseLabelKey(
  prediction: DashboardPrediction | null | undefined,
): string {
  return PHASE_LABEL_KEY[phaseOf(prediction)];
}

export function phaseTone(
  prediction: DashboardPrediction | null | undefined,
): string {
  return PHASE_TONE[phaseOf(prediction)];
}

/**
 * What to put in the "average cycle length" tile, and whether it is one.
 *
 * The tile read `profile.cycle_length` first — the number the user typed
 * during onboarding. That is a *declared* value, not an average of
 * anything, so a user who declared 28 and whose logged cycles average 33
 * was shown "Avg cycle length: 28 days" under a label saying average.
 *
 * `dashboard.insights.averageCycleLength` is a real average, computed by
 * `compute_cycle_stats` from her logged start dates, and it arrives on
 * the same response the page has already fetched. It is preferred, and
 * `measured` reports which one was used so the label can be honest when
 * it falls back.
 */
export interface CycleLengthDisplay {
  days: number | null;
  /** True when `days` came from logged history rather than onboarding. */
  measured: boolean;
}

export function cycleLengthDisplay(
  dashboard: DashboardData | null | undefined,
  profile: Profile | null | undefined,
): CycleLengthDisplay {
  const measured = dashboard?.insights?.averageCycleLength;
  if (typeof measured === 'number' && Number.isFinite(measured)) {
    return { days: measured, measured: true };
  }

  const declared = profile?.cycle_length;
  if (typeof declared === 'number' && Number.isFinite(declared)) {
    return { days: declared, measured: false };
  }

  // Deliberately not falling through to `dashboard.cycle.total`. That
  // field defaults to 28 when there is no history, so using it would put
  // a population constant in a tile labelled as this user's average —
  // the same false precision `prediction_service` exists to remove.
  return { days: null, measured: false };
}

export function cycleLengthLabelKey(display: CycleLengthDisplay): string {
  return display.measured ? 'profile.avgCycleLength' : 'profile.declaredCycleLength';
}
