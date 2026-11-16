export const adminMetrics = [
  ['total_shop_owners', 'Total Shop Owners'],
  ['total_customers', 'Total Customers'],
  ['total_drivers', 'Total Delivery Drivers'],
  ['total_businesses', 'Total Registered Businesses'],
  ['pending_driver_approvals', 'Pending Driver Approvals'],
  ['pending_business_approvals', 'Pending Business Approvals'],
  ['total_orders', 'Total Orders'],
  ['total_delivery_requests', 'Total Delivery Requests'],
];
export const adminActions = {
  driver_approved: 'Driver approved', driver_rejected: 'Driver rejected',
  business_approved: 'Business approved', business_rejected: 'Business rejected',
  account_suspended: 'Account suspended', account_reactivated: 'Account reactivated',
  admin_provisioned: 'Administrator provisioned',
};
const count = value => Number.isSafeInteger(value) && value >= 0;
const id = value => Number.isSafeInteger(value) && value > 0;
const record = value => value !== null && typeof value === 'object' && !Array.isArray(value);
export function adminTimestamp(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$/.test(value)) return null;
  const iso = /(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? value : value + 'Z';
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : { iso, label: date.toISOString().slice(0, 19).replace('T', ' ') + ' UTC' };
}
export function parseAdminOverview(data) {
  if (!record(data)) throw Error('Invalid overview');
  const result = {};
  for (const [key] of adminMetrics) {
    const value = data[key];
    if (value !== undefined && value !== null && !count(value)) throw Error('Invalid count');
    result[key] = value ?? null;
  }
  if (Object.values(result).every(value => value === null)) throw Error('No verified counts');
  return result;
}
export function parseAdminActivity(data) {
  if (!record(data) || !count(data.total) || data.limit !== 5 || data.offset !== 0 ||
      !Array.isArray(data.events) || data.events.length > 5 || data.events.length > data.total) throw Error('Invalid activity page');
  const seen = new Set();
  const events = data.events.map(row => {
    if (!record(row) || !id(row.audit_id) || !id(row.target_id) ||
        !Object.hasOwn(adminActions, row.action) || !adminTimestamp(row.created_at)) throw Error('Invalid audit event');
    const business = row.action.startsWith('business_');
    const target = business ? 'business' : row.action.startsWith('driver_') ? 'driver' : 'user';
    if (row.source !== (business ? 'business_approval' : 'administrative') || row.target_type !== target) throw Error('Invalid audit scope');
    const key = row.source + ':' + row.audit_id;
    if (seen.has(key)) throw Error('Duplicate audit event');
    seen.add(key);
    // Discard actor/contact fields, internal reasons and extra payloads.
    return Object.fromEntries(['source', 'audit_id', 'action', 'target_type', 'target_id', 'created_at'].map(field => [field, row[field]]));
  });
  return { total: data.total, events };
}
export function adminReadError(error) {
  if (error?.response?.status === 401) return 'Your session has expired. Please sign in again.';
  if (error?.response?.status === 403) return 'Administrator access denied. Check your account status or sign out.';
  if (error?.response?.status === 503 && error.response.data?.detail?.code === 'ADMIN_SCHEMA_UNAVAILABLE') return 'Platform database setup is incomplete. Contact the platform operator.';
  if (error?.code === 'INVALID_ADMIN_RESPONSE') return 'This response could not be verified. Please retry.';
  if (error?.code === 'ECONNABORTED') return 'The request timed out. Please retry.';
  return 'Platform information is unavailable. Check your connection and retry.';
}
const sections = ['overview', 'activity'];
const fresh = loading => ({ authError: '', ...Object.fromEntries(sections.map(key => [key, { data: null, loading, error: '' }])) });
export function createAdminDashboardReader(api) {
  let state = fresh(true), active = false, generation = 0;
  const listeners = new Set(), requests = {};
  const publish = next => { state = next; if (active) listeners.forEach(fn => fn()); };
  const abortAll = () => Object.values(requests).forEach(request => request.controller.abort());
  function load(section) {
    if (!active || state.authError || !sections.includes(section)) return Promise.resolve();
    if (requests[section]) return requests[section].promise;
    const controller = new AbortController(), current = generation;
    const valid = () => active && generation === current && !controller.signal.aborted;
    publish({ ...state, [section]: { data: null, loading: true, error: '' } });
    const promise = Promise.resolve().then(async () => {
      if (!valid()) return;
      try {
        const response = await api[section]({ signal: controller.signal });
        if (!valid()) return;
        let data;
        try { data = section === 'overview' ? parseAdminOverview(response) : parseAdminActivity(response); }
        catch { throw Object.assign(Error('Invalid Administrator response'), { code: 'INVALID_ADMIN_RESPONSE' }); }
        publish({ ...state, [section]: { data, loading: false, error: '' } });
      } catch (error) {
        if (!valid()) return;
        if ([401, 403].includes(error?.response?.status)) {
          generation++; abortAll(); publish({ ...fresh(false), authError: adminReadError(error) });
        } else publish({ ...state, [section]: { data: null, loading: false, error: adminReadError(error) } });
      }
    }).finally(() => { if (requests[section]?.promise === promise) delete requests[section]; });
    requests[section] = { controller, promise };
    return promise;
  }
  return {
    getSnapshot: () => state,
    subscribe: fn => { listeners.add(fn); return () => listeners.delete(fn); },
    load,
    start() {
      if (!active) { active = true; generation++; publish(fresh(true)); }
      return Promise.allSettled(sections.map(load));
    },
    dispose() {
      active = false; generation++; abortAll();
      for (const key of sections) delete requests[key];
      state = fresh(false);
    },
  };
}
