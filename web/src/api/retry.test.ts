import { describe, expect, it, vi } from 'vitest';
import type { AxiosError } from 'axios';

import {
  BASE_BACKOFF_MS,
  DEFAULT_TIMEOUT_MS,
  LONG_TIMEOUT_MS,
  MAX_BACKOFF_MS,
  MAX_RETRY_ATTEMPTS,
  backoffDelay,
  isNetworkError,
  isRetryableMethod,
  parseRetryAfter,
  shouldRetry,
  timeoutFor,
} from './retry';

function error(
  overrides: {
    status?: number;
    method?: string;
    code?: string;
  } = {},
): AxiosError {
  const { status, method = 'get', code } = overrides;
  return {
    isAxiosError: true,
    code,
    config: { method },
    response: status === undefined ? undefined : { status },
  } as unknown as AxiosError;
}

describe('isRetryableMethod', () => {
  it.each(['get', 'GET', 'head', 'options'])('%s is safe to replay', (method) => {
    expect(isRetryableMethod(method)).toBe(true);
  });

  it('POST is not', () => {
    // The constraint the whole module is built around. A POST /cycle/log
    // that timed out may already have been committed — the response was
    // lost, not the write — so replaying it creates a duplicate cycle
    // entry, which every prediction and insight downstream is computed
    // from. A visible error beats quietly corrupt data.
    expect(isRetryableMethod('post')).toBe(false);
  });

  it('PATCH and PUT are not', () => {
    expect(isRetryableMethod('patch')).toBe(false);
    expect(isRetryableMethod('put')).toBe(false);
  });

  it('DELETE is not, despite being idempotent by spec', () => {
    // This API answers 404 for a second delete, so a retry after a lost
    // success turns a completed operation into an error the user sees.
    expect(isRetryableMethod('delete')).toBe(false);
  });

  it('treats a missing method as GET, which is what axios does', () => {
    expect(isRetryableMethod(undefined)).toBe(true);
  });
});

describe('isNetworkError', () => {
  it('is true when no response arrived', () => {
    expect(isNetworkError(error())).toBe(true);
  });

  it('is false when the server answered', () => {
    expect(isNetworkError(error({ status: 500 }))).toBe(false);
  });

  it('is false for a request we cancelled ourselves', () => {
    // Retrying an aborted request would defeat the abort.
    expect(isNetworkError(error({ code: 'ERR_CANCELED' }))).toBe(false);
  });
});

describe('shouldRetry', () => {
  it.each([429, 502, 503, 504])('retries a %i', (status) => {
    expect(shouldRetry(error({ status }), 0)).toBe(true);
  });

  it.each([400, 401, 403, 404, 409, 422, 500])('does not retry a %i', (status) => {
    // 500 is excluded on purpose: an unhandled exception is deterministic,
    // so replaying it burns the budget to arrive at the same answer.
    expect(shouldRetry(error({ status }), 0)).toBe(false);
  });

  it('retries a network error', () => {
    expect(shouldRetry(error(), 0)).toBe(true);
  });

  it('does not retry a non-idempotent method even on a retryable status', () => {
    expect(shouldRetry(error({ status: 503, method: 'post' }), 0)).toBe(false);
  });

  it('stops at the attempt ceiling', () => {
    expect(shouldRetry(error({ status: 503 }), MAX_RETRY_ATTEMPTS - 1)).toBe(true);
    expect(shouldRetry(error({ status: 503 }), MAX_RETRY_ATTEMPTS)).toBe(false);
  });

  it('checks the ceiling before the reason, so the total is bounded', () => {
    // Otherwise a flapping endpoint could spend the budget once per
    // failure mode rather than once overall.
    expect(shouldRetry(error({ status: 429 }), MAX_RETRY_ATTEMPTS + 5)).toBe(false);
    expect(shouldRetry(error(), MAX_RETRY_ATTEMPTS + 5)).toBe(false);
  });
});

