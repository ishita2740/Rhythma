import { useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { fetchSmsSettings, saveSmsSettings, sendSmsSummary } from '../api/endpoints';
import { useDocumentMeta } from '../lib/useDocumentMeta';

const PHONE_PATTERN = /^\+[1-9]\d{1,14}$/;

function friendlyError(error: unknown, fallback: string): string {
  if (error && typeof error === 'object' && 'isAxiosError' in error) {
    const axiosErr = error as { response?: { status?: number; data?: { detail?: string } } };
    if (axiosErr.response?.status === 429 && axiosErr.response.data?.detail) {
      return axiosErr.response.data.detail;
    }
    if (axiosErr.response?.data?.detail) return axiosErr.response.data.detail;
  }
  return fallback;
}

export function SmsPage() {
  useDocumentMeta('meta.sms.title', 'meta.sms.description');
  const { t } = useTranslation();

  const [phone, setPhone] = useState('');
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    fetchSmsSettings()
      .then((settings) => {
        setPhone(settings.phoneNumber);
        setEnabled(settings.enabled);
      })
      .catch((err) => setError(friendlyError(err, t('insights.loadError'))))
      .finally(() => setLoading(false));
  }, [t]);

  const save = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    const trimmed = phone.trim();
    if (enabled && !trimmed) {
      setError(t('sms.phoneRequired'));
      return;
    }
    if (trimmed && !PHONE_PATTERN.test(trimmed)) {
      setError(t('sms.phoneInvalid'));
      return;
    }

    setSaving(true);
    try {
      await saveSmsSettings({ phoneNumber: trimmed, enabled });
      setSuccess('✓');
    } catch (err) {
      setError(friendlyError(err, t('sms.phoneInvalid')));
    } finally {
      setSaving(false);
    }
  };

  const sendNow = async () => {
    const trimmed = phone.trim();
    setError('');
    setSuccess('');
    if (!trimmed) {
      setError(t('sms.phoneRequired'));
      return;
    }
    if (!PHONE_PATTERN.test(trimmed)) {
      setError(t('sms.phoneInvalid'));
      return;
    }

    setSending(true);
    try {
      const message = `${t('sms.title')} — ${new Date().toLocaleDateString()}`;
      await sendSmsSummary(trimmed, message);
      setSuccess('✓');
    } catch (err) {
      setError(friendlyError(err, t('insights.loadError')));
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return <div className="centered-loader">{t('common.loading')}</div>;
  }

  return (
    <div className="page">
      <header className="page-header">
        <h1>{t('sms.title')}</h1>
      </header>

      <section className="glass-card">
        <p className="card-label">{t('sms.infoTitle')}</p>
        <p className="card-sub">{t('sms.infoBody')}</p>
      </section>

      <section className="glass-card">
        <p className="card-label">{t('sms.settings')}</p>

        <form className="sms-form" onSubmit={save}>
          <label>
            {t('sms.phoneNumber')}
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+919876543210"
              inputMode="tel"
            />
          </label>

          <label className="switch-row">
            <span>{t('sms.enableWeekly')}</span>
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="switch"
            />
          </label>

          {error ? <p className="error-text">{error}</p> : null}
          {success ? <p className="success-text">{success}</p> : null}

          <button type="submit" className="primary-btn full" disabled={saving}>
            {saving ? t('common.loading') : t('sms.saveSettings')}
          </button>
        </form>
      </section>

      <section className="glass-card">
        <p className="card-label">{t('sms.sendNow')}</p>
        {phone.trim() ? (
          <pre className="sms-preview">{phone.trim()}</pre>
        ) : (
          <p className="card-sub">{t('sms.noPhone')}</p>
        )}
        <button type="button" className="primary-btn full" disabled={sending || !phone.trim()} onClick={() => void sendNow()}>
          {sending ? t('common.loading') : t('sms.send')}
        </button>
      </section>
    </div>
  );
}
