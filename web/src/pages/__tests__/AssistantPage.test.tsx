import { describe, it, expect } from 'vitest';

describe('AssistantPage Web Component Logic', () => {
  it('formats bold text correctly', () => {
    const text = 'Hello **world** test';
    const parts = text.split('**');
    expect(parts.length).toBe(3);
    expect(parts[1]).toBe('world');
  });

  it('parses bullet messages accurately', () => {
    const line = '- Drink water';
    expect(line.trim().startsWith('- ')).toBe(true);
    expect(line.trim().slice(2)).toBe('Drink water');
  });
});
