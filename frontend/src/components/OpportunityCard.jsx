/**
 * components/OpportunityCard.jsx — Premium Card with Glassmorphism and Hover Reveals
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
  NO_DEADLINE:   'var(--border-strong)',
};

export default function OpportunityCard({ opp, onStatusChange }) {
  const navigate = useNavigate();
  const urgency = opp.deadline_urgency;
  const accentColor = URGENCY_BORDER[urgency] || 'var(--border-strong)';
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
      style={{ '--accent-color': accentColor }}
      onClick={() => navigate(`/opportunities/${opp._id}`)}
    >
      {/* ── Header ─────────────────────────────────── */}
      <div className="opp-card-header">
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div className="opp-company" style={{ color: isUnknown ? 'var(--text-muted)' : 'var(--text-primary)' }}>
              {companyDisplay}
            </div>
            {opp.eligibility_status === 'ELIGIBLE' && <span title="Eligible" style={{ flexShrink: 0, fontSize: '0.8rem' }}>✅</span>}
            {opp.eligibility_status === 'UNCLEAR' && <span title="Unclear" style={{ flexShrink: 0, fontSize: '0.8rem' }}>⚠️</span>}
            {opp.eligibility_status === 'NOT_ELIGIBLE' && <span title="Not Eligible" style={{ flexShrink: 0, fontSize: '0.8rem' }}>❌</span>}
          </div>
          <div className="opp-role">
            {opp.role || <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>Role not specified</span>}
            {opp.role_class && ['CSE_BOTH', 'CSE_ROLE'].includes(opp.role_class) && (
              <span title={opp.role_class_reason || 'CSE role match'} style={{
                marginLeft: 8, fontSize: '0.65rem', padding: '2px 6px', borderRadius: 6,
                background: 'rgba(34,197,94,0.15)', color: '#4ade80', fontWeight: 700,
              }}>
                CSE ROLE ✓
              </span>
            )}
            {opp.has_registration_form && (
              <span title="Google Form registration link found" style={{
                marginLeft: 6, fontSize: '0.65rem', padding: '2px 6px', borderRadius: 6,
                background: 'rgba(59,130,246,0.15)', color: '#60a5fa', fontWeight: 700,
              }}>
                📝 FORM
              </span>
            )}
          </div>
        </div>
        <StatusBadge status={opp.status} />
      </div>

      {/* ── Key Info Row ─────────────────────────── */}
      <div className="opp-meta-row">
        {opp.ctc && (
          <span className="meta-chip ctc">💰 {opp.ctc}</span>
        )}
        {opp.eligible_branches?.slice(0, 3).map(b => (
          <span key={b} className="meta-chip branch">{b}</span>
        ))}
        {opp.cgpa_requirement && (
          <span className="meta-chip">📊 {opp.cgpa_requirement}</span>
        )}
      </div>

      {/* ── Source Row ───────────────────────────── */}
      <div className="opp-meta-row" style={{ fontSize: '0.75rem' }}>
        {opp.source_document && (
          <span className="meta-chip source-document-chip" title={opp.source_document}>
            <FileText size={12} style={{ color: 'var(--text-muted)' }} />
            <span>{opp.source_document}</span>
          </span>
        )}
        <span className="meta-chip posted-date-chip" title="Posted on Telegram">
          <Send size={12} style={{ color: 'var(--blue)' }} />
          {opp.telegram_message_date ? formatDeadline(opp.telegram_message_date) : 'Unknown Date'}
        </span>
      </div>

      {/* ── Deadline ─────────────────────────────── */}
      {opp.deadline && (
        <div className="opp-deadline-box" style={{ borderColor: `${accentColor}33` }}>
          <Clock size={16} style={{ color: accentColor, flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <div className="deadline-label">Deadline</div>
            <div className="deadline-value">{formatDeadline(opp.deadline)}</div>
          </div>
          <div className="deadline-remaining" style={{ color: accentColor }}>
            {remaining}
          </div>
        </div>
      )}
      {!opp.deadline && (
        <div className="opp-no-deadline"><Clock size={14} /> No deadline shared</div>
      )}

      {/* ── Actions / Bottom Row ─────────────────── */}
      <div className="opp-actions-row">
        <div className="opp-score-group">
          <UrgencyBadge urgency={urgency} />
          {opp.cse_relevance_score !== undefined && (
            <span className={`badge ${opp.is_cse_relevant ? 'badge-applied' : 'badge-not-applied'}`}>
              {opp.is_cse_relevant ? `✅ CSE ${opp.cse_relevance_score}%` : '❌ Not CSE'}
            </span>
          )}
          <span className="confidence" title="Extraction Confidence">AI: {confidence}%</span>
        </div>

        {opp.status !== 'APPLIED' && opp.status !== 'IGNORED' && (
          <div className="opp-buttons" onClick={e => e.stopPropagation()}>
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
            ) : null}
            <button className="btn btn-success btn-sm" onClick={handleApply}>
              <CheckCircle size={12} /> Applied
            </button>
            <button className="btn btn-ghost btn-sm" onClick={handleIgnore}>Ignore</button>
          </div>
        )}
      </div>
    </div>
  );
}
