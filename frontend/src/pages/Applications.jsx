import { useState, useEffect } from 'react';
import { getOpportunities } from '../api/client';
import OpportunityCard from '../components/OpportunityCard';

export default function Applications() {
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showExpired, setShowExpired] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getOpportunities({ status: 'APPLIED', limit: 100 });
        setOpportunities(data.opportunities || []);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleStatusChange = (id, status) => {
    setOpportunities(prev => prev.filter(o => o._id !== id));
  };

  return (
    <div className="page-container fade-in">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 className="page-title">Applied Opportunities</h1>
          <p className="page-subtitle">Track jobs you have successfully applied for.</p>
        </div>
        <button 
          className="btn btn-ghost" 
          onClick={() => setShowExpired(!showExpired)}
          style={{ background: 'var(--bg-tertiary)', fontSize: '0.8rem' }}
        >
          {showExpired ? 'Hide' : 'Show'} Expired Applications
        </button>
      </div>

      {loading ? (
        <div className="loading"><div className="spinner" /></div>
      ) : (
        <>
          <div className="opp-grid">
            {opportunities.filter(o => showExpired || o.deadline_urgency !== 'EXPIRED').map(opp => (
              <OpportunityCard
                key={opp._id}
                opp={opp}
                onStatusChange={handleStatusChange}
              />
            ))}
          </div>
          {opportunities.length === 0 && (
            <div className="empty-state">
              <div style={{ fontSize: '3rem', marginBottom: 16 }}>💼</div>
              <h3>No applications yet</h3>
              <p>When you mark an opportunity as applied, it will appear here.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
