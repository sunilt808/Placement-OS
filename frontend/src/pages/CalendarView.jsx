import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Calendar as CalendarIcon, Clock, Briefcase } from 'lucide-react';
import api from '../api/client';

export default function CalendarView() {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchCalendar = async () => {
      try {
        const res = await api.get('/api/opportunities/meta/calendar');
        // Sort events by date
        const sorted = (res.data.events || []).sort((a, b) => new Date(a.date) - new Date(b.date));
        setEvents(sorted);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    fetchCalendar();
  }, []);

  const today = new Date().toISOString().split('T')[0];

  const futureEvents = events.filter(e => e.date >= today);
  const pastEvents = events.filter(e => e.date < today);

  const EventCard = ({ event }) => (
    <div 
      className={`card ${event.date < today ? 'opacity-50' : ''}`}
      style={{ padding: 16, marginBottom: 12, cursor: 'pointer', borderLeft: `4px solid var(--${event.color})` }}
      onClick={() => navigate(`/opportunities/${event.opp_id}`)}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <div style={{ fontWeight: 800, color: '#fff', fontSize: '1.1rem' }}>{event.company}</div>
          <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{event.role}</div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ 
            color: `var(--${event.color})`, 
            background: `rgba(var(--${event.color}-rgb, 255,255,255), 0.1)`, 
            padding: '2px 8px', 
            borderRadius: 12, 
            fontSize: '0.75rem', 
            fontWeight: 700 
          }}>
            {event.type}
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', marginTop: 4 }}>
            {new Date(event.date).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="page-container fade-in">
      <div className="page-header">
        <div className="page-badge">📅 Timeline</div>
        <h1 className="page-title">Placement <span className="gradient-text">Calendar</span></h1>
        <p className="page-subtitle">Track your upcoming deadlines, assessments, and interviews.</p>
      </div>

      {loading ? (
        <div className="loading"><div className="spinner" /><span>Loading calendar...</span></div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32 }}>
          <div>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, color: '#fff' }}>
              <Clock size={20} color="var(--blue)" /> Upcoming Events
            </h3>
            {futureEvents.length === 0 ? (
              <div className="empty-state">No upcoming events scheduled.</div>
            ) : (
              futureEvents.map((e, i) => <EventCard key={i} event={e} />)
            )}
          </div>
          <div>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, color: 'var(--text-muted)' }}>
              <Briefcase size={20} /> Past Events
            </h3>
            {pastEvents.map((e, i) => <EventCard key={i} event={e} />)}
          </div>
        </div>
      )}
    </div>
  );
}
