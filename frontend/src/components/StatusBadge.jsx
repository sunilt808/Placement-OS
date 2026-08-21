/** components/StatusBadge.jsx */
export default function StatusBadge({ status }) {
  const config = {
    NEW:         { label: 'New',         cls: 'badge-new' },
    VIEWED:      { label: 'Viewed',      cls: 'badge-viewed' },
    APPLIED:     { label: '✅ Applied',  cls: 'badge-applied' },
    NOT_APPLIED: { label: 'Not Applied', cls: 'badge-not-applied' },
    IGNORED:     { label: 'Ignored',     cls: 'badge-ignored' },
    EXPIRED:     { label: 'Expired',     cls: 'badge-expired' },
  };
  const { label, cls } = config[status] || { label: status, cls: '' };
  return <span className={`badge ${cls}`}>{label}</span>;
}
