/** components/UrgencyBadge.jsx */
export default function UrgencyBadge({ urgency }) {
  const config = {
    TODAY:        { label: '🔴 Today',      cls: 'badge-urgency-today' },
    WITHIN_24H:   { label: '🔴 <24h',       cls: 'badge-urgency-today' },
    TOMORROW:     { label: '🟠 Tomorrow',   cls: 'badge-urgency-tomorrow' },
    WITHIN_3_DAYS:{ label: '🟡 3 Days',    cls: 'badge-urgency-week' },
    THIS_WEEK:    { label: '🟡 This Week',  cls: 'badge-urgency-week' },
    UPCOMING:     { label: '🟢 Upcoming',   cls: 'badge-urgency-upcoming' },
    EXPIRED:      { label: '⚫ Expired',     cls: 'badge-urgency-expired' },
    NO_DEADLINE:  { label: '⚪ No Deadline', cls: '' },
  };
  const { label, cls } = config[urgency] || { label: urgency, cls: '' };
  return <span className={`badge ${cls}`}>{label}</span>;
}
