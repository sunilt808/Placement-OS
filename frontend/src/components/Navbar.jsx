/**
 * components/Navbar.jsx — Left sidebar navigation
 */
import { NavLink, useLocation } from 'react-router-dom';
import { useState, useEffect } from 'react';
import {
  LayoutDashboard, Briefcase, Upload, Bell, CheckCircle2,
  Settings, Zap, Activity
} from 'lucide-react';
import { getStats, getHealth } from '../api/client';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/opportunities', icon: Briefcase, label: 'Opportunities' },
  { to: '/applications', icon: CheckCircle2, label: 'Applications' },
  { to: '/reminders', icon: Bell, label: 'Reminders' },
  { to: '/import', icon: Upload, label: 'Import' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export default function Navbar() {
  const [stats, setStats] = useState({});
  const [health, setHealth] = useState({ userbot_running: false });

  useEffect(() => {
    const load = async () => {
      try {
        const s = await getStats();
        setStats(s);
      } catch {}
      try {
        const h = await getHealth();
        setHealth(h);
      } catch {}
    };
    load();
    const interval = setInterval(load, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h1>🎯 AI Placement<br />Monitor</h1>
        <p>Placement Control Center</p>
      </div>

      <nav className="sidebar-nav">
        <div className="nav-section-label">Navigation</div>
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <Icon size={16} />
            {label}
            {label === 'Opportunities' && stats.not_applied > 0 && (
              <span className="nav-badge">{stats.not_applied}</span>
            )}
            {label === 'Dashboard' && stats.deadline_today > 0 && (
              <span className="nav-badge">{stats.deadline_today}</span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="system-status">
          <div className={`status-dot ${health.userbot_running ? 'online' : 'offline'}`} />
          <span>
            {health.userbot_running ? 'Listening live' : 'Userbot offline'}
          </span>
        </div>
      </div>
    </aside>
  );
}
