import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import {
  fetchSmsPreview,
  fetchSmsSettings,
  saveSmsSettings,
  sendSmsSummary,
  type SmsPreview,
} from '../api/endpoints';
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

  // What the server currently holds, as distinct from what is in the form.
  // "Send now" used to read the live input and post it as the destination,
  // so typing a number and sending before saving produced a 403 telling
  // the user her own number was not hers (issue #532). The destination is
  // the account's; the form is a draft until it is saved.
  const [savedPhone, setSavedPhone] = useState('');
  const [savedEnabled, setSavedEnabled] = useState(false);

  const [preview, setPreview] = useState<SmsPreview | null>(null);
  const [previewError, setPreviewError] = useState('');

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const dirty = phone.trim() !== savedPhone || enabled !== savedEnabled;

  /**
   * The message that would actually be sent, fetched from the server.
   *
   * The old screen rendered the *phone number* inside the element whose
   * class is `sms-preview`, so the destination occupied the space a
   * preview belongs in and the text about her cycle was shown nowhere
   * before it went to her phone.
   *
   * Allowed to fail on its own: not being able to show the preview must
   * not stop her saving her settings, which is the more useful of the two
   * things this screen does.
   */
  const loadPreview = useCallback(async () => {
    setPreviewError('');
    try {
      setPreview(await fetchSmsPreview());
    } catch (err) {
      setPreview(null);
      setPreviewError(friendlyError(err, t('sms.previewUnavailable')));
    }
  }, [t]);

  useEffect(() => {
    fetchSmsSettings()
      .then((settings) => {
        setPhone(settings.phoneNumber);
        setEnabled(settings.enabled);
        setSavedPhone(settings.phoneNumber);
        setSavedEnabled(settings.enabled);
        if (settings.phoneNumber) void loadPreview();
      })
      .catch((err) => setError(friendlyError(err, t('insights.loadError'))))
      .finally(() => setLoading(false));
  }, [t, loadPreview]);

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
      const saved = await saveSmsSettings({ phoneNumber: trimmed, enabled });
      setSavedPhone(saved.phoneNumber);
      setSavedEnabled(saved.enabled);
      setPhone(saved.phoneNumber);
      setEnabled(saved.enabled);
      // A sentence, not a bare "✓". The tick said nothing about *what* had
      // been saved, and was the same untranslated glyph in all seventeen
      // locales.
      setSuccess(t('sms.settingsSaved'));
      if (saved.phoneNumber) void loadPreview();
    } catch (err) {
      setError(friendlyError(err, t('sms.phoneInvalid')));
    } finally {
      setSaving(false);
    }
  };

  const sendNow = async () => {
    setError('');
    setSuccess('');

    // Refuse rather than send the draft. Sending the saved number while
    // the user is looking at a different one on screen would be the same
    // class of surprise from the opposite direction.
    if (dirty) {
      setError(t('sms.saveBeforeSending'));
      return;
    }
    if (!savedPhone) {
      setError(t('sms.phoneRequired'));
      return;
    }
    if (!savedEnabled) {
      setError(t('sms.enableBeforeSending'));
      return;
    }

    setSending(true);
    try {
      await sendSmsSummary();
      setSuccess(t('sms.sent', { phone: savedPhone }));
      // The send counts against the weekly cadence server-side, so the
      // preview's "next" line is now stale.
      void loadPreview();
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

          <p className="card-sub">{t('sms.cadenceNote')}</p>

          {error ? <p className="error-text" role="alert">{error}</p> : null}
          {success ? <p className="success-text" role="status">{success}</p> : null}

          <button type="submit" className="primary-btn full" disabled={saving || !dirty}>
            {saving ? t('common.loading') : t('sms.saveSettings')}
          </button>
        </form>
      </section>

      <section className="glass-card">
        <p className="card-label">{t('sms.sendNow')}</p>

        {savedPhone ? (
          <p className="card-sub">{t('sms.willSendTo', { phone: savedPhone })}</p>
        ) : (
          <p className="card-sub">{t('sms.noPhone')}</p>
        )}

        {/* What will actually be texted, before it is texted. */}
        {preview ? (
          <>
            <p className="card-label">{t('sms.previewLabel')}</p>
            <pre className="sms-preview">{preview.body}</pre>
            <p className="card-sub">
              {t('sms.previewLength', { count: preview.characters })}
            </p>
          </>
        ) : previewError ? (
          <p className="card-sub">{previewError}</p>
        ) : null}

        {dirty ? <p className="card-sub">{t('sms.saveBeforeSending')}</p> : null}

        <button
          type="button"
          className="primary-btn full"
          disabled={sending || dirty || !savedPhone || !savedEnabled}
          onClick={() => void sendNow()}
        >
          {sending ? t('common.loading') : t('sms.send')}
        </button>
      </section>
    </div>
  );
}
