import { describe, expect, it } from 'vitest';

import {
  MAX_PASSWORD_BYTES,
  MIN_PASSWORD_LENGTH,
  byteLength,
  evaluatePassword,
  isPasswordAcceptable,
  serverPasswordFailures,
} from './password';

/**
 * These mirror `backend/tests/test_password_policy.py` case for case on
 * purpose. The client copy exists only to give live feedback while typing;
 * the moment the two disagree, a user sees a green tick on a password the
 * server then refuses. Keeping the cases aligned is what makes that
 * divergence show up here rather than in production.
 */

function failing(password: string, context = {}) {
  return evaluatePassword(password, context)
    .filter((rule) => !rule.met)
    .map((rule) => rule.code);
}

describe('evaluatePassword', () => {
  it('accepts an ordinary good password', () => {
    expect(failing('kolkata-monsoon-77')).toEqual([]);
  });

  it.each([
    'kolkata-monsoon-77',
    'chai without sugar',
    '9-cycles-and-counting',
    'MyDogIsCalledLaddoo',
  ])('does not reject the usable password %s', (password) => {
    expect(failing(password, { email: 'sana@example.com', username: 'sanakumari' })).toEqual(
      [],
    );
  });

  it('flags a password below the minimum length', () => {
    expect(failing('abc1')).toContain('too_short');
  });

  it('accepts a password exactly at the minimum', () => {
    expect('hibiscus'.length).toBe(MIN_PASSWORD_LENGTH);
    expect(failing('hibiscus')).not.toContain('too_short');
  });

  it('flags a password past bcrypt’s byte ceiling', () => {
    expect(failing('a'.repeat(73))).toContain('too_long');
  });

  it('measures the ceiling in bytes, not characters', () => {
    // The same trap as on the server: an Indian-language passphrase reaches
    // 72 bytes at roughly a third of the character count an English one
    // does, and bcrypt would silently keep only the first 72.
    const hindi = 'सुरक्षितपासवर्डहैयहबहुतअच्छा';

    expect(hindi.length).toBeLessThan(MAX_PASSWORD_BYTES);
    expect(byteLength(hindi)).toBeGreaterThan(MAX_PASSWORD_BYTES);
    expect(failing(hindi)).toContain('too_long');
  });

  it.each(['password', 'PASSWORD', 'qwerty123', 'iloveyou'])(
    'flags the common password %s regardless of case',
    (password) => {
      expect(failing(password)).toContain('too_common');
    },
  );

  it('flags a password containing the email local part', () => {
    expect(failing('sana-loves-mangoes', { email: 'sana@example.com' })).toContain(
      'contains_identifier',
    );
  });

  it('flags a password containing the email domain', () => {
    expect(failing('example-2026-pass', { email: 'sana@example.com' })).toContain(
      'contains_identifier',
    );
  });

  it('flags a password containing the username', () => {
    expect(failing('sanakumari2026', { username: 'sanakumari' })).toContain(
      'contains_identifier',
    );
  });

  it('does not treat a very short local part as an identifier', () => {
    expect(failing('kolkata-monsoon-77', { email: 'k@example.com' })).not.toContain(
      'contains_identifier',
    );
  });

  it('flags a password made of a couple of repeated characters', () => {
    expect(failing('aaaaaaaa')).toContain('not_varied_enough');
    expect(failing('abababababab')).toContain('not_varied_enough');
  });

  it.each(['abcdefgh', '12345678', 'qwertyuiop', '87654321'])(
    'flags the keyboard run %s',
    (password) => {
      expect(failing(password)).toContain('sequential');
    },
  );

  it('does not flag an ordinary word with three sequential letters', () => {
    expect(failing('first-monsoon-rain')).not.toContain('sequential');
  });

  it('reports every broken rule at once', () => {
    const broken = failing('123456');
    expect(broken).toContain('too_short');
    expect(broken).toContain('too_common');
    expect(broken).toContain('sequential');
  });

  it('returns the whole rule list, not only the failures', () => {
    // The form shows requirements before anything is typed, so an empty
    // password has to come back as "nothing met yet" rather than as an
    // empty list, which would render as "no requirements".
    const rules = evaluatePassword('');
    expect(rules).toHaveLength(6);
    expect(rules.some((rule) => !rule.met)).toBe(true);
  });
});

describe('isPasswordAcceptable', () => {
  it('is false for an empty password', () => {
    expect(isPasswordAcceptable('')).toBe(false);
  });

  it('is false while any rule is unmet', () => {
    expect(isPasswordAcceptable('abc')).toBe(false);
  });

  it('is true once every rule is met', () => {
    expect(isPasswordAcceptable('kolkata-monsoon-77')).toBe(true);
  });
});

describe('serverPasswordFailures', () => {
  function weakPasswordResponse(details: unknown) {
    return {
      isAxiosError: true,
      response: {
        status: 422,
        data: { detail: 'weak', error: { code: 'weak_password', details } },
      },
    };
  }

  it('extracts each rule message from the error envelope', () => {
    const error = weakPasswordResponse([
      { code: 'too_short', message: 'Use at least 8 characters.' },
      { code: 'too_common', message: 'That password is too common.' },
    ]);

    expect(serverPasswordFailures(error)).toEqual([
      'Use at least 8 characters.',
      'That password is too common.',
    ]);
  });

  it('ignores errors that are not about the password', () => {
    const error = {
      isAxiosError: true,
      response: { status: 409, data: { error: { code: 'conflict', details: null } } },
    };

    expect(serverPasswordFailures(error)).toEqual([]);
  });

  it('survives a malformed details payload', () => {
    // Defensive rather than hypothetical: this reads a nested field off a
    // network response, and throwing here would replace a helpful message
    // with a blank form and a console error.
    expect(serverPasswordFailures(weakPasswordResponse('not-an-array'))).toEqual([]);
    expect(serverPasswordFailures(weakPasswordResponse([null, 42, {}]))).toEqual([]);
    expect(serverPasswordFailures(undefined)).toEqual([]);
    expect(serverPasswordFailures({})).toEqual([]);
  });
});
