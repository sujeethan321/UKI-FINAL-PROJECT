// Purpose: Wrap admin management API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from './api';
import { getAdminBusinesses, getAdminBusinessDetails, decideAdminBusiness, getAdminBusinessAuditHistory } from './adminBusinessService';
import { getAdminOverview } from './adminDashboardService';
const roles = ['shop_owner', 'customer', 'driver', 'business'];
// Resolve the management endpoint for the supported resource area.
const target = value => { if (!Number.isSafeInteger(value) || value <= 0) throw Error('Invalid target'); return value; };
// Check the requested document kind before using its download response.
const kindCheck = kind => { if (!roles.includes(kind)) throw Error('Invalid management area'); };
export const adminManagementApi = {
  // Load the current resource list using this reader state.
  async list(kind, filters, { signal } = {}) {
    kindCheck(kind);
    const { q, status, approval_status, offset } = filters;
    if (kind === 'business') return getAdminBusinesses(status || 'all', { limit: 10, offset, q, signal });
    return (await api.get(kind === 'driver' ? '/admin/drivers' : '/admin/users', { signal, params: {
      limit: 10, offset, ...(kind !== 'driver' ? { role: kind } : {}), ...(q ? { q } : {}), ...(status ? { status } : {}), ...(kind === 'driver' && approval_status ? { approval_status } : {}),
    } })).data;
  },
  // Load the selected record detail within the current resource context.
  async detail(kind, id, { signal } = {}) {
    kindCheck(kind); target(id);
    if (kind === 'business') return getAdminBusinessDetails(id, { signal });
    return (await api.get(`/admin/${kind === 'driver' ? 'drivers' : 'users'}/${id}`, { signal })).data;
  },
  // Load associations for the selected customer resource.
  async associations(id, offset, { signal } = {}) {
    return (await api.get(`/admin/users/${target(id)}/businesses`, { signal, params: { limit: 10, offset } })).data;
  },
  // Read the history associated with the current resource selection.
  history(id, { signal } = {}) { return getAdminBusinessAuditHistory(target(id), { signal, limit: 10, offset: 0 }); },
  overview: getAdminOverview,
  // Route a resource change through the workflow pending and error handling.
  async mutate(kind, operation, { signal } = {}) {
    kindCheck(kind); const { id, action, text } = operation; target(id);
    if (['suspend', 'reactivate'].includes(action) && kind !== 'business') return (await api.patch(`/admin/users/${id}/status`, { account_status: action === 'suspend' ? 'suspended' : 'active', reason: text }, { signal })).data;
    if (!['approve', 'reject'].includes(action) || !['driver', 'business'].includes(kind)) throw Error('Unsupported action');
    if (kind === 'business') return decideAdminBusiness(id, action, text || null, { signal });
    return (await api.patch(`/admin/drivers/${id}/decision`, { decision: action, review_note: text || null }, { signal })).data;
  },
};
