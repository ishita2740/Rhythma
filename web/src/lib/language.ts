/**
 * Mapping the UI language onto a language the assistant actually speaks.
 *
 * `i18n.language` is not a safe value to send to `POST /assistant/chat`.
 * Two ways it diverges from what that endpoint accepts:
 *
 * - The browser language detector reports region tags — `en-US`, `hi-IN` —
 *   rather than bare codes.
 * - The web app registers Bengali (`bn`), which the assistant's own
 *   `GET /assistant/languages` does not list.
 *
 * The backend now validates this field (it is interpolated into the model
 * prompt, so it cannot stay free text), which means an unmapped value is a
 * 422 rather than a silently-ignored one. Answering in English beats
 * refusing to answer, so an unsupported UI language falls back rather than
 * failing.
 */

/** Codes served by GET /assistant/languages. */
export const ASSISTANT_LANGUAGES = [
  'en',
  'hi',
  'mr',
  'ta',
  'te',
  'kn',
  'ml',
  'gu',
] as const;

export type AssistantLanguage = (typeof ASSISTANT_LANGUAGES)[number];

const SUPPORTED = new Set<string>(ASSISTANT_LANGUAGES);

/**
 * Reduce a UI language tag to a code the assistant accepts.
 *
 * `en-US` → `en`, `HI` → `hi`, `bn` → `en` (not supported by the
 * assistant), anything unrecognized → `en`.
 */
export function toAssistantLanguage(uiLanguage: string | undefined): AssistantLanguage {
  if (!uiLanguage) return 'en';

  const base = uiLanguage.trim().toLowerCase().replace(/_/g, '-').split('-')[0];

  return SUPPORTED.has(base) ? (base as AssistantLanguage) : 'en';
}

/**
 * True when the assistant cannot answer in the user's chosen UI language.
 *
 * Lets a screen say so rather than replying in English with no
 * explanation — the failure is quiet otherwise, and looks like the app
 * ignoring the language setting.
 */
export function isAssistantLanguageFallback(uiLanguage: string | undefined): boolean {
  if (!uiLanguage) return false;
  const base = uiLanguage.trim().toLowerCase().replace(/_/g, '-').split('-')[0];
  return base !== 'en' && !SUPPORTED.has(base);
}
