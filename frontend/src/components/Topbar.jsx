/**
 * components/Topbar.jsx — Top navigation bar with live notification center.
 * Aggregates new drives (<24h), urgent deadlines and pending reminders into
 * one bell dropdown with an unread badge persisted in localStorage.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Bell, Sparkles, AlarmClock, CalendarClock, CheckCheck } from 'lucide-react';
import { getOpportunities, getReminders } from '../api/client';

const PAGE_TITLES = {
  '/dashboard': 'Command Center',
  '/opportunities': 'All Opportunities',
  '/applications': 'My Applications',
  '/calendar': 'Calendar View',
  '/messages': 'Message Inbox',
  '/reminders': 'Reminders',
  '/settings': 'Settings',
  '/gemini': 'Gemini Assistant',
};

const SEEN_KEY = 'pos_notif_seen';
const DAY_MS = 24 * 60 * 60 * 1000;

export default function Topbar() {
  const location = useLocation();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [seenAt, setSeenAt] = useState(() => Number(localStorage.getItem(SEEN_KEY)) || 0);
  const panelRef = useRef(null);

  const buildItems = useCallback(async () => {
    const out = [];
    try {
      const [oppsData, remData] = await Promise.all([
        getOpportunities({ limit: 50 }),
        getReminders(8).catch(() => ({ reminders: [] })),
      ]);
      const now = Date.now();

      for (const o of oppsData.opportunities || []) {
        const ts = new Date(o.telegram_message_date || o.created_at).getTime();
        if (!Number.isNaN(ts) && now - ts < DAY_MS && !['IGNORED'].includes(o.status)) {
          out.push({
            id: `new:${o._id}`,
            kind: 'new',
            icon: Sparkles,
            tone: '#22d3ee',
            title: o.company || 'Unknown company',
            sub: `New drive · ${o.role || 'role TBD'}`,
            ts,
            to: `/opportunities/${o._id}`,
          });
        }
        if (['TODAY', 'WITHIN_24H', 'TOMORROW'].includes(o.deadline_urgency)
            && !['APPLIED', 'IGNORED', 'EXPIRED'].includes(o.status)) {
          out.push({
            id: `due:${o._id}`,
            kind: 'due',
            icon: AlarmClock,
            tone: o.deadline_urgency === 'TOMORROW' ? '#fb923c' : '#f87171',
            title: o.company || 'Unknown company',
            sub: o.deadline_urgency === 'TOMORROW'
              ? 'Deadline is tomorrow'
              : 'Deadline due within 24 hours',
            ts: new Date(o.deadline).getTime() || ts,
            to: `/opportunities/${o._id}`,
          });
        }
      }

      for (const r of remData.reminders || []) {
        if (!r.scheduled_time) continue;
        out.push({
          id: `rem:${r._id}`,
          kind: 'rem',
          icon: CalendarClock,
          tone: '#a78bfa',
          title: r.company || 'Drive reminder',
          sub: r.role ? `${r.role} · reminder scheduled` : 'Reminder scheduled',
          ts: new Date(r.scheduled_time).getTime(),
          to: '/reminders',
        });
      }

      out.sort((a, b) => b.ts - a.ts);
      setItems(out.slice(0, 12));
    } catch {
      setItems([]);
    }
  }, []);

  useEffect(() => {
    buildItems();
    const iv = setInterval(buildItems, 60000);
    return () => clearInterval(iv);
  }, [buildItems]);

  useEffect(() => {
    if (!open) return;
    const onClick = (e) => {
      if (panelRef.current && !panelRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  const unread = items.filter((i) => i.ts > seenAt).length;

  const markAllRead = () => {
    const now = Date.now() + 1000;
    localStorage.setItem(SEEN_KEY, String(now));
    setSeenAt(now);
  };

  return (
    <header className="topbar">
      <div className="topbar-left">
        <span className="topbar-title">{PAGE_TITLES[location.pathname] || 'PlacementOS'}</span>
        <span className="topbar-live"><span className="pulse-dot" /> Live</span>
      </div>

      <div className="notif-wrap" ref={panelRef}>
        <button
          className={`bell-btn${unread ? ' has-unread' : ''}`}
          aria-label={`Notifications (${unread} unread)`}
          onClick={() => { setOpen((v) => !v); if (!open && unread) markAllRead(); }}
        >
          <Bell size={18} />
          {unread > 0 && <span className="bell-badge">{unread > 9 ? '9+' : unread}</span>}
        </button>

        {open && (
          <div className="notif-panel">
            <div className="notif-head">
              <span>Notifications</span>
              <button className="notif-clear" onClick={markAllRead}>
                <CheckCheck size={13} /> Mark all read
              </button>
            </div>
            <div className="notif-list">
              {items.length === 0 && (
                <div className="notif-empty">Nothing yet — new drives will appear here.</div>
              )}
              {items.map((i) => (
                <button
                  key={i.id}
                  className={`notif-row${i.ts > seenAt ? ' unread' : ''}`}
                  onClick={() => { setOpen(false); navigate(i.to); }}
                >
                  <span className="notif-ic" style={{ color: i.tone }}><i.icon size={15} /></span>
                  <span className="notif-txt">
                    <b>{i.title}</b>
                    <small>{i.sub}</small>
                  </span>
                  <span className="notif-time">
                    {new Date(i.ts).toLocaleString('en-IN', {
                      hour: '2-digit', minute: '2-digit',
                      day: '2-digit', month: 'short', hour12: true,
                    })}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
