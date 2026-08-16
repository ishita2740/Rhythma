import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { I18nextProvider } from 'react-i18next';

import i18n from '../../i18n';
import { ErrorBoundary, RouteErrorBoundary } from '../ErrorBoundary';

vi.mock('../../api/client', async () => {
  const actual = await vi.importActual<typeof import('../../api/client')>(
    '../../api/client',
  );
  return { ...actual, getLastRequestId: () => lastRequestId };
});

let lastRequestId: string | null = null;

/**
 * React logs every caught error to the console itself, on top of our own
 * componentDidCatch call. Silenced so a passing run isn't full of red
 * stack traces that look like failures — the assertions below check the
 * boundary's behaviour, not the console.
 */
beforeEach(() => {
  lastRequestId = null;
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

function Boom(): never {
  throw new Error('prediction.nextPeriodDate is null');
}

function renderInRouter(ui: React.ReactNode, route = '/') {
  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </I18nextProvider>,
  );
}

describe('ErrorBoundary', () => {
  it('renders its children when nothing throws', () => {
    renderInRouter(
      <ErrorBoundary>
        <p>Everything is fine</p>
      </ErrorBoundary>,
    );

    expect(screen.getByText('Everything is fine')).toBeInTheDocument();
  });

  it('shows a fallback instead of a blank page when a child throws', () => {
    // Without a boundary React unmounts the whole tree: no message, no way
    // back, and a reload that throws again on the same route.
    renderInRouter(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(i18n.t('errors.boundaryTitle'))).toBeInTheDocument();
  });

  it('offers a way back to a page that is known to work', () => {
    renderInRouter(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );

    expect(screen.getByRole('link', { name: i18n.t('errors.goHome') })).toHaveAttribute(
      'href',
      '/',
    );
  });

  it('reports the caught error to its onError hook', () => {
    const onError = vi.fn();

    renderInRouter(
      <ErrorBoundary onError={onError}>
        <Boom />
      </ErrorBoundary>,
    );

    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0][0].message).toBe('prediction.nextPeriodDate is null');
  });

  it('still logs to the console so the failure is diagnosable in the field', () => {
    renderInRouter(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );

    const logged = (console.error as unknown as ReturnType<typeof vi.fn>).mock.calls;
    expect(logged.some((call) => String(call[0]).includes('Unhandled render error'))).toBe(
      true,
    );
  });

  it('shows the API request id when there is one', () => {
    // Turns "the app broke" in a bug report into a specific server log line.
    lastRequestId = 'req-abc-123';

    renderInRouter(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );

    expect(screen.getByText('req-abc-123')).toBeInTheDocument();
  });

  it('omits the reference line when no request has been made', () => {
    renderInRouter(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );

    expect(screen.queryByText(/Reference/)).not.toBeInTheDocument();
  });

  it('recovers when retry is clicked and the child no longer throws', async () => {
    const user = userEvent.setup();

    // Driven by an external flag rather than a render counter: React 19
    // may render a component twice (it retries synchronously after a
    // concurrent render throws), so "throw only on the first call" is not
    // a reliable way to describe a transient failure.
    let failing = true;

    function Flaky() {
      if (failing) throw new Error('transient');
      return <p>Recovered</p>;
    }

    renderInRouter(
      <ErrorBoundary>
        <Flaky />
      </ErrorBoundary>,
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();

    failing = false;
    await user.click(screen.getByRole('button', { name: i18n.t('errors.retry') }));

    expect(await screen.findByText('Recovered')).toBeInTheDocument();
  });

  it('clears the error when the reset key changes', () => {
    const { rerender } = render(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter>
          <ErrorBoundary resetKey="/insights">
            <Boom />
          </ErrorBoundary>
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();

    rerender(
      <I18nextProvider i18n={i18n}>
        <MemoryRouter>
          <ErrorBoundary resetKey="/settings">
            <p>A page that works</p>
          </ErrorBoundary>
        </MemoryRouter>
      </I18nextProvider>,
    );

    expect(screen.getByText('A page that works')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});

describe('RouteErrorBoundary', () => {
  it('clears itself when the user navigates away from the broken page', async () => {
    // A latched boundary would keep showing the error screen on pages that
    // are perfectly fine, which is worse than the crash it replaced.
    const user = userEvent.setup();

    renderInRouter(
      <RouteErrorBoundary>
        <Routes>
          <Route path="/broken" element={<Boom />} />
          <Route path="/" element={<p>Home page</p>} />
        </Routes>
      </RouteErrorBoundary>,
      '/broken',
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();

    // The throwing route unmounted with the error, so the only way out is
    // the fallback's own link — which is the point of it being there.
    await user.click(screen.getByRole('link', { name: i18n.t('errors.goHome') }));

    expect(await screen.findByText('Home page')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument());
  });
});
