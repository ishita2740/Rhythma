import { beforeEach, describe, expect, it } from 'vitest';

import {
  applyDocumentLanguage,
  applyDocumentTitle,
  applyMetaProperty,
  applyMetaTag,
  composeTitle,
  directionFor,
  toDocumentLang,
} from './documentMeta';

beforeEach(() => {
  document.head.querySelectorAll('meta[name], meta[property]').forEach((tag) => {
    tag.remove();
  });
  document.documentElement.removeAttribute('lang');
  document.documentElement.removeAttribute('dir');
  document.title = '';
});

describe('toDocumentLang', () => {
  it('passes a bare code through', () => {
    expect(toDocumentLang('hi')).toBe('hi');
  });

  it('keeps the region tag', () => {
    // Unlike `toAssistantLanguage`, which must reduce to a bare code
    // because the backend only accepts those. `hi-IN` is valid BCP 47 and
    // a screen reader handles it, so truncating it would throw away a
    // regional pronunciation hint for no reason.
    expect(toDocumentLang('hi-IN')).toBe('hi-IN');
  });

  it('normalizes an underscore separator', () => {
    expect(toDocumentLang('pt_BR')).toBe('pt-BR');
  });

  it.each([undefined, '', '   '])('falls back to en for %p', (input) => {
    expect(toDocumentLang(input)).toBe('en');
  });
});

describe('directionFor', () => {
  it.each(['en', 'hi', 'bn', 'ta', 'te', 'kn', 'ml', 'mr', 'gu'])(
    '%s is left to right',
    (code) => {
      expect(directionFor(code)).toBe('ltr');
    },
  );

  it('is rtl for a right-to-left script', () => {
    // None shipped yet. #117 and #122 are both about adding languages and
    // Urdu is plausible for this audience, so the branch exists now rather
    // than being a rewrite later.
    expect(directionFor('ur')).toBe('rtl');
    expect(directionFor('ur-PK')).toBe('rtl');
  });
});

describe('applyDocumentLanguage', () => {
  it('sets lang and dir on the root element', () => {
    applyDocumentLanguage('ta');

    expect(document.documentElement.getAttribute('lang')).toBe('ta');
    expect(document.documentElement.getAttribute('dir')).toBe('ltr');
  });

  it('replaces a previous value rather than accumulating', () => {
    applyDocumentLanguage('hi');
    applyDocumentLanguage('ml');

    expect(document.documentElement.getAttribute('lang')).toBe('ml');
  });
});

describe('applyDocumentTitle', () => {
  it('sets the title', () => {
    applyDocumentTitle('Cycle · Rhythma');
    expect(document.title).toBe('Cycle · Rhythma');
  });

  it('trims', () => {
    applyDocumentTitle('  Insights  ');
    expect(document.title).toBe('Insights');
  });

  it.each([undefined, null, '', '   '])(
    'leaves the tab alone for %p rather than blanking it',
    (input) => {
      document.title = 'Rhythma';
      applyDocumentTitle(input);
      expect(document.title).toBe('Rhythma');
    },
  );
});

describe('applyMetaTag', () => {
  it('creates the tag when it does not exist', () => {
    applyMetaTag('description', 'Track your cycle.');

    const tag = document.head.querySelector('meta[name="description"]');
    expect(tag?.getAttribute('content')).toBe('Track your cycle.');
  });

  it('updates in place instead of appending a second one', () => {
    // The bug this prevents: one tag per navigation leaves a stack of
    // stale descriptions in the head, and a crawler reads the first — so
    // the description freezes on whichever page loaded first.
    applyMetaTag('description', 'First');
    applyMetaTag('description', 'Second');

    const tags = document.head.querySelectorAll('meta[name="description"]');
    expect(tags).toHaveLength(1);
    expect(tags[0].getAttribute('content')).toBe('Second');
  });

  it('ignores an empty value rather than emptying the tag', () => {
    applyMetaTag('description', 'Real content');
    applyMetaTag('description', '');

    expect(
      document.head.querySelector('meta[name="description"]')?.getAttribute('content'),
    ).toBe('Real content');
  });
});

describe('applyMetaProperty', () => {
  it('keys off property, not name', () => {
    applyMetaProperty('og:title', 'Rhythma');

    expect(document.head.querySelector('meta[name="og:title"]')).toBeNull();
    expect(
      document.head.querySelector('meta[property="og:title"]')?.getAttribute('content'),
    ).toBe('Rhythma');
  });

  it('updates in place', () => {
    applyMetaProperty('og:title', 'One');
    applyMetaProperty('og:title', 'Two');

    expect(document.head.querySelectorAll('meta[property="og:title"]')).toHaveLength(1);
  });
});

describe('composeTitle', () => {
  it('puts the page first so a truncated tab still distinguishes it', () => {
    expect(composeTitle('Cycle', 'Rhythma')).toBe('Cycle · Rhythma');
  });

  it('does not repeat the app name on the home page', () => {
    expect(composeTitle('Rhythma', 'Rhythma')).toBe('Rhythma');
  });

  it.each([undefined, '', '   '])('falls back to the app name for %p', (input) => {
    expect(composeTitle(input, 'Rhythma')).toBe('Rhythma');
  });
});
