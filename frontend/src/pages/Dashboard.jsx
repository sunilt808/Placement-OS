import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import { getStats, getOpportunities } from '../api/client';
import api from '../api/client';
import OpportunityCard from '../components/OpportunityCard';
import { Sparkles, BarChart2, Bell, CheckCircle, Clock, HardDrive } from 'lucide-react';

const URGENCY_SECTIONS = [
  {
    key: 'red',
    urgencies: ['TODAY', 'WITHIN_24H'],
    label: 'CRITICAL: Due Today',
    color: 'red',
    empty: '',
  },
  {
    key: 'orange',
    urgencies: ['TOMORROW'],
    label: 'URGENT: Due Tomorrow',
    color: 'orange',
    empty: '',
  },
  {
    key: 'yellow',
    urgencies: ['WITHIN_3_DAYS', 'THIS_WEEK'],
    label: 'ACTION REQUIRED: This Week',
    color: 'yellow',
    empty: '',
  },
  {
    key: 'green',
    urgencies: ['UPCOMING'],
    label: 'UPCOMING',
    color: 'green',
    empty: '',
  },
  {
    key: 'gray',
    urgencies: ['NO_DEADLINE'],
    label: 'NO DEADLINE SET',
    color: 'gray',
    empty: '',
  },
  {
    key: 'expired',
    urgencies: ['EXPIRED'],
    label: 'EXPIRED & MISSED',
    color: 'gray',
    empty: '',
  }
];

