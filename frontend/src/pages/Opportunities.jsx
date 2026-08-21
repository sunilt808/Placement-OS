import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Search } from 'lucide-react';
import { getOpportunities } from '../api/client';
import OpportunityCard from '../components/OpportunityCard';

export default function Opportunities() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  
  const [filters, setFilters] = useState({
    search: searchParams.get('search') || '',
    status: searchParams.get('status') || '',
    urgency: searchParams.get('urgency') || '',
  });

  const load = async () => {
    setLoading(true);
    try {
      const data = await getOpportunities({
        search: filters.search || undefined,
        status: filters.status || undefined,
        urgency: filters.urgency || undefined,
        limit: 100
      });
      setOpportunities(data.opportunities || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Sync URL params
    const params = new URLSearchParams();
    if (filters.search) params.set('search', filters.search);
    if (filters.status) params.set('status', filters.status);
    if (filters.urgency) params.set('urgency', filters.urgency);
    setSearchParams(params, { replace: true });
    
    // Debounce search slightly
    const timer = setTimeout(load, 300);
    return () => clearTimeout(timer);
  }, [filters]);

  const handleStatusChange = (id, status) => {
    setOpportunities(prev => prev.map(o => o._id === id ? { ...o, status } : o));
  };

  return (
    <div className="page-container fade-in">
      <div className="page-header">
        <h1 className="page-title">Opportunities</h1>
        <p className="page-subtitle">Search and filter all placement opportunities.</p>
      </div>

      <div className="search-bar">
        <div className="search-input-wrap">
          <Search className="icon" />
          <input 
            type="text" 
            className="search-input" 
            placeholder="Search by company, role, or keyword..."
            value={filters.search}
            onChange={e => setFilters(f => ({ ...f, search: e.target.value }))}
          />
        </div>
        
        <select 
          className="filter-select"
          value={filters.urgency}
          onChange={e => setFilters(f => ({ ...f, urgency: e.target.value }))}
        >
          <option value="">Any Deadline</option>
          <option value="TODAY">🔴 Today</option>
          <option value="WITHIN_24H">🔴 Within 24h</option>
          <option value="TOMORROW">🟠 Tomorrow</option>
          <option value="THIS_WEEK">🟡 This Week</option>
          <option value="UPCOMING">🟢 Upcoming</option>
          <option value="EXPIRED">⚫ Expired</option>
        </select>

        <select 
          className="filter-select"
          value={filters.status}
          onChange={e => setFilters(f => ({ ...f, status: e.target.value }))}
        >
          <option value="">Any Status</option>
          <option value="NEW">New</option>
          <option value="VIEWED">Viewed</option>
          <option value="NOT_APPLIED">Not Applied</option>
          <option value="APPLIED">Applied</option>
          <option value="IGNORED">Ignored</option>
        </select>
      </div>

      {loading ? (
        <div className="loading">
          <div className="spinner" />
          <span>Searching...</span>
        </div>
      ) : (
        <>
          <div className="opp-grid">
            {opportunities.map(opp => (
              <OpportunityCard 
                key={opp._id} 
                opp={opp} 
                onStatusChange={handleStatusChange} 
              />
            ))}
          </div>
          {opportunities.length === 0 && (
            <div className="empty-state">
              <div style={{ fontSize: '3rem', marginBottom: 16 }}>🔍</div>
              <h3>No opportunities found</h3>
              <p>Try adjusting your search or filters.</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
