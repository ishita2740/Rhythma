/**
 * Client-side mirror of the server's password policy (issue #330).
 *
 * `backend/core/password_policy.py` is the authority — this file exists so
 * the register form can tick requirements off as the user types instead of
 * making her submit to find out. Anything that passes here can still be
 * rejected by the server, and the server's answer always wins: the form
 * renders whatever rules came back from a 422 rather than assuming this
 * file agreed with it.
 *
 * Kept deliberately small and dependency-free. If the two ever disagree the
 * visible symptom is a requirement that shows as met and is then refused,
 * which is annoying but safe; the reverse — a rule enforced here and not
 * there — cannot let anything through.
 */

/** Matches `DEFAULT_MIN_LENGTH` in backend/core/password_policy.py. */
export const MIN_PASSWORD_LENGTH = 8;

/**
 * bcrypt hashes at most 72 bytes and silently drops the rest, so this is a
 * property of the hash rather than a policy choice. Measured in *bytes*:
 * most Devanagari, Tamil, Telugu, Kannada and Malayalam characters cost
 * three bytes each in UTF-8, so an Indian-language passphrase reaches the
 * ceiling at roughly a third of the character count an English one does.
 */
export const MAX_PASSWORD_BYTES = 72;

/** Shortest fragment of the user's own identity treated as "contains your email". */
const MIN_IDENTIFIER_FRAGMENT = 4;

/** Length of a keyboard/alphabet run that disqualifies a password. */
const MAX_SEQUENCE_RUN = 5;

const SEQUENCES = [
  'abcdefghijklmnopqrstuvwxyz',
  '0123456789',
  'qwertyuiop',
  'asdfghjkl',
  'zxcvbnm',
];

/** The head of the common-password distribution the server also refuses. */
const COMMON_PASSWORDS = new Set([
  '123456', '123456789', '12345678', '1234567', '1234567890', '12345',
  'password', 'password1', 'password123', 'passw0rd', 'p@ssw0rd',
  'qwerty', 'qwerty123', 'qwertyuiop', 'asdfghjkl', 'zxcvbnm',
  '111111', '000000', '123123', '654321', '666666', '888888',
  'abc123', 'abcd1234', 'a1b2c3d4', 'letmein', 'welcome', 'welcome1',
  'iloveyou', 'monkey', 'dragon', 'sunshine', 'princess', 'football',
  'baseball', 'superman', 'trustno1', 'master', 'shadow', 'michael',
  'jennifer', 'computer', 'internet', 'samsung', 'google', 'facebook',
  'whatsapp', 'india123', 'indian123', 'bharat123', 'krishna',
  'ganesh', 'chennai', 'mumbai123', 'delhi123', 'admin', 'admin123',
  'root', 'test123', 'changeme', 'secret', 'login', 'pass1234',
  'rhythma', 'rhythma123', 'period123', 'health123',
]);

/** Stable identifiers, shared with the server so messages can be localized. */
export type PasswordRuleCode =
  | 'too_short'
  | 'too_long'
  | 'too_common'
  | 'contains_identifier'
  | 'not_varied_enough'
  | 'sequential';

export interface PasswordRuleState {
  code: PasswordRuleCode;
  /** False once the user has typed something that breaks this rule. */
  met: boolean;
}

export interface PasswordContext {
  email?: string;
  username?: string;
}

/** Byte length under UTF-8, which is what bcrypt's 72 counts. */
export function byteLength(value: string): number {
  return new TextEncoder().encode(value).length;
}

/**
 * Pieces of the user's own identity a password shouldn't contain. Mirrors
 * `_identifier_fragments` on the server: the local part, its dot/underscore
 * separated pieces, and the first label of the domain — but not the TLD,
 * which would make every password containing "com" illegal.
 */
function identifierFragments({ email, username }: PasswordContext): string[] {
  const fragments: string[] = [];

  if (username) fragments.push(username);

  if (email && email.includes('@')) {
    const [local, domain] = email.split('@');
    fragments.push(local, ...local.split(/[._\-+]/));
    const firstLabel = domain?.split('.')[0];
    if (firstLabel) fragments.push(firstLabel);
  } else if (email) {
    fragments.push(email);
  }

  return fragments
    .map((fragment) => fragment.toLowerCase())
    .filter((fragment) => fragment.length >= MIN_IDENTIFIER_FRAGMENT);
}

function hasLongSequence(password: string): boolean {
  const lowered = password.toLowerCase();

  return SEQUENCES.some((source) => {
    const reversed = [...source].reverse().join('');
    for (let start = 0; start <= source.length - MAX_SEQUENCE_RUN; start += 1) {
      if (lowered.includes(source.slice(start, start + MAX_SEQUENCE_RUN))) return true;
      if (lowered.includes(reversed.slice(start, start + MAX_SEQUENCE_RUN))) return true;
    }
    return false;
  });
}

/**
 * Every rule, with whether the current value satisfies it.
 *
 * Returns the full list rather than only the failures so the form can show
 * the requirements up front — an empty password reads as "nothing met yet",
 * not as "no problems".
 */
export function evaluatePassword(
  password: string,
  context: PasswordContext = {},
): PasswordRuleState[] {
  const lowered = password.toLowerCase();
  const fragments = identifierFragments(context);
  const distinctCharacters = new Set(password).size;

  return [
    {
      code: 'too_short',
      met: password.length >= MIN_PASSWORD_LENGTH,
    },
    {
      code: 'too_long',
      met: byteLength(password) <= MAX_PASSWORD_BYTES,
    },
    {
      code: 'too_common',
      met: !COMMON_PASSWORDS.has(lowered),
    },
    {
      code: 'contains_identifier',
      met: !fragments.some((fragment) => lowered.includes(fragment)),
    },
    {
      // Only meaningful once there is something to judge; an empty box
      // isn't "too repetitive", it's empty, and the length rule says so.
      code: 'not_varied_enough',
      met: password.length < 4 || distinctCharacters >= 4,
    },
    {
      code: 'sequential',
      met: !hasLongSequence(password),
    },
  ];
}

/** True when nothing in the local mirror objects to this password. */
export function isPasswordAcceptable(
  password: string,
  context: PasswordContext = {},
): boolean {
  return password.length > 0 && evaluatePassword(password, context).every((rule) => rule.met);
}

/**
 * Pull the per-rule messages out of the server's 422.
 *
 * The backend answers a weak password with the standard error envelope
 * (`core/errors.py`): `error.code === 'weak_password'` and every broken
 * rule in `error.details`. Returns an empty array for any other failure, so
 * callers can fall back to their generic message.
 */
export function serverPasswordFailures(error: unknown): string[] {
  if (!error || typeof error !== 'object') return [];

  const response = (error as { response?: { data?: unknown } }).response;
  const data = response?.data as
    | { error?: { code?: string; details?: unknown } }
    | undefined;

  if (data?.error?.code !== 'weak_password') return [];
  if (!Array.isArray(data.error.details)) return [];

  return data.error.details
    .map((item) => (item && typeof item === 'object' ? (item as { message?: unknown }).message : null))
    .filter((message): message is string => typeof message === 'string' && message.length > 0);
}
