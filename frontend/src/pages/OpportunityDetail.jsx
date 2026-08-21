import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ExternalLink, ArrowLeft, Building2, MapPin, DollarSign,
  Clock, Calendar, CheckCircle, Download, FileText, Send, Zap, Award,
  Link as LinkIcon, Users, BookOpen, Tag
} from 'lucide-react';
import { getOpportunity, getOpportunitySourceDocument, updateStatus } from '../api/client';
import StatusBadge from '../components/StatusBadge';
import UrgencyBadge from '../components/UrgencyBadge';
import Timeline from '../components/Timeline';
import MatchScore from '../components/MatchScore';
import toast from 'react-hot-toast';

function fmt(ts) {
  if (!ts) return null;
  return new Date(ts).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: true,
    timeZone: 'Asia/Kolkata',
  });
}

function InfoRow({ icon: Icon, label, value, highlight }) {
  if (!value) return null;
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 0',
      borderBottom: '1px solid var(--border)',
    }}>
      <Icon size={15} style={{ color: 'var(--text-muted)', flexShrink: 0, marginTop: 2 }} />
      <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', minWidth: 130, flexShrink: 0 }}>
        {label}
      </span>
      <span style={{ fontWeight: 500, color: highlight || 'var(--text-primary)', fontSize: '0.9rem' }}>
        {value}
      </span>
    </div>
  );
}

