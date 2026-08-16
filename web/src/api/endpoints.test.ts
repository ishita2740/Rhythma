import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mock the client module rather than the network. These tests are about
// *which URL and payload* each function sends — the exact class of bug
// (#259) that type-checks, lints, builds, and then fails at runtime.
vi.mock('./client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
  setUnauthorizedHandler: vi.fn(),
  friendlyAuthError: vi.fn(),
}));

import { apiClient } from './client';
import {
  deleteAccount,
  deleteCycleLog,
  fetchCycleHistory,
  fetchCycleHistoryPage,
  fetchCycleHistoryRange,
  fetchDashboard,
  fetchObservations,
  fetchProfile,
  fetchSmsSettings,
  fetchSupportedLanguages,
  patchProfile,
  saveSmsSettings,
  sendChatMessage,
  sendSmsSummary,
  submitCycleLog,
  MAX_HISTORY_PAGE,
} from './endpoints';
import { dashboardFixture, observationsFixture } from '../test/utils';

const mockClient = apiClient as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  patch: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('dashboard', () => {
  it('GETs /dashboard and unwraps the body', async () => {
    mockClient.get.mockResolvedValue({ data: dashboardFixture() });

    const data = await fetchDashboard();

    expect(mockClient.get).toHaveBeenCalledWith('/dashboard');
    expect(data.user.name).toBe('Asha');
  });

  it('propagates a failure rather than returning a partial object', async () => {
    mockClient.get.mockRejectedValue(new Error('500'));
    await expect(fetchDashboard()).rejects.toThrow();
  });
});

describe('cycle tracking', () => {
  it('POSTs a log to /cycle/log with the payload untouched', async () => {
    mockClient.post.mockResolvedValue({ data: { id: 'log-1', message: 'ok' } });
    const log = { start_date: '2026-05-01', flow_intensity: 'light' };

    await submitCycleLog(log);

    expect(mockClient.post).toHaveBeenCalledWith('/cycle/log', log);
  });

  it('GETs history for a user id with the limit as a query param', async () => {
    mockClient.get.mockResolvedValue({ data: { message: 'ok', entries: [] } });

    await fetchCycleHistory('user-1', 30);

    expect(mockClient.get).toHaveBeenCalledWith('/cycle/user-1/history', {
      params: { limit: 30 },
    });
  });

  it('defaults the history limit to 90 days', async () => {
    mockClient.get.mockResolvedValue({ data: { message: 'ok', entries: [] } });

    await fetchCycleHistory('user-1');

    expect(mockClient.get).toHaveBeenCalledWith('/cycle/user-1/history', {
      params: { limit: 90 },
    });
  });

  it('returns the entries array, not the envelope', async () => {
    mockClient.get.mockResolvedValue({
      data: { message: 'ok', entries: [{ id: 'a', start_date: '2026-05-01' }] },
    });

    await expect(fetchCycleHistory('user-1')).resolves.toHaveLength(1);
  });

  it('DELETEs a log by id', async () => {
    mockClient.delete.mockResolvedValue({ data: {} });

    await deleteCycleLog('log-42');

    expect(mockClient.delete).toHaveBeenCalledWith('/cycle/log-42');
  });
});

