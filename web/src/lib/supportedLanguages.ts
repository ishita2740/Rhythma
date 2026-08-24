/**
 * The one list of languages this app speaks.
 *
 * There were five, and no two agreed (issue #512):
 *
 * | where | count |
 * |---|---|
 * | `i18n/index.ts` `resources` | 17 |
 * | `SettingsPage` `FALLBACK_LANGUAGES` | 7 |
 * | `SettingsPage` `LANGUAGE_KEY` | 7 |
 * | `AssistantPage` `<select>` | 9 |
 * | `lib/language.ts` `ASSISTANT_LANGUAGES` | 8 |
 *
 * Each disagreement was visible to a user. The assistant picker offered
 * Bengali and answered in English with no explanation, because `bn` is a
 * complete locale here and not a language the assistant serves. The
 * Settings picker dropped Gujarati whenever `/assistant/languages` was
 * unreachable — which is the condition this app is built around — and
 * rendered it in English when it was reachable, since `LANGUAGE_KEY` had
 * no `gu` entry either.
 *
 * The Flutter app got this right in #463: one `appSupportedLanguages`
 * const, and a test. This is the web equivalent, and it carries two
 * facts the Flutter list does not have to:
 *
 * **Whether the assistant serves it.** The UI ships in seventeen
 * languages; `POST /assistant/chat` accepts eight. That gap is real and
 * not going away soon, so it is recorded rather than papered over — a
 * screen can then say "the assistant will reply in English" instead of
 * just doing it.
 *
 * **Which direction it is written in.** Three of the shipped locales are
 * written in Perso-Arabic script.
 */

/** A language the app ships a locale file for. */
export interface AppLanguage {
  /** ISO 639 code, matching the locale file name and the i18next key. */
  code: string;
  /** The name of the language *in* that language. What a picker shows. */
  nativeName: string;
  /** The English name, for `lang` labels and for logs. */
  englishName: string;
  /**
   * True when `POST /assistant/chat` will answer in this language.
   *
   * Mirrors `SUPPORTED_LANGUAGES` in `backend/api/assistant.py`. Kept as
   * a field rather than a separate array so a language cannot be added
   * to one list and forgotten in the other — which is exactly how
   * `AssistantPage` came to offer Bengali.
   */
  assistant: boolean;
  /** Writing direction. */
  dir: 'ltr' | 'rtl';
}

/**
 * Every locale the app ships, in the order a picker should show them.
 *
 * English first, then the languages with the largest speaker populations
 * among the intended audience, then the rest alphabetically by code. Not
 * alphabetical throughout: a picker whose first eight entries are the
 * ones most users need is a better picker than a sorted one.
 */
export const APP_LANGUAGES: readonly AppLanguage[] = [
  { code: 'en', nativeName: 'English', englishName: 'English', assistant: true, dir: 'ltr' },
  { code: 'hi', nativeName: 'हिन्दी', englishName: 'Hindi', assistant: true, dir: 'ltr' },
  { code: 'mr', nativeName: 'मराठी', englishName: 'Marathi', assistant: true, dir: 'ltr' },
  { code: 'ta', nativeName: 'தமிழ்', englishName: 'Tamil', assistant: true, dir: 'ltr' },
  { code: 'te', nativeName: 'తెలుగు', englishName: 'Telugu', assistant: true, dir: 'ltr' },
  { code: 'kn', nativeName: 'ಕನ್ನಡ', englishName: 'Kannada', assistant: true, dir: 'ltr' },
  { code: 'ml', nativeName: 'മലയാളം', englishName: 'Malayalam', assistant: true, dir: 'ltr' },
  { code: 'gu', nativeName: 'ગુજરાતી', englishName: 'Gujarati', assistant: true, dir: 'ltr' },
  { code: 'bn', nativeName: 'বাংলা', englishName: 'Bengali', assistant: false, dir: 'ltr' },
  { code: 'as', nativeName: 'অসমীয়া', englishName: 'Assamese', assistant: false, dir: 'ltr' },
  { code: 'ks', nativeName: 'کٲشُر', englishName: 'Kashmiri', assistant: false, dir: 'rtl' },
  { code: 'mai', nativeName: 'मैथिली', englishName: 'Maithili', assistant: false, dir: 'ltr' },
  { code: 'ne', nativeName: 'नेपाली', englishName: 'Nepali', assistant: false, dir: 'ltr' },
  { code: 'or', nativeName: 'ଓଡ଼ିଆ', englishName: 'Odia', assistant: false, dir: 'ltr' },
  { code: 'sat', nativeName: 'ᱥᱟᱱᱛᱟᱲᱤ', englishName: 'Santali', assistant: false, dir: 'ltr' },
  { code: 'sd', nativeName: 'سنڌي', englishName: 'Sindhi', assistant: false, dir: 'rtl' },
  { code: 'ur', nativeName: 'اردو', englishName: 'Urdu', assistant: false, dir: 'rtl' },
];

