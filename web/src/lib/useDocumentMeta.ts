import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

import {
  applyDocumentLanguage,
  applyDocumentTitle,
  applyMetaProperty,
  applyMetaTag,
  composeTitle,
} from './documentMeta';

/**
 * Give the current page a localized title and description (#407).
 *
 * Takes translation *keys* rather than finished strings, and resolves them
 * inside the effect, so the title re-renders when the user switches
 * language and not only when the route changes. Passing `t('...')` in from
 * the caller would look equivalent and would leave the tab in the previous
 * language until the next navigation.
 *
 * ```tsx
 * export function CyclePage() {
 *   useDocumentMeta('meta.cycle.title', 'meta.cycle.description');
 *   ...
 * }
 * ```
 */
export function useDocumentMeta(titleKey: string, descriptionKey?: string): void {
  const { t, i18n } = useTranslation();
  const language = i18n.language;

  useEffect(() => {
    const appName = t('meta.appName');
    const title = composeTitle(t(titleKey), appName);

    applyDocumentTitle(title);
    // Open Graph mirrors the title so a link shared into WhatsApp — which
    // is how this app is most likely to be passed around — previews as the
    // page rather than as a bare URL.
    applyMetaProperty('og:title', title);

    if (descriptionKey) {
      const description = t(descriptionKey);
      applyMetaTag('description', description);
      applyMetaProperty('og:description', description);
    }
    // `language` is in the deps because `t` is not guaranteed to change
    // identity on a language switch; without it the tab keeps the previous
    // language's title until the next navigation.
  }, [t, i18n, language, titleKey, descriptionKey]);
}

/**
 * Keep `<html lang>` and `<html dir>` pointed at the active locale.
 *
 * Mounted once, near the root. Separate from `useDocumentMeta` because it
 * is a property of the application rather than of a page, and because
 * every page calling it would mean nine redundant attribute writes per
 * navigation.
 */
export function useDocumentLanguage(): void {
  const { i18n } = useTranslation();
  const language = i18n.language;

  useEffect(() => {
    applyDocumentLanguage(language);
  }, [language]);
}

/**
 * Renders nothing; exists so the root can use the hook above.
 *
 * `App` is not itself inside a component that can call hooks before the
 * providers mount, and i18next's context has to be available for
 * `useTranslation` to report the resolved language.
 */
export function DocumentLanguage(): null {
  useDocumentLanguage();
  return null;
}
