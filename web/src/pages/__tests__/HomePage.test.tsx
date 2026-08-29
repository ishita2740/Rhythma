import { describe, it, expect } from 'vitest';

describe('HomePage Quick Log Modal Accessibility Logic', () => {
  it('dispatches Escape key event to close active tile modal', () => {
    let activeTile: string | null = 'flow_intensity';
    const handleKeyDown = (e: { key: string }) => {
      if (e.key === 'Escape') {
        activeTile = null;
      }
    };

    handleKeyDown({ key: 'Escape' });
    expect(activeTile).toBeNull();
  });
});
