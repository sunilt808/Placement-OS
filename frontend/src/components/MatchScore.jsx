/** components/MatchScore.jsx */
import { Check, X, HelpCircle } from 'lucide-react';

export default function MatchScore({ score, checks }) {
  if (score == null) return null;
  
  const fillClass = score >= 80 ? 'high' : score >= 50 ? 'medium' : 'low';
  
  return (
    <div className="card" style={{ padding: '16px 20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h4 style={{ fontSize: '0.85rem', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Match Score</h4>
        <span style={{ fontSize: '1.2rem', fontWeight: 800, color: `var(--${fillClass === 'high' ? 'green' : fillClass === 'medium' ? 'yellow' : 'red'})` }}>
          {score}%
        </span>
      </div>
      
      <div className="match-bar" style={{ marginBottom: 16 }}>
        <div className={`match-fill ${fillClass}`} style={{ width: `${score}%` }} />
      </div>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {checks?.map((check, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem' }}>
            {check.status === 'pass' && <Check size={14} color="var(--green)" />}
            {check.status === 'fail' && <X size={14} color="var(--red)" />}
            {check.status === 'unknown' && <HelpCircle size={14} color="var(--text-muted)" />}
            <span style={{ color: check.status === 'fail' ? 'var(--text-muted)' : 'var(--text-primary)' }}>
              {check.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
