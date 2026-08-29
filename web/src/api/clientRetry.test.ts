import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient, friendlyApiError, friendlyAuthError } from './client';
import { DEFAULT_TIMEOUT_MS, LONG_TIMEOUT_MS } from './retry';

/**
 * Drives the real response interceptor, the same way `client.test.ts`
 * does for the 401 path — reaching into the registered handlers rather
 * than standing up a server, because the behaviour under test is the
 * interceptor's decision-making.
 */
function runResponseInterceptor(error: unknown) {
  const handlers = (
    apiClient.interceptors.response as unknown as {
      handlers: { rejected: (e: unknown) => Promise<unknown> }[];
    }
  ).handlers.filter(Boolean);
  const rejected = handlers[handlers.length - 1].rejected;
  return rejected(error).catch((e: unknown) => e);
}

function runRequestInterceptor(config: Record<string, unknown>) {
  const handlers = (
    apiClient.interceptors.request as unknown as {
      handlers: { fulfilled: (c: unknown) => unknown }[];
    }
  ).handlers.filter(Boolean);
  return handlers[0].fulfilled(config) as Record<string, unknown>;
}

function axiosFailure(overrides: {
  status?: number;
  method?: string;
  url?: string;
  code?: string;
  retryCount?: number;
  headers?: Record<string, string>;
}) {
  const { status, method = 'get', url = '/cycle/u1/history', code, retryCount, headers } =
    overrides;
  return {
    isAxiosError: true,
    code,
    config: { method, url, retryCount, headers: {} },
    response:
      status === undefined
        ? undefined
        : { status, headers: headers ?? {}, data: {} },
  };
}

let requestSpy: ReturnType<typeof vi.spyOn>;

beforeEach(() => {
  vi.useFakeTimers();
  // Intercept the replay so a retry does not reach the network.
  requestSpy = vi
    .spyOn(apiClient, 'request')
    .mockResolvedValue({ data: 'ok' } as never);
});

afterEach(() => {
  vi.useRealTimers();
  requestSpy.mockRestore();
});

/** Run the interceptor and let every scheduled backoff elapse. */
async function settle(error: unknown) {
  const promise = runResponseInterceptor(error);
  await vi.runAllTimersAsync();
  return promise;
}

describe('instance configuration', () => {
  it('sets a timeout, rather than axios\'s wait-forever default', () => {
    expect(apiClient.defaults.timeout).toBe(DEFAULT_TIMEOUT_MS);
  });

  it('leaves the existing configuration alone', () => {
    // #296's refresh setup and the platform header must survive.
    expect(apiClient.defaults.withCredentials).toBe(true);
    expect(apiClient.defaults.headers['X-Client-Platform']).toBe('web');
  });
});

describe('per-request timeout', () => {
  it('applies the default to an ordinary request', () => {
    const config = runRequestInterceptor({ url: '/cycle/u1/history' });
    expect(config.timeout).toBe(DEFAULT_TIMEOUT_MS);
  });

  it('gives the assistant chat endpoint a longer one', () => {
    const config = runRequestInterceptor({ url: '/assistant/chat' });
    expect(config.timeout).toBe(LONG_TIMEOUT_MS);
  });
});

