import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/useAuth';
import { friendlyAuthError } from '../api/client';
import { useDocumentMeta } from '../lib/useDocumentMeta';

export function LoginPage() {
  useDocumentMeta('meta.login.title', 'meta.login.description');
  const { t } = useTranslation();
  const { login } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(friendlyAuthError(err, t('auth.loginError')));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>{t('auth.loginTitle')}</h1>

        {error && <p className="error-text">{error}</p>}

        <label>
          {t('auth.username')}
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>

        <label>
          {t('auth.password')}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>

        <button type="submit" disabled={loading}>
          {loading ? t('auth.loggingIn') : t('auth.loginButton')}
        </button>

        <p>
          {t('auth.noAccount')} <Link to="/register">{t('auth.registerLink')}</Link>
        </p>
        <p>
          <Link to="/provider/login">{t('auth.providerLink')}</Link>
        </p>
      </form>
    </div>
  );
}
