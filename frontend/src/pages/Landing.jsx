/**
 * pages/Landing.jsx — Public landing page (unauthenticated).
 * Animated dark glassmorphism: parallax orbs, scroll reveals,
 * typewriter terminal, spotlight cards and marquee strip.
 */
import { useEffect, useRef } from 'react';
import { Link, Navigate } from 'react-router-dom';
import {
  Radar, FileSpreadsheet, FormInput, Image as ImageIcon, BellRing,
  Target, CalendarClock, ShieldCheck, ArrowRight, Sparkles, Zap,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const FEATURES = [
  { icon: Radar, title: '24/7 Group Monitoring', desc: 'A Telethon userbot persists a live connection to the placement group and back-fills missed history on every restart, so no announcement is ever lost to downtime.' },
  { icon: FileSpreadsheet, title: 'Excel Shortlist Matching', desc: 'Result sheets are parsed cell-by-cell against your USN and name. The moment your roll number appears in a shortlist, an instant alert is dispatched.' },
  { icon: Target, title: 'Role-First CSE Engine', desc: 'A curated taxonomy of 150+ CSE roles — SDE, FSD, QA, Data, DevOps — classifies drives even when branches are never mentioned. Unknown roles are surfaced, never hidden.' },
  { icon: FormInput, title: 'Registration-Form Detection', desc: 'Google Form links are auto-flagged during ingestion so a registration deadline can never slip by buried inside a message thread.' },
  { icon: ImageIcon, title: 'Document Intelligence', desc: 'PDFs, DOCX files and photo posters are read offline through local extraction and OCR — no paid API in the critical path.' },
  { icon: BellRing, title: 'Deadline Escalation', desc: 'Deterministic urgency buckets drive reminders at 3-day, 24-hour and 3-hour marks, each carrying inline Mark Applied / Snooze actions.' },
  { icon: CalendarClock, title: 'Urgency Control Center', desc: 'Red / orange / yellow triage sections, a calendar view and a morning briefing that answers one question: what do I apply for today?' },
  { icon: ShieldCheck, title: 'Self-Hosted & Private', desc: 'Every credential stays in a local .env behind JWT auth. Local NLP handles the core loop; Gemini is strictly opt-in and never required.' },
];

const TICKER_LINES = [
  '$ placementos ingest --source group --live',
  '✓ message captured → hash dedup → passed',
  '✓ result_sheet.xlsx parsed · USN 1DS24CS421 FOUND',
  '🎉 shortlist match → alert dispatched',
  '✓ new drive indexed · Accenture · SDE · due 30 Aug',
];

const STATS = [
  { value: 100, suffix: '+', label: 'messages processed daily' },
  { value: 150, suffix: '+', label: 'roles in CSE taxonomy' },
  { value: 3, suffix: '-tier', label: 'reminder escalation' },
  { value: 0, suffix: '', label: 'paid APIs in core loop' },
];

const MARQUEE = [
  'Telethon userbot', 'Excel shortlists', 'PDF extraction', 'Offline OCR',
  'Form-link flags', 'Deadline reminders', 'Morning briefing',
  'spaCy NLP engine', 'Urgency buckets', 'Calendar view',
];

const STACK = [
  { group: 'Frontend', items: ['React 19', 'Vite', 'React Router', 'Axios', 'Lucide'] },
  { group: 'Backend', items: ['FastAPI', 'Telethon', 'python-telegram-bot', 'APScheduler', 'PyJWT'] },
  { group: 'Intelligence', items: ['spaCy', 'dateparser', 'RapidFuzz', 'Tesseract OCR', 'Gemini (opt-in)'] },
  { group: 'Data', items: ['MongoDB', 'Motor (async)', 'openpyxl', 'PyMuPDF'] },
];

const ENGINEERING = [
  { k: '3-layer dedup', v: 'Content-hash → signature → fuzzy matching collapses repeat posts into one drive with a full event timeline.' },
  { k: 'IST-correct deadlines', v: 'Urgency buckets computed in UTC, rendered in IST; reminders fire at 3-day / 24-hour / 3-hour marks.' },
  { k: 'Streaming import', v: 'Historical Telegram exports ingest over Server-Sent Events with live per-message progress.' },
  { k: 'Fail-closed security', v: 'JWT auth guards every data route; docs endpoints are stripped unless explicitly enabled.' },
];

function Typewriter() {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    let line = 0, char = 0, deleting = false, timer;
    const tick = () => {
      const full = TICKER_LINES[line];
      char += deleting ? -1 : 1;
      if (el) el.textContent = full.slice(0, char);
      let delay = deleting ? 22 : 42;
      if (!deleting && char === full.length) { deleting = true; delay = 2200; }
      else if (deleting && char === 0) { deleting = false; line = (line + 1) % TICKER_LINES.length; delay = 400; }
      timer = setTimeout(tick, delay);
    };
    timer = setTimeout(tick, 600);
    return () => clearTimeout(timer);
  }, []);
  return <span ref={ref} className="type-line" />;
}

