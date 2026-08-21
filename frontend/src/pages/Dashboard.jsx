/**
 * pages/Dashboard.jsx — PLACEMENT CONTROL CENTER
 * Primary question: "What do I need to apply for RIGHT NOW?"
 */
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getStats, getOpportunities } from '../api/client';
import OpportunityCard from '../components/OpportunityCard';

const URGENCY_SECTIONS = [
  {
    key: 'red',
    urgencies: ['TODAY', 'WITHIN_24H'],
    label: '🔴 DEADLINE TODAY / WITHIN 24H',
    color: 'red',
    empty: 'No urgent deadlines right now!',
  },
  {
    key: 'orange',
    urgencies: ['TOMORROW'],
    label: '🟠 DEADLINE TOMORROW',
    color: 'orange',
    empty: 'Nothing due tomorrow.',
  },
  {
    key: 'yellow',
    urgencies: ['WITHIN_3_DAYS', 'THIS_WEEK'],
    label: '🟡 THIS WEEK',
    color: 'yellow',
    empty: 'Nothing this week.',
  },
  {
    key: 'green',
    urgencies: ['UPCOMING'],
    label: '🟢 UPCOMING',
    color: 'green',
    empty: 'No upcoming opportunities.',
  },
  {
    key: 'gray',
    urgencies: ['NO_DEADLINE'],
    label: '⚪ NO DEADLINE SET',
    color: 'gray',
    empty: '',
  },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showOnlyEligible, setShowOnlyEligible] = useState(false);

  const load = async () => {
    try {
      const [s, o] = await Promise.all([
        getStats(),
        getOpportunities({ limit: 100 }),
      ]);
      setStats(s);
      setOpportunities(o.opportunities || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { 
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleStatusChange = (id, status) => {
    setOpportunities(prev =>
      prev.map(o => o._id === id ? { ...o, status } : o)
    );
    load();
  };

  const activeOpps = opportunities.filter(o =>
    !['APPLIED', 'IGNORED'].includes(o.status) &&
    (!showOnlyEligible || o.eligibility_status === 'ELIGIBLE')
  );

  const getSection = (urgencies) =>
    activeOpps.filter(o => urgencies.includes(o.deadline_urgency));

  if (loading) {
    return (
      <div className="page-container">
        <div className="loading">
          <div className="spinner" />
          <span>Loading placement data...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container fade-in">
      {/* Hero */}
      <div className="page-header">
        <div style={{
          display: 'inline-block',
          background: 'var(--red-soft)',
          border: '1px solid var(--red-border)',
          borderRadius: 'var(--radius-sm)',
          padding: '6px 14px',
          fontSize: '0.72rem',
          fontWeight: 700,
          color: 'var(--red)',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          marginBottom: 12,
        }}>
          Placement Control Center
        </div>
        <h1 className="page-title" style={{ fontSize: '2.2rem' }}>
          What do you need to<br />
          <span style={{ background: 'var(--gradient-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            apply for RIGHT NOW?
          </span>
        </h1>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
          <p className="page-subtitle" style={{ margin: 0 }}>
            AI-monitored placements · Never miss an opportunity
          </p>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', cursor: 'pointer', fontWeight: 600 }}>
            <input 
              type="checkbox" 
              checked={showOnlyEligible} 
              onChange={e => setShowOnlyEligible(e.target.checked)} 
              style={{ width: 16, height: 16 }}
            />
            Show only CSE-Eligible
          </label>
        </div>
      </div>

      {/* Stats Grid */}
      {stats && (
        <div className="stat-grid">
          <div className="stat-card danger" onClick={() => navigate('/opportunities?urgency=TODAY')}>
            <div className="stat-value">{stats.deadline_today || 0}</div>
            <div className="stat-label">Deadline Today</div>
          </div>
          <div className="stat-card warning" onClick={() => navigate('/opportunities?urgency=TOMORROW')}>
            <div className="stat-value">{stats.deadline_tomorrow || 0}</div>
            <div className="stat-label">Tomorrow</div>
          </div>
          <div className="stat-card caution" onClick={() => navigate('/opportunities?urgency=THIS_WEEK')}>
            <div className="stat-value">{(stats.within_3_days || 0) + (stats.this_week || 0)}</div>
            <div className="stat-label">This Week</div>
          </div>
          <div className="stat-card info" onClick={() => navigate('/opportunities')}>
            <div className="stat-value">{stats.not_applied || 0}</div>
            <div className="stat-label">Not Applied</div>
          </div>
          <div className="stat-card success" onClick={() => navigate('/applications')}>
            <div className="stat-value">{stats.applied || 0}</div>
            <div className="stat-label">Applied</div>
          </div>
          <div className="stat-card neutral">
            <div className="stat-value">{stats.active || 0}</div>
            <div className="stat-label">Total Active</div>
          </div>
        </div>
      )}

      {/* Urgency Sections */}
      {URGENCY_SECTIONS.map(section => {
        const sectionOpps = getSection(section.urgencies);
        if (sectionOpps.length === 0) return null;

        return (
          <div className="urgency-section" key={section.key}>
            <div className="urgency-header">
              <div className={`urgency-indicator ${section.color}`} />
              <span className={`urgency-title ${section.color}`}>{section.label}</span>
              <span className="urgency-count">({sectionOpps.length})</span>
            </div>
            <div className="opp-grid">
              {sectionOpps.map(opp => (
                <OpportunityCard
                  key={opp._id}
                  opp={opp}
                  onStatusChange={handleStatusChange}
                />
              ))}
            </div>
          </div>
        );
      })}

      {/* Expired / Missed */}
      {(() => {
        const expired = opportunities.filter(o =>
          o.deadline_urgency === 'EXPIRED' &&
          !['APPLIED', 'IGNORED'].includes(o.status)
        );
        if (!expired.length) return null;
        return (
          <div className="urgency-section">
            <div className="urgency-header">
              <div className="urgency-indicator gray" />
              <span className="urgency-title gray">⚫ POSSIBLE MISSED OPPORTUNITIES</span>
              <span className="urgency-count">({expired.length})</span>
            </div>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: 12 }}>
              Deadline has passed. Not marked as applied — may have been missed.
            </p>
            <div className="opp-grid">
              {expired.map(opp => (
                <OpportunityCard key={opp._id} opp={opp} onStatusChange={handleStatusChange} />
              ))}
            </div>
          </div>
        );
      })()}

      {/* All clear */}
      {activeOpps.length === 0 && (
        <div className="empty-state">
          <div style={{ fontSize: '4rem' }}>🎉</div>
          <h3>All clear!</h3>
          <p>No pending placement opportunities right now.<br />
            Forward messages to your bot or import your Telegram history to get started.</p>
        </div>
      )}
    </div>
  );
}
