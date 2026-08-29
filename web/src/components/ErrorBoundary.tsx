import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

import { getLastRequestId } from '../api/client';

/**
 * Catches render errors so one broken page doesn't blank the whole app.
 *
 * React unmounts the entire tree when a render throws and nothing catches
 * it. With no boundary anywhere — which is where `App.tsx` was — a single
 * unguarded property access on a null field replaced Rhythma with a white
 * screen: no message, no way back, and a reload that lands on the same
 * route and throws again. On a phone with no dev tools, that is
 * indistinguishable from the app being permanently broken.
 *
 * The pages this protects render genuinely sparse server data —
 * `/dashboard` returns a nullable `prediction`, `PredictionResponse` has
 * optional dates, and a new user has no logs at all — so this is a
 * question of which failure the user sees, not whether one can happen.
 */

interface Props {
  children: ReactNode;
  /**
   * Changing this clears a caught error. The route path is passed in, so
   * navigating away from a broken page recovers: a boundary that stays
   * latched keeps showing the error screen on pages that work fine.
   */
  resetKey?: string;
  /** Test seam — lets a test assert what was caught without spying on console. */
  onError?: (error: Error, info: ErrorInfo) => void;
}

interface State {
  error: Error | null;
  requestId: string | null;
  /** Mirror of the last `resetKey` prop seen, so a change can be detected. */
  seenResetKey: string | undefined;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, requestId: null, seenResetKey: this.props.resetKey };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  /**
   * Clear a caught error when the reset key changes.
   *
   * Done here rather than in `componentDidUpdate` because that would mean
   * setting state after a completed render — a second render pass, and the
   * pattern `react/no-did-update-set-state` exists to flag. Deriving it
   * instead drops the error in the same pass that brings the new key.
   */
  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    if (props.resetKey === state.seenResetKey) return null;

    return state.error
      ? { error: null, requestId: null, seenResetKey: props.resetKey }
      : { seenResetKey: props.resetKey };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Captured at catch time rather than at render time: by the time the
    // user reports this, the id of the request that fed the broken render
    // is the one thing that ties their screenshot to a backend log line.
    // The middleware returns it as X-Request-ID and #268 exposed it to the
    // browser for exactly this.
    this.setState({ requestId: getLastRequestId() });

    // Kept even though it looks like debug output: this is the only record
    // of the failure in the field, where no dev tools were open when it
    // happened but the console log survives in a bug report.
    console.error('Unhandled render error:', error, info.componentStack);

    this.props.onError?.(error, info);
  }

  reset = () => {
    this.setState({ error: null, requestId: null });
  };

  render() {
    if (this.state.error) {
      return <ErrorFallback requestId={this.state.requestId} onRetry={this.reset} />;
    }

    return this.props.children;
  }
}

function ErrorFallback({
  requestId,
  onRetry,
}: {
  requestId: string | null;
  onRetry: () => void;
}) {
  const { t } = useTranslation();

  return (
    <div className="page error-boundary" role="alert">
      <h1>{t('errors.boundaryTitle')}</h1>
      <p className="card-sub">{t('errors.boundaryBody')}</p>

      <div className="error-boundary-actions">
        {/* Retry first: most render errors come from one bad payload, and
            re-rendering after the data has been refetched is the cheapest
            thing that can work. */}
        <button type="button" className="primary-btn" onClick={onRetry}>
          {t('errors.retry')}
        </button>
        <Link className="ghost-btn" to="/">
          {t('errors.goHome')}
        </Link>
      </div>

      {requestId && (
        <p className="card-sub error-request-id">
          {t('errors.requestId')}: <code>{requestId}</code>
        </p>
      )}
    </div>
  );
}

/**
 * The boundary as the app mounts it: keyed on the current path, so a
 * caught error clears when the user navigates somewhere else.
 *
 * Split from the class because hooks can't be used in one, and the reset
 * key has to come from the router.
 */
export function RouteErrorBoundary({ children }: { children: ReactNode }) {
  const location = useLocation();

  return <ErrorBoundary resetKey={location.pathname}>{children}</ErrorBoundary>;
}
