// Test-only policy and fixtures. Importing performs no filesystem/network writes.
import { fixtures } from '../tests/fixtures/customerDashboardFixtures.js';
import { driverFixtures } from '../tests/fixtures/driverDashboardFixtures.js';
import { overviewFixture, activityFixture } from '../tests/fixtures/adminDashboardFixtures.js';
import { businessFixture, driverFixture, historyFixture } from '../tests/fixtures/adminManagementFixtures.js';

export const ORIGIN = 'http://127.0.0.1:5173';
export const API = 'http://127.0.0.1:8001/api/v1';
export const OUTPUT = '.server-logs/four-role-mock-browser';
export const TOKEN = 'synthetic-browser-only-not-a-jwt';
export const ROLES = ['shop_owner', 'customer', 'driver', 'admin'];
export const LANGUAGES = ['en', 'ta', 'si'];
export const WIDTHS = [1366, 768, 375];
export const CASES = {
  shop_owner: [{ path: '/shop-owner/dashboard', marker: 'Visual QA Customer', label: 'Quick Actions' }],
  customer: [{ path: '/customer/dashboard', marker: 'SYNTHETIC-ORDER', label: 'Recent Orders' }, { path: '/customer/shops', marker: 'Linked Shop', label: 'Total Linked Shops' }],
  driver: [{ path: '/driver/dashboard', marker: 'DR-VISUAL-JOB', label: 'Available Orders' }, { path: '/driver/jobs', marker: 'DR-VISUAL-JOB', label: 'Available Delivery Jobs' }, { path: '/driver/deliveries', marker: 'DR-test-one', label: 'Assigned Deliveries' }],
  admin: [{ path: '/admin/dashboard', marker: null, label: 'Platform Dashboard' }, { path: '/admin/businesses', marker: 'Example business 7', label: 'Business Management' }, { path: '/admin/drivers', marker: 'driver Example 7', label: 'Delivery Driver Management' }],
};
export const MENU = { shop_owner: 'shop owner', customer: 'customer', driver: 'driver', admin: 'admin' };
export function executionGate(args) {
  if (!args.length) return false;
  if (JSON.stringify(args) !== JSON.stringify(['--execute', '--confirm-origin', ORIGIN, '--confirm-output', OUTPUT])) throw Error('confirmation');
  return true;
}
export function identity(role) {
  if (!ROLES.includes(role)) throw Error('role');
  return { user_id: role === 'driver' ? 7 : 90, full_name: 'Visual QA ' + role, email: role + '@visual.example.invalid', platform_role: role, account_status: 'active' };
}
export function classify(url, method = 'GET', resourceType = 'Other') {
  let u; try { u = new URL(url); } catch { return 'blocked'; }
  if (u.username || u.password || u.hash) return 'blocked';
  if (u.origin === new URL(API).origin && u.pathname.startsWith('/api/v1/')) return 'mock';
  if (u.origin !== ORIGIN || method !== 'GET') return 'blocked';
  if (resourceType === 'Document' && (u.pathname === '/login' || Object.values(CASES).flat().some(c => c.path === u.pathname))) return 'frontend';
  if (['/@vite/client', '/@react-refresh', '/favicon.svg'].includes(u.pathname)) return 'frontend';
  if (/^\/src\/[A-Za-z0-9_./-]+\.(jsx?|json|css|png|svg|webp)$/.test(u.pathname) && !u.pathname.includes('..')) return 'frontend';
  if (/^\/node_modules\/\.vite\/deps\/[A-Za-z0-9_.-]+\.js$/.test(u.pathname)) return 'frontend';
  if (/^\/node_modules\/@fontsource\/inter\/files\/[A-Za-z0-9_.-]+\.woff2?$/.test(u.pathname)) return 'frontend';
  if (/^\/node_modules\/@fontsource\/inter\/(400|500|600|700)\.css$/.test(u.pathname)) return 'frontend';
  return 'blocked';
}
export function validateIdentityResponses({ html, main, app, api }, local) {
  if (!html.includes('/@vite/client') || !html.includes('/src/main.jsx')) throw Error('frontend_identity');
  for (const [key, body] of Object.entries({ main, app, api })) {
    const encoded = body.match(/sourceMappingURL=data:application\/json(?:;charset=utf-8)?;base64,([A-Za-z0-9+/=]+)/)?.[1];
    let contents; try { contents = JSON.parse(Buffer.from(encoded || '', 'base64').toString()).sourcesContent; } catch { throw Error('source_map'); }
    if (!Array.isArray(contents) || !contents.includes(local[key])) throw Error('source_map');
  }
  const injected = api.match(/import\.meta\.env\s*=\s*(\{[^\n]+?\})\s*;/)?.[1];
  let env; try { env = JSON.parse(injected); } catch { throw Error('frontend_configuration'); }
  if (env.VITE_API_URL !== API || Object.keys(env).some(k => k.startsWith('VITE_') && k !== 'VITE_API_URL')) throw Error('frontend_configuration');
  return true;
}
const page = (rows, key, size) => ({ page: 1, page_size: size, total: rows.length, [key]: rows });
export function mockResponse(role, request, { error = false } = {}) {
  identity(role);
  if (classify(request.url, request.method) !== 'mock') throw Error('network');
  const u = new URL(request.url), p = u.pathname.slice('/api/v1'.length), method = request.method;
  const ok = data => ({ status: 200, data: structuredClone(data) });
  if (method === 'OPTIONS') {
    if (p !== '/auth/login') mockResponse(role, { ...request, method: 'GET', headers: { Authorization: 'Bearer ' + TOKEN } });
    else if (u.search) throw Error('query');
    return ok({});
  }
  const allowedQuery = p.startsWith('/shop-owner/dashboard/') ? ['business_id']
    : ['/customer/shops', '/customer/credit-accounts', '/customer/transactions', '/customer/orders', '/customer/join-requests', '/driver/jobs', '/driver/deliveries'].includes(p) ? ['page', 'page_size']
      : ['/admin/audit-events', '/admin/businesses', '/admin/drivers', '/admin/businesses/7/audit-history'].includes(p) ? ['limit', 'offset', 'status', 'approval_status'] : [];
  if ([...u.searchParams.keys()].some(key => !allowedQuery.includes(key))) throw Error('query');
  if (p === '/auth/login' && method === 'POST') {
    const form = new URLSearchParams(request.postData);
    if (form.get('username') !== identity(role).email || form.get('password') !== 'Synthetic-visual-input-only') throw Error('login_input');
    return ok({ access_token: TOKEN, token_type: 'bearer' });
  }
  if (method !== 'GET') throw Error('unexpected_mutation');
  const auth = Object.entries(request.headers || {}).find(([k]) => k.toLowerCase() === 'authorization')?.[1];
  if (auth !== 'Bearer ' + TOKEN) throw Error('mock_authorization');
  if (p === '/auth/me') return ok(identity(role));
  if (p === '/notifications/unread-count') return ok({ unread_count: 0 });
  const customer = fixtures(), driver = driverFixtures(), size = Number(u.searchParams.get('page_size') || 5);
  if (![5, 10, 20].includes(size) || u.searchParams.has('page') && u.searchParams.get('page') !== '1') throw Error('pagination');
  let data;
  if (role === 'shop_owner') {
    if (p === '/shop-owner/business-context') data = { businesses: [{ business_id: 2, business_name: 'Visual QA Shop', approval_status: 'approved', business_role: 'owner', membership_status: 'active' }] };
    if (p.startsWith('/shop-owner/dashboard/') && u.searchParams.get('business_id') !== '2') throw Error('business_scope');
    if (p === '/shop-owner/dashboard/summary') data = { total_outstanding: '100.25', collected_today: '30.10', overdue_amount: '0.00', pending_credit_requests: 0, credit_customers: 1, active_deliveries: 1 };
    if (p === '/shop-owner/dashboard/recent-transactions') data = { transactions: [{ id: 41, customer_name: 'Visual QA Customer', type: 'credit_sale', amount: '100.25' }, { id: 42, customer_name: 'Visual QA Customer', type: 'repayment', amount: '30.10' }] };
  }
  if (role === 'customer') {
    if (p === '/customer/dashboard/summary') data = customer.summary;
    if (p === '/customer/shops') data = { currency: 'LKR', ...page(customer.shops.shops, 'shops', size) };
    if (p === '/customer/credit-accounts') data = { currency: 'LKR', ...page(customer.accounts.credit_accounts, 'credit_accounts', size) };
    if (p === '/customer/transactions') data = { currency: 'LKR', ...page(customer.transactions.transactions, 'transactions', size) };
    if (p === '/customer/join-requests') data = page([], 'requests', 20);
    if (p === '/customer/orders') data = page([{ order_id: 7, reference: 'SYNTHETIC-ORDER', business_id: 2, business_name: 'Linked Shop', status: 'submitted', payment_method: 'cash', payment_status: 'unpaid', total: '12.50', subtotal: '12.50', currency: 'LKR', created_at: '2026-11-08T10:00:00', updated_at: '2026-11-08T10:00:00', credit_sale_id: null, items: [{ product_id: 3, product_name: 'Synthetic Item', quantity: 1, unit_price: '12.50', line_total: '12.50' }] }], 'orders', size);
  }
  if (role === 'driver') {
    if (p === '/driver/profile') data = driver.profile;
    if (p === '/driver/dashboard/summary') data = { ...driver.summary, available_jobs_count: 1 };
    if (p === '/driver/deliveries') data = { driver_user_id: 7, ...page(driver.deliveries.deliveries.map(r => ({ ...r, finished_at: null })), 'deliveries', size) };
    if (p === '/driver/jobs') data = { driver_user_id: 7, ...page([{ delivery_request_id: 32, reference: 'DR-VISUAL-JOB', business_name: 'Visual QA Shop', pickup_area: 'Synthetic pickup area', delivery_area: 'Synthetic destination', status: 'available', created_at: '2026-11-06T10:00:00' }], 'jobs', 10) };
  }
  if (role === 'admin') {
    if (p === '/admin/overview') data = overviewFixture();
    if (p === '/admin/audit-events') data = activityFixture();
    if (p === '/admin/businesses') data = { total: 1, limit: 10, offset: 0, businesses: [businessFixture()] };
    if (p === '/admin/businesses/7') data = businessFixture();
    if (p === '/admin/businesses/7/audit-history') data = historyFixture(7);
    if (p === '/admin/drivers') data = { total: 1, limit: 10, offset: 0, drivers: [driverFixture()] };
    if (p === '/admin/drivers/7') data = driverFixture();
  }
  if (data === undefined) throw Error('unexpected_api');
  return error ? { status: 503, data: { detail: 'Synthetic service unavailable' } } : ok(data);
}
