/**
 * Rendering an observation in the reader's own language (#485).
 *
 * The backend returns four fields for every observation:
 *
 *   title, body           English fallbacks
 *   titleKey, bodyKey     `observations.<code>.title` / `.body`
 *   evidence              the exact numbers that produced the sentence
 *
 * and `ObservationModel` in `backend/api/insights.py` states the contract
 * outright: "`title`/`body` are English fallbacks. Clients that have a
 * translation should render `titleKey`/`bodyKey` and interpolate
 * `evidence` themselves — which is why the numbers behind every statement
 * are exposed structurally rather than only baked into the sentence."
 *
 * `InsightsPage` rendered `observation.title` and `observation.body`
 * directly, so the page chrome translated and its content did not. Two of
 * these carry `severity: "seek_care"` — the two rules
 * `menstrual_insights_guidelines.md` designates as prompts to consult a
 * professional — which made the app's most important health message the
 * one most reliably shown in a language the reader may not read.
 *
 * ## Why the fallback matters more than the lookup
 *
 * The backend adds observation rules; this repo's locale files are
 * updated by different people at a different time. So the *normal* state
 * of the world is a server emitting a code the client has no string for.
 *
 * `t('observations.foo.title')` in that state renders the literal key —
 * `observations.foo.title` — into the middle of a health screen. That is
 * strictly worse than the English it replaced. Every lookup here is
 * therefore guarded by `i18n.exists`, and falls back to the server's own
 * English rather than to the key.
 */

import type { TFunction } from 'i18next';

import type { Observation } from '../api/endpoints';

/**
 * The only thing these helpers need from an i18n instance.
 *
 * Declared here rather than as `Pick<i18n, 'exists'>` because i18next
 * types `exists` as an overloaded type predicate. A real instance
 * satisfies this interface, and so does a two-line stub in a test —
 * whereas `Pick<i18n, 'exists'>` demands the predicate signature and
 * makes the stub a `tsc` error, which pushes tests towards `as never`
 * casts that would hide a genuine signature change.
 */
export interface KeyExistenceCheck {
  exists(key: string): boolean;
}

/**
 * `evidence` values, flattened to something i18next can interpolate.
 *
 * Most are numbers and pass through untouched. Three keys are arrays —
 * `start_dates`, `symptoms`, `symptoms_seen`, `recent_gaps` — and
 * interpolating an array yields the literal `[object Object]`-adjacent
 * mess of `Array.prototype.toString`, or nothing at all. They are joined
 * instead, so a translation is free to reference them.
 *
 * `null`/`undefined` are dropped rather than rendered as "null". A
 * placeholder with no value left unreplaced is more debuggable than the
 * word "null" in a sentence about someone's health.
 */
export function interpolationValues(
  evidence: Record<string, unknown> | undefined,
): Record<string, string | number> {
  const values: Record<string, string | number> = {};
  if (!evidence) return values;

  for (const [key, value] of Object.entries(evidence)) {
    if (value === null || value === undefined) continue;

    if (Array.isArray(value)) {
      const items = value.filter((item) => item !== null && item !== undefined);
      if (items.length > 0) values[key] = items.join(', ');
      continue;
    }

    if (typeof value === 'number' || typeof value === 'string') {
      values[key] = value;
      continue;
    }

    if (typeof value === 'boolean') {
      values[key] = String(value);
    }
    // Anything else (a nested object) is skipped: there is no sensible
    // one-line rendering, and `[object Object]` in a health sentence is
    // worse than an untranslated one.
  }

  return values;
}

/**
 * A translated string for `key`, or `fallback` when there is no translation.
 *
 * Exported because the same guard is needed anywhere an observation is
 * rendered — the Home screen's `topObservation` is the next caller — and
 * duplicating the `exists` check is how one copy ends up without it.
 */
export function translatedOr(
  t: TFunction,
  i18n: KeyExistenceCheck,
  key: string,
  fallback: string,
  evidence?: Record<string, unknown>,
): string {
  if (!key || typeof i18n.exists !== 'function' || !i18n.exists(key)) {
    return fallback;
  }

  const rendered = t(key, interpolationValues(evidence));

  // `exists` returning true and `t` returning the key back is not a
  // combination that should occur, but if it ever does — an empty string
  // in a locale file, a namespace mishap — the English is still better
  // than showing the reader a dotted key.
  return typeof rendered === 'string' && rendered && rendered !== key
    ? rendered
    : fallback;
}

export function observationTitle(
  t: TFunction,
  i18n: KeyExistenceCheck,
  observation: Observation,
): string {
  return translatedOr(
    t,
    i18n,
    observation.titleKey,
    observation.title,
    observation.evidence,
  );
}

export function observationBody(
  t: TFunction,
  i18n: KeyExistenceCheck,
  observation: Observation,
): string {
  return translatedOr(
    t,
    i18n,
    observation.bodyKey,
    observation.body,
    observation.evidence,
  );
}
