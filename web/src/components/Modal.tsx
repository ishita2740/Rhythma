/**
 * A dialog that behaves like one (issue #502).
 *
 * Two screens rendered a panel over the page and declared it a dialog:
 *
 *     <div className="modal-backdrop" role="presentation" onClick={close}>
 *       <div className="quick-log-panel" role="dialog" aria-label={...}
 *            onClick={(e) => e.stopPropagation()}>
 *
 * `role="dialog"` is a promise about behaviour, and none of it was kept.
 * Focus was never moved into the panel, so a screen-reader user was told
 * nothing had opened and the next Tab continued through the page
 * underneath. Focus was not trapped, so Tab walked out into the header,
 * the nav and the links behind the overlay — visually covered by the
 * backdrop, still focusable, still activated by Enter. Focus was never
 * restored, so closing dropped it to `<body>` and the next Tab started
 * from the top of the page rather than from the tile the user was on.
 * `aria-modal` was absent and nothing hid the background, so a screen
 * reader in browse mode read the whole Home screen straight through the
 * overlay as though it were still available.
 *
 * On Home the panel is the primary write path — four quick-log tiles, all
 * of them opening it — and the intended interaction is tapping several in
 * a row, which is exactly what losing focus on each close makes tedious.
 * On Profile the same markup had no Escape handler at all, so that dialog
 * could only be dismissed with a mouse. That divergence is what happens
 * when dialog behaviour lives in the page rather than in a component, and
 * it is why this is a component.
 *
 * The app already holds itself to this standard elsewhere. `SkipToContent`
 * is rendered first in the tree so Tab reaches it before anything else;
 * `RouteAnnouncer` exists because "a client-side route change fires no
 * load event, so without this the DOM swaps and assistive technology is
 * told nothing at all"; `DocumentLanguage` was added in #407 because a
 * screen reader pinned to `lang="en"` read Devanagari in an English
 * voice. A dialog that opens and announces nothing is the same omission.
 *
 * Three implementation choices that were not the obvious ones:
 *
 * **A portal, and the rest of `<body>` made `inert`.** `aria-modal="true"`
 * is the standard answer and is set here too, but `inert` additionally
 * removes the background from the *keyboard* order rather than only from
 * the accessibility tree — so a focusable element behind the overlay
 * cannot be reached even if the trap below has a hole in it. Belt and
 * braces on the one thing this component exists to guarantee.
 *
 * **The backdrop closes on `mousedown`, not `click`.** A `click` fires on
 * the common ancestor of press and release, so pressing inside the panel —
 * selecting text in an input, dragging across a label — and releasing
 * outside it counted as a backdrop click and threw away what the user had
 * typed. The old `stopPropagation` on the panel did not help, because the
 * release genuinely was outside it.
 *
 * **Focus lands on the panel, not on its first control.** The dialog's
 * accessible name is then announced before its contents, which is what
 * tells the user what has opened. Tab from there reaches the first
 * control, so nothing is further away than it was.
 */

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  type Ref,
} from 'react';
import { createPortal } from 'react-dom';

/**
 * What counts as reachable by Tab.
 *
 * `[tabindex="-1"]` is excluded because that is precisely the marker for
 * "focusable by script, not by Tab" — and the panel itself carries it.
 */
const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

/**
 * The controls inside `container` that Tab can reach, in document order.
 *
 * Deliberately does not consult `offsetParent` or `getComputedStyle` to
 * decide what is visible. Neither is meaningful without layout, and the
 * test environment has none — a visibility check that quietly returns
 * "nothing is focusable" under jsdom would make the trap below
 * `preventDefault` every Tab and pass its own tests while doing it. The
 * markers a component actually uses to withdraw a control are checked
 * instead, and they are all attributes.
 */
function focusableWithin(container: HTMLElement): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter(
    (element) =>
      !element.hasAttribute('hidden') &&
      !element.hasAttribute('inert') &&
      element.getAttribute('aria-hidden') !== 'true' &&
      element.style.display !== 'none' &&
      element.style.visibility !== 'hidden',
  );
}

/**
 * Hide everything already on the page from assistive technology and from Tab.
 *
 * Returns the undo. Written against `document.body`'s children rather than
 * a hardcoded `#root` so it holds wherever the app is mounted — including
 * under a test renderer, which appends its own container beside whatever
 * else happens to be there.
 *
 * Previous values are recorded rather than assumed, so an interrupted
 * unmount restores what was actually there instead of clearing an
 * `aria-hidden` something else had set.
 */
function hideBackground(except: HTMLElement): () => void {
  const changed: Array<{
    element: HTMLElement;
    ariaHidden: string | null;
    inert: string | null;
  }> = [];

  for (const child of Array.from(document.body.children)) {
    if (!(child instanceof HTMLElement) || child === except) continue;

    changed.push({
      element: child,
      ariaHidden: child.getAttribute('aria-hidden'),
      inert: child.getAttribute('inert'),
    });

    child.setAttribute('aria-hidden', 'true');
    child.setAttribute('inert', '');
  }

  return () => {
    for (const { element, ariaHidden, inert } of changed) {
      if (ariaHidden === null) element.removeAttribute('aria-hidden');
      else element.setAttribute('aria-hidden', ariaHidden);

      if (inert === null) element.removeAttribute('inert');
      else element.setAttribute('inert', inert);
    }
  };
}