export default function OpportunityDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [opp, setOpp] = useState(null);
  const [loading, setLoading] = useState(true);

  const downloadSource = async () => {
    try {
      const file = await getOpportunitySourceDocument(id);
      const url = URL.createObjectURL(file);
      const link = document.createElement('a');
      link.href = url;
      link.download = opp.source_document || 'source-document';
      link.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error('The original source document is not available.');
    }
  };

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

  const urgencyColor = {
    TODAY: 'var(--red)', WITHIN_24H: 'var(--red)',
    TOMORROW: 'var(--orange)', WITHIN_3_DAYS: 'var(--yellow)',
    THIS_WEEK: 'var(--yellow)', UPCOMING: 'var(--green)',
    EXPIRED: 'var(--gray)', NO_DEADLINE: 'var(--text-muted)',
  }[opp.deadline_urgency] || 'var(--text-muted)';

  const confidence = Math.round((opp.confidence || 0) * 100);

  return (
    <div className="page-container fade-in">
      {/* Back button */}
      <button
        className="btn btn-ghost btn-sm"
        style={{ marginBottom: 20 }}
        onClick={() => navigate(-1)}
      >
        <ArrowLeft size={14} /> Back to list
      </button>

      {/* ── Hero Card ─────────────────────────────────────────────── */}
      <div className="detail-hero card" style={{ marginBottom: 20 }}>
        {/* Top: company + badges */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
              <StatusBadge status={opp.status} />
              <UrgencyBadge urgency={opp.deadline_urgency} />
              {opp.cse_relevance_score !== undefined && (
                <span className={`badge ${opp.is_cse_relevant ? 'badge-applied' : 'badge-not-applied'}`}>
                  {opp.is_cse_relevant ? `✅ CSE ${opp.cse_relevance_score}%` : '❌ Not CSE'}
                </span>
              )}
            </div>

            <h1 style={{ fontSize: '1.8rem', fontWeight: 800, lineHeight: 1.2, marginBottom: 6 }}>
              {opp.company || <span style={{ color: 'var(--text-muted)' }}>Unknown Company</span>}
            </h1>
            {opp.role && (
              <p style={{ color: 'var(--text-secondary)', fontSize: '1rem', marginBottom: 8 }}>
                {opp.role}
              </p>
            )}

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
              {opp.ctc && (
                <span className="meta-chip ctc" style={{ fontSize: '0.9rem', padding: '4px 10px' }}>
                  💰 {opp.ctc}
                </span>
              )}
              {opp.location && (
                <span className="meta-chip location" style={{ fontSize: '0.9rem', padding: '4px 10px' }}>
                  📍 {opp.location}
                </span>
              )}
              {opp.eligible_branches?.map(b => (
                <span key={b} className="meta-chip branch" style={{ fontSize: '0.9rem', padding: '4px 10px' }}>
                  {b}
                </span>
              ))}
            </div>
          </div>

          {/* Actions */}
          <div className="opp-actions" style={{ flexShrink: 0 }}>
            {opp.registration_link ? (
              <a href={opp.registration_link} target="_blank" rel="noreferrer" className="btn btn-primary">
                <ExternalLink size={15} /> Apply Now
              </a>
            ) : (
              <button className="btn btn-ghost" disabled style={{ opacity: 0.5, cursor: 'not-allowed' }}>
                No Registration Link
              </button>
            )}
            {opp.status !== 'APPLIED' && (
              <button className="btn btn-success" onClick={() => handleStatus('APPLIED')}>
                <CheckCircle size={15} /> Mark Applied
              </button>
            )}
            {opp.status !== 'IGNORED' && (
              <button className="btn btn-ghost" onClick={() => handleStatus('IGNORED')}>
                Ignore
              </button>
            )}
          </div>
        </div>

        {/* Deadline banner if urgent */}
        {opp.deadline && (
          <div style={{
            marginTop: 16, padding: '10px 14px', borderRadius: 'var(--radius-sm)',
            background: urgencyColor === 'var(--red)' ? 'var(--red-soft)' : 'rgba(255,255,255,0.04)',
            border: `1px solid ${urgencyColor}33`,
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <Clock size={14} style={{ color: urgencyColor }} />
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: urgencyColor }}>
              Deadline: {fmt(opp.deadline)}
            </span>
          </div>
        )}
      </div>

      {/* ── Detail Grid ───────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>

        {/* Details Card */}
        <div className="card">
          <h3 style={{ fontSize: '0.875rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-muted)', marginBottom: 14 }}>
            Opportunity Details
          </h3>
          <InfoRow icon={DollarSign} label="CTC / Stipend" value={opp.ctc} highlight="var(--green)" />
          <InfoRow icon={MapPin} label="Location" value={opp.location} />
          <InfoRow icon={Users} label="Eligible Branches" value={opp.eligible_branches?.join(', ')} />
          <InfoRow icon={BookOpen} label="Eligible Batch" value={opp.eligible_batch} />
          <InfoRow icon={Award} label="CGPA Requirement" value={opp.cgpa_requirement} highlight="var(--yellow)" />
          <InfoRow icon={Tag} label="Backlog" value={opp.backlog_requirement} />
          <InfoRow icon={Tag} label="Experience" value={opp.experience_requirement} />
          <InfoRow icon={Calendar} label="Assessment Date" value={fmt(opp.assessment_date)} />
          <InfoRow icon={Calendar} label="Interview Date" value={fmt(opp.interview_date)} />
          {opp.source_document && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
              <FileText size={15} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
              <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', minWidth: 130 }}>Source Document</span>
              <button className="message-download" onClick={downloadSource}><Download size={14} /> {opp.source_document}</button>
            </div>
          )}
          <InfoRow icon={Send} label="Posted on Telegram" value={fmt(opp.telegram_message_date)} />
          <InfoRow icon={LinkIcon} label="Registration Link" value={opp.registration_link ? '🔗 Link Available' : null} />
          {opp.skills?.length > 0 && (
            <div style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <Zap size={15} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', minWidth: 130, flexShrink: 0 }}>Required Skills</span>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {opp.skills.map(s => (
                    <span key={s} className="meta-chip branch" style={{ fontSize: '0.75rem' }}>{s}</span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* AI Intelligence Card */}
        <div className="card">
          <h3 style={{ fontSize: '0.875rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-muted)', marginBottom: 14 }}>
            AI Analysis
          </h3>

          {/* Summary */}
          {opp.summary && (
            <div style={{ marginBottom: 16, padding: '12px 14px', background: 'rgba(255,255,255,0.03)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem', lineHeight: 1.6 }}>
                {opp.summary}
              </p>
            </div>
          )}

          {/* Confidence bar */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: '0.8rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Extraction Confidence</span>
              <span style={{ fontWeight: 700, color: confidence > 75 ? 'var(--green)' : confidence > 50 ? 'var(--yellow)' : 'var(--red)' }}>{confidence}%</span>
            </div>
            <div style={{ height: 6, background: 'var(--border)', borderRadius: 99, overflow: 'hidden' }}>
              <div style={{
                height: '100%', width: `${confidence}%`,
                background: confidence > 75 ? 'var(--green)' : confidence > 50 ? 'var(--yellow)' : 'var(--red)',
                borderRadius: 99, transition: 'width 0.6s ease',
              }} />
            </div>
          </div>

          {/* CSE score */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: '0.8rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>CSE Relevance Score</span>
              <span style={{ fontWeight: 700, color: opp.is_cse_relevant ? 'var(--green)' : 'var(--red)' }}>
                {opp.cse_relevance_score ?? 0}/100
              </span>
            </div>
            <div style={{ height: 6, background: 'var(--border)', borderRadius: 99, overflow: 'hidden' }}>
              <div style={{
                height: '100%', width: `${opp.cse_relevance_score ?? 0}%`,
                background: opp.is_cse_relevant ? 'var(--green)' : 'var(--red)',
                borderRadius: 99, transition: 'width 0.6s ease',
              }} />
            </div>
          </div>

          {/* CSE signals */}
          {opp.jd_cse_signals?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase', marginBottom: 8 }}>
                CSE Signals Found
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {opp.jd_cse_signals.map(s => (
                  <span key={s} className="meta-chip branch">{s}</span>
                ))}
              </div>
            </div>
          )}

          {/* Category */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderTop: '1px solid var(--border)' }}>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Category</span>
            <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--blue)' }}>{opp.category}</span>
          </div>
        </div>

        {/* Eligibility card */}
        {opp.relevance_score !== undefined && (
          <MatchScore score={opp.relevance_score} checks={opp.eligibility_checks} />
        )}

        {/* Timeline card */}
        <div className="card">
          <h3 style={{ fontSize: '0.875rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: 'var(--text-muted)', marginBottom: 14 }}>
            Timeline
          </h3>
          <Timeline events={opp.timeline} />
        </div>
      </div>
    </div>
  );
}
