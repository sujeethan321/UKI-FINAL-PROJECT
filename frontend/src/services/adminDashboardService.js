import api from './api';

export async function getAdminOverview({ signal } = {}) {
  return (await api.get('/admin/overview', { signal })).data;
}

export async function getRecentAdminActivity({ signal } = {}) {
  return (await api.get('/admin/audit-events', {
    signal, params: { limit: 5, offset: 0 },
  })).data;
}