export default function Landing() {
  const { token } = useAuth();
  const rootRef = useRef(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) return;

    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add('in-view'); io.unobserve(e.target); }
      }),
      { threshold: 0.15 }
    );
    root.querySelectorAll('.reveal').forEach((el) => io.observe(el));

    const counters = root.querySelectorAll('[data-count]');
    const cio = new IntersectionObserver(
      (entries) => entries.forEach((e) => {
        if (!e.isIntersecting) return;
        cio.unobserve(e.target);
        const target = Number(e.target.dataset.count);
        const t0 = performance.now();
        const step = (t) => {
          const p = Math.min((t - t0) / 1400, 1);
          e.target.textContent = Math.round(target * (1 - Math.pow(1 - p, 3)));
          if (p < 1) requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
      }),
      { threshold: 0.4 }
    );
    counters.forEach((el) => cio.observe(el));

    const onMove = (ev) => {
      const x = (ev.clientX / window.innerWidth - 0.5);
      const y = (ev.clientY / window.innerHeight - 0.5);
      root.style.setProperty('--mx', x.toFixed(3));
      root.style.setProperty('--my', y.toFixed(3));
      root.querySelectorAll('.card').forEach((card) => {
        const r = card.getBoundingClientRect();
        card.style.setProperty('--sx', `${ev.clientX - r.left}px`);
        card.style.setProperty('--sy', `${ev.clientY - r.top}px`);
      });
    };
    window.addEventListener('mousemove', onMove);
    return () => { io.disconnect(); cio.disconnect(); window.removeEventListener('mousemove', onMove); };
  }, []);

  if (token) return <Navigate to="/dashboard" replace />;

  return (
    <div className="landing" ref={rootRef}>
      <style>{`
        .landing { min-height: 100vh; background: var(--bg-primary); color: var(--text-primary);
                   overflow-x: hidden; position: relative; --mx: 0; --my: 0; }
        .landing * { box-sizing: border-box; }

        .bg-grid { position: fixed; inset: 0; z-index: 0; pointer-events: none;
                   background-image: linear-gradient(rgba(99,102,241,.055) 1px, transparent 1px),
                                     linear-gradient(90deg, rgba(99,102,241,.055) 1px, transparent 1px);
                   background-size: 44px 44px;
                   mask-image: radial-gradient(ellipse 90% 60% at 50% 0%, #000 40%, transparent 100%);
                   animation: gridDrift 26s linear infinite; }
        @keyframes gridDrift { from { background-position: 0 0, 0 0; } to { background-position: 44px 88px, 44px 88px; } }

        .orb { position: fixed; border-radius: 50%; filter: blur(95px); opacity: .38;
               pointer-events: none; z-index: 0; will-change: transform; }
        .orb-a { width: 500px; height: 500px; top: -170px; left: -130px;
                 background: radial-gradient(circle at 35% 35%, #6366f1, #4f46e5);
                 transform: translate(calc(var(--mx) * 46px), calc(var(--my) * 46px));
                 transition: transform .35s cubic-bezier(.2,.8,.2,1); }
        .orb-b { width: 440px; height: 440px; bottom: -150px; right: -110px;
                 background: radial-gradient(circle at 60% 60%, #06b6d4, #0891b2);
                 transform: translate(calc(var(--mx) * -34px), calc(var(--my) * -34px));
                 transition: transform .45s cubic-bezier(.2,.8,.2,1); animation: orbPulse 9s ease-in-out infinite; }
        @keyframes orbPulse { 0%,100% { opacity:.34; } 50% { opacity:.5; } }

        .l-nav { position: sticky; top: 0; z-index: 10; display:flex; align-items:center; justify-content:space-between;
                 padding: 16px clamp(20px,6vw,64px); backdrop-filter: blur(16px);
                 background: color-mix(in srgb, var(--bg-primary) 72%, transparent);
                 border-bottom: 1px solid var(--border); animation: navDrop .6s ease both; }
        @keyframes navDrop { from { transform: translateY(-100%); opacity:0;} to { transform:none; opacity:1;} }
        .l-logo { display:flex; align-items:center; gap:10px; font-weight:800; letter-spacing:.04em; font-size:1.05rem; }
        .l-logo svg { animation: spinSlow 10s linear infinite; }
        @keyframes spinSlow { to { transform: rotate(360deg); } }
        .l-logo span.grad { background: linear-gradient(90deg,#818cf8,#22d3ee,#818cf8); background-size:200% auto;
                            -webkit-background-clip:text; background-clip:text; color:transparent;
                            animation: gradSlide 4s linear infinite; }
        @keyframes gradSlide { to { background-position: 200% center; } }

        .btn-l { display:inline-flex; align-items:center; gap:8px; padding:11px 22px; border-radius:12px; font-weight:700;
                 font-size:.92rem; text-decoration:none; position:relative; overflow:hidden;
                 transition: transform .18s ease, box-shadow .18s ease, background .18s ease; }
        .btn-l:hover { transform: translateY(-2px); }
        .btn-l:active { transform: translateY(0) scale(.98); }
        .btn-primary { background: linear-gradient(90deg,#6366f1,#06b6d4); color:#fff;
                       background-size: 160% auto; box-shadow: 0 8px 24px -8px rgba(99,102,241,.55); }
        .btn-primary:hover { background-position: right center; box-shadow: 0 14px 30px -8px rgba(99,102,241,.7); }
        .btn-primary::after { content:''; position:absolute; inset:0;
                              background: linear-gradient(110deg, transparent 30%, rgba(255,255,255,.35) 50%, transparent 70%);
                              transform: translateX(-120%); animation: sheen 3.4s ease-in-out infinite; }
        @keyframes sheen { 0%,55% { transform: translateX(-120%);} 85%,100% { transform: translateX(120%);} }
        .btn-ghost { border:1px solid var(--border); color: var(--text-primary); }
        .btn-ghost:hover { background: var(--bg-secondary); border-color:#6366f188; }

        .hero { position:relative; z-index:1; max-width: 980px; margin: 0 auto; padding: clamp(64px,12vh,130px) 24px 70px; text-align:center; }
        .hero-badge { display:inline-flex; align-items:center; gap:8px; padding:8px 16px; border-radius:999px;
                      border:1px solid var(--border); background:var(--bg-secondary); font-size:.8rem; color:var(--text-muted);
                      animation: rise .7s ease both; }
        .pulse-dot { width:7px; height:7px; border-radius:50%; background:#4ade80; box-shadow:0 0 0 0 rgba(74,222,128,.6);
                     animation: pulseDot 1.8s ease-out infinite; }
        @keyframes pulseDot { 70% { box-shadow: 0 0 0 8px rgba(74,222,128,0);} 100% { box-shadow: 0 0 0 0 rgba(74,222,128,0);} }
        .hero h1 { font-size: clamp(2.2rem, 6vw, 3.9rem); line-height:1.12; margin: 26px 0 18px; font-weight:850; letter-spacing:-.02em;
                   animation: rise .7s .08s ease both; }
        .grad-text { background: linear-gradient(92deg,#a5b4fc 0%,#67e8f9 45%,#6ee7b7 80%,#a5b4fc 100%);
                     background-size: 220% auto; -webkit-background-clip:text; background-clip:text; color:transparent;
                     animation: gradFlow 6s linear infinite; display:inline-block; }
        @keyframes gradFlow { to { background-position: 220% center; } }
        .hero p.sub { max-width: 640px; margin: 0 auto 34px; color: var(--text-muted); font-size: 1.06rem; line-height:1.65;
                      animation: rise .7s .16s ease both; }
        .hero-cta { display:flex; gap:14px; justify-content:center; flex-wrap:wrap; animation: rise .7s .24s ease both; }

        .terminal { margin: 56px auto 0; max-width: 720px; text-align:left; border-radius:14px; overflow:hidden;
                    border:1px solid var(--border); background: color-mix(in srgb, var(--bg-secondary) 88%, transparent);
                    backdrop-filter: blur(8px); box-shadow: 0 24px 60px -30px rgba(0,0,0,.6);
                    animation: rise .7s .32s ease both, floatY 6s ease-in-out 1.2s infinite; }
        @keyframes floatY { 0%,100% { transform: translateY(0);} 50% { transform: translateY(-8px);} }
        .term-bar { display:flex; align-items:center; gap:8px; padding:10px 14px; border-bottom:1px solid var(--border); }
        .term-dot { width:11px; height:11px; border-radius:50%; }
        .term-body { padding:18px 18px 20px; font-family: ui-monospace, 'Cascadia Code', Consolas, monospace;
                     font-size:.88rem; min-height:58px; color:#a5f3fc; }
        .term-prompt { color:#818cf8; margin-right:8px; }
        .caret { display:inline-block; width:9px; height:1.05em; background:#67e8f9; vertical-align:text-bottom;
                 margin-left:3px; animation: blink 1s steps(1) infinite; }
        @keyframes blink { 50% { opacity:0; } }

        .stats-strip { position:relative; z-index:1; max-width:1120px; margin:-10px auto 0; padding: 26px 24px 8px;
                       display:grid; grid-template-columns: repeat(auto-fit,minmax(180px,1fr)); gap:14px; }
        .stat { border:1px solid var(--border); border-radius:16px; padding:20px 16px; text-align:center;
                background: var(--bg-secondary); transition: transform .25s ease, border-color .25s ease; }
        .stat:hover { transform: translateY(-4px); border-color:#22d3ee66; }
        .stat b { font-size:1.9rem; font-weight:850; background:linear-gradient(120deg,#a5b4fc,#67e8f9);
                  -webkit-background-clip:text; background-clip:text; color:transparent; }
        .stat span { display:block; margin-top:6px; color:var(--text-muted); font-size:.82rem; letter-spacing:.03em; }

        .marquee-wrap { position:relative; z-index:1; overflow:hidden; margin: 46px auto 0; max-width:1120px;
                        border-block:1px solid var(--border); padding:13px 0;
                        mask-image: linear-gradient(90deg, transparent, #000 12%, #000 88%, transparent); }
        .marquee { display:flex; gap:38px; width:max-content; animation: marquee 26s linear infinite; }
        .marquee span { color:var(--text-muted); font-size:.84rem; white-space:nowrap; display:flex; align-items:center; gap:38px; }
        .marquee span::after { content:'✦'; color:#67e8f9; font-size:.7rem; }
        @keyframes marquee { to { transform: translateX(-50%); } }

        .section { position:relative; z-index:1; max-width:1120px; margin:0 auto; padding: 80px 24px; }
        .section-title { text-align:center; font-size: clamp(1.5rem,3.5vw,2.1rem); font-weight:800; margin-bottom:10px; }
        .section-sub { text-align:center; color:var(--text-muted); margin-bottom:44px; }

        .grid { display:grid; grid-template-columns: repeat(auto-fit,minmax(255px,1fr)); gap:18px; }
        .card { position:relative; overflow:hidden; border:1px solid var(--border); background: var(--bg-secondary);
                border-radius:18px; padding:24px 22px;
                transition: transform .25s cubic-bezier(.2,.8,.2,1), border-color .25s ease, box-shadow .25s ease; }
        .card::before { content:''; position:absolute; inset:0; border-radius:inherit; pointer-events:none;
                        background: radial-gradient(340px circle at var(--sx,50%) var(--sy,50%), rgba(103,232,249,.09), transparent 65%);
                        opacity:0; transition: opacity .3s ease; }
        .card:hover::before { opacity:1; }
        .card:hover { transform: translateY(-7px); border-color:#6366f166; box-shadow: 0 18px 40px -18px rgba(99,102,241,.4); }
        .card:nth-child(even):hover { border-color:#22d3ee66; box-shadow: 0 18px 40px -18px rgba(34,211,238,.35); }
        .card .ic { width:42px;height:42px;border-radius:12px;display:grid;place-items:center;margin-bottom:14px;
                    background:linear-gradient(135deg,rgba(99,102,241,.25),rgba(34,211,238,.18)); color:#93c5fd;
                    transition: transform .3s ease, color .3s ease; }
        .card:hover .ic { transform: scale(1.14) rotate(-6deg); color:#c4b5fd; }
        .card h3 { font-size:1rem; margin:0 0 8px; }
        .card p { margin:0; color:var(--text-muted); font-size:.86rem; line-height:1.6; }

        .reveal { opacity:0; transform: translateY(30px); transition: opacity .7s cubic-bezier(.2,.8,.2,1), transform .7s cubic-bezier(.2,.8,.2,1); }
        .reveal.in-view { opacity:1; transform:none; }

        .flow { display:flex; flex-wrap:wrap; justify-content:center; align-items:center; gap:12px; margin-top:8px; }
        .flow-step { padding:12px 20px; border-radius:12px; border:1px solid var(--border); background:var(--bg-secondary);
                     font-size:.88rem; transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease;
                     animation: floatY 5s ease-in-out infinite; }
        .flow-step:nth-child(4n+3) { animation-delay: -.9s; } .flow-step:nth-child(4n+5) { animation-delay: -2.1s; }
        .flow-step:nth-child(4n+7) { animation-delay: -3.3s; } .flow-step:nth-child(4n+9) { animation-delay: -4.2s; }
        .flow-step:hover { transform: translateY(-5px) scale(1.04); border-color:#67e8f988;
                           box-shadow: 0 12px 28px -12px rgba(103,232,249,.45); }
        .flow-arrow { color:#67e8f9; font-weight:800; animation: nudgeX 1.4s ease-in-out infinite; }
        @keyframes nudgeX { 0%,100% { transform: translateX(0);} 50% { transform: translateX(5px);} }

        .stack-grid { display:grid; grid-template-columns: repeat(auto-fit,minmax(240px,1fr)); gap:18px; }
        .stack-card { border:1px solid var(--border); background:var(--bg-secondary); border-radius:18px;
                      padding:22px; transition: transform .25s cubic-bezier(.2,.8,.2,1), border-color .25s ease, box-shadow .25s ease; }
        .stack-card:hover { transform: translateY(-5px); border-color:#22d3ee66; box-shadow:0 16px 36px -18px rgba(34,211,238,.35); }
        .stack-group { font-size:.72rem; font-weight:800; letter-spacing:.18em; text-transform:uppercase;
                       color:#67e8f9; margin-bottom:14px; }
        .stack-items { display:flex; flex-wrap:wrap; gap:8px; }
        .stack-chip { font-size:.78rem; padding:6px 12px; border-radius:999px; border:1px solid var(--border);
                      background:color-mix(in srgb, var(--bg-primary) 60%, transparent); color:var(--text-muted);
                      transition: color .2s ease, border-color .2s ease; }
        .stack-chip:hover { color:var(--text-primary); border-color:#818cf8aa; }

        .eng-card .eng-k { font-size:.95rem; font-weight:800; margin-bottom:8px;
                           background:linear-gradient(120deg,#a5b4fc,#67e8f9);
                           -webkit-background-clip:text; background-clip:text; color:transparent; }
        .eng-card .eng-v { margin:0; color:var(--text-muted); font-size:.85rem; line-height:1.65; }

        .cta-final { position:relative; z-index:1; max-width:760px; margin:0 auto; padding: 30px 24px 90px; text-align:center; }
        .cta-box { border:1px solid var(--border); border-radius:22px; padding: clamp(30px,6vw,54px);
                   background: linear-gradient(145deg, rgba(99,102,241,.12), rgba(34,211,238,.07));
                   animation: rise .8s ease both; }
        .cta-box h2 { font-size: clamp(1.5rem,3.4vw,2.1rem); font-weight:850; margin:0 0 12px; }
        .cta-box p { color:var(--text-muted); margin:0 0 26px; }

        footer { position:relative; z-index:1; text-align:center; color:var(--text-muted); font-size:.82rem;
                 padding:36px 20px 46px; border-top:1px solid var(--border); }
        @keyframes rise { from { opacity:0; transform: translateY(22px);} to { opacity:1; transform:none;} }
        @media (prefers-reduced-motion: reduce) { .landing *, .landing *::before, .landing *::after { animation: none !important; transition: none !important; } }
      `}</style>

      <div className="bg-grid" />
      <div className="orb orb-a" /><div className="orb orb-b" />

      <nav className="l-nav">
        <div className="l-logo"><Radar size={20} color="#67e8f9" /> Placement<span className="grad">OS</span></div>
        <Link to="/login" className="btn-l btn-primary">Open Dashboard <ArrowRight size={15} /></Link>
      </nav>

      <header className="hero">
        <div className="hero-badge"><span className="pulse-dot" /> Built for one student. Yours.</div>
        <h1>Never miss a placement<br /><span className="grad-text">opportunity again.</span></h1>
        <p className="sub">
          PlacementOS is a self-hosted intelligence pipeline for campus hiring. It ingests every
          message, PDF, spreadsheet and poster from your college placement group, extracts real
          opportunities with local NLP, tracks every deadline, and alerts you on Telegram —
          before it's too late.
        </p>
        <div className="hero-cta">
          <Link to="/login" className="btn-l btn-primary">Get Started — It's Yours</Link>
          <a
            href="#features"
            className="btn-l btn-ghost"
            onClick={(e) => {
              e.preventDefault();
              document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' });
            }}
          ><Zap size={15} /> See What It Does</a>
        </div>

        <div className="terminal">
          <div className="term-bar">
            <span className="term-dot" style={{ background: '#f87171' }} />
            <span className="term-dot" style={{ background: '#fbbf24' }} />
            <span className="term-dot" style={{ background: '#4ade80' }} />
            <span style={{ marginLeft: 8, fontSize: '.72rem', color: 'var(--text-muted)' }}>placementos · live feed</span>
          </div>
          <div className="term-body">
            <span className="term-prompt">$</span><Typewriter /><span className="caret" />
          </div>
        </div>
      </header>

      <div className="stats-strip">
        {STATS.map((s) => (
          <div className="stat reveal" key={s.label}>
            <b data-count={s.value}>0</b>{s.suffix}
            <span>{s.label}</span>
          </div>
        ))}
      </div>

      <div className="marquee-wrap">
        <div className="marquee">
          {[...MARQUEE, ...MARQUEE].map((m, i) => <span key={i}>{m}</span>)}
        </div>
      </div>

      <section className="section" id="features">
        <h2 className="section-title reveal">Everything, handled automatically</h2>
        <p className="section-sub reveal">Local-first intelligence. The core loop runs with zero paid APIs.</p>
        <div className="grid">
          {FEATURES.map((f, i) => (
            <div className="card reveal" key={f.title} style={{ transitionDelay: `${(i % 4) * 70}ms` }}>
              <div className="ic"><f.icon size={20} /></div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="section" style={{ paddingTop: 0 }}>
        <h2 className="section-title reveal">How a drive reaches you</h2>
        <div className="flow">
          <span className="flow-step">Group post arrives</span><span className="flow-arrow">→</span>
          <span className="flow-step">Userbot captures msg · PDF · Excel · photo</span><span className="flow-arrow">→</span>
          <span className="flow-step">Local extraction + role matching</span><span className="flow-arrow">→</span>
          <span className="flow-step">One clean drive card</span><span className="flow-arrow">→</span>
          <span className="flow-step">Deadline alerts until you apply</span>
        </div>
      </section>

      <section className="section" style={{ paddingTop: 0 }}>
        <h2 className="section-title reveal">Engineering highlights</h2>
        <p className="section-sub reveal">The unglamorous details that make it dependable.</p>
        <div className="stack-grid">
          {ENGINEERING.map((e, gi) => (
            <div className="stack-card eng-card reveal" key={e.k} style={{ transitionDelay: `${gi * 70}ms` }}>
              <div className="eng-k">{e.k}</div>
              <p className="eng-v">{e.v}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="section" style={{ paddingTop: 0 }}>
        <h2 className="section-title reveal">Built with</h2>
        <p className="section-sub reveal">A production-shaped stack: async backend, event-driven ingestion, JWT-secured API.</p>
        <div className="stack-grid">
          {STACK.map((s, gi) => (
            <div className="stack-card reveal" key={s.group} style={{ transitionDelay: `${gi * 70}ms` }}>
              <div className="stack-group">{s.group}</div>
              <div className="stack-items">
                {s.items.map((it) => <span className="stack-chip" key={it}>{it}</span>)}
              </div>
            </div>
          ))}
        </div>
      </section>

      <div className="cta-final">
        <div className="cta-box reveal">
          <h2>Your next drive is already in the group.<br />Don't let it scroll past.</h2>
          <p>Set it up once — PlacementOS watches so you don't have to.</p>
          <Link to="/login" className="btn-l btn-primary"><Sparkles size={15} /> Launch Dashboard</Link>
        </div>
      </div>

      <footer>
        PlacementOS · self-hosted AI placement monitor — FastAPI · React · MongoDB · Telethon
        <br />© {new Date().getFullYear()} · designed, built and operated as a single-user production system
      </footer>
    </div>
  );
}
