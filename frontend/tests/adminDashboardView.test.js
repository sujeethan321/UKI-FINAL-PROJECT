import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { createElement as h } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { createServer } from 'vite';
import { adminMetrics, parseAdminOverview, parseAdminActivity } from '../src/utils/adminDashboard.js';
import { overviewFixture, activityFixture } from './fixtures/adminDashboardFixtures.js';
const actions = { start() {}, load() {} };
const ready = () => ({ authError: '', overview: { data: parseAdminOverview(overviewFixture()), loading: false, error: '' }, activity: { data: parseAdminActivity(activityFixture()), loading: false, error: '' } });

test('Administrator actual React dashboard, protected layout and shared Axios contracts', async t => {
  const server = await createServer({ logLevel: 'silent', appType: 'custom', server: { middlewareMode: true, hmr: false } });
  try {
    const { AdminDashboardView: View, default: Dashboard } = await server.ssrLoadModule('/src/pages/admin/AdminDashboard.jsx');
    const { default: Sidebar } = await server.ssrLoadModule('/src/components/admin/AdminSidebar.jsx');
    const { default: Layout } = await server.ssrLoadModule('/src/layouts/AdminLayout.jsx');
    const { AuthContext } = await server.ssrLoadModule('/src/context/AuthContext.jsx');
    const { default: Guard } = await server.ssrLoadModule('/src/routes/ProtectedRoute.jsx');
    const render = (state = ready()) => renderToStaticMarkup(h(MemoryRouter, null, h(View, { state, actions })));
    await t.test('renders all real summary metrics and pending approval counts', () => {
      const html = render();
      for (const value of ['Platform Dashboard', 'Monitor and manage LankaPex platform activity.', 'Pending Approvals', 'Quick Navigation', 'Recent Administrative Activity']) assert.ok(html.includes(value), value);
      for (const [field, label] of adminMetrics) { assert.ok(html.includes(label), label); assert.ok(html.includes('>' + overviewFixture()[field] + '</p>'), field); }
      assert.ok(!html.includes('AI Summary')); assert.ok(!html.includes('Earnings')); assert.ok(!html.includes('Approve Driver'));
    });
    await t.test('zero counts, no pending approvals and empty audit history are real empty states', () => {
      const state = ready(); state.overview.data = Object.fromEntries(adminMetrics.map(([key]) => [key, 0])); state.activity.data = { total: 0, events: [] };
      const html = render(state); assert.ok(html.includes('>0</p>')); assert.ok(html.includes('No records yet.')); assert.ok(html.includes('No pending Driver applications.')); assert.ok(html.includes('No pending Business registrations.')); assert.ok(html.includes('No administrative activity recorded yet.')); assert.ok(!html.includes('Unavailable'));
    });
    await t.test('initial loading disables refresh without zero or false empty state', () => {
      const state = ready(); for (const key of ['overview', 'activity']) state[key] = { data: null, loading: true, error: '' };
      const html = render(state); assert.ok(html.includes('role="status"')); assert.ok(html.includes('Loading platform summary')); assert.ok(html.includes('Loading recent activity')); assert.ok(html.includes('disabled=""')); assert.ok(!html.includes('>0</p>')); assert.ok(!html.includes('No administrative activity recorded yet.'));
    });
    await t.test('partial metrics show unavailable while retaining successful counts', () => {
      const state = ready(); state.overview.data = parseAdminOverview({ total_customers: 30 }); const html = render(state);
      assert.ok(html.includes('Some metrics are unavailable')); assert.ok(html.includes('Unavailable')); assert.ok(html.includes('>30</p>')); assert.ok(!html.includes('>0</p>'));
    });
    await t.test('summary and activity errors expose independent retries without old data', () => {
      const state = ready(); state.overview = { data: null, loading: false, error: 'Platform information is unavailable.' };
      let html = render(state); assert.ok(html.includes('Retry platform summary')); assert.ok(html.includes('Driver approved')); assert.ok(!html.includes('>61</p>'));
      state.overview = ready().overview; state.activity = { data: null, loading: false, error: 'Recent activity unavailable.' }; html = render(state);
      assert.ok(html.includes('Retry recent activity')); assert.ok(html.includes('>61</p>')); assert.ok(!html.includes('Driver approved'));
    });
    await t.test('real audit records render only safe labels, identifiers and UTC times', () => {
      const html = render(); for (const value of ['Driver approved', 'Driver #7', 'Business rejected', 'Business #13', 'Recorded', '2026-11-07 08:00:00 UTC', 'Showing 2 of 2']) assert.ok(html.includes(value), value);
      for (const value of ['PRIVATE', 'admin_user_id', 'previous_state', 'password_hash', 'Credit balance']) assert.ok(!html.includes(value), value);
    });
    await t.test('authentication errors hide all administrative records and navigation', () => {
      for (const authError of ['Your session has expired. Please sign in again.', 'Administrator access denied.']) {
        const html = render({ ...ready(), authError }); assert.ok(html.includes('role="alert"')); assert.ok(html.includes(authError)); assert.ok(!html.includes('Driver approved')); assert.ok(!html.includes('>61</p>')); assert.ok(!html.includes('Quick Navigation'));
      }
    });
    await t.test('quick navigation links only implemented destinations and labels deferred work', () => {
      const html = render(); for (const path of ['/admin/businesses', '/admin/dashboard#recent-admin-activity', '/admin/notifications']) assert.ok(html.includes('href="' + path + '"'), path);
      for (const path of ['/admin/shop-owners', '/admin/customers', '/admin/drivers']) assert.ok(html.includes('href="' + path + '"'), path);
      for (const path of ['/admin/users', '/admin/reports']) assert.ok(!html.includes('href="' + path + '"'), path);
      for (const label of ['Shop Owners', 'Customers', 'Delivery Drivers', 'Platform Reports', 'Coming soon']) assert.ok(html.includes(label));
      assert.ok(html.includes('View Driver Applications')); assert.ok(!html.includes('Reject application'));
    });
    await t.test('sidebar preserves existing sections and adds safe activity navigation and accessible mobile dialog', () => {
      const html = renderToStaticMarkup(h(MemoryRouter, null, h(Sidebar)));
      for (const label of ['Dashboard', 'Business Management', 'Shop Owners', 'Customers', 'Drivers', 'Notifications', 'Activity Logs', 'Platform Reports', 'LankaPex']) assert.ok(html.includes(label), label);
      for (const path of ['/admin/dashboard', '/admin/businesses', '/admin/notifications', '/admin/dashboard#recent-admin-activity']) assert.ok(html.includes('href="' + path + '"'), path);
      assert.ok(html.includes('aria-controls="admin-mobile-sidebar"')); assert.ok(html.includes('<dialog')); assert.ok(html.includes('aria-label="Admin menu"')); assert.ok(html.includes('aria-disabled="true"'));
    });
    const auth = { isAuthenticated: true, loading: false, token: 'fixture', user: { user_id: 90, full_name: 'Safe Admin', account_status: 'active', platform_role: 'admin' }, logout() {} };
    await t.test('activity anchor marks only its own navigation entry current', () => {
      const html = renderToStaticMarkup(h(MemoryRouter, { initialEntries: ['/admin/dashboard#recent-admin-activity'] }, h(Sidebar)));
      const dashboardLink = html.match(/<a\b[^>]*href="\/admin\/dashboard"[^>]*>/)[0];
      const activityLink = html.match(/<a\b[^>]*href="\/admin\/dashboard#recent-admin-activity"[^>]*>/)[0];
      assert.ok(!dashboardLink.includes('aria-current="page"'));
      assert.ok(activityLink.includes('aria-current="page"'));
    });
    const route = value => renderToStaticMarkup(h(MemoryRouter, { initialEntries: ['/admin/dashboard'] }, h(AuthContext.Provider, { value }, h(Routes, null, h(Route, { element: h(Guard, { allowedRoles: ['admin'] }) }, h(Route, { element: h(Layout) }, h(Route, { path: '/admin/dashboard', element: h(Dashboard) })))))));
    await t.test('active Admin renders dashboard through actual guard and layout', () => { const html = route(auth); assert.ok(html.includes('Monitor and manage LankaPex')); assert.ok(html.includes('Safe Admin')); assert.ok(html.includes('Loading platform summary')); });
    for (const role of ['customer', 'shop_owner', 'driver']) await t.test(role + ' cannot render Administrator dashboard', () => { assert.ok(!route({ ...auth, user: { ...auth.user, platform_role: role } }).includes('Monitor and manage LankaPex')); });
    await t.test('signed-out, loading and suspended identities never display Admin dashboard', () => {
      assert.ok(!route({ ...auth, isAuthenticated: false }).includes('Monitor and manage LankaPex'));
      for (const account_status of ['suspended', 'inactive', 'deactivated']) assert.ok(!route({ ...auth, user: { ...auth.user, account_status } }).includes('Monitor and manage LankaPex'));
      assert.ok(route({ ...auth, loading: true }).includes('Checking your LankaPex session'));
    });
    await t.test('service reuses Axios token injection and bounded GET-only audit request cancellation', async () => {
      const { default: api } = await server.ssrLoadModule('/src/services/api.js'); const service = await server.ssrLoadModule('/src/services/adminDashboardService.js');
      const adapter = api.defaults.adapter, storage = globalThis.sessionStorage, calls = [];
      globalThis.sessionStorage = { getItem: () => 'admin-fixture-token' };
      api.defaults.adapter = async config => { calls.push(config); return { data: config.url === '/admin/overview' ? overviewFixture() : activityFixture(), status: 200, statusText: 'OK', headers: {}, config }; };
      try {
        const signal = new AbortController().signal;
        assert.deepEqual(await service.getAdminOverview({ signal }), overviewFixture()); await service.getRecentAdminActivity({ signal });
        assert.deepEqual(calls.map(call => call.url), ['/admin/overview', '/admin/audit-events']); assert.deepEqual(calls[1].params, { limit: 5, offset: 0 });
        for (const call of calls) { assert.equal(call.method, 'get'); assert.equal(call.signal, signal); assert.equal(call.headers.Authorization, 'Bearer admin-fixture-token'); }
      } finally { api.defaults.adapter = adapter; if (storage === undefined) delete globalThis.sessionStorage; else globalThis.sessionStorage = storage; }
    });
    await t.test('existing role routes and corrected landing headline are preserved; session changes remount private readers', async () => {
      const [app, page, sidebar, landing] = await Promise.all(['src/App.jsx', 'src/pages/admin/AdminDashboard.jsx', 'src/components/admin/AdminSidebar.jsx', 'src/i18n/locales/en.json'].map(path => readFile(new URL('../' + path, import.meta.url), 'utf8')));
      for (const value of ['allowedRoles={["admin"]}', '<AdminDashboard />', '<CustomerDashboard />', '<ShopOwnerDashboard />', '<DriverDashboard />', '<LoginPage />', '<RegisterPage />']) assert.ok(app.includes(value), value);
      assert.ok(page.includes("key={user.user_id + ':' + token}")); assert.ok(!page.includes('sessionStorage')); assert.ok(!page.includes('setInterval'));
      for (const value of ['sm:grid-cols-2', 'xl:grid-cols-4', 'min-w-0', '[overflow-wrap:anywhere]', 'focus-visible:']) assert.ok(page.includes(value), value);
      for (const value of ['showModal()', 'overflow-y-auto', 'max-w-none', '85vw']) assert.ok(sidebar.includes(value), value);
      assert.ok(landing.includes('Management')); assert.ok(!landing.includes('Ma2xnagement'));
    });
  } finally { await server.close(); }
});
