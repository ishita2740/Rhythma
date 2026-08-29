import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// The Sharing screen is where a patient learns what sharing actually
// means. Before #350 it could only say who *had* permission; it now says
// who used it. These tests are mostly about the difference between "no
// views", "never viewed" and "the server didn't say" — three states that
// are easy to collapse into one and mean very different things to a user.
vi.mock('../api/endpoints', () => ({
  fetchConsents: vi.fn(),
  fetchAccessLog: vi.fn(),
  grantConsent: vi.fn(),
  revokeConsent: vi.fn(),
}));

import { fetchAccessLog, fetchConsents } from '../api/endpoints';
import { SharingPage } from './SharingPage';
import { renderWithProviders } from '../test/utils';

const mockConsents = fetchConsents as unknown as ReturnType<typeof vi.fn>;
const mockAccessLog = fetchAccessLog as unknown as ReturnType<typeof vi.fn>;

function consentFixture(overrides: Record<string, unknown> = {}) {
  return {
    id: 'consent-1',
    patient_id: 'patient-1',
    provider_id: 'provider-1',
    provider_email: 'dr.rao@clinic.in',
    provider_name: 'Dr. Priya Rao',
    status: 'active' as const,
    created_at: '2026-03-12T09:00:00Z',
    viewCount: 0,
    lastAccessedAt: null,
    ...overrides,
  };
}

function accessEntry(overrides: Record<string, unknown> = {}) {
  return {
    id: 'access-1',
    providerId: 'provider-1',
    providerName: 'Dr. Priya Rao',
    view: 'patient_detail' as const,
    consentId: 'consent-1',
    accessedAt: '2026-08-02T11:30:00Z',
    ...overrides,
  };
}

function emptyPage() {
  return {
    entries: [],
    page: { limit: 20, offset: 0, count: 0, hasMore: false, nextOffset: null },
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockConsents.mockResolvedValue([]);
  mockAccessLog.mockResolvedValue(emptyPage());
});

describe('access history', () => {
  it('lists who opened the record and when', async () => {
    mockAccessLog.mockResolvedValue({
      ...emptyPage(),
      entries: [accessEntry()],
    });

    renderWithProviders(<SharingPage />);

    expect(await screen.findByText(/Opened your full record/i)).toBeInTheDocument();
  });

  it('distinguishes a summary card from the full record', async () => {
    mockAccessLog.mockResolvedValue({
      ...emptyPage(),
      entries: [accessEntry({ view: 'patient_list' })],
    });

    renderWithProviders(<SharingPage />);

    expect(await screen.findByText(/Saw your summary card/i)).toBeInTheDocument();
  });

  it('says so plainly when nobody has looked', async () => {
    renderWithProviders(<SharingPage />);

    expect(
      await screen.findByText(/No provider has viewed your data yet/i),
    ).toBeInTheDocument();
  });

  it('names a provider who has since closed their account', async () => {
    mockAccessLog.mockResolvedValue({
      ...emptyPage(),
      entries: [accessEntry({ providerName: null })],
    });

    renderWithProviders(<SharingPage />);

    expect(await screen.findByText(/closed their account/i)).toBeInTheDocument();
  });
});

describe('consent rows carry usage', () => {
  it('shows a view count and a last-viewed date', async () => {
    mockConsents.mockResolvedValue([
      consentFixture({ viewCount: 4, lastAccessedAt: '2026-08-02T11:30:00Z' }),
    ]);

    renderWithProviders(<SharingPage />);

    expect(await screen.findByText(/Viewed 4 times/i)).toBeInTheDocument();
  });

  it('distinguishes "granted but never used" from silence', async () => {
    mockConsents.mockResolvedValue([consentFixture({ viewCount: 0 })]);

    renderWithProviders(<SharingPage />);

    expect(await screen.findByText(/Has not viewed your data yet/i)).toBeInTheDocument();
  });

  it('says nothing at all when the server omitted the field', async () => {
    // An older backend, or a client cached across a deploy. Rendering
    // "never viewed" here would be a claim this client cannot support.
    const consent = consentFixture();
    delete (consent as Record<string, unknown>).viewCount;
    delete (consent as Record<string, unknown>).lastAccessedAt;
    mockConsents.mockResolvedValue([consent]);

    renderWithProviders(<SharingPage />);

    await screen.findByText('Dr. Priya Rao');
    expect(screen.queryByText(/Has not viewed your data yet/i)).toBeNull();
    // Scoped to the per-consent summary — a bare /Viewed/i also matches
    // the access-history section heading further down the page.
    expect(screen.queryByText(/Viewed \d+ times/i)).toBeNull();
  });

  it('keeps the history visible on a revoked consent', async () => {
    // The point of revoking is knowing what was read while it was live.
    mockConsents.mockResolvedValue([
      consentFixture({ status: 'revoked', viewCount: 2 }),
    ]);

    renderWithProviders(<SharingPage />);

    expect(await screen.findByText(/Viewed 2 times/i)).toBeInTheDocument();
  });
});

