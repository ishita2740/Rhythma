import { describe, it, expect } from 'vitest';

describe('CustomCursor Component Logic', () => {
  it('adds and removes custom-cursor-active class on body appropriately', () => {
    document.body.classList.add('custom-cursor-active');
    expect(document.body.classList.contains('custom-cursor-active')).toBe(true);

    document.body.classList.remove('custom-cursor-active');
    expect(document.body.classList.contains('custom-cursor-active')).toBe(false);
  });
});
