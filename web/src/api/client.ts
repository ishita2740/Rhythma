// `AxiosHeaders` is a value — it is constructed below. The other two are
// types only, and `verbatimModuleSyntax` is on in tsconfig, so importing a
// type through a value import is a build error (TS1484).
import axios, { AxiosHeaders } from 'axios';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';

import {
  DEFAULT_TIMEOUT_MS,
  backoffDelay,
  isOffline,
  parseRetryAfter,
  shouldRetry,
  sleep,
  timeoutFor,
  type RetryableConfig,
} from './retry';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

/**
 * Per-request deadline (#408).
 *
 * Axios defaults to `0`, meaning wait forever, and that is what this
 * client was doing. A request that got a connection and then nothing
 * never rejected, so the `finally` that clears a page's loading flag
 * never ran and the spinner stayed up until the user reloaded.
 */
const TIMEOUT_MS = Number(import.meta.env.VITE_API_TIMEOUT_MS) || DEFAULT_TIMEOUT_MS;

// Set by the auth provider once the router is mounted, so a 401 anywhere
// can redirect to /login without this module needing to import React.
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

export const apiClient = axios.create({
  baseURL: BASE_URL,
  withCredentials: true, // send cookies with requests to the backend
  headers: { 'X-Client-Platform': 'web' }, // for the backend to know which client is making requests
  timeout: TIMEOUT_MS,
});

// The id the backend stamped on the most recent response, success or
// failure. `core/middleware.py` returns it as X-Request-ID and #268
// exposed it to JavaScript so the client could surface it; the error
// boundary shows it, which is what turns "the app broke" in a bug report
// into a specific line in the server log.
const REQUEST_ID_HEADER = 'x-request-id';
let lastRequestId: string | null = null;

export function getLastRequestId(): string | null {
  return lastRequestId;
}

function recordRequestId(headers: unknown) {
  if (!headers || typeof headers !== 'object') return;
  const value = (headers as Record<string, unknown>)[REQUEST_ID_HEADER];
  if (typeof value === 'string' && value) lastRequestId = value;
}

// ─── Auto-Refresh Token Logic ─────────────────────────────────────────────

/// Endpoints that should never trigger token refresh or retry logic.
const PUBLIC_ENDPOINTS = new Set([
  '/auth/login',
  '/auth/register',
  '/auth/firebase-login',
  '/auth/refresh',
  '/auth/logout',
  '/auth/password-requirements',
  '/auth/forgot-password',
  '/auth/reset-password',
  '/auth/verify-email',
  '/auth/resend-verification',
  '/assistant/languages',
  '/health',
]);

function isPublicEndpoint(path: string): boolean {
  for (const publicPath of PUBLIC_ENDPOINTS) {
    if (path === publicPath || path.endsWith(publicPath)) return true;
  }
  return false;
}

/// Shared in-flight refresh promise so concurrent 401s do not spawn
/// multiple refresh requests.
let refreshPromise: Promise<boolean> | null = null;

async function performRefresh(): Promise<boolean> {
  // If a refresh is already in flight, reuse it.
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      // The refresh cookie is sent automatically via withCredentials.
      // We use a plain axios call (not apiClient) to avoid recursion.
      await axios.post(`${BASE_URL}/auth/refresh`, {}, { withCredentials: true });
      // On success the backend rotated the HttpOnly cookies; no local
      // storage needed.
      return true;
    } catch {
      return false;
    }
  })();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

// ─── Request Interceptor ──────────────────────────────────────────────────

apiClient.interceptors.request.use(
  (config) => {
    // The assistant waits on a model call and legitimately runs longer
    // than the default deadline. Raising the instance-wide timeout to
    // suit it would give every other endpoint a 45-second window in which
    // to hang, so the exception is per-path (#408).
    config.timeout = timeoutFor(config.url, TIMEOUT_MS);
    return config;
  },
  (error) => Promise.reject(error),
);

// ─── Response Interceptor ─────────────────────────────────────────────────

