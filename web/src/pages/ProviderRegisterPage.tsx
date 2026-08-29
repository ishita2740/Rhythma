import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/useAuth';
import { friendlyAuthError } from '../api/client';
import { useDocumentMeta } from '../lib/useDocumentMeta';

export function ProviderRegisterPage() {
  useDocumentMeta('meta.providerRegister.title', 'meta.providerRegister.description');
  const { t } = useTranslation();
  const { registerProvider } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [specialty, setSpecialty] = useState('');
  const [licenseNumber, setLicenseNumber] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await registerProvider(email, password, fullName, specialty, licenseNumber);
      navigate('/provider/login', { replace: true });
    } catch (err) {
      setError(friendlyAuthError(err, t('provider.registerError')));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h1>{t('provider.registerTitle')}</h1>
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
          {t('provider.fullName')}
          <input value={fullName} onChange={(e) => setFullName(e.target.value)} />
        </label>

        <label>
          {t('provider.specialty')}
          <input
            value={specialty}
            onChange={(e) => setSpecialty(e.target.value)}
            placeholder={t('provider.specialtyPlaceholder')}
          />
        </label>

        <label>
          {t('provider.licenseNumber')}
          <input
            value={licenseNumber}
            onChange={(e) => setLicenseNumber(e.target.value)}
          />
        </label>

        <label>
          {t('provider.password')}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </label>

        <button type="submit" disabled={loading}>
          {loading ? t('provider.registering') : t('provider.registerButton')}
        </button>

        <p>
          {t('provider.haveAccount')}{' '}
          <Link to="/provider/login">{t('provider.loginLink')}</Link>
        </p>
        <p>
          <Link to="/register">{t('provider.patientLogin')}</Link>
        </p>
      </form>
    </div>
  );
}
