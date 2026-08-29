/**
 * The parts of the document a React tree does not otherwise own.
 *
 * `index.html` is rendered once, before any of this code runs, so `<title>`,
 * `<meta name="description">` and the `lang` attribute on `<html>` are
 * outside the tree React re-renders. Issue #407: the title was the literal
 * string `web` on every route, there was no description at all, and `lang`
 * was hard-coded to `en` regardless of which of the nine locales the user
 * had chosen.
 *
 * `lang` is the one with teeth. It is what a screen reader reads to pick a
 * speech synthesizer, so a user who has switched to Hindi was getting
 * Devanagari text handed to an English voice, which pronounces it as
 * nonsense or skips it. It is also what the browser uses for font fallback
 * and hyphenation, and what a search engine uses to decide which language's
 * results a page belongs in — the reason `#328`'s Kannada/Malayalam
 * rendering work is partly downstream of this.
 *
 * Written as plain DOM functions with React hooks layered on top, so the
 * behaviour can be tested without mounting a component and so a caller
 * outside the tree (an error boundary, say) can still set a title.
 */

import { directionForLanguage } from './supportedLanguages';

// Direction comes from `supportedLanguages.ts` now. The set that used to
// live here was `['ar', 'fa', 'he', 'ur']` — a guess in both directions.
// It carried three languages the app does not ship, and it was written
// when the comment below was true ("none of the nine locales is RTL"),
// so the three Perso-Arabic locales added since were only half covered:
// `ur` made it in, `sd` (Sindhi) and `ks` (Kashmiri) did not. A user on
// either got `dir="ltr"` — punctuation at the wrong end of every line and
// the whole layout mirrored the wrong way (#512).

/**
 * The `lang` value for a tag from i18next.
 *
 * The browser language detector reports region tags (`en-US`, `hi-IN`).
 * Those are valid BCP 47 and a screen reader handles them fine, so they
 * are passed through rather than truncated — unlike `toAssistantLanguage`
 * in `language.ts`, which has to reduce to a bare code because the backend
 * only accepts those. Different consumers, different rules.
 */
export function toDocumentLang(language: string | undefined): string {
  if (!language) return 'en';
  const trimmed = language.trim();
  if (!trimmed) return 'en';
  return trimmed.replace(/_/g, '-');
}

/** `rtl` for the scripts that need it, `ltr` otherwise. */
export function directionFor(language: string | undefined): 'ltr' | 'rtl' {
  return directionForLanguage(language);
}

/**
 * Point `<html lang>` and `<html dir>` at the active locale.
 *
 * Three of the shipped locales are RTL — Urdu, Sindhi and Kashmiri — so
 * this is load-bearing rather than the forward-looking gesture the
 * original comment described.
 */
export function applyDocumentLanguage(language: string | undefined): void {
  if (typeof document === 'undefined') return;
  const root = document.documentElement;
  root.setAttribute('lang', toDocumentLang(language));
  root.setAttribute('dir', directionFor(language));
}

/** Set `document.title`, ignoring an empty value rather than blanking the tab. */
export function applyDocumentTitle(title: string | undefined | null): void {
  if (typeof document === 'undefined') return;
  if (!title || !title.trim()) return;
  document.title = title.trim();
}

/**
 * Create or update a `<meta name="...">` tag.
 *
 * Updating in place matters: creating one per navigation would leave a
 * stack of stale `<meta name="description">` tags in the head, and a
 * crawler reads the first one — so the description would freeze on
 * whichever page the user happened to land on first.
 */
export function applyMetaTag(name: string, content: string | undefined | null): void {
  if (typeof document === 'undefined') return;
  if (!content || !content.trim()) return;

  let tag = document.head.querySelector<HTMLMetaElement>(`meta[name="${name}"]`);
  if (!tag) {
    tag = document.createElement('meta');
    tag.setAttribute('name', name);
    document.head.appendChild(tag);
  }
  tag.setAttribute('content', content.trim());
}

/** The same, for the `property`-keyed Open Graph tags. */
export function applyMetaProperty(
  property: string,
  content: string | undefined | null,
): void {
  if (typeof document === 'undefined') return;
  if (!content || !content.trim()) return;

  let tag = document.head.querySelector<HTMLMetaElement>(
    `meta[property="${property}"]`,
  );
  if (!tag) {
    tag = document.createElement('meta');
    tag.setAttribute('property', property);
    document.head.appendChild(tag);
  }
  tag.setAttribute('content', content.trim());
}

/**
 * Compose a page title.
 *
 * `Cycle · Rhythma` rather than `Rhythma · Cycle`: a browser truncates a
 * tab label from the right, and with eight tabs open the distinguishing
 * word is the page, not the app name. The home page is the app name alone,
 * because `Home · Rhythma` says the same thing twice.
 */
export function composeTitle(pageTitle: string | undefined, appName: string): string {
  const page = pageTitle?.trim();
  if (!page || page === appName) return appName;
  return `${page} · ${appName}`;
}
