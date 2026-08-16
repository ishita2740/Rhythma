import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { MAIN_CONTENT_ID } from './SkipToContent';
import { routeTitleKey } from '../lib/routeTitles';

/**
 * Say the page name on navigation, and move focus into the content (#409).
 *
 * Two problems, one cause. A client-side route change swaps the DOM
 * without firing a page load, so:
 *
 * - Assistive technology is told nothing. A screen-reader user activates
 *   "Insights", hears silence, and cannot tell whether the click landed.
 * - Focus stays on the link the router has just unmounted, at which point
 *   the browser resets it to `<body>`. The next Tab starts from the top
 *   of the document, so every navigation costs a keyboard user a full
 *   re-traverse of the nav.
 *
 * The live region fixes the first and moving focus to `<main>` fixes the
 * second. They are in one component because they must happen together and
 * in this order: announcing without moving focus leaves the user informed
 * and still stranded at the top of the page.
 */
export function RouteAnnouncer() {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  const [message, setMessage] = useState('');
  const isFirstRender = useRef(true);

  useEffect(() => {
    // Skip the initial mount. On a fresh page load the browser has
    // already announced the document and put focus where the user
    // expects it; stealing focus here would move it for no reason, and
    // announcing would duplicate what the title already said.
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }

    setMessage(t('a11y.navigatedTo', { page: t(routeTitleKey(pathname)) }));

    const main = document.getElementById(MAIN_CONTENT_ID);
    // `preventScroll` because the router has already put the scroll
    // position where it belongs, and focusing an element scrolls it into
    // view by default — which would undo that.
    main?.focus({ preventScroll: true });
  }, [pathname, t]);

  return (
    // `polite` rather than `assertive`: a navigation the user just asked
    // for is not an interruption, and `assertive` would cut off whatever
    // the screen reader was mid-way through saying.
    //
    // `role="status"` alongside `aria-live` because some screen reader and
    // browser pairings honour one and not the other.
    <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">
      {message}
    </div>
  );
}