/** Every shipped code. */
export const APP_LANGUAGE_CODES: readonly string[] = APP_LANGUAGES.map((l) => l.code);

/** The codes `POST /assistant/chat` accepts. */
export const ASSISTANT_LANGUAGE_CODES: readonly string[] = APP_LANGUAGES.filter(
  (l) => l.assistant,
).map((l) => l.code);

/** Codes written right to left. */
export const RTL_LANGUAGE_CODES: readonly string[] = APP_LANGUAGES.filter(
  (l) => l.dir === 'rtl',
).map((l) => l.code);

const BY_CODE = new Map(APP_LANGUAGES.map((l) => [l.code, l]));
const ASSISTANT_SET = new Set(ASSISTANT_LANGUAGE_CODES);
const RTL_SET = new Set(RTL_LANGUAGE_CODES);

/**
 * Reduce a language tag to its base code.
 *
 * The browser language detector reports region tags — `en-US`, `hi-IN`,
 * `ta-IN`. Four places in this codebase did `.split('-')[0]` inline and a
 * fifth forgot to, which is why the Settings picker could not mark the
 * user's own language as selected: `'hi-IN' === 'hi'` is false, so on a
 * phone set to Hindi the app rendered in Hindi with no chip highlighted,
 * and she had to select a language she was already using to make the
 * screen admit it.
 *
 * Underscores are folded too (`hi_IN`), because a stored preference from
 * an older build can carry them.
 */
export function baseLanguage(tag: string | undefined | null): string {
  if (!tag) return 'en';
  const base = tag.trim().toLowerCase().replace(/_/g, '-').split('-')[0];
  return base || 'en';
}

/** True when the two tags name the same language, region aside. */
export function isSameLanguage(
  a: string | undefined | null,
  b: string | undefined | null,
): boolean {
  return baseLanguage(a) === baseLanguage(b);
}

/** The entry for a tag, or undefined when the app does not ship it. */
export function languageFor(tag: string | undefined | null): AppLanguage | undefined {
  return BY_CODE.get(baseLanguage(tag));
}

/** True when the app ships a locale for this tag. */
export function isSupportedLanguage(tag: string | undefined | null): boolean {
  return BY_CODE.has(baseLanguage(tag));
}

/** True when the assistant will answer in this tag's language. */
export function isAssistantLanguage(tag: string | undefined | null): boolean {
  return ASSISTANT_SET.has(baseLanguage(tag));
}

/** `rtl` for the scripts that need it, `ltr` otherwise. */
export function directionForLanguage(tag: string | undefined | null): 'ltr' | 'rtl' {
  return RTL_SET.has(baseLanguage(tag)) ? 'rtl' : 'ltr';
}

/**
 * The name to render for a tag, in its own script.
 *
 * Falls back to the tag itself rather than to English, so an unshipped
 * code shows as something recognisable instead of silently becoming
 * "English".
 */
export function nativeNameFor(tag: string | undefined | null): string {
  return languageFor(tag)?.nativeName ?? baseLanguage(tag);
}
