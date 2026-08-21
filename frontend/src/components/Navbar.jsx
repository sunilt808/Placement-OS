import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Briefcase, Calendar as CalendarIcon, CheckSquare, Settings, LogOut, ShieldAlert, MessagesSquare } from 'lucide-react';

const NAV_LINKS = [
  { path: '/', label: 'Command Center', icon: LayoutDashboard },
  { path: '/opportunities', label: 'All Opportunities', icon: Briefcase },
  { path: '/applications', label: 'My Applications', icon: CheckSquare },
  { path: '/calendar', label: 'Calendar View', icon: CalendarIcon },
  { path: '/messages', label: 'Message Inbox', icon: MessagesSquare },
];

const SYS_LINKS = [
  { path: '/reminders', label: 'Reminders', icon: ShieldAlert },
  { path: '/settings', label: 'Settings', icon: Settings },
];

export default function Navbar() {
  return (
    <nav className="sidebar">
      <div className="sidebar-brand">
        <h1 style={{ fontFamily: 'var(--font-display)', letterSpacing: '0.05em' }}>Placement Assistant</h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.75rem', fontWeight: 600 }}>AI Tracker System v2.0</p>
      </div>
      
      <div className="sidebar-nav">
        <div className="nav-section-label">Main Navigation</div>
        {NAV_LINKS.map(link => (
          <NavLink 
            key={link.path} 
            to={link.path} 
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            end={link.path === '/'}
          >
            <link.icon className="nav-icon" size={18} />
            {link.label}
          </NavLink>
        ))}

        <div className="nav-section-label" style={{ marginTop: 'auto' }}>System</div>
        {SYS_LINKS.map(link => (
          <NavLink 
            key={link.path} 
            to={link.path} 
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <link.icon className="nav-icon" size={18} />
            {link.label}
          </NavLink>
        ))}
        
        <button className="nav-item" style={{ 
          border: 'none', width: '100%', background: 'transparent', 
          textAlign: 'left', cursor: 'pointer', marginTop: 8 
        }} onClick={() => window.location.reload()}>
          <LogOut className="nav-icon" size={18} />
          Sign Out
        </button>
      </div>
    </nav>
  );
}
