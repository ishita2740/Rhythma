import { beforeEach, describe, expect, it, vi } from 'vitest';

// Same approach as endpoints.test.ts: mock the client, not the network,
// because what these functions get wrong is the URL, the params and the
// response type — not the transport.
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
  confirmAccountDeletion,
  exportFilename,
  fetchDataExport,
  fetchDataSummary,
  requestAccountDeletion,
} from './endpoints';

const mockClient = apiClient as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('fetchDataSummary', () => {
  it('reads the inventory endpoint', async () => {
    mockClient.get.mockResolvedValue({ data: { categories: [], totalRecords: 0 } });

    await fetchDataSummary();

    expect(mockClient.get).toHaveBeenCalledWith('/privacy/summary');
  });
});

describe('fetchDataExport', () => {
  it('asks for JSON as a blob by default', async () => {
    mockClient.get.mockResolvedValue({ data: new Blob(['{}']), headers: {} });

    await fetchDataExport();

    expect(mockClient.get).toHaveBeenCalledWith('/privacy/export', {
      params: { format: 'json' },
      responseType: 'blob',
    });
  });

  it('passes the CSV format through', async () => {
    mockClient.get.mockResolvedValue({ data: new Blob(['a,b']), headers: {} });

    await fetchDataExport('csv');

    expect(mockClient.get.mock.calls[0][1].params).toEqual({ format: 'csv' });
  });

  it("saves under the server's filename", async () => {
    mockClient.get.mockResolvedValue({
      data: new Blob(['{}']),
      headers: {
        'content-disposition': 'attachment; filename="rhythma-data-export-2026-08-10.json"',
      },
    });

    const file = await fetchDataExport();

    expect(file.filename).toBe('rhythma-data-export-2026-08-10.json');
  });
});

describe('exportFilename', () => {
  it('reads a quoted filename', () => {
    expect(exportFilename('attachment; filename="export.json"', 'json')).toBe('export.json');
  });

  it('reads an unquoted filename', () => {
    expect(exportFilename('attachment; filename=export.csv', 'csv')).toBe('export.csv');
  });

  it('decodes an RFC 5987 filename', () => {
    expect(exportFilename("attachment; filename*=UTF-8''my%20export.json", 'json')).toBe(
      'my export.json',
    );
  });

  it('falls back when a proxy stripped the header', () => {
    // A download with an ordinary name beats no download at all, which is
    // what throwing here would produce.
    expect(exportFilename(undefined, 'csv')).toBe('rhythma-data-export.csv');
    expect(exportFilename('attachment', 'json')).toBe('rhythma-data-export.json');
  });
});

describe('deletion', () => {
  it('previews with an empty body, so nothing is destroyed', async () => {
    mockClient.post.mockResolvedValue({ data: { confirmationToken: 't' } });

    await requestAccountDeletion();

    expect(mockClient.post).toHaveBeenCalledWith('/privacy/delete-account', {});
  });

  it('confirms with the token the preview returned', async () => {
    mockClient.post.mockResolvedValue({ data: { status: 'success' } });

    await confirmAccountDeletion('token-abc');

    expect(mockClient.post).toHaveBeenCalledWith('/privacy/delete-account', {
      confirmationToken: 'token-abc',
    });
  });

  it('uses the privacy route rather than the legacy one', async () => {
    // `DELETE /auth/me` still exists and still deletes; it just does not
    // preview, does not report counts, and is what Settings used to call.
    mockClient.post.mockResolvedValue({ data: {} });

    await requestAccountDeletion();

    expect(String(mockClient.post.mock.calls[0][0])).toBe('/privacy/delete-account');
  });
});
