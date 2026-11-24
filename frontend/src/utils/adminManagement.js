// Purpose: Keep admin management data handling and workflow helpers separate from React rendering so callers use consistent rules.
import { adminTimestamp, parseAdminOverview } from './adminDashboard.js';
import { parseDriverVerification } from './adminDriverDocuments.js';
export const managementAreas = {
  shop_owner: { title: 'Shop Owner Management', singular: 'Shop Owner', collection: 'users', path: '/admin/shop-owners' },
  customer: { title: 'Customer Management', singular: 'Customer', collection: 'users', path: '/admin/customers' },
  driver: { title: 'Delivery Driver Management', singular: 'Driver', collection: 'drivers', path: '/admin/drivers' },
  business: { title: 'Business Management', singular: 'Business', collection: 'businesses', path: '/admin/businesses' },
};
// Accept only supported identifiers before response data is used for lookups or navigation.
const id = value => Number.isSafeInteger(value) && value > 0;
// Validate count values before the interface uses them for totals or pagination.
const count = value => Number.isSafeInteger(value) && value >= 0;
// Validate text values at the response boundary before rendering them.
const text = value => typeof value === 'string' && !!value.trim();
// Allow an absent text value while checking any text supplied by the API.
const nullableText = value => value === null || typeof value === 'string';
// Reject non-printable control characters before accepting administrative form text.
const hasControl = value => [...value].some(character => character.charCodeAt(0) < 32 || character.charCodeAt(0) === 127);
const statuses = ['pending', 'approved', 'rejected'];
export const driverStatuses = [...statuses, 'suspended', 'not_submitted'];
// Project only the named response fields so unrelated API fields do not enter view state.
const pick = (row, fields) => Object.fromEntries(fields.map(key => [key, row[key]]));
// Reject an unverified API response instead of publishing malformed management data.
const invalid = () => { throw Object.assign(Error('Unverified management response'), { code: 'INVALID_ADMIN_RESPONSE' }); };
// Validate the user response fields before platform management renders an account.
function userRow(kind, row) {
  if (!row || !id(row.user_id) || row.platform_role !== kind || !text(row.full_name) || !text(row.email) || !text(row.account_status) || !adminTimestamp(row.created_at)) invalid();
  return pick(row, ['user_id', 'full_name', 'email', 'platform_role', 'account_status', 'created_at']);
}
// Validate the driver response fields before displaying profile and review state.
function driverRow(row) {
  const result = userRow('driver', row), profile = row.profile;
  if (profile === null) return { ...result, profile: null };
  if (!profile || !driverStatuses.slice(0, -1).includes(profile.approval_status) || !nullableText(profile.vehicle_type) || !nullableText(profile.registration_reference) || !(profile.reviewed_by === null || id(profile.reviewed_by)) || !(profile.reviewed_at === null || adminTimestamp(profile.reviewed_at))) invalid();
  return { ...result, profile: pick(profile, ['approval_status', 'vehicle_type', 'registration_reference', 'reviewed_at']),
    verification: row.verification ? parseDriverVerification(row.verification, row.user_id) : null };
}
// Validate the business response fields before rendering the management list.
function businessRow(row) {
  if (!row || !id(row.business_id) || !text(row.business_name) || !text(row.business_type) || !statuses.includes(row.approval_status) || !['registration_number', 'phone', 'address'].every(key => nullableText(row[key])) || !adminTimestamp(row.created_at)) invalid();
  return pick(row, ['business_id', 'business_name', 'business_type', 'registration_number', 'phone', 'address', 'approval_status', 'created_at']);
}
// Check management detail before the surrounding workflow uses it.
export function parseManagementDetail(kind, row, expectedId, baseOnly = false) {
  if (!Object.hasOwn(managementAreas, kind)) invalid();
  let result = kind === 'business' ? businessRow(row) : kind === 'driver' && !baseOnly ? driverRow(row) : userRow(kind, row);
  if (expectedId !== undefined && (result.user_id ?? result.business_id) !== expectedId) invalid();
  if (kind === 'business' && !baseOnly) {
    if (!Array.isArray(row.owners)) invalid();
    const seen = new Set();
    result = { ...result, owners: row.owners.map(owner => {
      if (!id(owner.user_id) || seen.has(owner.user_id) || !text(owner.full_name) || !text(owner.email) || !nullableText(owner.phone)) invalid();
      seen.add(owner.user_id); return pick(owner, ['user_id', 'full_name', 'email', 'phone']);
    }) };
  }
  return result;
}
// Validate page metadata and project its rows before the management reader publishes the result.
function page(data, collection, offset) {
  if (!data || data.limit !== 10 || data.offset !== offset || !count(data.total) || !Array.isArray(data[collection]) || data[collection].length > 10 || data[collection].length > data.total) invalid();
  return data[collection];
}
// Check management list before the surrounding workflow uses it.
export function parseManagementList(kind, data, filters) {
  const rows = page(data, managementAreas[kind].collection, filters.offset), seen = new Set();
  return { total: data.total, rows: rows.map(row => {
    const value = parseManagementDetail(kind, row, undefined, kind === 'business'), key = value.user_id ?? value.business_id;
    if (seen.has(key) || filters.status && (kind === 'business' ? value.approval_status : value.account_status) !== filters.status || kind === 'driver' && filters.approval_status && (value.profile?.approval_status ?? 'not_submitted') !== filters.approval_status) invalid();
    seen.add(key); return value;
  }) };
}
// Check owner businesses before the surrounding workflow uses it.
export function parseOwnerBusinesses(data, userId, offset) {
  if (data?.user_id !== userId) invalid();
  const seen = new Set();
  return { total: data.total, rows: page(data, 'businesses', offset).map(row => {
    if (!id(row.business_id) || seen.has(row.business_id) || !text(row.business_name) || !statuses.includes(row.approval_status) || !text(row.membership_status) || !text(row.business_role)) invalid();
    seen.add(row.business_id); return pick(row, ['business_id', 'business_name', 'approval_status', 'membership_status', 'business_role']);
  }) };
}
// Check business history before the surrounding workflow uses it.
export function parseBusinessHistory(data, businessId) {
  if (data?.business_id !== businessId) invalid();
  return { total: data.total, rows: page(data, 'history', 0).map(row => {
    if (!id(row.audit_id) || !['approve', 'reject'].includes(row.decision) || row.previous_status !== 'pending' || row.new_status !== (row.decision === 'approve' ? 'approved' : 'rejected') || !adminTimestamp(row.created_at)) invalid();
    // Keep existing target-specific history, without expanding audit reporting or internal notes.
    return pick(row, ['audit_id', 'decision', 'previous_status', 'new_status', 'created_at']);
  }) };
}
// Derive management actions from account and review state before showing action controls.
export function allowedManagementActions(kind, row) {
  if (!row) return [];
  const result = [];
  if (kind === 'business') {
    if (row.approval_status === 'pending') { if (row.owners?.length) result.push('approve'); result.push('reject'); }
  } else {
    if (row.platform_role !== kind) return [];
    if (row.account_status === 'active') result.push('suspend');
    if (row.account_status === 'suspended') result.push('reactivate');
    if (kind === 'driver' && row.account_status === 'active' && row.profile?.approval_status === 'pending') {
      if (text(row.profile.vehicle_type) && text(row.profile.registration_reference) && row.verification?.approval_ready === true) result.push('approve');
      result.push('reject');
    }
  }
  return result;
}
export const actionLabels = { approve: 'Approve', reject: 'Reject', suspend: 'Suspend account', reactivate: 'Reactivate account' };
// Translate management outcomes into display text for the interface.
export function managementError(error) {
  const status = error?.response?.status;
  if (status === 401) return 'Your session has expired. Please sign in again.';
  if (status === 403) return 'Administrator access denied. Check your account status or sign out.';
  if (status === 404) return 'This record is no longer available. Refresh the list.';
  if (status === 409) return 'This action conflicted with the current state or an operational safeguard. The record is being refreshed; review it before another decision.';
  if (status === 422) return 'The request was not accepted. Check the search, filters or single-line reason and try again.';
  if (error?.code === 'INVALID_ADMIN_RESPONSE') return 'The response could not be verified. Refresh and try again.';
  return 'Management information is unavailable. Check your connection and retry.';
}
// Create the resource state consumed by the management screen.
const resource = (loading = false) => ({ data: null, loading, error: '' });
// Build the default management filters and form values for a new workflow instance.
const defaults = kind => ({ q: '', status: kind === 'business' ? 'pending' : '', approval_status: '', offset: 0 });
// Create independent initial resource state so new readers do not inherit another instance state.
function fresh(kind) { return { authError: '', filters: defaults(kind), list: resource(true), detail: resource(), associations: resource(), history: resource(), overview: resource(true), selectedId: null, associationOffset: 0, dialog: null, submitting: false, uncertain: null, feedback: null }; }
// Create admin management for the admin management workflow.
export function createAdminManagement(api, kind) {
  if (!Object.hasOwn(managementAreas, kind)) throw Error('Unsupported management area');
  let state = fresh(kind), active = false, generation = 0, mutation = null;
  const listeners = new Set(), reads = {}, versions = {};
  // Replace the store snapshot and notify subscribers so React can render the new state.
  const publish = patch => { state = { ...state, ...patch }; if (active) listeners.forEach(fn => fn()); };
  // Cancel outstanding reads before context or selection changes.
  const abortReads = () => Object.values(reads).forEach(row => row.controller.abort());
  // Clear protected resource state after access is denied so earlier data is not left visible.
  function deny(error) {
    generation++; abortReads(); publish({ ...fresh(kind), list: resource(), overview: resource(), authError: managementError(error) });
  }
  // Invalidate or release this workflow instance so old work cannot keep updating its consumers.
  function cancel(section) { reads[section]?.controller.abort(); delete reads[section]; versions[section] = (versions[section] || 0) + 1; }
  // Load the current resource data and update the state consumed by the interface.
  function load(section) {
    if (!active || state.authError || !['list', 'detail', 'associations', 'history', 'overview'].includes(section)) return Promise.resolve();
    if (reads[section]) return reads[section].promise;
    const selected = state.selectedId, filters = { ...state.filters }, offset = state.associationOffset;
    if (['detail', 'associations', 'history'].includes(section) && !selected || section === 'associations' && kind !== 'shop_owner' || section === 'history' && kind !== 'business') return Promise.resolve();
    const controller = new AbortController(), current = generation, version = versions[section] = (versions[section] || 0) + 1;
    // Check valid before the surrounding workflow uses it.
    const valid = () => active && generation === current && versions[section] === version && !controller.signal.aborted;
    publish({ [section]: resource(true) });
    const promise = Promise.resolve().then(async () => {
      if (!valid()) return;
      try {
        let response, data;
        const options = { signal: controller.signal };
        if (section === 'list') { response = await api.list(kind, filters, options); if (valid()) data = parseManagementList(kind, response, filters); }
        else if (section === 'detail') { response = await api.detail(kind, selected, options); if (valid()) data = parseManagementDetail(kind, response, selected); }
        else if (section === 'associations') { response = await api.associations(selected, offset, options); if (valid()) data = parseOwnerBusinesses(response, selected, offset); }
        else if (section === 'history') { response = await api.history(selected, options); if (valid()) data = parseBusinessHistory(response, selected); }
        else { response = await api.overview(options); if (valid()) data = parseAdminOverview(response); }
        if (!valid()) return;
        if (section === 'list' && !data.rows.length && filters.offset > 0 && filters.offset >= data.total) {
          delete reads.list; publish({ filters: { ...state.filters, offset: Math.max(0, Math.ceil(data.total / 10) - 1) * 10 } }); return load('list');
        }
        publish({ [section]: { data, loading: false, error: '' } });
      } catch (error) {
        if (!valid()) return;
        if ([401, 403].includes(error?.response?.status)) deny(error);
        else publish({ [section]: { data: null, loading: false, error: managementError(error) } });
      }
    }).finally(() => { if (reads[section]?.promise === promise) delete reads[section]; });
    reads[section] = { controller, promise }; return promise;
  }
  // Check whether current workflow state prevents another management operation.
  const blocked = () => !active || state.authError || state.submitting || state.uncertain;
  // Close details within the admin management workflow.
  const closeDetails = () => { for (const key of ['detail', 'associations', 'history']) cancel(key); publish({ selectedId: null, detail: resource(), associations: resource(), history: resource(), associationOffset: 0, dialog: null }); };
  // Change the active management area and prepare its corresponding list and detail state.
  function select(ident) {
    if (blocked() || !id(ident)) return Promise.resolve();
    closeDetails(); publish({ selectedId: ident, feedback: null });
    return Promise.allSettled(['detail', 'associations', 'history'].map(load));
  }
  // Apply the requested filters and reload the relevant resource list.
  function filter(changes) {
    if (blocked()) return Promise.resolve();
    const next = { ...state.filters, ...pick(changes, Object.keys(changes).filter(key => ['q', 'status', 'approval_status'].includes(key))), offset: 0 };
    next.q = typeof next.q === 'string' ? next.q.trim() : '';
    if (next.q.length > 100 || hasControl(next.q) || !(kind === 'business' ? ['', ...statuses] : ['', 'active', 'suspended']).includes(next.status) || !['', ...driverStatuses].includes(next.approval_status)) { publish({ feedback: { type: 'error', message: 'Use supported filters and a single-line search of at most 100 characters.' } }); return Promise.resolve(); }
    cancel('list'); closeDetails(); publish({ filters: next, feedback: null }); return load('list');
  }
  // Open the selected management record and prepare its detail/action state.
  function open(action) {
    if (blocked() || state.detail.loading || !allowedManagementActions(kind, state.detail.data).includes(action)) return false;
    const row = state.detail.data;
    publish({ dialog: { id: state.selectedId, action, name: row.full_name ?? row.business_name, text: '', error: '' }, feedback: null }); return true;
  }
  // Submit the current form through its workflow and expose pending, success, or error state to the interface.
  function submit() {
    if (mutation) return mutation.promise;
    if (!active || state.authError || !state.dialog && !state.uncertain) return Promise.resolve(false);
    const operation = state.uncertain || { ...state.dialog, text: state.dialog.text.trim() };
    if (!state.uncertain && (!allowedManagementActions(kind, state.detail.data).includes(operation.action) || operation.id !== state.selectedId)) return Promise.resolve(false);
    if (operation.text.length > 500 || hasControl(operation.text) || ['suspend', 'reactivate'].includes(operation.action) && !operation.text) { publish({ dialog: { ...state.dialog, error: 'Provide a single-line reason of 1–500 characters for account changes; optional review notes must be at most 500 characters.' } }); return Promise.resolve(false); }
    const controller = new AbortController(), current = generation;
    publish({ submitting: true, feedback: null, dialog: state.dialog ? { ...state.dialog, error: '' } : null });
    // Check valid before the surrounding workflow uses it.
    const valid = () => active && current === generation;
    const promise = Promise.resolve().then(async () => {
      if (!valid()) return false;
      let confirmed = false;
      try {
        const response = await api.mutate(kind, operation, { signal: controller.signal });
        if (!valid()) return false;
        const statusAction = ['suspend', 'reactivate'].includes(operation.action);
        const row = parseManagementDetail(kind, response, operation.id, statusAction || kind === 'business');
        const expected = { approve: 'approved', reject: 'rejected', suspend: 'suspended', reactivate: 'active' }[operation.action];
        if ((statusAction ? row.account_status : kind === 'business' ? row.approval_status : row.profile.approval_status) !== expected) invalid();
        confirmed = true;
        publish({ uncertain: null, dialog: null, feedback: { type: 'success', message: statusAction ? 'Account status confirmed as ' + expected + '.' : managementAreas[kind].singular + ' ' + expected + '.' } });
      } catch (error) {
        if (!valid()) return false;
        const status = error?.response?.status;
        if ([401, 403].includes(status)) { deny(error); return false; }
        const unknown = !status || status >= 500;
        publish({ dialog: null, uncertain: unknown ? operation : null, feedback: { type: 'error', message: unknown ? 'The result could not be confirmed. Review the refreshed record and retry the same action; no success has been assumed.' : managementError(error) } });
      }
      if (valid()) {
        for (const key of ['list', 'detail', 'associations', 'history', 'overview']) cancel(key);
        await Promise.allSettled(['list', 'detail', 'associations', 'history', 'overview'].map(load));
      }
      return confirmed;
    }).finally(() => { if (valid()) publish({ submitting: false }); if (mutation?.promise === promise) mutation = null; });
    mutation = { controller, promise }; return promise;
  }
  return {
    // Expose the current store snapshot to subscribers without starting a request.
    getSnapshot: () => state,
    // Register a state listener and return cleanup so consumers can unsubscribe.
    subscribe: fn => { listeners.add(fn); return () => listeners.delete(fn); },
    // Start the resource workflow using its current context and selection.
    start() { if (!active) { active = true; generation++; } return Promise.allSettled(['list', 'overview'].map(load)); },
    load, select, filter, open, submit,
    // Remove saved state only within the scope checked by this storage adapter.
    clear() { return filter({ q: '', status: '', approval_status: '' }); },
    // Close the selected detail view and release its resource state.
    closeDetails() { if (!blocked()) closeDetails(); },
    // Close the action dialog through the workflow pending-state rules.
    closeDialog() { if (!state.submitting) publish({ dialog: null }); },
    // Update the note associated with the current workflow action.
    note(value) { if (state.dialog && !state.submitting && typeof value === 'string') publish({ dialog: { ...state.dialog, text: value, error: '' } }); },
    // Change the current page and load its resource records.
    page(offset) { if (blocked() || !count(offset) || offset > 1000000 || offset % 10 || state.list.loading || !state.list.data || offset && offset >= state.list.data.total) return Promise.resolve(); cancel('list'); closeDetails(); publish({ filters: { ...state.filters, offset }, feedback: null }); return load('list'); },
    // Load the requested association page without changing the selected customer.
    associationPage(offset) { if (blocked() || !count(offset) || offset > 1000000 || offset % 10 || state.associations.loading || !state.associations.data || offset && offset >= state.associations.data.total) return Promise.resolve(); cancel('associations'); publish({ associationOffset: offset }); return load('associations'); },
    // Request current resource data instead of continuing to display an earlier result.
    refresh() { if (state.submitting) return Promise.resolve(); return Promise.allSettled(['list', 'detail', 'associations', 'history', 'overview'].map(load)); },
    // Release pending work and subscriptions when this resource reader is no longer used.
    dispose() { active = false; generation++; abortReads(); mutation?.controller.abort(); for (const key of Object.keys(reads)) delete reads[key]; mutation = null; state = fresh(kind); },
  };
}