/** Stop the page behind the overlay scrolling under it. Returns the undo. */
function lockScroll(): () => void {
  const previous = document.body.style.overflow;
  document.body.style.overflow = 'hidden';
  return () => {
    document.body.style.overflow = previous;
  };
}

export interface ModalProps {
  /** Whether the dialog is on screen. Nothing is rendered when false. */
  open: boolean;
  /**
   * Called for every way out: Escape, the backdrop, and anything inside
   * the panel that dismisses it.
   */
  onClose: () => void;
  /**
   * The dialog's visible heading. Rendered as an `<h2>` and wired to
   * `aria-labelledby`, so the name a screen reader announces is the one on
   * screen rather than a second copy in an `aria-label` that can drift
   * away from it.
   */
  title: ReactNode;
  children: ReactNode;
  /** Class for the panel, so each screen keeps the layout it already had. */
  panelClassName?: string;
  /**
   * Render the panel as a `<form>` and submit through this.
   *
   * Profile's edit panel is a form. Wrapping a form inside a dialog `div`
   * would work, but making the dialog the form keeps the markup the page
   * already had rather than adding a level for the sake of the component.
   */
  onSubmit?: (event: FormEvent<HTMLFormElement>) => void;
}

export function Modal({
  open,
  onClose,
  title,
  children,
  panelClassName,
  onSubmit,
}: ModalProps) {
  const panelRef = useRef<HTMLElement | null>(null);
  const titleId = useId();

  // Captured on open so it can be handed back on close. A ref rather than
  // state: nothing renders from it, and reading it during cleanup must not
  // see a value from a later render.
  const openerRef = useRef<Element | null>(null);

  // Held in a ref so the key handler can be created once rather than
  // re-created on every render the parent happens to do.
  const onCloseRef = useRef(onClose);
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;

    openerRef.current = document.activeElement;

    const panel = panelRef.current;
    // The panel itself, so its accessible name is announced before its
    // contents. `tabIndex={-1}` below is what makes this legal.
    panel?.focus();

    const releaseScroll = lockScroll();
    const revealBackground = panel?.parentElement
      ? hideBackground(panel.parentElement)
      : () => {};

    return () => {
      revealBackground();
      releaseScroll();

      // Back to the control that opened it — the tile, the menu row —
      // rather than to `<body>`, which would restart Tab from the top of
      // the page. Guarded, because that element can have been removed
      // while the dialog was up.
      const opener = openerRef.current;
      if (opener instanceof HTMLElement && document.contains(opener)) {
        opener.focus();
      }
    };
  }, [open]);

  const handleKeyDown = useCallback((event: ReactKeyboardEvent) => {
    if (event.key === 'Escape') {
      // Stopped here so a page-level Escape handler behind the dialog does
      // not also act on it. Profile's panel had no Escape at all; Home's
      // was a `window` listener the page installed for itself.
      event.stopPropagation();
      onCloseRef.current();
      return;
    }

    if (event.key !== 'Tab') return;

    const panel = panelRef.current;
    if (!panel) return;

    const focusable = focusableWithin(panel);
    if (focusable.length === 0) {
      // Nothing to move to. Holding focus on the panel beats letting Tab
      // escape into the page behind it.
      event.preventDefault();
      return;
    }

    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement;

    if (event.shiftKey) {
      // Also fires when focus is on the panel itself, which is where it
      // starts: Shift+Tab from there wraps to the end rather than stepping
      // out into the page.
      if (active === first || active === panel || !panel.contains(active)) {
        event.preventDefault();
        last.focus();
      }
      return;
    }

    if (active === last) {
      event.preventDefault();
      first.focus();
    }
  }, []);

  if (!open) return null;

  const panelProps = {
    className: panelClassName,
    role: 'dialog',
    'aria-modal': true,
    'aria-labelledby': titleId,
    tabIndex: -1,
    onKeyDown: handleKeyDown,
  } as const;

  const heading = (
    <h2 id={titleId} className="modal-title">
      {title}
    </h2>
  );

  return createPortal(
    <div
      className="modal-backdrop"
      // `mousedown`, not `click` — see the note at the top of the file.
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      {onSubmit ? (
        <form
          {...panelProps}
          ref={panelRef as Ref<HTMLFormElement>}
          onSubmit={onSubmit}
        >
          {heading}
          {children}
        </form>
      ) : (
        <div {...panelProps} ref={panelRef as Ref<HTMLDivElement>}>
          {heading}
          {children}
        </div>
      )}
    </div>,
    document.body,
  );
}