apiClient.interceptors.response.use(
  (response) => {
    recordRequestId(response.headers);
    return response;
  },
  async (error: AxiosError) => {
    recordRequestId(error.response?.headers);

    const status = error.response?.status;
    const config = error.config as RetryableConfig | undefined;
    const url = config?.url ?? '';

    // ── Transient failures (#408) ─────────────────────────────────────
    //
    // Handled before the 401 branch and kept entirely separate from it.
    // The two paths use different counters — `retryCount` here, the
    // `X-Retry-After-Refresh` header below — so a request that was
    // retried after a token refresh does not also consume its transient
    // budget, and neither can multiply against the other.
    if (status !== 401) {
      if (config && shouldRetry(error, config.retryCount ?? 0)) {
        // No point spending the budget on requests that cannot succeed.
        // Checked here rather than in `shouldRetry` so the decision stays
        // a pure function of the error.
        if (isOffline()) {
          return Promise.reject(error);
        }

        const attempt = config.retryCount ?? 0;
        const retryAfter = parseRetryAfter(
          error.response?.headers?.['retry-after'] as string | undefined,
        );

        await sleep(backoffDelay(attempt, retryAfter));

        config.retryCount = attempt + 1;
        return apiClient.request(config);
      }

      // Not a 401 and not worth retrying — pass through unchanged.
      return Promise.reject(error);
    }

    // Public endpoints should not trigger refresh.
    if (isPublicEndpoint(url)) {
      onUnauthorized?.();
      return Promise.reject(error);
    }

    // Prevent infinite retry loops: if this request was already retried
    // after a refresh, force logout.
    if (config?.headers?.['X-Retry-After-Refresh'] === '1') {
      onUnauthorized?.();
      return Promise.reject(error);
    }

    // Attempt to refresh using the HttpOnly cookie.
    const refreshed = await performRefresh();

    if (!refreshed) {
      // Refresh failed — clear session and redirect.
      onUnauthorized?.();
      return Promise.reject(error);
    }

    // Retry the original request once with the new cookies (auto-sent).
    //
    // The marker goes on a real `AxiosHeaders`, not a plain object cast to
    // one. `InternalAxiosRequestConfig.headers` is an `AxiosHeaders`, which
    // carries `set`/`get`/`has` and a normalized key map; a bare
    // `Record<string, string>` satisfies none of that, and the `as` was
    // asserting a lie the compiler correctly refused (TS2322). Downstream
    // axios internals call methods on this object.
    const headers = AxiosHeaders.from(config?.headers);
    headers.set('X-Retry-After-Refresh', '1');

    const retryConfig = {
      ...config,
      headers,
    } as InternalAxiosRequestConfig;

    // `apiClient.request(...)` rather than `apiClient(...)`. They run the
    // same code — the instance *is* a bound `request` — but only the named
    // form is a property lookup, so it is the one a caller can observe.
    return apiClient.request(retryConfig);
  },
);

/**
 * Turns an auth-flow error into an accurate message instead of always
 * blaming bad credentials. A request that never reaches the server (e.g.
 * blocked by CORS, or the backend isn't running) throws with no
 * `error.response` at all — previously this was shown as "Invalid
 * username or password", which was actively misleading and made a CORS
 * misconfiguration look like a login bug.
 */
export function friendlyAuthError(error: unknown, fallback: string): string {
  if (error && typeof error === 'object' && 'isAxiosError' in error) {
    const axiosErr = error as {
      code?: string;
      response?: { status?: number; data?: { detail?: string } };
    };
    if (!axiosErr.response) {
      // A timeout and a CORS rejection both arrive with no response, but
      // they are different problems and the CORS text sends the reader
      // looking in entirely the wrong place (#408).
      if (axiosErr.code === 'ECONNABORTED' || axiosErr.code === 'ETIMEDOUT') {
        return 'The server took too long to respond. Please try again.';
      }
      if (isOffline()) {
        return "You appear to be offline. Check your connection and try again.";
      }
      return "Couldn't reach the server. Check your connection, that the backend is running, and that this origin is allowed by its CORS settings.";
    }
    const status = axiosErr.response.status;
    if (status === 401) return 'Invalid username or password.';
    if (status === 429) {
      return (
        axiosErr.response.data?.detail ||
        'Too many attempts. Please wait a few minutes and try again.'
      );
    }
    if (axiosErr.response.data?.detail) return axiosErr.response.data.detail;
  }
  return fallback;
}

/**
 * The same, for requests that have nothing to do with credentials.
 *
 * `friendlyAuthError` says "Invalid username or password" on a 401, which
 * is right on the login screen and wrong everywhere else — on the cycle
 * screen a 401 means the session expired. Everything below the auth-
 * specific cases is shared.
 */
export function friendlyApiError(error: unknown, fallback: string): string {
  if (error && typeof error === 'object' && 'isAxiosError' in error) {
    const axiosErr = error as {
      code?: string;
      response?: { status?: number; data?: { detail?: string } };
    };

    if (!axiosErr.response) {
      if (axiosErr.code === 'ECONNABORTED' || axiosErr.code === 'ETIMEDOUT') {
        return 'The server took too long to respond. Please try again.';
      }
      if (isOffline()) {
        return "You appear to be offline. Check your connection and try again.";
      }
      return "Couldn't reach the server. Please check your connection and try again.";
    }

    const status = axiosErr.response.status;
    if (status === 401) return 'Your session has expired. Please sign in again.';
    if (status === 503 || status === 502 || status === 504) {
      return 'The service is temporarily unavailable. Please try again in a moment.';
    }
    // `detail` is a string on this API's error envelope. A Pydantic 422
    // makes it a list of objects, which would render as "[object Object]"
    // — so it is only used when it really is a string.
    const detail = axiosErr.response.data?.detail;
    if (typeof detail === 'string' && detail) return detail;
  }
  return fallback;
}
