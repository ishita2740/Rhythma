/**
 * Deciding whether a failed request is worth trying again, and when.
 *
 * Issue #408. The web client set no `timeout` and retried nothing: the
 * response interceptor handled `status === 401` and rejected everything
 * else straight through. So a request that got a socket and then silence —
 * a wedged backend, a proxy holding the connection, a phone that walked
 * out of coverage — never settled, and every page does this with the
 * promise:
 *
 *     setLoading(true);
 *     try { ... } finally { setLoading(false); }
 *
 * The `finally` never ran. The spinner stayed up forever, with no error
 * and nothing to click, and the only way out was a manual reload the user
 * had no reason to know was needed.
 *
 * Split out of `client.ts` rather than inlined because the interesting
 * part is a set of policy decisions that are worth reading — and worth
 * testing — without an axios instance in the way.
 */

import type { AxiosError, InternalAxiosRequestConfig } from 'axios';

/** Default per-request deadline. Matches Flutter's Dio client. */
export const DEFAULT_TIMEOUT_MS = 10_000;

/**
 * The assistant legitimately runs long — it waits on a model call.
 * Applying the default here would turn a working answer into a timeout,
 * so this endpoint gets its own budget rather than pushing everyone
 * else's up to match.
 */
export const LONG_TIMEOUT_MS = 45_000;
export const LONG_TIMEOUT_PATHS = ['/assistant/chat'];

export const MAX_RETRY_ATTEMPTS = 3;
export const BASE_BACKOFF_MS = 300;
export const MAX_BACKOFF_MS = 5_000;

/**
 * Statuses worth retrying.
 *
 * All transient by definition: the server said "not now", not "no". Every
 * other 4xx is a statement about the request itself, and replaying it
 * unchanged would produce the same answer more slowly.
 */
const RETRYABLE_STATUSES = new Set([429, 502, 503, 504]);

/**
 * Methods safe to replay.
 *
 * This is the constraint the whole module is built around. A
 * `POST /cycle/log` that timed out may well have been committed
 * server-side — the response was lost, not the write — so replaying it
 * would silently create a duplicate cycle entry. A duplicate log is worse
 * than an error message, because the error is visible and the duplicate
 * quietly corrupts the data every prediction and insight is computed
 * from.
 *
 * Only the methods HTTP defines as idempotent are here. `DELETE` is
 * idempotent by spec but omitted deliberately: this API answers 404 for a
 * second delete, so a retry after a lost success turns a completed
 * operation into an error the user sees.
 */
const RETRYABLE_METHODS = new Set(['get', 'head', 'options']);

/** Config with our bookkeeping attached. */
export interface RetryableConfig extends InternalAxiosRequestConfig {
  /** How many times this request has already been retried by us. */
  retryCount?: number;
}

export function isRetryableMethod(method: string | undefined): boolean {
  return RETRYABLE_METHODS.has((method ?? 'get').toLowerCase());
}

/** True when the request never got a response at all. */
export function isNetworkError(error: AxiosError): boolean {
  if (error.response) return false;
  // A timeout axios raised itself, a DNS failure, a refused connection, a
  // dropped socket. `ERR_CANCELED` is not in here on purpose — an aborted
  // request was aborted by us, and retrying it would defeat the abort.
  return error.code !== 'ERR_CANCELED';
}

/**
 * Whether to try this request again.
 *
 * Order matters: the attempt ceiling is checked before anything else, so
 * a persistently failing endpoint costs a bounded number of requests
 * rather than a bounded number *per reason*.
 */
export function shouldRetry(error: AxiosError, attempt: number): boolean {
  if (attempt >= MAX_RETRY_ATTEMPTS) return false;
  if (!isRetryableMethod(error.config?.method)) return false;

  const status = error.response?.status;
  if (status === undefined) return isNetworkError(error);
  return RETRYABLE_STATUSES.has(status);
}

/**
 * Parse `Retry-After`, which comes in two shapes.
 *
 * Delta-seconds (`Retry-After: 2`) or an HTTP date
 * (`Retry-After: Wed, 21 Oct 2026 07:28:00 GMT`). #135 added the header to
 * this API's 429s in the delta form, but a proxy or CDN in front of the
 * backend can emit either, so both are handled.
 *
 * Returns `null` for anything unparseable, so a malformed header falls
 * back to the computed backoff instead of failing the request.
 */
export function parseRetryAfter(
  value: string | undefined | null,
  now: number = Date.now(),
): number | null {
  if (!value) return null;

  const trimmed = value.trim();
  if (!trimmed) return null;

  // Delta-seconds.
  if (/^\d+$/.test(trimmed)) {
    return Number(trimmed) * 1000;
  }

  // HTTP date.
  const timestamp = Date.parse(trimmed);
  if (Number.isNaN(timestamp)) return null;

  // A date in the past means "now"; a negative delay would be a bug.
  return Math.max(0, timestamp - now);
}

/**
 * How long to wait before attempt `attempt + 1`.
 *
 * Exponential with full jitter. The jitter is not decoration: without it,
 * every client that failed against the same backend restart retries at
 * the same instant, and the retry storm is what keeps it down. Randomising
 * across the whole window spreads the load rather than merely shifting it.
 *
 * A server-supplied `Retry-After` always wins. It knows when it will be
 * ready and we are guessing.
 */
export function backoffDelay(
  attempt: number,
  retryAfterMs: number | null = null,
  random: () => number = Math.random,
): number {
  if (retryAfterMs !== null) {
    return Math.min(retryAfterMs, MAX_BACKOFF_MS * 4);
  }
  const ceiling = Math.min(BASE_BACKOFF_MS * 2 ** attempt, MAX_BACKOFF_MS);
  return Math.round(random() * ceiling);
}

/** The timeout for a given request path. */
export function timeoutFor(url: string | undefined, defaultMs: number): number {
  if (!url) return defaultMs;
  return LONG_TIMEOUT_PATHS.some((path) => url.includes(path))
    ? LONG_TIMEOUT_MS
    : defaultMs;
}

/** True when the browser is confident there is no network at all. */
export function isOffline(): boolean {
  // `navigator.onLine === true` means "has an interface", not "has
  // internet", so it is only trusted in the negative direction. False is
  // reliable; true tells us nothing.
  return typeof navigator !== 'undefined' && navigator.onLine === false;
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}
