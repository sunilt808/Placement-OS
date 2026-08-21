import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ExternalLink, ArrowLeft, Building2, MapPin, DollarSign, Clock, Calendar, CheckCircle } from 'lucide-react';
import { getOpportunity, updateStatus } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import UrgencyBadge from '../components/UrgencyBadge';
import Timeline from '../components/Timeline';
import toast from 'react-hot-toast';

function fmt(ts) {
  if (!ts) return 'Not specified';
  return new Date(ts).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: true,
  });
}

export default function OpportunityDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [opp, setOpp] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await getOpportunity(id);
        setOpp(data);
        if (data.status === 'NEW') {
          await updateStatus(id, 'VIEWED');
        }
      } catch (e) {
        toast.error('Opportunity not found');
        navigate('/opportunities');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id, navigate]);

  const handleStatus = async (status) => {
    try {
      await updateStatus(id, status);
      setOpp(prev => ({ ...prev, status }));
      toast.success(`Status updated to ${status}`);
    } catch {
      toast.error('Failed to update status');
    }
  };

  if (loading) {
    return (
      <div className="page-container loading">
        <div className="spinner" />
      </div>
    );
  }

  if (!opp) return null;

  return (
    <div className="page-container fade-in">
      <button 
        className="btn btn-ghost btn-sm" 
        style={{ marginBottom: 24 }}
        onClick={() => navigate(-1)}
      >
        <ArrowLeft size={14} /> Back
      </button>

      <div className="card" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16 }}>
          <div>
            <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              {opp.company}
              <StatusBadge status={opp.status} />
              <UrgencyBadge urgency={opp.deadline_urgency} />
            </h1>
            <p className="page-subtitle" style={{ fontSize: '1.1rem', marginTop: 8 }}>{opp.role}</p>
          </div>
          
          <div className="opp-actions">
            {opp.registration_link && (
              <a href={opp.registration_link} target="_blank" rel="noreferrer" className="btn btn-primary">
                <ExternalLink size={16} /> Apply Now
              </a>
            )}
            {opp.status !== 'APPLIED' && (
              <button className="btn btn-success" onClick={() => handleStatus('APPLIED')}>
                <CheckCircle size={16} /> Mark Applied
              </button>
            )}
            {opp.status !== 'IGNORED' && (
              <button className="btn btn-ghost" onClick={() => handleStatus('IGNORED')}>
                Ignore
              </button>
            )}
          </div>
        </div>

        <div className="divider" />

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 24, marginBottom: 24 }}>
          <div>
            <div className="text-muted" style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>CTC</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 500 }}>
              <DollarSign size={16} className="text-muted" /> {opp.ctc || 'Not specified'}
            </div>
          </div>
          <div>
            <div className="text-muted" style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>Location</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 500 }}>
              <MapPin size={16} className="text-muted" /> {opp.location || 'Not specified'}
            </div>
          </div>
          <div>
            <div className="text-muted" style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>Deadline</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 500, color: 'var(--red)' }}>
              <Clock size={16} /> {fmt(opp.deadline)}
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 24 }}>
          <div>
            <div className="text-muted" style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>Eligible Branches</div>
            <div style={{ fontWeight: 500 }}>{opp.eligible_branches?.join(', ') || 'Not specified'}</div>
          </div>
          <div>
            <div className="text-muted" style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>Eligible Batch</div>
            <div style={{ fontWeight: 500 }}>{opp.eligible_batch || 'Not specified'}</div>
          </div>
          <div>
            <div className="text-muted" style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>CGPA Requirement</div>
            <div style={{ fontWeight: 500 }}>{opp.cgpa_requirement || 'Not specified'}</div>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 24 }}>
        <div className="card">
          <h3 style={{ fontSize: '1.1rem', marginBottom: 16 }}>AI Summary</h3>
          <p style={{ color: 'var(--text-secondary)' }}>{opp.summary}</p>
          <div style={{ marginTop: 12, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Confidence: {Math.round(opp.confidence * 100)}%
          </div>
          
          <div className="divider" />
          
          <h3 style={{ fontSize: '1.1rem', marginBottom: 16 }}>Dates</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Calendar size={16} className="text-muted" />
              <span className="text-muted" style={{ width: 100 }}>Assessment:</span>
              <span>{fmt(opp.assessment_date)}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Calendar size={16} className="text-muted" />
              <span className="text-muted" style={{ width: 100 }}>Interview:</span>
              <span>{fmt(opp.interview_date)}</span>
            </div>
          </div>
        </div>

        <div className="card">
          <h3 style={{ fontSize: '1.1rem', marginBottom: 16 }}>Opportunity Timeline</h3>
          <Timeline events={opp.timeline} />
        </div>
      </div>
    </div>
  );
}