// The server bounds `limit` at 100 (`MAX_HISTORY_PAGE` in
// backend/api/cycle.py) and answers 422 above it — not a truncated page, a
// refused request. The Cycle page asked for 365 and rendered an empty
// calendar for every user as a result (#349).
describe('cycle history paging', () => {
  function pageResponse(entries: unknown[], page: Record<string, unknown> = {}) {
    return {
      data: {
        message: 'ok',
        entries,
        page: {
          limit: 100,
          offset: 0,
          count: entries.length,
          hasMore: false,
          nextOffset: null,
          ...page,
        },
      },
    };
  }

  it('never asks for more than the server accepts', async () => {
    mockClient.get.mockResolvedValue(pageResponse([]));

    await fetchCycleHistoryPage('user-1', { limit: 365 });

    expect(mockClient.get.mock.calls[0][1].params.limit).toBe(MAX_HISTORY_PAGE);
  });

  it('clamps a zero or negative limit up to a real page', async () => {
    mockClient.get.mockResolvedValue(pageResponse([]));

    await fetchCycleHistoryPage('user-1', { limit: 0 });

    expect(mockClient.get.mock.calls[0][1].params.limit).toBeGreaterThanOrEqual(1);
  });

  it('keeps the legacy helper inside the ceiling too', async () => {
    // `fetchCycleHistory(id, 365)` was the exact call that broke.
    mockClient.get.mockResolvedValue(pageResponse([]));

    await fetchCycleHistory('user-1', 365);

    expect(mockClient.get.mock.calls[0][1].params.limit).toBe(MAX_HISTORY_PAGE);
  });

  it('returns the page object rather than discarding it', async () => {
    mockClient.get.mockResolvedValue(
      pageResponse([{ id: 'a' }], { hasMore: true, nextOffset: 100 }),
    );

    const result = await fetchCycleHistoryPage('user-1');

    expect(result.page.hasMore).toBe(true);
    expect(result.page.nextOffset).toBe(100);
  });

  it('sends a date window as start_date and end_date', async () => {
    mockClient.get.mockResolvedValue(pageResponse([]));

    await fetchCycleHistoryPage('user-1', {
      startDate: '2026-05-01',
      endDate: '2026-05-31',
    });

    expect(mockClient.get.mock.calls[0][1].params).toMatchObject({
      start_date: '2026-05-01',
      end_date: '2026-05-31',
    });
  });

  it('omits offset when there is nothing to skip', async () => {
    mockClient.get.mockResolvedValue(pageResponse([]));

    await fetchCycleHistoryPage('user-1', { offset: 0 });

    expect(mockClient.get.mock.calls[0][1].params).not.toHaveProperty('offset');
  });

  it('follows nextOffset until the server says there is no more', async () => {
    mockClient.get
      .mockResolvedValueOnce(
        pageResponse([{ id: 'a' }], { hasMore: true, nextOffset: 100 }),
      )
      .mockResolvedValueOnce(
        pageResponse([{ id: 'b' }], { offset: 100, hasMore: true, nextOffset: 200 }),
      )
      .mockResolvedValueOnce(pageResponse([{ id: 'c' }], { offset: 200 }));

    const entries = await fetchCycleHistoryRange('user-1', '2026-01-01', '2026-12-31');

    expect(entries.map((entry) => entry.id)).toEqual(['a', 'b', 'c']);
    expect(mockClient.get).toHaveBeenCalledTimes(3);
  });

  it('stops rather than spinning when hasMore never goes false', async () => {
    // A server bug must not become an infinite client loop.
    mockClient.get.mockResolvedValue(
      pageResponse([{ id: 'x' }], { hasMore: true, nextOffset: 100 }),
    );

    await fetchCycleHistoryRange('user-1', '2026-01-01', '2026-12-31');

    expect(mockClient.get.mock.calls.length).toBeLessThanOrEqual(10);
  });

  it('stops when the offset stops advancing', async () => {
    // `hasMore: true` with an unchanged `nextOffset` would otherwise
    // re-fetch the same page until the ceiling.
    mockClient.get.mockResolvedValue(
      pageResponse([{ id: 'x' }], { offset: 0, hasMore: true, nextOffset: 0 }),
    );

    const entries = await fetchCycleHistoryRange('user-1', '2026-01-01', '2026-12-31');

    expect(mockClient.get).toHaveBeenCalledTimes(1);
    expect(entries).toHaveLength(1);
  });

  it('survives a response with no page object', async () => {
    mockClient.get.mockResolvedValue({ data: { message: 'ok', entries: [{ id: 'a' }] } });

    await expect(
      fetchCycleHistoryRange('user-1', '2026-01-01', '2026-12-31'),
    ).resolves.toHaveLength(1);
  });

  it('propagates a failure rather than returning a partial range', async () => {
    // The page needs to be able to tell "no logs" from "could not load".
    mockClient.get.mockRejectedValue(new Error('422'));

    await expect(
      fetchCycleHistoryRange('user-1', '2026-01-01', '2026-12-31'),
    ).rejects.toThrow();
  });
});

describe('assistant', () => {
  it('POSTs message, language and history to /assistant/chat', async () => {
    mockClient.post.mockResolvedValue({
      data: { response: 'hi', language: 'en', disclaimer: 'not medical advice' },
    });
    const history = [{ role: 'user' as const, content: 'hello' }];

    await sendChatMessage('hello', 'hi', history);

    expect(mockClient.post).toHaveBeenCalledWith('/assistant/chat', {
      message: 'hello',
      language: 'hi',
      history,
    });
  });

  it('GETs the supported language list', async () => {
    mockClient.get.mockResolvedValue({ data: [{ code: 'en', name: 'English' }] });

    await fetchSupportedLanguages();

    expect(mockClient.get).toHaveBeenCalledWith('/assistant/languages');
  });
});

