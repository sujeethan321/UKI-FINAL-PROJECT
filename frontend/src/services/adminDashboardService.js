// Purpose: Wrap admin dashboard API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from './api';

// Call GET /admin/overview through the shared client so authentication and API configuration are applied consistently.
export async function getAdminOverview({ signal } = {}) {
  return (await api.get('/admin/overview', { signal })).data;
}

// Call GET /admin/audit-events through the shared client so authentication and API configuration are applied consistently.
export async function getRecentAdminActivity({ signal } = {}) {
  return (await api.get('/admin/audit-events', {
    signal, params: { limit: 5, offset: 0 },
  })).data;
}
