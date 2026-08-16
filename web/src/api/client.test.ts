import { afterEach, describe, expect, it, vi } from 'vitest';
import axios from 'axios';
import { apiClient, friendlyAuthError, setUnauthorizedHandler } from './client';
import { axiosError } from '../test/utils';

// Mock axios so the refresh helper does not hit the network.
vi.mock('axios', async (importOriginal) => {
  const actual = await importOriginal<typeof import('axios')>();
  return {
    ...actual,
    default: {
      ...actual.default,
      post: vi.fn(),
    },
  };
});

const mockedAxiosPost = vi.mocked(axios.post);

describe('apiClient configuration', () => {
  it('sends cookies with every request', () => {
    expect(apiClient.defaults.withCredentials).toBe(true);
  });

  it('identifies itself as the web client', () => {
    expect(apiClient.defaults.headers['X-Client-Platform']).toBe('web');
  });

  it('points at the /api/v1 prefix the backend mounts its routers under', () => {
    expect(apiClient.defaults.baseURL).toMatch(/\/api\/v1$/);
  });
});

describe('401 interceptor — auto-refresh', () => {
  afterEach(() => {
    setUnauthorizedHandler(() => {});
    vi.clearAllMocks();
  });

  async function runResponseInterceptor(error: unknown) {
    const handlers = (
      apiClient.interceptors.response as unknown as {
        handlers: { rejected: (e: unknown) => Promise<unknown> }[];
      }
    ).handlers.filter(Boolean);
    const rejected = handlers[handlers.length - 1].rejected;
    return rejected(error).catch((e: unknown) => e);
  }

  it('calls the unauthorized handler on a 401 for public endpoints', async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);

    await runResponseInterceptor({
      response: { status: 401 },
      config: { url: '/auth/login' },
    });

    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('refreshes token and retries on 401 for protected endpoints', async () => {
    mockedAxiosPost.mockResolvedValueOnce({ status: 200 });

    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);

    const error = {
      response: { status: 401 },
      config: { url: '/dashboard', headers: {} },
    };

    // The interceptor retries through `apiClient.request`, which is what
    // this spy stands in for. It had been failing with "expected 1, got 0":
    // the source called `apiClient(retryConfig)`, and an axios instance is
    // a *bound* `request` function, so invoking it never touches the
    // `request` property the spy replaced.
    const apiSpy = vi.spyOn(apiClient, 'request').mockResolvedValueOnce({
      data: { user: { name: 'Asha' } },
      status: 200,
      statusText: 'OK',
      headers: {},
      config: error.config,
    });

    await runResponseInterceptor(error);

    expect(mockedAxiosPost).toHaveBeenCalledTimes(1);
    expect(mockedAxiosPost).toHaveBeenCalledWith(
      expect.stringContaining('/auth/refresh'),
      {},
      { withCredentials: true },
    );
    expect(apiSpy).toHaveBeenCalledTimes(1);
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('marks the retry so a second 401 cannot loop', async () => {
    // The marker is what breaks the retry loop, and nothing was checking
    // it reached the retried request — the assertion above only counted
    // the call. Reading it back off the header object also confirms the
    // `AxiosHeaders` the interceptor now builds behaves like the plain
    // object the loop guard indexes into.
    mockedAxiosPost.mockResolvedValueOnce({ status: 200 });
    setUnauthorizedHandler(vi.fn());

    const error = {
      response: { status: 401 },
      config: { url: '/dashboard', headers: {} },
    };

    const apiSpy = vi.spyOn(apiClient, 'request').mockResolvedValueOnce({
      data: {},
      status: 200,
      statusText: 'OK',
      headers: {},
      config: error.config,
    });

    await runResponseInterceptor(error);

    const retried = apiSpy.mock.calls[0][0] as unknown as {
      url: string;
      headers: Record<string, unknown>;
    };
    expect(retried.headers['X-Retry-After-Refresh']).toBe('1');
    expect(retried.url).toBe('/dashboard');
  });

  it('gives up instead of retrying a request that was already retried', async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);

    const apiSpy = vi.spyOn(apiClient, 'request');

    await runResponseInterceptor({
      response: { status: 401 },
      config: {
        url: '/dashboard',
        headers: { 'X-Retry-After-Refresh': '1' },
      },
    });

    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(mockedAxiosPost).not.toHaveBeenCalled();
    expect(apiSpy).not.toHaveBeenCalled();
  });

  it('calls unauthorized handler when refresh fails', async () => {
    mockedAxiosPost.mockRejectedValueOnce(new Error('refresh failed'));

    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);

    const error = {
      response: { status: 401 },
      config: { url: '/dashboard', headers: {} },
    };

    await runResponseInterceptor(error);

    expect(mockedAxiosPost).toHaveBeenCalledTimes(1);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('does not retry a request that was already retried (infinite loop prevention)', async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);

    const error = {
      response: { status: 401 },
      config: {
        url: '/dashboard',
        headers: { 'X-Retry-After-Refresh': '1' },
      },
    };

    await runResponseInterceptor(error);

    expect(mockedAxiosPost).not.toHaveBeenCalled();
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });

  it('deduplicates concurrent refresh attempts', async () => {
    mockedAxiosPost.mockImplementation(
      () =>
        new Promise((resolve) => {
          setTimeout(() => resolve({ status: 200 }), 50);
        }),
    );

    setUnauthorizedHandler(() => {});

    const error1 = {
      response: { status: 401 },
      config: { url: '/dashboard', headers: {} },
    };
    const error2 = {
      response: { status: 401 },
      config: { url: '/profile', headers: {} },
    };

    const handlers = (
      apiClient.interceptors.response as unknown as {
        handlers: { rejected: (e: unknown) => Promise<unknown> }[];
      }
    ).handlers.filter(Boolean);
    const rejected = handlers[handlers.length - 1].rejected;

    // Fire two concurrent 401s
    const p1 = rejected(error1).catch(() => {});
    const p2 = rejected(error2).catch(() => {});

    await Promise.all([p1, p2]);

    // Only ONE refresh call despite two concurrent 401s
    expect(mockedAxiosPost).toHaveBeenCalledTimes(1);
  });

  it('does not call unauthorized for non-401 errors', async () => {
    const onUnauthorized = vi.fn();
    setUnauthorizedHandler(onUnauthorized);

    await runResponseInterceptor({ response: { status: 500 } });
    await runResponseInterceptor({ response: { status: 403 } });
    await runResponseInterceptor({ response: { status: 404 } });

    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('re-rejects so callers still see the error when refresh fails', async () => {
    mockedAxiosPost.mockRejectedValueOnce(new Error('refresh failed'));
    setUnauthorizedHandler(vi.fn());

    const original = { response: { status: 401 }, config: { url: '/dashboard', headers: {} } };
    const result = await runResponseInterceptor(original);
    expect(result).toBe(original);
  });

  it('tolerates an error with no response at all', async () => {
    setUnauthorizedHandler(vi.fn());
    await expect(
      runResponseInterceptor(new Error('network down')),
    ).resolves.toBeInstanceOf(Error);
  });
});

