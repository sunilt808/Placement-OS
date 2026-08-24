import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import api from '../api/client';
import { Lock, User, Key, ShieldCheck } from 'lucide-react';
import toast from 'react-hot-toast';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [securityCode, setSecurityCode] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const data = await api.post('/api/auth/login', {
        username,
        password,
        security_code: securityCode,
      }).then(r => r.data);

      login(data.access_token, data.user);
      toast.success(`Welcome back, ${data.user?.username || 'Sunil'}!`);
      navigate('/dashboard');
    } catch (e) {
      toast.error(e.response?.data?.detail || e.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', padding: 20 }}>
      <div className="card fade-in" style={{ width: '100%', maxWidth: 400, textAlign: 'center' }}>
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
          <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'var(--blue-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--blue)' }}>
            <ShieldCheck size={32} />
          </div>
        </div>
        <h2 style={{ marginBottom: 8, color: '#fff' }}>PlacementOS</h2>
        <p className="text-muted" style={{ marginBottom: 32 }}>Secure Admin Login</p>
        
        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={{ position: 'relative' }}>
            <User size={18} style={{ position: 'absolute', left: 16, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Username"
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
              style={{ width: '100%', padding: '12px 12px 12px 44px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', borderRadius: 8, color: '#fff', outline: 'none' }}
            />
          </div>
          <div style={{ position: 'relative' }}>
            <Lock size={18} style={{ position: 'absolute', left: 16, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              style={{ width: '100%', padding: '12px 12px 12px 44px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', borderRadius: 8, color: '#fff', outline: 'none' }}
            />
          </div>
          <div style={{ position: 'relative' }}>
            <Key size={18} style={{ position: 'absolute', left: 16, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              type="password"
              placeholder="Security Code (5-digit)"
              value={securityCode}
              onChange={e => setSecurityCode(e.target.value)}
              maxLength={5}
              required
              style={{ width: '100%', padding: '12px 12px 12px 44px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', borderRadius: 8, color: '#fff', outline: 'none', letterSpacing: '2px' }}
            />
          </div>
          <button type="submit" className="btn btn-primary" style={{ marginTop: 8, width: '100%' }} disabled={loading}>
            {loading ? 'Authenticating...' : 'Secure Login'}
          </button>
        </form>
      </div>
    </div>
  );
}
