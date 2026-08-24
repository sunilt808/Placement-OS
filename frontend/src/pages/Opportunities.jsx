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
    category: searchParams.get('category') || '',
    eligibility: searchParams.get('eligibility') || '',
    role_class: searchParams.get('role_class') || '',
    forms_only: searchParams.get('forms_only') === 'true',
    days: searchParams.get('days') || '',
    cse_only: searchParams.get('cse_only') === 'true',
  });

  const load = async () => {
    setLoading(true);
    try {
      const data = await getOpportunities({
        search: filters.search || undefined,
        status: filters.status || undefined,
        urgency: filters.urgency || undefined,
        category: filters.category || undefined,
        eligibility: filters.eligibility || undefined,
        role_class: filters.role_class || undefined,
        forms_only: filters.forms_only || undefined,
        days: filters.days || undefined,
        cse_only: filters.cse_only || undefined,
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
    if (filters.category) params.set('category', filters.category);
    if (filters.eligibility) params.set('eligibility', filters.eligibility);
    if (filters.role_class) params.set('role_class', filters.role_class);
    if (filters.forms_only) params.set('forms_only', 'true');
    if (filters.days) params.set('days', filters.days);
    if (filters.cse_only) params.set('cse_only', 'true');
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
          value={filters.category}
          onChange={e => setFilters(f => ({ ...f, category: e.target.value }))}
        >
          <option value="">Any Type</option>
          <option value="PLACEMENT_OPPORTUNITY">New opportunity</option>
          <option value="PLACEMENT_UPDATE">Placement update</option>
          <option value="DEADLINE_UPDATE">Deadline update</option>
          <option value="ASSESSMENT">Assessment</option>
          <option value="INTERVIEW">Interview</option>
          <option value="SHORTLIST">Shortlist</option>
          <option value="NEEDS_REVIEW">Needs review</option>
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

        <select 
          className="filter-select"
          value={filters.days}
          onChange={e => setFilters(f => ({ ...f, days: e.target.value }))}
        >
          <option value="">Any Date</option>
          <option value="1">Last 24 Hours</option>
          <option value="2">Last 2 Days</option>
          <option value="3">Last 3 Days</option>
          <option value="7">Last 7 Days</option>
          <option value="10">Last 10 Days</option>
          <option value="15">Last 15 Days</option>
          <option value="30">Last 30 Days</option>
        </select>

        <select 
          className="filter-select"
          value={filters.eligibility}
          onChange={e => setFilters(f => ({ ...f, eligibility: e.target.value }))}
        >
          <option value="">Any Eligibility</option>
          <option value="ELIGIBLE">✅ Eligible</option>
          <option value="UNCLEAR">⚠️ Unclear</option>
          <option value="NOT_ELIGIBLE">❌ Not Eligible</option>
        </select>

        <select
          className="filter-select"
          value={filters.role_class}
          onChange={e => setFilters(f => ({ ...f, role_class: e.target.value }))}
        >
          <option value="">Any Role Match</option>
          <option value="CSE_BOTH">🎯 CSE Role + Branch</option>
          <option value="CSE_ROLE">✅ CSE Role (SDE/FSD/QA/Data…)</option>
          <option value="CSE_BRANCH">🟡 CSE/ISE Branch Only</option>
          <option value="UNKNOWN">❓ Unknown Role</option>
          <option value="NOT_CSE">⚪ Non-CSE Roles</option>
        </select>

        <label className="toggle-switch" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.875rem', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={filters.forms_only}
            onChange={e => setFilters(f => ({ ...f, forms_only: e.target.checked }))}
            style={{ accentColor: 'var(--blue)' }}
          />
          📝 Form Drives
        </label>

        <label className="toggle-switch" style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.875rem', cursor: 'pointer' }}>
          <input 
            type="checkbox" 
            checked={filters.cse_only}
            onChange={e => setFilters(f => ({ ...f, cse_only: e.target.checked }))}
            style={{ accentColor: 'var(--blue)' }}
          />
          CSE Only
        </label>
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