export default function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [briefing, setBriefing] = useState(null);
  const [storage, setStorage] = useState(null);
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showOnlyEligible, setShowOnlyEligible] = useState(false);
  const [showExpired, setShowExpired] = useState(false);
  const knownIds = useRef(null);

  const load = async () => {
    try {
      const [s, o, b, st] = await Promise.all([
        getStats(),
        getOpportunities({ limit: 100 }),
        api.get('/api/opportunities/meta/briefing').then(r => r.data).catch(() => null),
        api.get('/api/storage').then(r => r.data).catch(() => null),
      ]);
      setStats(s);
      setBriefing(b);
      setStorage(st);
      const list = o.opportunities || [];

      if (knownIds.current) {
        const fresh = list.filter((x) => !knownIds.current.has(x._id));
        fresh.slice(0, 3).forEach((opp) =>
          toast.success(
            `🆕 New drive: ${opp.company || 'Unknown company'} — ${opp.role || 'role TBD'}`,
            { duration: 6000 }
          )
        );
        if (fresh.length > 3) toast.success(`🆕 +${fresh.length - 3} more new drives`, { duration: 6000 });
      }
      knownIds.current = new Set(list.map((x) => x._id));
      setOpportunities(list);
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
          <span>Syncing Command Center...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container fade-in">
      {/* ── Premium Hero Section ── */}
      <div className="page-header" style={{ position: 'relative', overflow: 'hidden' }}>
        
        {/* Animated Background Glows */}
        <div style={{ position: 'absolute', top: -50, right: -50, width: 200, height: 200, background: 'var(--blue)', filter: 'blur(100px)', opacity: 0.15, borderRadius: '50%' }} />
        <div style={{ position: 'absolute', bottom: -50, left: 100, width: 300, height: 100, background: 'var(--purple)', filter: 'blur(100px)', opacity: 0.15, borderRadius: '50%' }} />

        <div style={{ position: 'relative', zIndex: 10 }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            background: 'var(--bg-tertiary)', border: '1px solid var(--border-glow)',
            borderRadius: '99px', padding: '6px 16px', fontSize: '0.75rem',
            fontWeight: 700, color: 'var(--text-accent)', letterSpacing: '0.15em',
            textTransform: 'uppercase', marginBottom: 20, boxShadow: 'var(--shadow-sm)'
          }}>
            <Sparkles size={14} style={{ color: 'var(--blue-bright)' }} /> Placement Intelligence Active
          </div>
          
          <h1 className="page-title" style={{ fontSize: '3.5rem', letterSpacing: '-0.03em', marginBottom: 12 }}>
            {briefing ? briefing.greeting : 'Welcome back'}, <span style={{ color: 'white' }}>Sunil.</span>
          </h1>
          <h2 style={{ fontFamily: 'var(--font-sans)', fontSize: '1.4rem', fontWeight: 400, color: 'var(--text-secondary)', marginBottom: 24 }}>
            What do you need to <span style={{ background: 'var(--gradient-primary)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', fontWeight: 800 }}>apply for right now?</span>
          </h2>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
            <p style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8, color: 'var(--blue-bright)', fontWeight: 600, fontSize: '0.9rem', background: 'var(--blue-soft)', padding: '8px 16px', borderRadius: '99px' }}>
              <Bell size={16} /> {briefing ? briefing.message : 'AI is monitoring new drives.'}
            </p>

            <label className="toggle-switch" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', cursor: 'pointer', fontWeight: 700, background: 'var(--bg-card)', padding: '8px 16px', borderRadius: '99px', border: '1px solid var(--border)' }}>
              <input 
                type="checkbox" 
                checked={showOnlyEligible} 
                onChange={e => setShowOnlyEligible(e.target.checked)} 
                style={{ width: 16, height: 16, accentColor: 'var(--emerald-bright)' }}
              />
              Show only CSE-Eligible
            </label>
          </div>
        </div>
      </div>

      {/* ── Glassmorphism Stat Grid ── */}
      {stats && (
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-info">
              <div className="stat-value" style={{ color: 'var(--blue-bright)' }}>{briefing?.new_since_yesterday || 0}</div>
              <div className="stat-label">New Opportunities</div>
            </div>
            <div className="stat-icon blue"><Sparkles size={24} /></div>
          </div>
          
          <div className="stat-card">
            <div className="stat-info">
              <div className="stat-value" style={{ color: 'var(--orange)' }}>{(stats.deadline_today || 0) + (stats.deadline_tomorrow || 0)}</div>
              <div className="stat-label">Urgent Deadlines</div>
            </div>
            <div className="stat-icon orange"><Clock size={24} /></div>
          </div>
          
          <div className="stat-card">
            <div className="stat-info">
              <div className="stat-value">{stats.active}</div>
              <div className="stat-label">Total Active</div>
            </div>
            <div className="stat-icon purple"><BarChart2 size={24} /></div>
          </div>
          
          <div className="stat-card">
            <div className="stat-info">
              <div className="stat-value" style={{ color: 'var(--emerald-bright)' }}>{stats.applied}</div>
              <div className="stat-label">Applications Sent</div>
            </div>
            <div className="stat-icon green"><CheckCircle size={24} /></div>
          </div>
        </div>
      )}

      {/* ── Cloud-Storage Guardian ── */}
      {storage && (
        <div className={`storage-bar ${storage.should_warn ? 'warn' : ''}`}>
          <div className="storage-info">
            <HardDrive size={16} />
            <span>
              Cloud storage: <b>{storage.used_mb} MB</b> / {storage.limit_mb} MB
              {storage.should_warn && ' — cleanup advised (auto-delete runs at 25 days)'}
            </span>
          </div>
          <div className="storage-track">
            <div
              className="storage-fill"
              style={{
                width: `${Math.min(100, storage.percent)}%`,
                background: storage.should_warn
                  ? 'linear-gradient(90deg, var(--orange), #ef4444)'
                  : undefined,
              }}
            />
          </div>
          <span className="storage-pct">{storage.percent}%</span>
        </div>
      )}

      {/* ── Dynamic Urgency Sections ── */}
      <div>
        {URGENCY_SECTIONS.map(section => {
          const sectionOpps = getSection(section.urgencies);
          if (!sectionOpps.length) return null;
          
          if (section.key === 'expired') {
            return (
              <div key="expired-section" className="urgency-section fade-in" style={{ marginTop: 60, opacity: 0.8 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 24 }}>
                  <button 
                    className="btn btn-ghost" 
                    onClick={() => setShowExpired(!showExpired)}
                    style={{ background: 'var(--bg-tertiary)' }}
                  >
                    {showExpired ? 'Hide' : 'Show'} {sectionOpps.length} Expired / Missed Opportunities
                  </button>
                </div>
                
                {showExpired && (
                  <>
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: 16,
                      marginBottom: 24, position: 'relative'
                    }}>
                      <div className={`urgency-indicator ${section.color}`} style={{ width: 12, height: 12 }} />
                      <h3 className={`urgency-title ${section.color}`}>{section.label}</h3>
                      <span className="urgency-count">{sectionOpps.length} missed</span>
                      <div style={{
                        flex: 1, height: 1,
                        background: `linear-gradient(90deg, var(--${section.color}-glow) 0%, transparent 100%)`
                      }} />
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
                  </>
                )}
              </div>
            );
          }

          return (
            <div key={section.key} className="urgency-section fade-in">
              {/* Premium Gradient Divider Header */}
              <div style={{
                display: 'flex', alignItems: 'center', gap: 16,
                marginBottom: 24, position: 'relative'
              }}>
                <div className={`urgency-indicator ${section.color}`} style={{ width: 12, height: 12 }} />
                <h3 className={`urgency-title ${section.color}`}>{section.label}</h3>
                <span className="urgency-count">{sectionOpps.length} pending</span>
                <div style={{
                  flex: 1, height: 1,
                  background: `linear-gradient(90deg, var(--${section.color}-glow) 0%, transparent 100%)`
                }} />
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

        {activeOpps.length === 0 && (
          <div style={{ textAlign: 'center', padding: '60px 20px', background: 'var(--bg-card)', borderRadius: 'var(--radius-xl)', border: '1px dashed var(--border)' }}>
            <CheckCircle size={48} style={{ color: 'var(--emerald)', opacity: 0.5, margin: '0 auto 16px' }} />
            <h3 style={{ fontSize: '1.2rem', color: 'var(--text-primary)' }}>You're all caught up!</h3>
            <p style={{ color: 'var(--text-muted)' }}>No active opportunities match your current filters.</p>
          </div>
        )}
      </div>
    </div>
  );
}
