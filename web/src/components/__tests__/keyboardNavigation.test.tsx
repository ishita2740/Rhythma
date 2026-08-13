import { describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { I18nextProvider } from 'react-i18next';
import { MemoryRouter, Route, Routes, Link } from 'react-router-dom';

import i18n from '../../i18n';
import { MAIN_CONTENT_ID, SkipToContent } from '../SkipToContent';
import { RouteAnnouncer } from '../RouteAnnouncer';
import { routeTitleKey } from '../../lib/routeTitles';
import { ScrollToTopButton } from '../ScrollToTopButton';

/**
 * A miniature app with the same structure as the real one: skip link
 * first, announcer, a nav, and a `<main>` carrying the shared id.
 */
function Harness({ initial = '/' }: { initial?: string }) {
  return (
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={[initial]}>
        <SkipToContent />
        <RouteAnnouncer />
        <nav aria-label="Main">
          <Link to="/">Home</Link>
          <Link to="/insights">Insights</Link>
        </nav>
        <main id={MAIN_CONTENT_ID} tabIndex={-1}>
          <Routes>
            <Route path="/" element={<h1>Home page</h1>} />
            <Route path="/insights" element={<h1>Insights page</h1>} />
          </Routes>
        </main>
      </MemoryRouter>
    </I18nextProvider>
  );
}

describe('skip to content', () => {
  it('is the first thing Tab reaches', async () => {
    // A skip link that is not the first tab stop skips nothing.
    const user = userEvent.setup();
    render(<Harness />);

    await user.tab();

    expect(document.activeElement).toHaveTextContent(/skip to content/i);
  });

  it('points at the main landmark', () => {
    render(<Harness />);

    const link = screen.getByRole('link', { name: /skip to content/i });
    expect(link).toHaveAttribute('href', `#${MAIN_CONTENT_ID}`);
    // The target must exist, or the link is a tab stop that promises help
    // and does nothing.
    expect(document.getElementById(MAIN_CONTENT_ID)).not.toBeNull();
  });

  it('stays in the focus order while hidden', () => {
    // The bug this guards against: hiding it with `display: none` or
    // `visibility: hidden` removes it from the focus order, making it
    // unreachable by the only user it exists for.
    render(<Harness />);

    const link = screen.getByRole('link', { name: /skip to content/i });
    expect(link).toBeVisible();
    expect(link).not.toHaveAttribute('hidden');
    expect(link).not.toHaveAttribute('aria-hidden');
  });

  it('is localized rather than hardcoded English', async () => {
    render(<Harness />);
    await i18n.changeLanguage('hi');

    await waitFor(() => {
      expect(
        screen.getByRole('link', { name: i18n.t('a11y.skipToContent') }),
      ).toBeInTheDocument();
    });

    await i18n.changeLanguage('en');
  });
});

describe('route announcer', () => {
  it('renders a polite live region', () => {
    render(<Harness />);

    const region = screen.getByRole('status');
    expect(region).toHaveAttribute('aria-live', 'polite');
    // `atomic` so the whole sentence is read, not just the changed words.
    expect(region).toHaveAttribute('aria-atomic', 'true');
  });

  it('says nothing on the initial render', () => {
    // A fresh page load already announces the document; repeating it here
    // would be duplicate noise.
    render(<Harness />);

    expect(screen.getByRole('status')).toHaveTextContent('');
  });

  it('announces the new page after a navigation', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole('link', { name: 'Insights' }));

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/insights/i);
    });
  });

  it('does not steal focus on the initial render', () => {
    // Focusing <main> on first load would move focus away from wherever
    // the browser put it, for no reason the user asked for.
    render(<Harness />);

    expect(document.activeElement).not.toBe(document.getElementById(MAIN_CONTENT_ID));
  });

  it('moves focus into main after a navigation', async () => {
    // Without this, focus sits on the unmounted link, the browser resets
    // it to <body>, and the next Tab re-traverses the whole nav.
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole('link', { name: 'Insights' }));

    await waitFor(() => {
      expect(document.activeElement).toBe(document.getElementById(MAIN_CONTENT_ID));
    });
  });

  it('leaves main out of the Tab order', async () => {
    render(<Harness />);

    // tabIndex={-1} is focusable programmatically but must not add a stop.
    expect(document.getElementById(MAIN_CONTENT_ID)).toHaveAttribute('tabindex', '-1');
  });
});

describe('routeTitleKey', () => {
  it.each([
    ['/', 'meta.home.title'],
    ['/cycle', 'meta.cycle.title'],
    ['/insights', 'meta.insights.title'],
    ['/sharing', 'meta.sharing.title'],
    ['/provider', 'meta.providerDashboard.title'],
  ])('%s maps to %s', (path, key) => {
    expect(routeTitleKey(path)).toBe(key);
  });

  it('prefers the more specific provider route', () => {
    // `/provider/patients/abc` must not fall through to the dashboard
    // key just because `/provider` also matches.
    expect(routeTitleKey('/provider/patients/abc')).toBe('meta.providerPatient.title');
    expect(routeTitleKey('/provider/login')).toBe('meta.providerLogin.title');
  });

  it('falls back to the app name for an unknown path', () => {
    // Silence would defeat the purpose — something must be announced.
    expect(routeTitleKey('/nothing-here')).toBe('meta.appName');
  });
});

describe('scroll to top button', () => {
  function renderScrollButton() {
    return render(
      <I18nextProvider i18n={i18n}>
        <ScrollToTopButton />
      </I18nextProvider>,
    );
  }

  it('exposes a localized accessible name', async () => {
    // Its visible content is an arrow glyph, so `aria-label` is the only
    // name it has — and it was hardcoded English.
    renderScrollButton();
    Object.defineProperty(window, 'scrollY', { value: 500, configurable: true });
    window.dispatchEvent(new Event('scroll'));

    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: i18n.t('a11y.scrollToTop') }),
      ).toBeInTheDocument();
    });
  });

  it('hides the arrow glyph from the accessibility tree', async () => {
    renderScrollButton();
    Object.defineProperty(window, 'scrollY', { value: 500, configurable: true });
    window.dispatchEvent(new Event('scroll'));

    await waitFor(() => {
      const button = screen.getByRole('button');
      // Otherwise a screen reader reads the name and then the arrow.
      expect(button.querySelector('[aria-hidden="true"]')).not.toBeNull();
    });
  });
});

describe('decorative cursor', () => {
  it('is hidden from the accessibility tree', async () => {
    // The component returns null on a touch device, and jsdom defines
    // `ontouchstart`, so it renders nothing unless that is removed first.
    // `setupTests.ts` already stubs matchMedia with `matches: false`,
    // which covers the other half of the check.
    const hadTouchStart = 'ontouchstart' in window;
    if (hadTouchStart) {
      delete (window as unknown as Record<string, unknown>).ontouchstart;
    }

    try {
      const { CustomCursor } = await import('../CustomCursor');
      const { container } = render(<CustomCursor />);

      const decorations = container.querySelectorAll('div');
      // Guard: without it this test passes vacuously whenever the
      // component takes its early-return branch.
      expect(decorations.length).toBeGreaterThan(0);

      for (const node of decorations) {
        // Two divs trailing the pointer. Without this a screen reader
        // walks into them as unlabelled nodes inside the page content.
        expect(node).toHaveAttribute('aria-hidden', 'true');
      }
    } finally {
      if (hadTouchStart) {
        (window as unknown as Record<string, unknown>).ontouchstart = undefined;
      }
    }
  });
});
