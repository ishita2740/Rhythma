import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/useAuth';
import { Modal } from '../components/Modal';
import { fetchDashboard, fetchProfile, patchProfile, type DashboardData, type Profile } from '../api/endpoints';
import { cycleSpread, formatSpread } from '../lib/cycleStats';
import { useDocumentMeta } from '../lib/useDocumentMeta';

const AVATAR_COLORS = ['#AA3BFF', '#E07AAD', '#52B3B0', '#E8946A', '#6A98E8', '#B3528A'];

function phasePill(day: number | null, t: (k: string) => string): string {
  if (day == null) return '—';
  if (day <= 5) return t('profile.menstrual');
  if (day <= 13) return t('profile.follicular');
  if (day <= 16) return t('profile.ovulation');
  return t('profile.luteal');
}

export function ProfilePage() {
  useDocumentMeta('meta.profile.title', 'meta.profile.description');
  const { t } = useTranslation();
  const { user } = useAuth();

  const [profile, setProfile] = useState<Profile | null>(null);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const [name, setName] = useState('');
  const [age, setAge] = useState('');
  const [cycleLength, setCycleLength] = useState('');
  const [avatar, setAvatar] = useState(AVATAR_COLORS[0]);
  const [formErrors, setFormErrors] = useState<{ name?: string; age?: string; cycle?: string }>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [prof, dash] = await Promise.all([
        fetchProfile(),
        fetchDashboard().catch(() => null),
      ]);
      setProfile(prof);
      setDashboard(dash);
    } catch {
      setError(t('insights.loadError'));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const openEdit = () => {
    setName(profile?.full_name ?? '');
    setAge(profile?.age != null ? String(profile.age) : '');
    setCycleLength(profile?.cycle_length != null ? String(profile.cycle_length) : '');
    setAvatar(profile?.avatar || AVATAR_COLORS[0]);
    setFormErrors({});
    setEditing(true);
  };

  const submitEdit = async (e: FormEvent) => {
    e.preventDefault();
    const errors: typeof formErrors = {};
    if (!name.trim()) errors.name = t('profile.nameRequired');
    const ageNum = parseInt(age, 10);
    if (age && (Number.isNaN(ageNum) || ageNum < 10 || ageNum > 120)) errors.age = t('profile.ageInvalid');
    const cycleNum = parseInt(cycleLength, 10);
    if (cycleLength && (Number.isNaN(cycleNum) || cycleNum < 15 || cycleNum > 45)) errors.cycle = t('profile.cycleInvalid');
    setFormErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setSaving(true);
    try {
      const updated = await patchProfile({
        full_name: name.trim() || null,
        age: age ? ageNum : null,
        cycle_length: cycleLength ? cycleNum : null,
        avatar,
      });
      setProfile(updated);
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  if (loading && !profile) {
    return <div className="centered-loader">{t('common.loading')}</div>;
  }

  const cycleDay = dashboard?.cycle.day ?? null;
  const displayName = profile?.full_name || user?.username || 'User';
  const initial = displayName.charAt(0).toUpperCase();
  const avatarColor = profile?.avatar && AVATAR_COLORS.includes(profile.avatar) ? profile.avatar : AVATAR_COLORS[0];
  const lengths = dashboard?.cycleHistory.map((p) => p.cycle_length) ?? [];
  // Measured against the mean of these lengths, in days. It used to be a
  // variance (squared deviations, never square-rooted) taken around
  // `dashboard.cycle.total` — a rounded average from a different
  // calculation that falls back to 28 when the user has almost no
  // history. See lib/cycleStats.ts and issue #383.
  const spread = formatSpread(cycleSpread(lengths));
  const lastCycle = lengths.length > 0 ? lengths[lengths.length - 1] : null;

  return (
    <div className="page">
      <header className="page-header">
        <h1>{t('profile.title')}</h1>
      </header>

      {error ? <div className="error-card"><p>{error}</p></div> : null}

      <section className="glass-card profile-header">
        <div className="profile-avatar" style={{ background: avatarColor }}>
          {initial}
        </div>
        <div>
          <h2 className="profile-name">{displayName}</h2>
          <p className="card-sub">
            {profile?.age != null ? t('profile.yearsOld', { age: profile.age }) : ''}
          </p>
          <span className="phase-pill" style={{ borderColor: avatarColor, color: avatarColor }}>
            {cycleDay != null ? `${t('profile.cycleDay', { day: cycleDay })} • ${phasePill(cycleDay, t)}` : '—'}
          </span>
        </div>
      </section>

      <section className="mini-stats">
        <MiniStat label={t('profile.avgCycleLength')} value={profile?.cycle_length != null ? `${profile.cycle_length} ${t('profile.days')}` : dashboard?.cycle.total != null ? `${dashboard.cycle.total} ${t('profile.days')}` : '—'} />
        <MiniStat label={t('profile.avgBleeding')} value={dashboard?.insights.averageBleedingDuration != null ? `${dashboard.insights.averageBleedingDuration} ${t('profile.days')}` : '—'} />
        <MiniStat label={t('profile.cycleVariability')} value={spread == null ? '—' : `${spread} ${t('profile.days')}`} />
        <MiniStat label={t('profile.lastCycleLength')} value={lastCycle != null ? `${lastCycle} ${t('profile.days')}` : '—'} />
      </section>

      <section className="menu-list">
        <button type="button" className="menu-item glass-card" onClick={openEdit}>
          <span>✏️</span>
          <span>{t('profile.editInfo')}</span>
          <span className="chevron">›</span>
        </button>
        <button
          type="button"
          className="menu-item glass-card"
          onClick={() => window.alert(t('profile.emergencyContacts'))}
        >
          <span>🆘</span>
          <span>{t('profile.emergencyContacts')}</span>
          <span className="chevron">›</span>
        </button>
        <Link to="/settings" className="menu-item glass-card">
          <span>⚙️</span>
          <span>{t('profile.appSettings')}</span>
          <span className="chevron">›</span>
        </Link>
      </section>

      {/* Same dialog behaviour as Home's quick-log panel, from the same
          component (#502). This one previously had no Escape handler at
          all, which is what happens when the behaviour lives in the page:
          one screen gets it and the next one does not. */}
      <Modal
        open={editing}
        onClose={() => setEditing(false)}
        panelClassName="edit-panel"
        title={t('profile.editInfo')}
        onSubmit={submitEdit}
      >
        <div className="avatar-picker">
          {AVATAR_COLORS.map((color) => (
            <button
              key={color}
              type="button"
              className={`avatar-option${avatar === color ? ' selected' : ''}`}
              style={{ background: color }}
              onClick={() => setAvatar(color)}
              aria-label={color}
            />
          ))}
        </div>

        <label>
          {t('profile.name')}
          <input value={name} onChange={(e) => setName(e.target.value)} required />
          {formErrors.name ? <span className="error-text">{formErrors.name}</span> : null}
        </label>

        <label>
          {t('profile.age')}
          <input type="number" value={age} onChange={(e) => setAge(e.target.value)} min={10} max={120} />
          {formErrors.age ? <span className="error-text">{formErrors.age}</span> : null}
        </label>

        <label>
          {t('profile.cycleLength')}
          <input type="number" value={cycleLength} onChange={(e) => setCycleLength(e.target.value)} min={15} max={45} />
          {formErrors.cycle ? <span className="error-text">{formErrors.cycle}</span> : null}
        </label>

        <button type="submit" className="primary-btn full" disabled={saving}>
          {saving ? t('common.loading') : t('profile.saveChanges')}
        </button>
        <button type="button" className="ghost-btn full" onClick={() => setEditing(false)}>
          {t('common.cancel')}
        </button>
      </Modal>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass-card mini-stat">
      <p className="mini-stat-label">{label}</p>
      <p className="mini-stat-value">{value}</p>
    </div>
  );
}
