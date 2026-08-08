import { describe, it, expect } from 'vitest';
import kn from '../locales/kn.json';
import ml from '../locales/ml.json';

describe('Kannada and Malayalam Locale QA & Rendering Checks', () => {
  it('loads Kannada locale keys correctly without empty values', () => {
    expect(kn).toBeDefined();
    expect(kn.common.loading).toBeDefined();
    expect(typeof kn.common.loading).toBe('string');
    expect(kn.common.loading.length).toBeGreaterThan(0);
  });

  it('loads Malayalam locale keys correctly without empty values', () => {
    expect(ml).toBeDefined();
    expect(ml.common.loading).toBeDefined();
    expect(typeof ml.common.loading).toBe('string');
    expect(ml.common.loading.length).toBeGreaterThan(0);
  });
});