describe('access log paging (#540)', () => {
  // The list stopped at the first twenty rows with nothing on screen to
  // say so. It is newest-first, so what fell off the end was the *oldest*
  // history — and "has anyone been looking at my records, and since when"
  // is the question this screen exists to answer. An unmarked window reads
  // as a complete one.
  //
  // The consent list directly above it already walks its pages to the end,
  // and the provider dashboard already renders a "Load more". Only this
  // list stopped silently.

  function page(entries: ReturnType<typeof accessEntry>[], overrides = {}) {
    return {
      entries,
      page: {
        limit: 20,
        offset: 0,
        count: entries.length,
        hasMore: false,
        nextOffset: null,
        ...overrides,
      },
    };
  }

  function entries(from: number, to: number) {
    return Array.from({ length: to - from }, (_, i) =>
      accessEntry({ id: `access-${from + i}` }),
    );
  }

  it('offers to load more when the server says there is more', async () => {
    mockAccessLog.mockResolvedValue(
      page(entries(0, 20), { hasMore: true, nextOffset: 20 }),
    );

    renderWithProviders(<SharingPage />);

    expect(
      await screen.findByRole('button', { name: /Show earlier views/i }),
    ).toBeInTheDocument();
  });

  it('does not offer to load more when the history fits on one page', async () => {
    mockAccessLog.mockResolvedValue(page(entries(0, 3)));

    renderWithProviders(<SharingPage />);

    await screen.findAllByText(/Opened your full record/i);
    expect(screen.queryByRole('button', { name: /Show earlier views/i })).toBeNull();
  });

  it("asks for the server's nextOffset, not its own row count", async () => {
    // The two differ whenever a page comes back short. Computing the
    // offset from `entries.length` is the client-side version of the bug
    // this fixes on the server in #538.
    mockAccessLog.mockResolvedValueOnce(
      page(entries(0, 20), { hasMore: true, nextOffset: 26 }),
    );
    mockAccessLog.mockResolvedValueOnce(page(entries(20, 24)));

    renderWithProviders(<SharingPage />);

    const button = await screen.findByRole('button', { name: /Show earlier views/i });
    await userEvent.click(button);

    await waitFor(() => {
      expect(mockAccessLog).toHaveBeenLastCalledWith(20, 26);
    });
  });

  it('appends the next page rather than replacing what is shown', async () => {
    mockAccessLog.mockResolvedValueOnce(
      page(entries(0, 20), { hasMore: true, nextOffset: 20 }),
    );
    mockAccessLog.mockResolvedValueOnce(page(entries(20, 25)));

    renderWithProviders(<SharingPage />);

    await userEvent.click(
      await screen.findByRole('button', { name: /Show earlier views/i }),
    );

    await waitFor(() => {
      expect(screen.getAllByText(/Opened your full record/i)).toHaveLength(25);
    });
  });

  it('drops the button once the last page has arrived', async () => {
    mockAccessLog.mockResolvedValueOnce(
      page(entries(0, 20), { hasMore: true, nextOffset: 20 }),
    );
    mockAccessLog.mockResolvedValueOnce(page(entries(20, 22)));

    renderWithProviders(<SharingPage />);

    await userEvent.click(
      await screen.findByRole('button', { name: /Show earlier views/i }),
    );

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Show earlier views/i })).toBeNull();
    });
  });

  it('says how many are shown while more remain, and stops once they do not', async () => {
    mockAccessLog.mockResolvedValueOnce(
      page(entries(0, 20), { hasMore: true, nextOffset: 20 }),
    );
    mockAccessLog.mockResolvedValueOnce(page(entries(20, 22)));

    renderWithProviders(<SharingPage />);

    expect(await screen.findByText(/Showing the 20 most recent views/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Show earlier views/i }));

    await waitFor(() => {
      expect(screen.queryByText(/most recent views/i)).toBeNull();
    });
  });

  it('keeps the entries already loaded when loading more fails', async () => {
    // A patient who can see twenty rows and cannot fetch the twenty-first
    // should keep her twenty. Clearing the list on a failed "load more"
    // would take away history she was already reading.
    mockAccessLog.mockResolvedValueOnce(
      page(entries(0, 20), { hasMore: true, nextOffset: 20 }),
    );
    mockAccessLog.mockRejectedValueOnce(new Error('500'));

    renderWithProviders(<SharingPage />);

    await userEvent.click(
      await screen.findByRole('button', { name: /Show earlier views/i }),
    );

    expect(await screen.findByText(/Couldn't load earlier views/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Opened your full record/i)).toHaveLength(20);
  });

  it('leaves the consent list alone when loading more fails', async () => {
    // The existing guarantee, re-asserted against the new code path:
    // revoking is the more urgent of the two actions and must survive any
    // access-log failure.
    mockConsents.mockResolvedValue([consentFixture()]);
    mockAccessLog.mockResolvedValueOnce(
      page(entries(0, 20), { hasMore: true, nextOffset: 20 }),
    );
    mockAccessLog.mockRejectedValueOnce(new Error('500'));

    renderWithProviders(<SharingPage />);

    await userEvent.click(
      await screen.findByRole('button', { name: /Show earlier views/i }),
    );

    await screen.findByText(/Couldn't load earlier views/i);
    // The provider's email is unique to the consent row; her name also
    // appears on every access-log entry below it.
    expect(screen.getByText('dr.rao@clinic.in')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Revoke access/i }),
    ).toBeInTheDocument();
  });

  it('asks for the first page explicitly rather than relying on a default', async () => {
    mockAccessLog.mockResolvedValue(page(entries(0, 2)));

    renderWithProviders(<SharingPage />);

    await waitFor(() => {
      expect(mockAccessLog).toHaveBeenCalledWith(20, 0);
    });
  });
});

describe('failure handling', () => {
  it('still shows consents when the access log cannot be loaded', async () => {
    // Revoking is the more urgent of the two actions, so a failed access
    // log must not take the consent list down with it.
    mockConsents.mockResolvedValue([consentFixture()]);
    mockAccessLog.mockRejectedValue(new Error('500'));

    renderWithProviders(<SharingPage />);

    expect(await screen.findByText('Dr. Priya Rao')).toBeInTheDocument();
  });

  it('reports an error when the consents themselves fail', async () => {
    mockConsents.mockRejectedValue(new Error('500'));

    const { container } = renderWithProviders(<SharingPage />);

    await waitFor(() => {
      expect(container.querySelector('.error-text')).not.toBeNull();
    });
  });
});
