import { useMemo, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/useAuth';
import { friendlyAuthError } from '../api/client';
import {
  MAX_PASSWORD_BYTES,
  MIN_PASSWORD_LENGTH,
  evaluatePassword,
  serverPasswordFailures,
} from '../lib/password';
import { useDocumentMeta } from '../lib/useDocumentMeta';

export function RegisterPage() {
  useDocumentMeta('meta.register.title', 'meta.register.description');
  const { t } = useTranslation();
  const { register } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [passwordErrors, setPasswordErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  // Recomputed as she types, so the requirements tick off in place rather
  // than only appearing after a rejected submission.
  const passwordRules = useMemo(
    () => evaluatePassword(password, { email, username }),
    [password, email, username],
  );
  const passwordReady = password.length > 0 && passwordRules.every((rule) => rule.met);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setPasswordErrors([]);
    setLoading(true);
    try {
      await register(username, email, password, fullName);
      navigate('/login', { replace: true });
    } catch (err) {
      // The server's own per-rule messages take precedence over the local
      // mirror in lib/password.ts — it is the thing that actually decides,
      // and it may know rules this build does not.
      const failures = serverPasswordFailures(err);
      if (failures.length > 0) {
        setPasswordErrors(failures);
        setError(t('auth.passwordRejected'));
      } else {
        setError(friendlyAuthError(err, t('auth.registerError')));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>{t('auth.registerTitle')}</h1>

        {error && <p className="error-text">{error}</p>}

        {passwordErrors.length > 0 && (
          <ul className="error-text" data-testid="server-password-errors">
            {passwordErrors.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        )}

        <label>
          {t('auth.username')}
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>

        <label>
          {t('auth.email')}
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>

        <label>
          {t('auth.fullName')}
          <input value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </label>

        <label>
          {t('auth.password')}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-describedby="password-requirements"
            required
          />
        </label>

        {/* Rendered before anything is typed, not only after a rejection —
            requirements a user discovers by failing are requirements she
            works around rather than meets. */}
        <div id="password-requirements" className="password-requirements">
          <p>{t('auth.passwordRequirementsTitle')}</p>
          <ul>
            {passwordRules.map((rule) => (
              <li
                key={rule.code}
                data-rule={rule.code}
                data-met={rule.met}
                className={rule.met ? 'rule-met' : 'rule-unmet'}
              >
                <span aria-hidden="true">{rule.met ? '✓' : '•'}</span>{' '}
                {t(`auth.passwordRules.${rule.code}`, {
                  min: MIN_PASSWORD_LENGTH,
                  bytes: MAX_PASSWORD_BYTES,
                })}
              </li>
            ))}
          </ul>
        </div>

        {/* Disabled only on rules this build knows about; the server still
            has the final say on submit. */}
        <button type="submit" disabled={loading || !passwordReady}>
          {loading ? t('auth.registering') : t('auth.registerButton')}
        </button>

        <p>
          {t('auth.haveAccount')} <Link to="/login">{t('auth.loginLink')}</Link>
        </p>
      </form>
    </div>
  );
}
