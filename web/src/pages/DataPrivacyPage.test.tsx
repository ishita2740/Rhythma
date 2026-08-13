import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// The bug this screen exists for is not "there is no export button". It
// is that the previous Delete flow logged the user out whether or not the
// deletion succeeded, so a failure was indistinguishable from a success —
// she would believe her health records were gone when they were not.
// `does not sign the user out when the deletion fails` is the test that
// matters most here; the rest describe the surface around it.
vi.mock('../api/endpoints', () => ({
  fetchDataSummary: vi.fn(),
  fetchDataExport: vi.fn(),
  requestAccountDeletion: vi.fn(),
  confirmAccountDeletion: vi.fn(),
}));

const logout = vi.fn();
const navigate = vi.fn();

vi.mock('../auth/useAuth', () => ({
  useAuth: () => ({ user: { id: 'u1', username: 'asha' }, loading: false, logout }),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => navigate };
});

import {
  confirmAccountDeletion,
  fetchDataExport,
  fetchDataSummary,
  requestAccountDeletion,
} from '../api/endpoints';
import { DataPrivacyPage } from './DataPrivacyPage';
import { renderWithProviders } from '../test/utils';
import { axiosError } from '../test/utils';

const mockSummary = fetchDataSummary as unknown as ReturnType<typeof vi.fn>;
const mockExport = fetchDataExport as unknown as ReturnType<typeof vi.fn>;
const mockRequestDeletion = requestAccountDeletion as unknown as ReturnType<typeof vi.fn>;
const mockConfirmDeletion = confirmAccountDeletion as unknown as ReturnType<typeof vi.fn>;

function summaryFixture(overrides: Record<string, unknown> = {}) {
  return {
    userId: 'u1',
    generatedAt: '2026-08-10T09:00:00Z',
    categories: [
      {
        key: 'cycle_logs',
        label: 'Cycle logs, symptoms and notes',
        recordCount: 34,
        storedFields: ['start_date', 'end_date', 'symptoms', 'notes'],
        collection: 'cycle_logs',
        earliestEntry: '2024-01-04',
        latestEntry: '2026-07-29',
        retentionNote: 'Kept until you delete your account or the individual log.',
      },
      {
        key: 'assistant_conversation',
        label: 'AI assistant conversation',
        recordCount: 12,
        storedFields: ['role', 'content'],
        collection: 'conversations',
        retentionNote: 'A rolling window of your most recent messages.',
      },
      {
        key: 'rate_limits',
        label: 'Abuse-prevention counters',
        recordCount: 0,
        storedFields: [],
        collection: 'rate_limits',
        retentionNote: 'Short-lived request timestamps, no health data.',
      },
    ],
    totalRecords: 46,
    ...overrides,
  };
}

function previewFixture(overrides: Record<string, unknown> = {}) {
  return {
    confirmationToken: 'token-abc',
    expiresInSeconds: 300,
    impact: summaryFixture(),
    warning:
      'This permanently deletes your cycle logs, symptoms, notes, profile and assistant conversation. It cannot be undone.',
    ...overrides,
  };
}

/** Get to the confirmation step, which every deletion test needs. */
async function openConfirmation(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: /delete my account/i }));
  await screen.findByRole('button', { name: /delete everything/i });
}

beforeEach(() => {
  vi.clearAllMocks();
  mockSummary.mockResolvedValue(summaryFixture());
  mockRequestDeletion.mockResolvedValue(previewFixture());
  mockConfirmDeletion.mockResolvedValue({
    status: 'success',
    deletedCounts: { cycle_logs: 34 },
    totalDeleted: 46,
    deletedAt: '2026-08-10T09:05:00Z',
    message: 'Your account and all associated data have been deleted.',
  });
});

describe('the inventory', () => {
  it('lists every category with its record count', async () => {
    renderWithProviders(<DataPrivacyPage />);

    expect(await screen.findByText('Cycle logs, symptoms and notes')).toBeInTheDocument();
    expect(screen.getByText('34')).toBeInTheDocument();
    expect(screen.getByText('AI assistant conversation')).toBeInTheDocument();
  });

  it('shows the date range of logged entries', async () => {
    renderWithProviders(<DataPrivacyPage />);

    expect(await screen.findByText(/From .* to .*/)).toBeInTheDocument();
  });

  it('names the stored fields rather than their values', async () => {
    renderWithProviders(<DataPrivacyPage />);

    expect(await screen.findByText(/start_date/)).toBeInTheDocument();
  });

  it('offers a retry when the summary cannot be loaded', async () => {
    mockSummary.mockRejectedValueOnce(axiosError());
    renderWithProviders(<DataPrivacyPage />);

    const retry = await screen.findByRole('button', { name: /retry/i });
    mockSummary.mockResolvedValueOnce(summaryFixture());
    await userEvent.setup().click(retry);

    expect(await screen.findByText('AI assistant conversation')).toBeInTheDocument();
  });
});

