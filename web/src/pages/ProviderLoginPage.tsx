import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/useAuth';
import { friendlyAuthError } from '../api/client';
import { useDocumentMeta } from '../lib/useDocumentMeta';

export function ProviderLoginPage() {
  useDocumentMeta('meta.providerLogin.title', 'meta.providerLogin.description');
  const { t } = useTranslation();
  const { loginProvider } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await loginProvider(email, password);
      navigate('/provider', { replace: true });
    } catch (err) {
      setError(friendlyAuthError(err, t('provider.loginError')));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>{t('provider.loginTitle')}</h1>
        <p className="auth-subtitle">{t('provider.subtitle')}</p>

        {error && <p className="error-text">{error}</p>}

        <label>
          {t('provider.email')}
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>

        <label>
          {t('provider.password')}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>

        <button type="submit" disabled={loading}>
          {loading ? t('provider.loggingIn') : t('provider.loginButton')}
        </button>

        <p>
          {t('provider.noAccount')}{' '}
          <Link to="/provider/register">{t('provider.registerLink')}</Link>
        </p>
        <p>
          <Link to="/login">{t('provider.patientLogin')}</Link>
        </p>
      </form>
    </div>
  );
}
