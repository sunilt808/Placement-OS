import { useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import api from '../api/client';

const SUGGESTIONS = [
  'Which deadlines are closest?',
  'Which drives have a Google Form to fill?',
  'Summarize everything I can still apply for.',
  'Which companies am I eligible for?',
];

export default function GeminiPage() {
  const [status, setStatus] = useState({ enabled: false, configured: false });
  const [statusError, setStatusError] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  const loadStatus = () =>
    api.get('/api/gemini/status')
      .then((r) => { setStatus(r.data); setStatusError(false); })
      .catch(() => setStatusError(true));

  useEffect(() => { loadStatus(); }, []);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const toggle = async (enable) => {
    if (toggling) return;
    setToggling(true);
    try {
      const res = await api.post('/api/gemini/toggle', { enabled: enable });
      setStatus((s) => ({ ...s, enabled: res.data?.enabled ?? enable }));
      toast.success(enable ? 'Gemini enabled' : 'Gemini disabled');
    } catch (e) {
      const detail = e?.response?.data?.detail;
      if (!e.response) {
        toast.error('Backend unreachable — is uvicorn running on port 8000?');
      } else if (e.response.status === 401) {
        toast.error('Session expired — please log in again.');
      } else {
        toast.error(detail || 'Toggle failed');
      }
      loadStatus();
    } finally {
      setToggling(false);
    }
  };

  const ask = async (q) => {
    const question = (q ?? input).trim();
    if (!question || busy) return;
    setInput('');
    setMessages((m) => [...m, { role: 'user', text: question }]);
    setBusy(true);
    try {
      const res = await api.post('/api/gemini/chat', { question });
      setMessages((m) => [...m, { role: 'ai', text: res.data.answer }]);
    } catch (e) {
      const detail = e?.response?.data?.detail || '';
      const outOfCredits =
        e?.response?.status === 429 ||
        /quota|429|exhaust|resource.?limit|credit/i.test(detail);
      const busy = e?.response?.status === 503 ||
        /busy|unavailable|high demand|overload/i.test(detail);
      setMessages((m) => [...m, {
        role: 'ai', error: true,
        text: outOfCredits
          ? '⚠️ Gemini credits are used up for now — please try again a little later.'
          : busy
            ? '⏳ Gemini is busy right now (Google-side demand spike) — please try again in a moment.'
            : detail || 'Gemini request failed.',
      }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Gemini Assistant</h1>
          <p className="subtitle">
            Chat with an AI grounded in your live placement data. Fully opt-in.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            className={`btn ${status.enabled ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => toggle(true)}
            disabled={toggling}
          >
            {toggling ? 'Enabling…' : status.enabled ? 'Enabled ✓' : 'Enable'}
          </button>
          <button
            className={`btn ${!status.enabled ? 'btn-danger' : 'btn-ghost'}`}
            onClick={() => toggle(false)}
            disabled={toggling}
          >
            {!toggling && !status.enabled ? 'Disabled ✓' : toggling ? 'Disabling…' : 'Disable'}
          </button>
        </div>
      </div>

      {statusError && (
        <div className="card warn-card" style={{ marginBottom: 16 }}>
          ⚠️ Cannot reach the backend API — restart uvicorn on port 8000 and
          hard-refresh this page (Ctrl+Shift+R).
        </div>
      )}

      {!status.configured && (
        <div className="card warn-card" style={{ marginBottom: 16 }}>
          ⚠️ No <code>GEMINI_API_KEY</code> in backend .env — enable will fail until
          you add one.
        </div>
      )}
      <div className={`card status-strip ${status.enabled ? 'ok' : ''}`}>
        Status: <b>{status.enabled ? 'ENABLED' : 'DISABLED'}</b> · API key:{' '}
        <b>{status.configured ? 'present' : 'missing'}</b>. Nothing is sent to
        Google while disabled.
      </div>

      <div className="card chat-window">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>Ask anything about your tracked drives:</p>
            {SUGGESTIONS.map((s) => (
              <button key={s} className="chip" onClick={() => ask(s)}>{s}</button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg ${m.role} ${m.error ? 'error' : ''}`}>
            {m.text}
          </div>
        ))}
        {busy && <div className="chat-msg ai typing">Thinking…</div>}
        <div ref={endRef} />
      </div>

      <form
        className="chat-input-row"
        onSubmit={(e) => { e.preventDefault(); ask(); }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={status.enabled ? 'Ask Gemini…' : 'Enable Gemini to start chatting'}
          disabled={!status.enabled}
        />
        <button className="btn btn-primary" disabled={!status.enabled || busy}>
          Send
        </button>
      </form>
    </div>
  );
}