describe('export', () => {
  it('downloads the JSON bundle under the name the server chose', async () => {
    const createObjectURL = vi.fn(() => 'blob:fake');
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });
    mockExport.mockResolvedValue({
      blob: new Blob(['{}'], { type: 'application/json' }),
      filename: 'rhythma-data-export-2026-08-10.json',
    });

    renderWithProviders(<DataPrivacyPage />);
    await screen.findByText('Cycle logs, symptoms and notes');
    await userEvent.setup().click(screen.getByRole('button', { name: /download json/i }));

    await waitFor(() => expect(mockExport).toHaveBeenCalledWith('json'));
    expect(
      await screen.findByText(/rhythma-data-export-2026-08-10\.json/),
    ).toBeInTheDocument();
    // Not revoking would keep the whole export in memory for the life of
    // the tab, which on a long history is not a small amount.
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:fake');

    vi.unstubAllGlobals();
  });

  it('asks for CSV when the CSV button is used', async () => {
    vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn(() => 'blob:x'), revokeObjectURL: vi.fn() });
    mockExport.mockResolvedValue({ blob: new Blob(['a,b']), filename: 'logs.csv' });

    renderWithProviders(<DataPrivacyPage />);
    await screen.findByText('Cycle logs, symptoms and notes');
    await userEvent.setup().click(screen.getByRole('button', { name: /download csv/i }));

    await waitFor(() => expect(mockExport).toHaveBeenCalledWith('csv'));

    vi.unstubAllGlobals();
  });

  it('reports a failed download instead of silently doing nothing', async () => {
    mockExport.mockRejectedValue(axiosError(500));

    renderWithProviders(<DataPrivacyPage />);
    await screen.findByText('Cycle logs, symptoms and notes');
    await userEvent.setup().click(screen.getByRole('button', { name: /download json/i }));

    expect(await screen.findByText(/could not be prepared/i)).toBeInTheDocument();
  });
});

describe('deletion', () => {
  it('does not delete anything on the first click', async () => {
    renderWithProviders(<DataPrivacyPage />);
    await screen.findByText('Cycle logs, symptoms and notes');

    await openConfirmation(userEvent.setup());

    expect(mockRequestDeletion).toHaveBeenCalledTimes(1);
    expect(mockConfirmDeletion).not.toHaveBeenCalled();
  });

  it("shows the server's warning and what will be destroyed", async () => {
    renderWithProviders(<DataPrivacyPage />);
    await screen.findByText('Cycle logs, symptoms and notes');

    await openConfirmation(userEvent.setup());

    expect(screen.getByText(/It cannot be undone/i)).toBeInTheDocument();
    expect(screen.getByText(/34 × Cycle logs/)).toBeInTheDocument();
  });

  it('leaves out categories with nothing in them', async () => {
    renderWithProviders(<DataPrivacyPage />);
    await screen.findByText('Cycle logs, symptoms and notes');

    await openConfirmation(userEvent.setup());

    expect(screen.queryByText(/0 × Abuse-prevention/)).not.toBeInTheDocument();
  });

  it('keeps the confirm button disabled until the word is typed', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DataPrivacyPage />);
    await screen.findByText('Cycle logs, symptoms and notes');
    await openConfirmation(user);

    const confirm = screen.getByRole('button', { name: /delete everything/i });
    expect(confirm).toBeDisabled();

    await user.type(screen.getByRole('textbox'), 'DELETE');

    expect(confirm).toBeEnabled();
  });

  it('does not arm on a near miss', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DataPrivacyPage />);
    await screen.findByText('Cycle logs, symptoms and notes');
    await openConfirmation(user);

    await user.type(screen.getByRole('textbox'), 'DELET');

    expect(screen.getByRole('button', { name: /delete everything/i })).toBeDisabled();
  });

  it('sends the confirmation token the preview returned', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DataPrivacyPage />);
    await screen.findByText('Cycle logs, symptoms and notes');
    await openConfirmation(user);
    await user.type(screen.getByRole('textbox'), 'DELETE');

    await user.click(screen.getByRole('button', { name: /delete everything/i }));

    await waitFor(() => expect(mockConfirmDeletion).toHaveBeenCalledWith('token-abc'));
  });

  it('signs the user out once the deletion succeeds', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DataPrivacyPage />);
    await screen.findByText('Cycle logs, symptoms and notes');
    await openConfirmation(user);
    await user.type(screen.getByRole('textbox'), 'DELETE');

    await user.click(screen.getByRole('button', { name: /delete everything/i }));

    await waitFor(() => expect(logout).toHaveBeenCalled());
  });

  it('does not sign the user out when the deletion fails', async () => {
    // The whole point. Signing her out here would put her on the login
    // page — the same screen a successful deletion produces — so she
    // would have no way to know her records are still there.
    mockConfirmDeletion.mockRejectedValue(axiosError(500, 'Deletion failed.'));
    const user = userEvent.setup();
    renderWithProviders(<DataPrivacyPage />);
    await screen.findByText('Cycle logs, symptoms and notes');
    await openConfirmation(user);
    await user.type(screen.getByRole('textbox'), 'DELETE');

    await user.click(screen.getByRole('button', { name: /delete everything/i }));

    expect(await screen.findByText('Deletion failed.')).toBeInTheDocument();
    expect(logout).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
  });

  it('stays on the page when the preview itself fails', async () => {
    mockRequestDeletion.mockRejectedValue(axiosError(503));
    const user = userEvent.setup();
    renderWithProviders(<DataPrivacyPage />);
    await screen.findByText('Cycle logs, symptoms and notes');

    await user.click(screen.getByRole('button', { name: /delete my account/i }));

    expect(await screen.findByText(/Nothing has been removed/i)).toBeInTheDocument();
    expect(mockConfirmDeletion).not.toHaveBeenCalled();
  });

  it('can be cancelled, and forgets what was typed', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DataPrivacyPage />);
    await screen.findByText('Cycle logs, symptoms and notes');
    await openConfirmation(user);
    await user.type(screen.getByRole('textbox'), 'DELETE');

    await user.click(screen.getByRole('button', { name: /cancel/i }));
    await openConfirmation(user);

    expect(screen.getByRole('textbox')).toHaveValue('');
    expect(screen.getByRole('button', { name: /delete everything/i })).toBeDisabled();
  });
});
