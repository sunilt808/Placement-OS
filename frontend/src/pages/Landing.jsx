/**
 * pages/Landing.jsx — Public landing page (unauthenticated).
 * Clean dark glassmorphism consistent with the app design system.
 */
import { Link, Navigate } from 'react-router-dom';
import {
  Radar, FileSpreadsheet, FormInput, Image as ImageIcon, BellRing,
  Target, CalendarClock, ShieldCheck, ArrowRight, Sparkles,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const FEATURES = [
  { icon: Radar, title: '24/7 Group Listening', desc: 'A personal Telegram userbot watches your placement group and catches every announcement the moment it drops.' },
  { icon: FileSpreadsheet, title: 'Excel Shortlist Finder', desc: 'Result sheets are scanned locally for YOUR USN — the instant your roll number appears in a shortlist, you get a 🎉 alert.' },
  { icon: Target, title: 'Role-First CSE Engine', desc: 'SDE, FSD, QA, Data Analyst — 150+ CSE-family roles detected even when branches are never mentioned. Unknown roles are never hidden.' },
  { icon: FormInput, title: 'Google Forms Detection', desc: 'Registration forms are auto-flagged so a deadline never passes because the link was buried.' },
  { icon: ImageIcon, title: 'PDF + Image Reading', desc: 'Brochures, JDs and photo posters are read offline — text pulled from documents and screenshots without any paid API.' },
  { icon: BellRing, title: 'Deadline Reminders', desc: '3-day, 24-hour and 3-hour Telegram alerts with Mark Applied / Snooze buttons. Escalates when time runs out.' },
  { icon: CalendarClock, title: 'Urgency Control Center', desc: 'Red / orange / yellow urgency buckets, calendar view and a morning briefing that answers: what do I apply for today?' },
  { icon: ShieldCheck, title: 'Self-Hosted & Private', desc: 'Your data stays on your machine. Local NLP extraction works with zero AI API keys — Gemini is optional, never required.' },
];

export default function Landing() {
  const { token } = useAuth();
  if (token) return <Navigate to="/dashboard" replace />;

  return (
    <div className="landing">
      <style>{`
        .landing { min-height: 100vh; background: var(--bg-primary); color: var(--text-primary);
                   overflow-x: hidden; position: relative; }
        .landing * { box-sizing: border-box; }
        .orb { position: fixed; border-radius: 50%; filter: blur(90px); opacity: .35;
               pointer-events: none; z-index: 0; animation: orbFloat 14s ease-in-out infinite alternate; }
        .orb-a { width: 480px; height: 480px; background: #4f46e5; top: -160px; left: -120px; }
        .orb-b { width: 420px; height: 420px; background: #0891b2; bottom: -140px; right: -100px; animation-delay: -7s; }
        @keyframes orbFloat { from { transform: translate(0,0) scale(1); } to { transform: translate(40px,-30px) scale(1.12); } }

        .l-nav { position: sticky; top: 0; z-index: 10; display:flex; align-items:center; justify-content:space-between;
                 padding: 16px clamp(20px,6vw,64px); backdrop-filter: blur(14px);
                 background: color-mix(in srgb, var(--bg-primary) 70%, transparent);
                 border-bottom: 1px solid var(--border); }
        .l-logo { display:flex; align-items:center; gap:10px; font-weight:800; letter-spacing:.04em; font-size:1.05rem; }
        .l-logo span.grad { background: linear-gradient(90deg,#818cf8,#22d3ee); -webkit-background-clip:text; background-clip:text; color:transparent; }

        .btn-l { display:inline-flex; align-items:center; gap:8px; padding:11px 22px; border-radius:12px; font-weight:700;
                 font-size:.92rem; text-decoration:none; transition: transform .18s ease, box-shadow .18s ease, background .18s ease; }
         .btn-l:hover { transform: translateY(-2px); }
        .btn-primary { background: linear-gradient(90deg,#6366f1,#06b6d4); color:#fff;
                       box-shadow: 0 8px 24px -8px rgba(99,102,241,.55); }
        .btn-primary:hover { box-shadow: 0 14px 30px -8px rgba(99,102,241,.7); }
        .btn-ghost { border:1px solid var(--border); color: var(--text-primary); }
        .btn-ghost:hover { background: var(--bg-secondary); }

        .hero { position:relative; z-index:1; max-width: 980px; margin: 0 auto; padding: clamp(64px,12vh,130px) 24px 70px; text-align:center; }
        .hero-badge { display:inline-flex; align-items:center; gap:8px; padding:8px 16px; border-radius:999px;
                      border:1px solid var(--border); background:var(--bg-secondary); font-size:.8rem; color:var(--text-muted);
                      animation: rise .7s ease both; }
        .hero h1 { font-size: clamp(2.2rem, 6vw, 3.9rem); line-height:1.12; margin: 26px 0 18px; font-weight:850; letter-spacing:-.02em;
                   animation: rise .7s .08s ease both; }
        .grad-text { background: linear-gradient(92deg,#a5b4fc 0%,#67e8f9 55%,#6ee7b7 100%);
                     -webkit-background-clip:text; background-clip:text; color:transparent; }
        .hero p.sub { max-width: 640px; margin: 0 auto 34px; color: var(--text-muted); font-size: 1.06rem; line-height:1.65;
                      animation: rise .7s .16s ease both; }
        .hero-cta { display:flex; gap:14px; justify-content:center; flex-wrap:wrap; animation: rise .7s .24s ease both; }

        .ticker { margin: 54px auto 0; max-width: 720px; padding: 14px 20px; border-radius: 14px;
                  border:1px dashed var(--border); background: var(--bg-secondary); color: var(--text-muted);
                  font-size:.85rem; animation: rise .7s .32s ease both; }
        .ticker b { color:#4ade80; }

        .section { position:relative; z-index:1; max-width:1120px; margin:0 auto; padding: 80px 24px; }
        .section-title { text-align:center; font-size: clamp(1.5rem,3.5vw,2.1rem); font-weight:800; margin-bottom:10px; }
        .section-sub { text-align:center; color:var(--text-muted); margin-bottom:44px; }

        .grid { display:grid; grid-template-columns: repeat(auto-fit,minmax(255px,1fr)); gap:18px; }
        .card { border:1px solid var(--border); background: var(--bg-secondary); border-radius:18px; padding:24px 22px;
                transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease; }
        .card:hover { transform: translateY(-6px); border-color:#6366f166; box-shadow: 0 18px 40px -18px rgba(99,102,241,.35); }
        .card .ic { width:42px;height:42px;border-radius:12px;display:grid;place-items:center;margin-bottom:14px;
                    background:linear-gradient(135deg,rgba(99,102,241,.25),rgba(34,211,238,.18)); color:#93c5fd; }
        .card h3 { font-size:1rem; margin:0 0 8px; }
        .card p { margin:0; color:var(--text-muted); font-size:.86rem; line-height:1.6; }

        .flow { display:flex; flex-wrap:wrap; justify-content:center; align-items:center; gap:12px; margin-top:8px; }
        .flow-step { padding:12px 20px; border-radius:12px; border:1px solid var(--border); background:var(--bg-secondary); font-size:.88rem; }
        .flow-arrow { color:#67e8f9; font-weight:800; }

        footer { position:relative; z-index:1; text-align:center; color:var(--text-muted); font-size:.82rem;
                 padding:36px 20px 46px; border-top:1px solid var(--border); }
        @keyframes rise { from { opacity:0; transform: translateY(22px);} to { opacity:1; transform:none;} }
      `}</style>

      <div className="orb orb-a" /><div className="orb orb-b" />

      <nav className="l-nav">
        <div className="l-logo"><Radar size={20} color="#67e8f9" /> Placement<span className="grad">OS</span></div>
        <Link to="/login" className="btn-l btn-primary">Open Dashboard <ArrowRight size={15} /></Link>
      </nav>

      <header className="hero">
        <div className="hero-badge"><Sparkles size={14} color="#67e8f9" /> Built for one student. Yours.</div>
        <h1>Never miss a placement<br /><span className="grad-text">opportunity again.</span></h1>
        <p className="sub">
          Your college group floods with 100+ messages a day. PlacementOS reads every message,
          PDF, form link, image and result sheet — extracts the drives you qualify for, tracks
          every deadline, and alerts you before it's too late.
        </p>
        <div className="hero-cta">
          <Link to="/login" className="btn-l btn-primary">Get Started — It's Yours</Link>
          <a href="#features" className="btn-l btn-ghost">See What It Does</a>
        </div>
        <div className="ticker">
          📊 Result sheet posted → scanning… <b>SUNIL T · 1DS24CS421 FOUND</b> → 🎉 shortlist alert sent
        </div>
      </header>

      <section className="section" id="features">
        <h2 className="section-title">Everything, handled automatically</h2>
        <p className="section-sub">Local-first intelligence. No paid APIs required for the core loop.</p>
        <div className="grid">
          {FEATURES.map((f, i) => (
            <div className="card" key={f.title} style={{ animation: `rise .6s ${i * 0.07}s ease both` }}>
              <div className="ic"><f.icon size={20} /></div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="section" style={{ paddingTop: 0 }}>
        <h2 className="section-title">How a drive reaches you</h2>
        <div className="flow">
          <span className="flow-step">📨 College posts</span><span className="flow-arrow">→</span>
          <span className="flow-step">🤖 Bot captures msg / PDF / Excel / photo</span><span className="flow-arrow">→</span>
          <span className="flow-step">🧠 Local extraction + role matching</span><span className="flow-arrow">→</span>
          <span className="flow-step">🗂️ One clean drive card</span><span className="flow-arrow">→</span>
          <span className="flow-step">🔔 Deadline alerts till you apply</span>
        </div>
      </section>

      <footer>
        PlacementOS — a self-hosted AI placement monitor · single-user build
      </footer>
    </div>
  );
}