describe('transient retry', () => {
  it('retries a GET that hit a 503', async () => {
    await settle(axiosFailure({ status: 503 }));

    expect(requestSpy).toHaveBeenCalledTimes(1);
  });

  it('retries a GET that never got a response', async () => {
    await settle(axiosFailure({}));

    expect(requestSpy).toHaveBeenCalledTimes(1);
  });

  it('retries a timeout', async () => {
    await settle(axiosFailure({ code: 'ECONNABORTED' }));

    expect(requestSpy).toHaveBeenCalledTimes(1);
  });

  it('does not retry a POST', async () => {
    // The important negative. A replayed POST /cycle/log silently creates
    // a duplicate entry.
    const result = await settle(axiosFailure({ status: 503, method: 'post' }));

    expect(requestSpy).not.toHaveBeenCalled();
    expect(result).toMatchObject({ isAxiosError: true });
  });

  it('does not retry a 404', async () => {
    await settle(axiosFailure({ status: 404 }));

    expect(requestSpy).not.toHaveBeenCalled();
  });

  it('does not retry a 422', async () => {
    await settle(axiosFailure({ status: 422 }));

    expect(requestSpy).not.toHaveBeenCalled();
  });

  it('increments the retry counter on the replayed config', async () => {
    await settle(axiosFailure({ status: 503, retryCount: 0 }));

    const replayed = requestSpy.mock.calls[0][0] as { retryCount?: number };
    expect(replayed.retryCount).toBe(1);
  });

  it('gives up once the counter reaches the ceiling', async () => {
    await settle(axiosFailure({ status: 503, retryCount: 3 }));

    expect(requestSpy).not.toHaveBeenCalled();
  });

  it('rejects with the original error when it gives up', async () => {
    const failure = axiosFailure({ status: 503, retryCount: 3 });

    const result = await settle(failure);

    expect(result).toBe(failure);
  });

  it('honours Retry-After on a 429', async () => {
    const promise = runResponseInterceptor(
      axiosFailure({ status: 429, headers: { 'retry-after': '2' } }),
    );

    // Not yet — the interceptor is waiting out the server's delay.
    await vi.advanceTimersByTimeAsync(1500);
    expect(requestSpy).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(600);
    expect(requestSpy).toHaveBeenCalledTimes(1);

    await promise;
  });
});

describe('offline', () => {
  const original = Object.getOwnPropertyDescriptor(navigator, 'onLine');

  afterEach(() => {
    if (original) Object.defineProperty(navigator, 'onLine', original);
  });

  it('does not burn the retry budget when the browser reports no network', async () => {
    Object.defineProperty(navigator, 'onLine', {
      configurable: true,
      get: () => false,
    });

    await settle(axiosFailure({}));

    expect(requestSpy).not.toHaveBeenCalled();
  });
});

describe('the 401 path is untouched', () => {
  it('a 401 does not go through the transient-retry branch', async () => {
    // #296's refresh logic owns 401 entirely. If the retry branch caught
    // it too, a failed refresh would be attempted several times over.
    const result = await settle(
      axiosFailure({ status: 401, url: '/auth/login' }),
    );

    expect(result).toMatchObject({ isAxiosError: true });
  });
});

describe('friendlyApiError', () => {
  it('names a timeout as a timeout', () => {
    // Previously this fell through to CORS advice, which sends the reader
    // looking in entirely the wrong place.
    const message = friendlyApiError(
      { isAxiosError: true, code: 'ECONNABORTED' },
      'fallback',
    );
    expect(message).toMatch(/took too long/i);
  });

  it('reads a 401 as an expired session, not bad credentials', () => {
    // The difference from friendlyAuthError: outside the login screen a
    // 401 does not mean the password was wrong.
    expect(
      friendlyApiError({ isAxiosError: true, response: { status: 401 } }, 'fallback'),
    ).toMatch(/session/i);
    expect(
      friendlyAuthError({ isAxiosError: true, response: { status: 401 } }, 'fallback'),
    ).toMatch(/password/i);
  });

  it('reads a 503 as temporary', () => {
    expect(
      friendlyApiError({ isAxiosError: true, response: { status: 503 } }, 'fallback'),
    ).toMatch(/temporarily unavailable/i);
  });

  it('uses the API detail string when there is one', () => {
    expect(
      friendlyApiError(
        {
          isAxiosError: true,
          response: { status: 400, data: { detail: 'Phone number must be E.164.' } },
        },
        'fallback',
      ),
    ).toBe('Phone number must be E.164.');
  });

  it('ignores a list-shaped detail rather than rendering [object Object]', () => {
    // A Pydantic 422 makes `detail` a list of error objects.
    expect(
      friendlyApiError(
        {
          isAxiosError: true,
          response: { status: 422, data: { detail: [{ msg: 'nope' }] } },
        },
        'fallback',
      ),
    ).toBe('fallback');
  });

  it('falls back for a non-axios error', () => {
    expect(friendlyApiError(new Error('boom'), 'fallback')).toBe('fallback');
  });
});
