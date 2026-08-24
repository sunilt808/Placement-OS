/**
 * api/client.js — Axios client for backend API.
 */
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !window.location.pathname.startsWith('/login')) {
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ── Opportunities ─────────────────────────────────────────────────────────────

export const getOpportunities = (params = {}) =>
  api.get('/api/opportunities', { params }).then(r => r.data);

export const getOpportunity = (id) =>
  api.get(`/api/opportunities/${id}`).then(r => r.data);

export const getStats = () =>
  api.get('/api/opportunities/stats').then(r => r.data);

export const updateStatus = (id, status) =>
  api.patch(`/api/opportunities/${id}/status`, { status }).then(r => r.data);

export const getTimeline = (id) =>
  api.get(`/api/opportunities/${id}/timeline`).then(r => r.data);

export const deleteOpportunity = (id) =>
  api.delete(`/api/opportunities/${id}`).then(r => r.data);

export const getMessages = (params = {}) =>
  api.get('/api/opportunities/messages', { params }).then(r => r.data);

export const getMessageAttachment = (id) =>
  api.get(`/api/opportunities/messages/${id}/attachment`, { responseType: 'blob' }).then(r => r.data);

export const getOpportunitySourceDocument = (id) =>
  api.get(`/api/opportunities/${id}/source-document`, { responseType: 'blob' }).then(r => r.data);

// ── Reminders ─────────────────────────────────────────────────────────────────

export const getReminders = (limit = 20) =>
  api.get('/api/reminders', { params: { limit } }).then(r => r.data);

// ── Settings ──────────────────────────────────────────────────────────────────

export const getProfile = () =>
  api.get('/api/settings/profile').then(r => r.data);

export const saveProfile = (profile) =>
  api.post('/api/settings/profile', profile).then(r => r.data);

export const getSystemConfig = () =>
  api.get('/api/settings/system_config').then(r => r.data);

export const saveSystemConfig = (config) =>
  api.post('/api/settings/system_config', config).then(r => r.data);

export const getSystemStatus = () =>
  api.get('/api/settings/system').then(r => r.data);

export const getHealth = () =>
  api.get('/api/health').then(r => r.data);

// ── Import (SSE-based) ────────────────────────────────────────────────────────

export const uploadExport = async (file, onProgress) => {
  const formData = new FormData();
  formData.append('file', file);

  const headers = {};
  const token = localStorage.getItem('token');
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}/api/import/upload`, {
    method: 'POST',
    headers,
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`Import failed: ${response.status} ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let result = {};

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value);
    const lines = text.split('\n').filter(l => l.startsWith('data:'));
    for (const line of lines) {
      try {
        const data = JSON.parse(line.slice(5).trim());
        result = data;
        onProgress(data);
      } catch {}
    }
  }
  return result;
};

export default api;
