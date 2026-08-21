/**
 * components/OpportunityCard.jsx — Clean, well-structured opportunity card
 */
import { useNavigate } from 'react-router-dom';
import { Clock, ExternalLink, CheckCircle, FileText, Send, Link as LinkIcon } from 'lucide-react';
import UrgencyBadge from './UrgencyBadge';
import StatusBadge from './StatusBadge';
import { updateStatus } from '../api/client';
import toast from 'react-hot-toast';

function formatDeadline(dl) {
  if (!dl) return null;
  return new Date(dl).toLocaleString('en-IN', {
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

const URGENCY_BORDER = {
  TODAY:         'var(--red)',
  WITHIN_24H:    'var(--red)',
  TOMORROW:      'var(--orange)',
  WITHIN_3_DAYS: 'var(--yellow)',
  THIS_WEEK:     'var(--yellow)',
  UPCOMING:      'var(--green)',
  EXPIRED:       'var(--gray)',
  NO_DEADLINE:   'var(--border)',
};

export default function OpportunityCard({ opp, onStatusChange }) {
  const navigate = useNavigate();
  const urgency = opp.deadline_urgency;
  const accentColor = URGENCY_BORDER[urgency] || 'var(--border)';
  const remaining = timeRemaining(opp.deadline);
  const confidence = Math.round((opp.confidence || 0) * 100);
  const companyDisplay = opp.company || 'Unknown Company';
  const isUnknown = !opp.company;

  const handleApply = async (e) => {
    e.stopPropagation();
    try {
      await updateStatus(opp._id, 'APPLIED');
      toast.success(`Marked as Applied: ${companyDisplay}`);
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

  return (
    <div
      className="opp-card fade-in"
      style={{ borderLeft: `3px solid ${accentColor}` }}
      onClick={() => navigate(`/opportunities/${opp._id}`)}
    >
      {/* ── Header ─────────────────────────────────── */}
      <div className="opp-card-header">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div className="opp-company" style={{ color: isUnknown ? 'var(--text-muted)' : 'var(--text-primary)' }}>
              {companyDisplay}
            </div>
            {opp.eligibility_status === 'ELIGIBLE' && <span title="Eligible" style={{ flexShrink: 0 }}>✅</span>}
            {opp.eligibility_status === 'UNCLEAR' && <span title="Unclear" style={{ flexShrink: 0 }}>⚠️</span>}
            {opp.eligibility_status === 'NOT_ELIGIBLE' && <span title="Not Eligible" style={{ flexShrink: 0 }}>❌</span>}
          </div>
          <div className="opp-role">
            {opp.role || <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Role not specified</span>}
          </div>
        </div>
        <StatusBadge status={opp.status} />
      </div>

      {/* ── Key Info Row ─────────────────────────── */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {opp.ctc && (
          <span className="meta-chip ctc">💰 {opp.ctc}</span>
        )}
        {opp.eligible_branches?.slice(0, 3).map(b => (
          <span key={b} className="meta-chip branch">{b}</span>
        ))}
        {opp.cgpa_requirement && (
          <span className="meta-chip">📊 {opp.cgpa_requirement}</span>
        )}
        {opp.skills?.slice(0, 3).map(s => (
          <span key={s} className="meta-chip branch" style={{ color: 'var(--blue)' }}>{s}</span>
        ))}
      </div>

      {/* ── Source Row ───────────────────────────── */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', fontSize: '0.75rem' }}>
        <span className="meta-chip" title="Source Document" style={{ opacity: opp.source_document ? 1 : 0.5 }}>
          <FileText size={10} />
          {opp.source_document || 'No Document'}
        </span>
        <span className="meta-chip" title="Posted on Telegram">
          <Send size={10} />
          {opp.telegram_message_date ? formatDeadline(opp.telegram_message_date) : 'Unknown Date'}
        </span>
        {opp.registration_link ? (
          <a
            href={opp.registration_link}
            target="_blank"
            rel="noreferrer"
            className="meta-chip"
            style={{ color: 'var(--blue)', fontWeight: 600, textDecoration: 'none' }}
            onClick={e => e.stopPropagation()}
          >
            <LinkIcon size={10} /> Apply Link
          </a>
        ) : (
          <span className="meta-chip" style={{ opacity: 0.4 }}>
            <LinkIcon size={10} /> No Link
          </span>
        )}
      </div>

      {/* ── Deadline ─────────────────────────────── */}
      {opp.deadline && (
        <div className="opp-deadline">
          <Clock size={12} style={{ color: accentColor, flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <div className="deadline-label">Deadline</div>
            <div className="deadline-value">{formatDeadline(opp.deadline)}</div>
          </div>
          <div className="deadline-remaining" style={{ color: accentColor }}>
            {remaining}
          </div>
        </div>
      )}

      {/* ── Bottom Row: Urgency + AI Score ────────── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          <UrgencyBadge urgency={urgency} />
          {opp.cse_relevance_score !== undefined && (
            <span className={`badge ${opp.is_cse_relevant ? 'badge-applied' : 'badge-not-applied'}`}>
              {opp.is_cse_relevant ? `✅ CSE ${opp.cse_relevance_score}%` : '❌ Not CSE'}
            </span>
          )}
        </div>
        <span className="confidence" title="Extraction Confidence">AI: {confidence}%</span>
      </div>

      {/* ── Actions ──────────────────────────────── */}
      {opp.status !== 'APPLIED' && opp.status !== 'IGNORED' && (
        <div className="opp-actions" onClick={e => e.stopPropagation()}>
          {opp.registration_link ? (
            <a
              href={opp.registration_link}
              target="_blank"
              rel="noreferrer"
              className="btn btn-primary btn-sm"
              onClick={e => e.stopPropagation()}
            >
              <ExternalLink size={12} /> Apply
            </a>
          ) : (
            <button className="btn btn-ghost btn-sm" disabled style={{ opacity: 0.4, cursor: 'not-allowed' }}>
              No Link
            </button>
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
