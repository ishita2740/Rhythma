/**
 * Mapping the UI language onto a language the assistant actually speaks.
 *
 * `i18n.language` is not a safe value to send to `POST /assistant/chat`.
 * Two ways it diverges from what that endpoint accepts:
 *
 * - The browser language detector reports region tags — `en-US`, `hi-IN` —
 *   rather than bare codes.
 * - The web app registers nine locales the assistant does not serve, of
 *   which Bengali is the one the assistant's own picker offered.
 *
 * The backend validates this field (it is interpolated into the model
 * prompt, so it cannot stay free text), which means an unmapped value is a
 * 422 rather than a silently-ignored one. Answering in English beats
 * refusing to answer, so an unsupported UI language falls back rather than
 * failing — but the screen has to *say* it fell back, which is what
 * `isAssistantLanguageFallback` is for and what nothing called (#512).
 *
 * The list itself now comes from `supportedLanguages.ts`. It used to be a
 * literal here, which is one of the five copies that had drifted apart.
 */

import {
  ASSISTANT_LANGUAGE_CODES,
  baseLanguage,
  isAssistantLanguage,
} from './supportedLanguages';

/**
 * Codes served by GET /assistant/languages.
 *
 * Derived from the single source of truth rather than restated, so a
 * language cannot be marked assistant-capable there and missing here.
 */
export const ASSISTANT_LANGUAGES = ASSISTANT_LANGUAGE_CODES;

export type AssistantLanguage = string;

/**
 * Reduce a UI language tag to a code the assistant accepts.
 *
 * `en-US` → `en`, `HI` → `hi`, `bn` → `en` (not supported by the
 * assistant), anything unrecognized → `en`.
 */
export function toAssistantLanguage(uiLanguage: string | undefined): AssistantLanguage {
  const base = baseLanguage(uiLanguage);
  return isAssistantLanguage(base) ? base : 'en';
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
  const base = baseLanguage(uiLanguage);
  return base !== 'en' && !isAssistantLanguage(base);
}
