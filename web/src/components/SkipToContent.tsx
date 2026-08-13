import { useTranslation } from 'react-i18next';

import './SkipToContent.css';

/**
 * The id every layout puts on its `<main>`, and the target of the link.
 *
 * Exported so a layout cannot drift from the link by retyping the string.
 * A skip link pointing at nothing is worse than no skip link: it is a tab
 * stop that promises to help and then does nothing.
 */
export const MAIN_CONTENT_ID = 'main-content';

/**
 * "Skip to content", visible only when focused (#409).
 *
 * WCAG 2.1 §2.4.1 Bypass Blocks, Level A. `AppLayout` renders the nav on
 * every authenticated route, so without this a keyboard user tabs through
 * every navigation link before reaching the content they came for — and
 * again on the next route, because the nav re-renders each time.
 *
 * Rendered as the first focusable element in the tree, so it is the first
 * thing Tab reaches from the address bar.
 *
 * Hidden by being positioned off-screen rather than with `display: none`
 * or `visibility: hidden`, both of which remove an element from the focus
 * order entirely — which would make it unreachable by the exact user it
 * exists for. See SkipToContent.css.
 */
export function SkipToContent() {
  const { t } = useTranslation();

  return (
    <a className="skip-to-content" href={`#${MAIN_CONTENT_ID}`}>
      {t('a11y.skipToContent')}
    </a>
  );
}
