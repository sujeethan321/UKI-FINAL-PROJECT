import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createElement as h } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { createServer } from 'vite';
import { managementAreas, parseManagementDetail, parseManagementList, parseOwnerBusinesses, parseBusinessHistory } from '../src/utils/adminManagement.js';
import { parseAdminOverview } from '../src/utils/adminDashboard.js';
import { rowFixture, driverFixture, businessFixture, associationFixture, historyFixture } from './fixtures/adminManagementFixtures.js';
import { overviewFixture } from './fixtures/adminDashboardFixtures.js';
const methods = ['start', 'load', 'refresh', 'select', 'filter', 'clear', 'page', 'associationPage', 'open', 'note', 'submit', 'closeDetails', 'closeDialog'];
const actions = Object.fromEntries(methods.map(key => [key, () => {}]));
function ready(kind, raw = rowFixture(kind)) {
  const filters = { q: '', status: kind === 'business' ? 'pending' : '', approval_status: '', offset: 0 };
  return { authError: '', filters, selectedId: 7, associationOffset: 0, submitting: false, uncertain: null, feedback: null, dialog: null,
    list: { data: parseManagementList(kind, { total: 1, limit: 10, offset: 0, [managementAreas[kind].collection]: [raw] }, filters), loading: false, error: '' },
    detail: { data: parseManagementDetail(kind, raw, 7), loading: false, error: '' },
    associations: { data: kind === 'shop_owner' ? parseOwnerBusinesses(associationFixture(7), 7, 0) : null, loading: false, error: '' },
    history: { data: kind === 'business' ? parseBusinessHistory(historyFixture(7), 7) : null, loading: false, error: '' },
    overview: { data: parseAdminOverview(overviewFixture()), loading: false, error: '' },
  };
}
test('Administrator management real React views, routes, confirmations and Axios integration', async t => {
  const server = await createServer({ logLevel: 'silent', appType: 'custom', server: { middlewareMode: true, hmr: false } });
  try {
    const { AdminManagementView: View, default: Management, ManagementConfirmation: Confirmation } = await server.ssrLoadModule('/src/pages/admin/AdminManagement.jsx');
    const { default: Businesses } = await server.ssrLoadModule('/src/pages/admin/AdminBusinesses.jsx');
    const { default: Guard } = await server.ssrLoadModule('/src/routes/ProtectedRoute.jsx');
    const { default: Layout } = await server.ssrLoadModule('/src/layouts/AdminLayout.jsx');
    const { default: Sidebar } = await server.ssrLoadModule('/src/components/admin/AdminSidebar.jsx');
    const { AuthContext } = await server.ssrLoadModule('/src/context/AuthContext.jsx');
    const render = (kind, state = ready(kind)) => renderToStaticMarkup(h(MemoryRouter, null, h(View, { kind, state, actions })));
    for (const kind of Object.keys(managementAreas)) {
      await t.test(kind + ' renders verified profile, status, registration and server list controls', () => {
        const html = render(kind); for (const value of [managementAreas[kind].title, 'View Details', 'Registered', '2026-11-07 08:00:00 UTC', 'Search', 'Clear filters', 'Previous', 'Next', 'Showing 1–1 of 1']) assert.ok(html.includes(value), value);
        for (const value of ['password_hash', 'access_token', 'Credit balance', 'Repayment', 'Impersonate', 'Delete account']) assert.ok(!html.includes(value), value);
      });
      await t.test(kind + ' loading/error/empty/search states never invent records', () => {
        const state = ready(kind); state.selectedId = null; state.list = { data: null, loading: true, error: '' }; let html = render(kind, state); assert.ok(html.includes('role="status"')); assert.ok(!html.includes('Example 7'));
        state.list = { data: null, loading: false, error: 'Backend unavailable.' }; html = render(kind, state); assert.ok(html.includes('Backend unavailable.')); assert.ok(!html.includes('No records match'));
        state.filters.q = 'NoMatch'; state.list = { data: { total: 0, rows: [] }, loading: false, error: '' }; html = render(kind, state); assert.ok(html.includes('No records match this search.')); assert.ok(html.includes('Showing 0–0 of 0'));
      });
    }
    await t.test('Owner associations and business active owners display only supported contact/status fields', () => {
      let html = render('shop_owner'); for (const value of ['Associated businesses', 'Associated business', 'Business #20', 'Membership:', 'approved']) assert.ok(html.includes(value), value);
      html = render('business'); for (const value of ['Shop Owners', 'Owner Example', 'owner@example.com', 'Example area', 'REG-123', 'Approval history']) assert.ok(html.includes(value), value);
    });
    await t.test('Driver pending details expose vehicle information and eligible actions without verification claims', () => {
      const html = render('driver'); for (const value of ['Vehicle type', 'Vehicle registration', 'van', 'TEST-123', 'Approve Driver', 'Reject Driver', 'Suspend account', 'Pending Driver approvals:']) assert.ok(html.includes(value), value);
      assert.ok(!html.includes('Identity verified')); assert.ok(!html.includes('Document'));
      const invalid = driverFixture(); invalid.profile.vehicle_type = null; invalid.profile.registration_reference = null;
      const noVehicle = render('driver', ready('driver', invalid)); assert.ok(!noVehicle.includes('Approve Driver')); assert.ok(noVehicle.includes('Reject Driver')); assert.ok(noVehicle.includes('Approval requires stored vehicle'));
    });
    await t.test('approved/rejected/suspended Drivers and businesses cannot be reapproved', () => {
      for (const approval of ['approved', 'rejected', 'suspended']) { const html = render('driver', ready('driver', driverFixture(7, approval))); assert.ok(!html.includes('Approve Driver')); assert.ok(!html.includes('Reject Driver')); }
      for (const approval of ['approved', 'rejected']) { const state = ready('business'); state.detail.data = parseManagementDetail('business', businessFixture(7, approval), 7); const html = render('business', state); assert.ok(!html.includes('Approve Business')); assert.ok(!html.includes('Reject Business')); }
      const suspended = render('driver', ready('driver', driverFixture(7, 'pending', 'suspended'))); assert.ok(suspended.includes('Reactivate account')); assert.ok(!suspended.includes('Approve Driver'));
    });
    await t.test('pending business without active owner allows rejection but hides approval', () => {
      const html = render('business', ready('business', { ...businessFixture(), owners: [] })); assert.ok(!html.includes('Approve Business')); assert.ok(html.includes('Reject Business')); assert.ok(html.includes('No active Shop Owner'));
    });
    await t.test('partial association failure is distinct from profile failure', () => {
      const state = ready('shop_owner'); state.associations = { data: null, loading: false, error: 'Associations unavailable.' }; const html = render('shop_owner', state); assert.ok(html.includes('Associations unavailable.')); assert.ok(html.includes('shop_owner7@example.com')); assert.ok(html.includes('Suspend account'));
    });
    await t.test('confirmation explains consequences, requires account reason and disables duplicate submission', () => {
      for (const action of ['approve', 'reject', 'suspend', 'reactivate']) {
        const state = ready('driver'); state.dialog = { id: 7, name: 'Driver <Safe>', action, text: '', error: '' };
        let html = renderToStaticMarkup(h(Confirmation, { state, actions, kind: 'driver' })); assert.ok(html.includes('<dialog')); assert.ok(html.includes('aria-labelledby="admin-confirmation-title"')); assert.ok(html.includes('Driver &lt;Safe&gt;')); assert.ok(html.includes('maxLength="500"'));
        if (['suspend', 'reactivate'].includes(action)) assert.ok(html.includes('required=""'));
        if (action === 'suspend') for (const text of ['Existing sessions', 'Active Driver jobs', 'last active owner']) assert.ok(html.includes(text));
        if (action === 'reactivate') assert.ok(html.includes('restores account access only'));
        state.submitting = true; html = renderToStaticMarkup(h(Confirmation, { state, actions, kind: 'driver' })); assert.ok(html.includes('Submitting')); assert.ok(html.includes('disabled=""'));
      }
    });
    await t.test('uncertain response is not success; conflicting actions are disabled and safe retry is visible', () => {
      const state = ready('driver'); state.uncertain = { id: 7, name: 'Driver Example', action: 'approve', text: '' }; state.feedback = { type: 'error', message: 'The result could not be confirmed.' }; const html = render('driver', state); assert.ok(html.includes('Retry same action')); assert.ok(html.includes('Other changes are paused')); assert.ok(html.includes('disabled=""')); assert.ok(!html.includes('Driver approved.'));
    });
    await t.test('401/403 auth error hides every record, detail, dialog and action', () => {
      for (const kind of Object.keys(managementAreas)) { const state = ready(kind); state.authError = 'Administrator access denied.'; state.dialog = { id: 7, action: 'approve', name: 'SECRET', text: '' }; const html = render(kind, state); assert.ok(html.includes('Administrator access denied.')); for (const value of ['Example', 'SECRET', 'View Details', 'Approve Driver', 'REG-123']) assert.ok(!html.includes(value)); }
    });
    const auth = { isAuthenticated: true, loading: false, token: 'fixture', user: { user_id: 90, full_name: 'Admin Test', platform_role: 'admin', account_status: 'active' }, logout() {} };
    for (const [kind, area] of Object.entries(managementAreas)) {
      const route = identity => renderToStaticMarkup(h(MemoryRouter, { initialEntries: [area.path] }, h(AuthContext.Provider, { value: identity }, h(Routes, null, h(Route, { element: h(Guard, { allowedRoles: ['admin'] }) }, h(Route, { element: h(Layout) }, h(Route, { path: area.path, element: kind === 'business' ? h(Businesses) : h(Management, { kind }) })))))));
      await t.test(kind + ' route mounts through actual Admin layout and denies other/inactive identities', () => {
        assert.ok(route(auth).includes(area.title));
        for (const role of ['customer', 'shop_owner', 'driver']) assert.ok(!route({ ...auth, user: { ...auth.user, platform_role: role } }).includes('Review '));
        assert.ok(!route({ ...auth, isAuthenticated: false }).includes('Review ')); for (const account_status of ['suspended', 'inactive', 'deactivated']) assert.ok(!route({ ...auth, user: { ...auth.user, account_status } }).includes('Review '));
      });
    }
    await t.test('sidebar and existing Dashboard now link to real management routes; reports stay deferred', () => {
      const html = renderToStaticMarkup(h(MemoryRouter, null, h(Sidebar))); for (const area of Object.values(managementAreas)) assert.ok(html.includes('href="' + area.path + '"'), area.path); assert.ok(!html.includes('href="/admin/reports"'));
    });
    await t.test('shared Axios uses exact bounded API routes and only supported mutation fields', async () => {
      const { default: api } = await server.ssrLoadModule('/src/services/api.js'); const { adminManagementApi: service } = await server.ssrLoadModule('/src/services/adminManagementService.js'); const adapter = api.defaults.adapter, storage = globalThis.sessionStorage, calls = [];
      globalThis.sessionStorage = { getItem: () => 'admin-test-token' }; api.defaults.adapter = async config => { calls.push(config); return { data: {}, status: 200, statusText: 'OK', headers: {}, config }; };
      try {
        const signal = new AbortController().signal;
        for (const kind of Object.keys(managementAreas)) { await service.list(kind, { q: 'Example', status: kind === 'business' ? 'pending' : 'active', approval_status: kind === 'driver' ? 'pending' : '', offset: 10 }, { signal }); await service.detail(kind, 7, { signal }); }
        await service.associations(7, 10, { signal }); await service.history(7, { signal }); await service.overview({ signal });
        for (const kind of ['driver', 'business']) for (const action of ['approve', 'reject']) await service.mutate(kind, { id: 7, action, text: 'Reviewed', platform_role: 'admin' }, { signal });
        for (const kind of ['shop_owner', 'customer', 'driver']) for (const action of ['suspend', 'reactivate']) await service.mutate(kind, { id: 7, action, text: 'Operational review' }, { signal });
        assert.deepEqual(calls.filter(call => call.url === '/admin/users').map(call => call.params.role), ['shop_owner', 'customer']);
        assert.deepEqual(calls.find(call => call.url === '/admin/drivers').params, { limit: 10, offset: 10, q: 'Example', status: 'active', approval_status: 'pending' });
        assert.deepEqual(calls.find(call => call.url === '/admin/businesses').params, { status: 'pending', limit: 10, offset: 10, q: 'Example' });
        assert.deepEqual(calls.find(call => call.url.endsWith('/businesses') && call.url !== '/admin/businesses').params, { limit: 10, offset: 10 });
        assert.deepEqual(calls.find(call => call.url.endsWith('/audit-history')).params, { limit: 10, offset: 0 });
        for (const call of calls) { assert.equal(call.signal, signal); assert.equal(call.headers.Authorization, 'Bearer admin-test-token'); assert.ok(['get', 'patch'].includes(call.method)); if (call.method === 'patch') { const body = JSON.parse(call.data); assert.ok(!Object.hasOwn(body, 'platform_role')); assert.deepEqual(Object.keys(body).sort(), call.url.endsWith('/status') ? ['account_status', 'reason'] : ['decision', 'review_note']); } }
        for (const action of ['delete', 'impersonate', 'adjust_balance']) await assert.rejects(service.mutate('customer', { id: 7, action, text: 'No' }));
        await assert.rejects(service.detail('admin', 7)); await assert.rejects(service.detail('customer', '../other'));
      } finally { api.defaults.adapter = adapter; if (storage === undefined) delete globalThis.sessionStorage; else globalThis.sessionStorage = storage; }
    });
    await t.test('real routing, session keys, native dialog and responsive rules remain scoped', async () => {
      const [app, page, source, landing] = await Promise.all(['src/App.jsx', 'src/pages/admin/AdminManagement.jsx', 'src/utils/adminManagement.js', 'src/i18n/locales/en.json'].map(path => readFile(new URL('../' + path, import.meta.url), 'utf8')));
      for (const path of ['shop-owners', 'customers', 'drivers', 'businesses']) assert.ok(app.includes('path="' + path + '"'));
      assert.ok(app.includes('allowedRoles={["admin"]}')); assert.ok(page.includes("key={kind + ':' + user.user_id + ':' + token}")); for (const value of ['showModal()', 'onCancel=', 'max-h-[90dvh]', 'overflow-y-auto', 'min-w-0', 'sm:grid-cols-2', 'xl:grid-cols-2', 'focus-visible:']) assert.ok(page.includes(value), value);
      assert.ok(!source.includes('sessionStorage')); assert.ok(!source.includes('setInterval')); assert.ok(!landing.includes('Ma2xnagement')); assert.ok(landing.includes('Management'));
    });
  } finally { await server.close(); }
});
