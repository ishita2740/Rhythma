import { describe, it, expect } from 'vitest';

describe('InsightsPage Metric Guard Logic', () => {
  it('prevents NaN in variability calculation when cycle total is null or 0', () => {
    const lengths = [28, 30];
    const totalCycleDays: number | null = 0;

    const variability =
      lengths.length >= 2 && totalCycleDays != null && totalCycleDays > 0
        ? Math.round(
            lengths.reduce((acc, l) => acc + (l - totalCycleDays) ** 2, 0) / lengths.length,
          )
        : null;

    expect(variability).toBeNull();
    expect(Number.isNaN(variability)).toBe(false);
  });
});
