/** components/Timeline.jsx — Opportunity event timeline */
const EVENT_ICONS = {
  CREATED: '🆕',
  DEADLINE_UPDATED: '📅',
  STATUS_CHANGED: '🔄',
  REMINDER_SENT: '🔔',
  UPDATE_RECEIVED: '📨',
  SHORTLISTED: '⭐',
  INTERVIEW_SCHEDULED: '🤝',
};

function fmt(ts) {
  if (!ts) return '';
  return new Date(ts).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit', hour12: true,
    timeZone: 'Asia/Kolkata',
  });
}

export default function Timeline({ events = [] }) {
  if (!events.length) {
    return <p className="text-muted" style={{ fontSize: '0.85rem' }}>No timeline events yet.</p>;
  }
  return (
    <div className="timeline">
      {events.map((e, i) => (
        <div key={i} className="timeline-item">
          <div className="timeline-dot" />
          <div className="timeline-date">{fmt(e.timestamp)}</div>
          <div className="timeline-content">
            <strong>{EVENT_ICONS[e.event_type] || '•'} {e.event_type?.replace(/_/g, ' ')}</strong>
            {e.note && <p style={{ marginTop: 2 }}>{e.note}</p>}
            {e.old_value && e.new_value && (
              <p style={{ marginTop: 2 }}>
                <span style={{ color: 'var(--red)', textDecoration: 'line-through' }}>{e.old_value}</span>
                {' → '}
                <span style={{ color: 'var(--green)' }}>{e.new_value}</span>
              </p>
            )}
            {e.new_value && !e.old_value && (
              <p style={{ marginTop: 2 }}>{e.new_value}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
