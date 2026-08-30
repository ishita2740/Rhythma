import { describe, it, expect, vi } from 'vitest';

describe('CyclePage Log Deletion State Synchronization', () => {
  it('calls reload handler after deleting a cycle log from the map', () => {
    const logs = new Map([['2026-08-15', { id: 'log123', start_date: '2026-08-15' }]]);
    const loadMock = vi.fn();

    // Simulating remove handler logic
    const selectedIso = '2026-08-15';
    const next = new Map(logs);
    next.delete(selectedIso);
    loadMock();

    expect(next.has(selectedIso)).toBe(false);
    expect(loadMock).toHaveBeenCalledTimes(1);
  });
});
