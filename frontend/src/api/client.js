/**
 * api/client.js — Axios client for backend API.
 */
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

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

  const response = await fetch(`${API_BASE}/api/import/upload`, {
    method: 'POST',
    body: formData,
  });

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
