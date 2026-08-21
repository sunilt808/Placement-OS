/**
 * components/OpportunityCard.jsx — Placement opportunity card
 */
import { useNavigate } from 'react-router-dom';
import { MapPin, DollarSign, Clock, ExternalLink, CheckCircle } from 'lucide-react';
import UrgencyBadge from './UrgencyBadge';
import StatusBadge from './StatusBadge';
import { updateStatus } from '../api/client';
import toast from 'react-hot-toast';

const URGENCY_CARD_CLASS = {
  TODAY:         'urgency-red',
  WITHIN_24H:    'urgency-red',
  TOMORROW:      'urgency-orange',
  WITHIN_3_DAYS: 'urgency-yellow',
  THIS_WEEK:     'urgency-yellow',
  UPCOMING:      'urgency-green',
};

function formatDeadline(dl) {
  if (!dl) return null;
  const d = new Date(dl);
  return d.toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: true,
    timeZone: 'Asia/Kolkata',
  });
}

function timeRemaining(dl) {
  if (!dl) return null;
  const diff = new Date(dl) - new Date();
  if (diff <= 0) return 'Expired';
  const d = Math.floor(diff / 86400000);
  const h = Math.floor((diff % 86400000) / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  if (d > 0) return `${d}d ${h}h left`;
  if (h > 0) return `${h}h ${m}m left`;
  return `${m}m left`;
}

export default function OpportunityCard({ opp, onStatusChange }) {
  const navigate = useNavigate();
  const urgency = opp.deadline_urgency;
  const cardClass = URGENCY_CARD_CLASS[urgency] || '';

  const handleApply = async (e) => {
    e.stopPropagation();
    try {
      await updateStatus(opp._id, 'APPLIED');
      toast.success(`Marked as Applied: ${opp.company}`);
      onStatusChange && onStatusChange(opp._id, 'APPLIED');
    } catch {
      toast.error('Failed to update status');
    }
  };

  const handleIgnore = async (e) => {
    e.stopPropagation();
    try {
      await updateStatus(opp._id, 'IGNORED');
      toast.success('Opportunity ignored');
      onStatusChange && onStatusChange(opp._id, 'IGNORED');
    } catch {
      toast.error('Failed to update');
    }
  };

  const remaining = timeRemaining(opp.deadline);
  const confidence = Math.round((opp.confidence || 0) * 100);

  return (
    <div
      className={`opp-card ${cardClass} fade-in`}
      onClick={() => navigate(`/opportunities/${opp._id}`)}
    >
      {/* Header */}
      <div className="opp-card-header">
        <div>
          <div className="opp-company">
            {opp.company || 'Unknown Company'}
            {opp.eligibility_status === 'ELIGIBLE' && <span title="Eligible" style={{ marginLeft: 6 }}>✅</span>}
            {opp.eligibility_status === 'UNCLEAR' && <span title="Unclear Eligibility" style={{ marginLeft: 6 }}>⚠️</span>}
            {opp.eligibility_status === 'NOT_ELIGIBLE' && <span title="Not Eligible" style={{ marginLeft: 6 }}>❌</span>}
          </div>
          <div className="opp-role">{opp.role || 'Role not specified'}</div>
        </div>
        <StatusBadge status={opp.status} />
      </div>

      {/* Meta chips */}
      <div className="opp-meta">
        {opp.ctc && (
          <span className="meta-chip ctc">
            <DollarSign size={10} />
            {opp.ctc}
          </span>
        )}
        {opp.location && (
          <span className="meta-chip location">
            <MapPin size={10} />
            {opp.location}
          </span>
        )}
        {opp.eligible_branches?.slice(0, 2).map(b => (
          <span key={b} className="meta-chip branch">{b}</span>
        ))}
        {opp.cgpa_requirement && (
          <span className="meta-chip">CGPA {opp.cgpa_requirement}</span>
        )}
      </div>

      {/* Deadline */}
      {opp.deadline && (
        <div className="opp-deadline">
          <Clock size={13} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <div className="deadline-label">Deadline</div>
            <div className="deadline-value">{formatDeadline(opp.deadline)}</div>
          </div>
          <div className="deadline-remaining" style={{
            color: urgency === 'TODAY' || urgency === 'WITHIN_24H' ? 'var(--red)'
              : urgency === 'TOMORROW' ? 'var(--orange)'
              : urgency === 'WITHIN_3_DAYS' || urgency === 'THIS_WEEK' ? 'var(--yellow)'
              : 'var(--green)'
          }}>
            {remaining}
          </div>
        </div>
      )}

      {/* Urgency + confidence row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <UrgencyBadge urgency={urgency} />
        <span className="confidence">AI: {confidence}%</span>
      </div>

      {/* Actions */}
      {opp.status !== 'APPLIED' && opp.status !== 'IGNORED' && (
        <div className="opp-actions" onClick={e => e.stopPropagation()}>
          {opp.registration_link && (
            <a
              href={opp.registration_link}
              target="_blank"
              rel="noreferrer"
              className="btn btn-primary btn-sm"
              onClick={e => e.stopPropagation()}
            >
              <ExternalLink size={12} /> Apply
            </a>
          )}
          <button className="btn btn-success btn-sm" onClick={handleApply}>
            <CheckCircle size={12} /> Mark Applied
          </button>
          <button className="btn btn-ghost btn-sm" onClick={handleIgnore}>
            Ignore
          </button>
        </div>
      )}
    </div>
  );
}