describe('friendlyAuthError', () => {
  it('reports an unreachable server instead of blaming credentials', () => {
    const message = friendlyAuthError(axiosError(undefined), 'fallback');
    expect(message).toMatch(/Couldn't reach the server/i);
    expect(message).not.toMatch(/invalid/i);
  });

  it('maps 401 to invalid credentials', () => {
    expect(friendlyAuthError(axiosError(401), 'fallback')).toMatch(/Invalid/i);
  });

  it('prefers the server detail on a 429', () => {
    expect(friendlyAuthError(axiosError(429, 'Wait 5 minutes.'), 'fallback')).toBe(
      'Wait 5 minutes.',
    );
  });

  it('falls back to generic copy on a 429 with no detail', () => {
    expect(friendlyAuthError(axiosError(429), 'fallback')).toMatch(/Too many attempts/i);
  });

  it('passes through a server-provided detail for other statuses', () => {
    expect(friendlyAuthError(axiosError(409, 'Email already registered'), 'fallback')).toBe(
      'Email already registered',
    );
  });

  it('uses the caller fallback for a non-axios error', () => {
    expect(friendlyAuthError(new Error('boom'), 'fallback')).toBe('fallback');
    expect(friendlyAuthError(null, 'fallback')).toBe('fallback');
    expect(friendlyAuthError('a string', 'fallback')).toBe('fallback');
  });

  it('uses the fallback when a status carries no detail', () => {
    expect(friendlyAuthError(axiosError(500), 'fallback')).toBe('fallback');
  });
});

describe('base URL configuration', () => {
  it('is always set, so a missing env var cannot produce relative requests', () => {
    expect(apiClient.defaults.baseURL).toBeTruthy();
  });

  it('has no trailing slash, so paths do not become //dashboard', () => {
    expect(apiClient.defaults.baseURL).not.toMatch(/\/$/);
  });
});
