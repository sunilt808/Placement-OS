import { useState, useEffect } from 'react';
import { getProfile, saveProfile, getSystemStatus, getSystemConfig, saveSystemConfig } from '../api/client';
import toast from 'react-hot-toast';

export default function Settings() {
  const [profile, setProfile] = useState({
    branch: '',
    batch: '',
    cgpa: '',
    min_ctc_lpa: '',
    preferred_locations: '',
    preferred_roles: ''
  });
  const [systemConfig, setSystemConfig] = useState({ catchup_days: 30 });
  const [status, setStatus] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getProfile().then(p => {
      if (p) {
        setProfile({
          ...p,
          cgpa: p.cgpa || '',
          min_ctc_lpa: p.min_ctc_lpa || '',
          preferred_locations: p.preferred_locations?.join(', ') || '',
          preferred_roles: p.preferred_roles?.join(', ') || ''
        });
      }
    });
    getSystemConfig().then(c => {
      if (c) setSystemConfig(c);
    });
    loadStatus();
    const timer = setInterval(loadStatus, 30000);
    return () => clearInterval(timer);
  }, []);

  const loadStatus = () => {
    getSystemStatus().then(setStatus).catch(() => {});
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await saveProfile({
        branch: profile.branch,
        batch: profile.batch,
        cgpa: parseFloat(profile.cgpa) || null,
        min_ctc_lpa: parseFloat(profile.min_ctc_lpa) || null,
        preferred_locations: profile.preferred_locations.split(',').map(s => s.trim()).filter(Boolean),
        preferred_roles: profile.preferred_roles.split(',').map(s => s.trim()).filter(Boolean)
      });
      await saveSystemConfig({ catchup_days: parseInt(systemConfig.catchup_days) || 30 });
      toast.success('Settings saved');
    } catch (e) {
      toast.error('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="page-container fade-in" style={{ maxWidth: 800 }}>
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
        <p className="page-subtitle">Configure your eligibility profile and system settings.</p>
      </div>

      <div className="card" style={{ marginBottom: 32 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h3 style={{ margin: 0 }}>System Status</h3>
          <button className="btn" onClick={loadStatus} style={{ fontSize: '0.8rem' }}>Refresh</button>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          <div style={{ padding: 16, background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
            <div className="text-muted" style={{ fontSize: '0.8rem', textTransform: 'uppercase', marginBottom: 4 }}>Live Listener (Userbot)</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600 }}>
              <div className={`status-dot ${status?.userbot_running ? 'online' : 'offline'}`} />
              {status?.userbot_running ? 'Running' : 'Stopped'}
            </div>
          </div>
          <div style={{ padding: 16, background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
            <div className="text-muted" style={{ fontSize: '0.8rem', textTransform: 'uppercase', marginBottom: 4 }}>Last Heartbeat</div>
            <div style={{ fontWeight: 600 }}>
              {status?.last_message_received
                ? new Date(status.last_message_received).toLocaleString()
                : 'No messages received yet'}
            </div>
          </div>
          <div style={{ padding: 16, background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
            <div className="text-muted" style={{ fontSize: '0.8rem', textTransform: 'uppercase', marginBottom: 4 }}>Database</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600 }}>
              <div className={`status-dot ${status?.db_reachable ? 'online' : 'offline'}`} />
              {status?.db_reachable ? 'Connected' : 'Unreachable'}
            </div>
          </div>
          <div style={{ padding: 16, background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
            <div className="text-muted" style={{ fontSize: '0.8rem', textTransform: 'uppercase', marginBottom: 4 }}>Notifications</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600 }}>
              <div className={`status-dot ${status?.notifications_ready ? 'online' : 'offline'}`} />
              {status?.notifications_ready ? 'Ready' : 'Not configured'}
            </div>
          </div>
        </div>

        {status && !status.notifications_ready && (
          <div style={{ marginTop: 16, padding: 12, background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 'var(--radius-sm)', fontSize: '0.85rem' }}>
            ⚠️ Telegram alerts are not set up. Open your bot in Telegram, press <b>START</b>, then set <code>TELEGRAM_CHAT_ID</code> in the backend environment.
          </div>
        )}
        {status && status.notifications_ready && status.userbot_running && !status.last_message_received && (
          <div style={{ marginTop: 16, padding: 12, background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.3)', borderRadius: 'var(--radius-sm)', fontSize: '0.85rem' }}>
            ⚠️ Listener is running but no messages received yet — the placement group may be quiet.
          </div>
        )}
        {status?.userbot_error && (
          <div style={{ marginTop: 16, padding: 12, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 'var(--radius-sm)', fontSize: '0.85rem' }}>
            ❌ Listener error: {status.userbot_error}
          </div>
        )}

        <div style={{ marginTop: 24, padding: 16, background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)' }}>
          <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 6 }}>
            History Scan Range
          </label>
          <select 
            className="search-input" 
            style={{ width: '100%', maxWidth: 200 }}
            value={systemConfig.catchup_days}
            onChange={e => setSystemConfig(c => ({ ...c, catchup_days: e.target.value }))}
          >
            <option value="30">1 Month</option>
            <option value="15">15 Days</option>
            <option value="10">10 Days</option>
            <option value="7">7 Days</option>
            <option value="3">3 Days</option>
            <option value="2">2 Days</option>
            <option value="1">1 Day</option>
          </select>
          <p className="text-muted" style={{ fontSize: '0.8rem', marginTop: 8 }}>
            How far back to scan Telegram history when the backend starts up.
          </p>
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginBottom: 20 }}>Eligibility Profile</h3>
        <p className="text-muted" style={{ fontSize: '0.85rem', marginBottom: 24 }}>
          This information is used to highlight relevant opportunities. Opportunities are never hidden automatically.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 6 }}>Branch</label>
            <input 
              type="text" 
              className="search-input" 
              placeholder="e.g. CSE"
              value={profile.branch}
              onChange={e => setProfile(p => ({ ...p, branch: e.target.value }))}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 6 }}>Batch</label>
            <input 
              type="text" 
              className="search-input" 
              placeholder="e.g. 2024-2027"
              value={profile.batch}
              onChange={e => setProfile(p => ({ ...p, batch: e.target.value }))}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 6 }}>CGPA</label>
            <input 
              type="number" 
              step="0.1"
              className="search-input" 
              placeholder="e.g. 8.5"
              value={profile.cgpa}
              onChange={e => setProfile(p => ({ ...p, cgpa: e.target.value }))}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 6 }}>Min Preferred CTC (LPA)</label>
            <input 
              type="number" 
              className="search-input" 
              placeholder="e.g. 10"
              value={profile.min_ctc_lpa}
              onChange={e => setProfile(p => ({ ...p, min_ctc_lpa: e.target.value }))}
            />
          </div>
        </div>

        <div style={{ marginBottom: 20 }}>
          <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 6 }}>Preferred Locations (comma separated)</label>
          <input 
            type="text" 
            className="search-input" 
            placeholder="e.g. Bangalore, Hyderabad, Remote"
            value={profile.preferred_locations}
            onChange={e => setProfile(p => ({ ...p, preferred_locations: e.target.value }))}
          />
        </div>

        <div style={{ marginBottom: 32 }}>
          <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: 6 }}>Preferred Roles (comma separated)</label>
          <input 
            type="text" 
            className="search-input" 
            placeholder="e.g. Software Engineer, Data Scientist"
            value={profile.preferred_roles}
            onChange={e => setProfile(p => ({ ...p, preferred_roles: e.target.value }))}
          />
        </div>

        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Profile'}
        </button>
      </div>
    </div>
  );
}