describe('parseRetryAfter', () => {
  it('reads delta-seconds', () => {
    // The form #135 added to this API's 429 responses.
    expect(parseRetryAfter('2')).toBe(2000);
  });

  it('reads an HTTP date', () => {
    const now = Date.parse('2026-01-01T00:00:00Z');
    const later = new Date(now + 5000).toUTCString();
    expect(parseRetryAfter(later, now)).toBeGreaterThanOrEqual(4000);
    expect(parseRetryAfter(later, now)).toBeLessThanOrEqual(5000);
  });

  it('never returns a negative delay for a date in the past', () => {
    const now = Date.parse('2026-01-01T00:00:00Z');
    const earlier = new Date(now - 60_000).toUTCString();
    expect(parseRetryAfter(earlier, now)).toBe(0);
  });

  it.each([undefined, null, '', '   ', 'soon', 'NaN'])(
    'returns null for %p so the computed backoff is used instead',
    (value) => {
      expect(parseRetryAfter(value)).toBeNull();
    },
  );
});

describe('backoffDelay', () => {
  it('grows with the attempt number', () => {
    // Compared at the ceiling, since the value itself is jittered.
    const noJitter = () => 1;
    expect(backoffDelay(0, null, noJitter)).toBe(BASE_BACKOFF_MS);
    expect(backoffDelay(1, null, noJitter)).toBe(BASE_BACKOFF_MS * 2);
    expect(backoffDelay(2, null, noJitter)).toBe(BASE_BACKOFF_MS * 4);
  });

  it('is capped', () => {
    expect(backoffDelay(20, null, () => 1)).toBe(MAX_BACKOFF_MS);
  });

  it('jitters across the whole window', () => {
    // Without jitter every client that failed against the same restart
    // retries at the same instant, and the storm is what keeps the server
    // down. Spreading across the window is the point, not decoration.
    expect(backoffDelay(2, null, () => 0)).toBe(0);
    expect(backoffDelay(2, null, () => 1)).toBe(BASE_BACKOFF_MS * 4);
  });

  it('prefers a server-supplied Retry-After over its own guess', () => {
    expect(backoffDelay(0, 2000, () => 1)).toBe(2000);
  });

  it('still caps an absurd Retry-After', () => {
    // A misconfigured proxy saying "come back in an hour" should not hang
    // the tab for an hour.
    expect(backoffDelay(0, 3_600_000, () => 1)).toBe(MAX_BACKOFF_MS * 4);
  });
});

describe('timeoutFor', () => {
  it('uses the default for an ordinary endpoint', () => {
    expect(timeoutFor('/cycle/history', DEFAULT_TIMEOUT_MS)).toBe(DEFAULT_TIMEOUT_MS);
  });

  it('gives the assistant a longer budget', () => {
    // It waits on a model call. Applying the default would turn a working
    // answer into a timeout.
    expect(timeoutFor('/assistant/chat', DEFAULT_TIMEOUT_MS)).toBe(LONG_TIMEOUT_MS);
  });

  it('does not raise the budget for the rest of the assistant router', () => {
    expect(timeoutFor('/assistant/languages', DEFAULT_TIMEOUT_MS)).toBe(
      DEFAULT_TIMEOUT_MS,
    );
  });

  it('handles a missing url', () => {
    expect(timeoutFor(undefined, DEFAULT_TIMEOUT_MS)).toBe(DEFAULT_TIMEOUT_MS);
  });
});

describe('the default timeout', () => {
  it('matches the Flutter client', () => {
    // rhythma_flutter/lib/services/api_client.dart sets 10s connect and
    // receive timeouts. The two clients talking to one backend should not
    // disagree about how long is too long.
    expect(DEFAULT_TIMEOUT_MS).toBe(10_000);
  });

  it('is not zero, which is what axios defaults to', () => {
    // The bug: axios `timeout: 0` means wait forever, so a hung request
    // never settled and the page's `finally` never cleared the spinner.
    expect(DEFAULT_TIMEOUT_MS).toBeGreaterThan(0);
  });
});

describe('mocked clock behaviour', () => {
  it('sleep resolves after the given delay', async () => {
    vi.useFakeTimers();
    const { sleep } = await import('./retry');

    let resolved = false;
    void sleep(1000).then(() => {
      resolved = true;
    });

    expect(resolved).toBe(false);
    await vi.advanceTimersByTimeAsync(1000);
    expect(resolved).toBe(true);

    vi.useRealTimers();
  });
});
