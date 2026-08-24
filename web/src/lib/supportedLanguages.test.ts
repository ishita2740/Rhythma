import { describe, expect, it } from 'vitest';

import i18n from '../i18n';
import {
  APP_LANGUAGES,
  APP_LANGUAGE_CODES,
  ASSISTANT_LANGUAGE_CODES,
  RTL_LANGUAGE_CODES,
  baseLanguage,
  directionForLanguage,
  isAssistantLanguage,
  isSameLanguage,
  isSupportedLanguage,
  languageFor,
  nativeNameFor,
} from './supportedLanguages';

/**
 * Issue #512. The web app decided what languages it speaks in five
 * places and no two agreed, each disagreement visible to a user.
 *
 * The `drift` group is the one that matters: it compares this module
 * against the locale bundle i18next actually registered, so a locale
 * added in one place and forgotten in the other fails the build rather
 * than shipping as a chip nobody can select or an option that answers in
 * the wrong language.
 */
describe('drift between the list and the bundle', () => {
  it('ships a locale for every language in the list', () => {
    const registered = new Set(Object.keys(i18n.options.resources ?? {}));

    const missing = APP_LANGUAGE_CODES.filter((code) => !registered.has(code));

    expect(missing, `no locale bundle for: ${missing.join(', ')}`).toEqual([]);
  });

  it('lists every locale the bundle registers', () => {
    // The other direction, and the one that actually broke: `bn` was
    // registered and offered, and the assistant refused to answer in it.
    const listed = new Set(APP_LANGUAGE_CODES);
    const registered = Object.keys(i18n.options.resources ?? {});

    const unlisted = registered.filter((code) => !listed.has(code));

    expect(unlisted, `registered but not listed: ${unlisted.join(', ')}`).toEqual([]);
  });

  it('has no duplicate codes', () => {
    expect(new Set(APP_LANGUAGE_CODES).size).toBe(APP_LANGUAGE_CODES.length);
  });

  it('gives every language a name in its own script', () => {
    // Gujarati rendered as the English word "Gujarati" while every other
    // chip rendered natively, because `LANGUAGE_KEY` had no `gu` entry.
    const wrong = APP_LANGUAGES.filter(
      (l) => !l.nativeName.trim() || (l.code !== 'en' && l.nativeName === l.englishName),
    );

    expect(wrong.map((l) => l.code)).toEqual([]);
  });

  it('gives every language a direction', () => {
    for (const lang of APP_LANGUAGES) {
      expect(['ltr', 'rtl']).toContain(lang.dir);
    }
  });
});

describe('the assistant subset', () => {
  it('matches the eight codes the backend accepts', () => {
    // `backend/api/assistant.py::SUPPORTED_LANGUAGES`. If that list
    // changes, this is the test that says so.
    expect([...ASSISTANT_LANGUAGE_CODES].sort()).toEqual(
      ['en', 'gu', 'hi', 'kn', 'ml', 'mr', 'ta', 'te'].sort(),
    );
  });

  it('is a subset of what the app ships', () => {
    for (const code of ASSISTANT_LANGUAGE_CODES) {
      expect(APP_LANGUAGE_CODES).toContain(code);
    }
  });

  it('does not claim to serve Bengali', () => {
    // The concrete bug: the picker offered it and the reply came back in
    // English with no explanation.
    expect(isAssistantLanguage('bn')).toBe(false);
    expect(isSupportedLanguage('bn')).toBe(true);
  });

  it('recognizes a region tag', () => {
    expect(isAssistantLanguage('hi-IN')).toBe(true);
    expect(isAssistantLanguage('en-US')).toBe(true);
  });
});

describe('writing direction', () => {
  it('marks all three Perso-Arabic locales as RTL', () => {
    // `ur` was already covered. `sd` (Sindhi) and `ks` (Kashmiri) were
    // not, so both rendered LTR: punctuation at the wrong end of every
    // line and the layout mirrored the wrong way.
    expect([...RTL_LANGUAGE_CODES].sort()).toEqual(['ks', 'sd', 'ur']);
  });

  it('does not claim languages the app does not ship', () => {
    // The old set carried `ar`, `fa` and `he` — a guess, not a fact
    // about this app.
    for (const code of ['ar', 'fa', 'he']) {
      expect(APP_LANGUAGE_CODES).not.toContain(code);
      expect(directionForLanguage(code)).toBe('ltr');
    }
  });

  it('reads direction through a region tag', () => {
    expect(directionForLanguage('ur-PK')).toBe('rtl');
    expect(directionForLanguage('hi-IN')).toBe('ltr');
  });

  it('defaults to ltr for anything unrecognized', () => {
    expect(directionForLanguage(undefined)).toBe('ltr');
    expect(directionForLanguage('zzz')).toBe('ltr');
  });
});

describe('baseLanguage', () => {
  it('strips a region tag', () => {
    expect(baseLanguage('en-US')).toBe('en');
    expect(baseLanguage('hi-IN')).toBe('hi');
  });

  it('folds underscores and case', () => {
    expect(baseLanguage('hi_IN')).toBe('hi');
    expect(baseLanguage('HI')).toBe('hi');
    expect(baseLanguage('  ta-IN  ')).toBe('ta');
  });

  it('keeps a three-letter code whole', () => {
    // `AssistantPage` used `.slice(0, 2)`, which turned `mai` into `ma`,
    // `sat` into `sa` and `sd` into `sd` — two of the three matched no
    // option, so the select silently showed the first entry instead.
    expect(baseLanguage('mai')).toBe('mai');
    expect(baseLanguage('sat')).toBe('sat');
  });

  it('falls back to en for nothing', () => {
    expect(baseLanguage(undefined)).toBe('en');
    expect(baseLanguage(null)).toBe('en');
    expect(baseLanguage('')).toBe('en');
    expect(baseLanguage('   ')).toBe('en');
  });
});

describe('isSameLanguage', () => {
  it('matches a region tag against a bare code', () => {
    // The comparison the Settings picker got wrong: `'hi-IN' === 'hi'` is
    // false, so no chip was ever marked active for a user whose browser
    // reports a region.
    expect(isSameLanguage('hi-IN', 'hi')).toBe(true);
    expect(isSameLanguage('en-GB', 'en')).toBe(true);
  });

  it('does not match different languages', () => {
    expect(isSameLanguage('hi-IN', 'mr')).toBe(false);
    expect(isSameLanguage('ta', 'te')).toBe(false);
  });
});

describe('lookups', () => {
  it('finds a language by tag', () => {
    expect(languageFor('gu-IN')?.englishName).toBe('Gujarati');
    expect(languageFor('zzz')).toBeUndefined();
  });

  it('returns the native name', () => {
    expect(nativeNameFor('gu')).toBe('ગુજરાતી');
    expect(nativeNameFor('hi-IN')).toBe('हिन्दी');
  });

  it('falls back to the code rather than to English', () => {
    // Silently becoming "English" is how a missing entry hides.
    expect(nativeNameFor('zzz')).toBe('zzz');
  });
});
