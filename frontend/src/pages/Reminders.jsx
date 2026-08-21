import { useState, useEffect } from 'react';
import { getReminders } from '../api/client';
import { Bell, Clock } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

function fmt(ts) {
  if (!ts) return '';
  return new Date(ts).toLocaleString('en-IN', {
    day: '2-digit', month: 'short',
    hour: '2-digit', minute: '2-digit', hour12: true,
  });
}

export default function Reminders() {
  const [reminders, setReminders] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getReminders(50);
        setReminders(data.reminders || []);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  return (
    <div className="page-container fade-in">
      <div className="page-header">
        <h1 className="page-title">Upcoming Reminders</h1>
        <p className="page-subtitle">Scheduled Telegram alerts for upcoming deadlines.</p>
      </div>

      {loading ? (
        <div className="loading"><div className="spinner" /></div>
      ) : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          {reminders.length === 0 ? (
            <div className="empty-state">
              <Bell size={48} style={{ color: 'var(--text-muted)', marginBottom: 16 }} />
              <h3>No upcoming reminders</h3>
              <p>When you have active opportunities with deadlines, their reminders will appear here.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {reminders.map((r, i) => (
                <div 
                  key={r._id} 
                  style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    padding: '16px 20px',
                    borderBottom: i < reminders.length - 1 ? '1px solid var(--border)' : 'none',
                    gap: 16,
                    cursor: 'pointer'
                  }}
                  className="nav-item"
                  onClick={() => navigate(`/opportunities/${r.opportunity_id}`)}
                >
                  <div style={{ 
                    background: 'var(--blue-soft)', 
                    color: 'var(--blue)', 
                    padding: 10, 
                    borderRadius: '50%' 
                  }}>
                    <Clock size={20} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{r.company}</div>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{r.role}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                      {r.reminder_type.replace(/_/g, ' ')}
                    </div>
                    <div style={{ fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-primary)' }}>
                      {fmt(r.scheduled_time)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