describe('sms', () => {
  it('GETs settings', async () => {
    mockClient.get.mockResolvedValue({ data: { phoneNumber: '+91', enabled: true } });

    await expect(fetchSmsSettings()).resolves.toEqual({
      phoneNumber: '+91',
      enabled: true,
    });
    expect(mockClient.get).toHaveBeenCalledWith('/sms/settings');
  });

  it('treats a 404 as "never configured" rather than an error', async () => {
    // A first-run user has no settings document; surfacing that as an
    // error would show a red banner on a perfectly normal screen.
    mockClient.get.mockRejectedValue({ response: { status: 404 } });

    await expect(fetchSmsSettings()).resolves.toEqual({
      phoneNumber: '',
      enabled: false,
    });
  });

  it('still throws on a non-404 failure', async () => {
    mockClient.get.mockRejectedValue({ response: { status: 500 } });
    await expect(fetchSmsSettings()).rejects.toBeDefined();
  });

  it('still throws when the request never reached the server', async () => {
    mockClient.get.mockRejectedValue(new Error('network'));
    await expect(fetchSmsSettings()).rejects.toBeDefined();
  });

  it('POSTs settings', async () => {
    const settings = { phoneNumber: '+919876543210', enabled: true };
    mockClient.post.mockResolvedValue({ data: settings });

    await saveSmsSettings(settings);

    expect(mockClient.post).toHaveBeenCalledWith('/sms/settings', settings);
  });

  it('POSTs a summary with snake_case keys the backend expects', async () => {
    // The SMSRequest model uses phone_number; sending phoneNumber here
    // would 422 at runtime while type-checking cleanly.
    mockClient.post.mockResolvedValue({ data: { message: 'ok', sid: 'SM1' } });

    await sendSmsSummary('+919876543210', 'Your cycle summary');

    expect(mockClient.post).toHaveBeenCalledWith('/sms/send-summary', {
      phone_number: '+919876543210',
      message: 'Your cycle summary',
    });
  });
});

describe('profile', () => {
  it('GETs /auth/profile', async () => {
    mockClient.get.mockResolvedValue({ data: { id: 'u1' } });

    await fetchProfile();

    expect(mockClient.get).toHaveBeenCalledWith('/auth/profile');
  });

  it('PATCHes /auth/profile with only the changed fields', async () => {
    // PATCH semantics matter: the backend writes only non-None fields, so
    // sending a full object with nulls would clobber unrelated data.
    mockClient.patch.mockResolvedValue({ data: { id: 'u1', age: 30 } });

    await patchProfile({ age: 30 });

    expect(mockClient.patch).toHaveBeenCalledWith('/auth/profile', { age: 30 });
  });

  it('DELETEs /auth/me to close the account', async () => {
    mockClient.delete.mockResolvedValue({ data: {} });

    await deleteAccount();

    expect(mockClient.delete).toHaveBeenCalledWith('/auth/me');
  });
});

describe('insights observations', () => {
  it('GETs /insights/{userId}/observations and unwraps the body', async () => {
    mockClient.get.mockResolvedValue({ data: observationsFixture() });

    const data = await fetchObservations('user-1');

    expect(mockClient.get).toHaveBeenCalledWith('/insights/user-1/observations');
    expect(data.cycleConsistency).toBe('slightly_variable');
    expect(data.observations).toHaveLength(2);
  });

  it('propagates a failure rather than returning a partial object', async () => {
    mockClient.get.mockRejectedValue(new Error('500'));
    await expect(fetchObservations('user-1')).rejects.toThrow();
  });
});

describe('endpoint paths as a contract', () => {
  it('never calls a path outside the routers the backend registers', async () => {
    // main.py mounts auth, health, assistant, cycle, insights, sms and the
    // dashboard. A call to anything else is a client/server mismatch, which
    // is exactly how the /auth/token bug shipped.
    const mounted = [
      '/auth',
      '/health',
      '/assistant',
      '/cycle',
      '/insights',
      '/sms',
      '/dashboard',
    ];

    mockClient.get.mockResolvedValue({ data: dashboardFixture() });
    mockClient.post.mockResolvedValue({ data: {} });
    mockClient.patch.mockResolvedValue({ data: {} });
    mockClient.delete.mockResolvedValue({ data: {} });

    await fetchDashboard();
    await fetchCycleHistory('u1');
    await fetchProfile();
    await fetchSupportedLanguages();
    await submitCycleLog({ start_date: '2026-05-01' });
    await deleteCycleLog('log-1');
    await deleteAccount();

    const calledPaths = [
      ...mockClient.get.mock.calls,
      ...mockClient.post.mock.calls,
      ...mockClient.patch.mock.calls,
      ...mockClient.delete.mock.calls,
    ].map((call) => String(call[0]));

    expect(calledPaths.length).toBeGreaterThan(0);
    for (const path of calledPaths) {
      expect(
        mounted.some((prefix) => path.startsWith(prefix)),
        `${path} is not under a router the backend mounts`,
      ).toBe(true);
    }
  });
});
