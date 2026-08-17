import { describe, expect, it } from 'vitest';

import en from './locales/en.json';
import bn from './locales/bn.json';
import gu from './locales/gu.json';
import hi from './locales/hi.json';
import kn from './locales/kn.json';
import ml from './locales/ml.json';
import mr from './locales/mr.json';
import ta from './locales/ta.json';
import te from './locales/te.json';

// A missing key does not throw — i18next falls back to the key itself, so
// the user sees a raw string like "home.flow" in the middle of the UI. That
// is invisible to tsc, to the linter, and to a build. It is only catchable
// by comparing the locale files, which is what this file does.

const LOCALES = { bn, gu, hi, kn, ml, mr, ta, te } as const;

// Locales that currently carry a full translation of en.json. These are
// held to strict parity: a new English key that isn't translated here
// fails the build.
const COMPLETE_LOCALES = ['bn', 'gu', 'hi', 'kn', 'ml', 'mr', 'ta', 'te'] as const;

// Locales that are genuinely incomplete today. Writing this test turned up
// that `bn` and `gu` each define only 18 of the 182 keys in en.json — so
// roughly 90% of the Bengali and Gujarati UI silently renders raw key
// strings like "home.flow" to the user.
//
// They are not held to parity, because the fix is real translation work
// and filling them with English strings would be worse than the gap: it
// would look translated, and the parity test above would then have nothing
// left to catch. Instead they are ratcheted — the counts below are a floor,
// so these locales can only improve. Lower the floor and the test fails;
// raise a locale to 182 and move it into COMPLETE_LOCALES.
const KNOWN_INCOMPLETE: Record<string, number> = {};

type Json = Record<string, unknown>;

function flatten(value: Json, prefix = ''): string[] {
  return Object.entries(value).flatMap(([key, inner]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return inner && typeof inner === 'object' && !Array.isArray(inner)
      ? flatten(inner as Json, path)
      : [path];
  });
}

function valueAt(source: Json, path: string): unknown {
  return path.split('.').reduce<unknown>(
    (node, part) =>
      node && typeof node === 'object' ? (node as Json)[part] : undefined,
    source,
  );
}

const EN_KEYS = flatten(en as Json);

describe('locale coverage', () => {
  it('English is the reference and is not empty', () => {
    expect(EN_KEYS.length).toBeGreaterThan(20);
  });

  it.each(COMPLETE_LOCALES)('%s defines every key English defines', (code) => {
    const locale = LOCALES[code] as Json;
    const missing = EN_KEYS.filter((key) => valueAt(locale, key) === undefined);
    expect(missing, `${code} is missing: ${missing.join(', ')}`).toEqual([]);
  });

  it.each(Object.keys(KNOWN_INCOMPLETE))(
    '%s has not lost any of the keys it already had',
    (code) => {
      const locale = LOCALES[code as keyof typeof LOCALES] as Json;
      const present = EN_KEYS.filter((key) => valueAt(locale, key) !== undefined);
      expect(
        present.length,
        `${code} translates ${present.length}/${EN_KEYS.length} keys; ` +
          `the floor is ${KNOWN_INCOMPLETE[code]}. If you added translations, ` +
          `raise the floor. If this dropped, a key was removed or renamed.`,
      ).toBeGreaterThanOrEqual(KNOWN_INCOMPLETE[code]);
    },
  );

  it('the known-incomplete list does not quietly cover a complete locale', () => {
    // Otherwise a locale could be finished and still never get held to
    // strict parity, which defeats the point of the list.
    for (const code of Object.keys(KNOWN_INCOMPLETE)) {
      const locale = LOCALES[code as keyof typeof LOCALES] as Json;
      const present = EN_KEYS.filter((key) => valueAt(locale, key) !== undefined);
      expect(
        present.length,
        `${code} is now complete — move it into COMPLETE_LOCALES`,
      ).toBeLessThan(EN_KEYS.length);
    }
  });

  it.each(Object.keys(LOCALES))('%s defines no keys English does not', (code) => {
    // An extra key is dead weight at best, and usually a typo of a real
    // one — which reads as "translated" while never being rendered.
    const locale = LOCALES[code as keyof typeof LOCALES] as Json;
    const extra = flatten(locale).filter((key) => !EN_KEYS.includes(key));
    expect(extra, `${code} has unexpected keys: ${extra.join(', ')}`).toEqual([]);
  });

  it.each(Object.keys(LOCALES))('%s has no empty translations', (code) => {
    const locale = LOCALES[code as keyof typeof LOCALES] as Json;
    const empty = flatten(locale).filter((key) => {
      const value = valueAt(locale, key);
      return typeof value === 'string' && value.trim() === '';
    });
    expect(empty, `${code} has empty values: ${empty.join(', ')}`).toEqual([]);
  });

  it.each(Object.keys(LOCALES))('%s has no TODO markers left in copy', (code) => {
    const locale = LOCALES[code as keyof typeof LOCALES] as Json;
    const unfinished = flatten(locale).filter((key) => {
      const value = valueAt(locale, key);
      return typeof value === 'string' && /\b(TODO|FIXME|XXX|TRANSLATE)\b/i.test(value);
    });
    expect(unfinished, `${code} has unfinished copy: ${unfinished.join(', ')}`).toEqual([]);
  });
});

describe('interpolation placeholders', () => {
  it.each(Object.keys(LOCALES))(
    '%s keeps the same {{placeholders}} as English',
    (code) => {
      // A dropped placeholder renders a sentence with a hole in it; an
      // invented one renders the literal "{{count}}" to the user.
      const locale = LOCALES[code as keyof typeof LOCALES] as Json;
      const mismatched: string[] = [];

      for (const key of EN_KEYS) {
        const source = valueAt(en as Json, key);
        const translated = valueAt(locale, key);
        if (typeof source !== 'string' || typeof translated !== 'string') continue;

        const placeholders = (text: string) =>
          [...text.matchAll(/\{\{(\w+)\}\}/g)].map((match) => match[1]).sort();

        if (placeholders(source).join() !== placeholders(translated).join()) {
          mismatched.push(key);
        }
      }

      expect(mismatched, `${code} placeholder mismatch: ${mismatched.join(', ')}`).toEqual(
        [],
      );
    },
  );
});

describe('i18n registration', () => {
  it('registers every locale file that exists', async () => {
    // A locale file can be added and simply never wired into resources —
    // which is exactly what happened to Kannada and Malayalam in the
    // Flutter app (issue #183).
    const i18n = (await import('./index')).default;
    const registered = Object.keys(i18n.options.resources ?? {});
    for (const code of ['en', ...Object.keys(LOCALES)]) {
      expect(registered, `${code} is not registered in i18n/index.ts`).toContain(code);
    }
  });

  it('falls back to English', async () => {
    const i18n = (await import('./index')).default;
    expect(i18n.options.fallbackLng).toContain('en');
  });
});
