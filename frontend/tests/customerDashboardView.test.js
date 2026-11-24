import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { createServer } from "vite";
import { parseCustomerResponse } from "../src/utils/customerDashboard.js";
import { fixtures, transaction } from "./fixtures/customerDashboardFixtures.js";

const actions = { start() {}, load() {} };
const ready = () => ({ authError: "", ...Object.fromEntries(Object.entries(fixtures()).map(([key, data]) => [key, { data: parseCustomerResponse(key, data), loading: false, error: "" }])) });

test("customer dashboard React views, routes and existing Axios contracts", async t => {
  const server = await createServer({ logLevel: "silent", appType: "custom", server: { middlewareMode: true, hmr: false } });
  try {
    const { CustomerDashboardView, default: Dashboard } = await server.ssrLoadModule("/src/pages/customer/CustomerDashboard.jsx");
    const { default: Sidebar } = await server.ssrLoadModule("/src/components/customer/CustomerSidebar.jsx");
    const { default: Layout } = await server.ssrLoadModule("/src/layouts/CustomerLayout.jsx");
    const { AuthContext } = await server.ssrLoadModule("/src/context/AuthContext.jsx");
    const { default: Guard } = await server.ssrLoadModule("/src/routes/ProtectedRoute.jsx");
    const render = (state = ready()) => renderToStaticMarkup(createElement(MemoryRouter, null, createElement(CustomerDashboardView, { state, actions, displayName: "Kumar" })));
    await t.test("successful overview and previews display actual backend fields", () => {
      const html = render();
      for (const value of ["Outstanding Credit", "Credit Accounts", "Due Soon", "Overdue Amount", "LKR 100.25", "LKR 1,000.00", "Linked Shop", "Account #8", "CS-test-reference", "Credit sale", "2026-11-06 10:00:00", "Next Payment"]) assert.ok(html.includes(value), value);
      assert.ok(!html.includes("View Details")); assert.ok(!html.includes("Make Payment"));
    });
    await t.test("loading and unavailable values cannot masquerade as zero balances", () => {
      const state = ready(); for (const key of ["summary", "shops", "accounts", "transactions"]) state[key] = { data: null, loading: true, error: "" };
      const html = render(state); assert.ok(html.includes("Loading your account summary")); assert.ok(html.includes('role="status"')); assert.ok(!html.includes("LKR 0.00")); assert.ok(!html.includes("No shops are linked"));
    });
    await t.test("unlinked, no-account and no-history states preserve explicit backend zero", () => {
      const state = ready(); state.summary.data = { linked_shop_count: 0, credit_account_count: 0, total_outstanding_balance: "0.00", recent_activity: [] };
      for (const key of ["shops", "accounts", "transactions"]) state[key].data = { total: 0, items: [] };
      const html = render(state); assert.ok(!html.includes('id="my-shops"')); assert.ok(html.includes("LKR 0.00")); assert.ok(html.includes("No transactions to display yet.")); assert.ok(html.includes("No credit accounts are linked"));
      state.shops.data = { total: 1, items: [{ business_id: 2, business_name: "My Shop", credit_account_count: 0, outstanding_balance: "0.00" }] };
      assert.ok(!render(state).includes("My Shop"));
    });
    await t.test("partial failure retains other previews and offers a section-specific retry", () => {
      const state = ready(); state.accounts = { data: null, loading: false, error: "The customer service is unavailable. Please retry." };
      const html = render(state); assert.ok(html.includes("Retry my credit accounts")); assert.ok(html.includes("CS-test-reference")); assert.ok(html.includes('role="alert"'));
    });
    await t.test("expired and forbidden access conceal all previously loaded financial data", () => {
      for (const message of ["Your session has expired. Please sign in again.", "You do not have permission to view customer records."]) {
        const state = ready(); state.authError = message; const html = render(state);
        assert.ok(html.includes(message)); assert.ok(!html.includes("LKR 100.25")); assert.ok(!html.includes("Linked Shop"));
      }
    });
    await t.test("zero, large values, reversals and repayment language remain accurate", () => {
      const state = ready(); state.summary.data.total_outstanding_balance = "1999999999999.98";
      state.accounts.data.items[0].outstanding_balance = "0.00";
      state.transactions.data.items = [transaction({ entry_type: "repayment", balance_delta: "-100.25" }), transaction({ entry_id: 42, entry_type: "reversal", status: "reversal", amount: "1.00", balance_delta: "-100.25" })];
      const html = render(state); for (const text of ["LKR 1,999,999,999,999.98", "LKR 0.00", "Repayment record", "Reversal", "Balance adjustment", "LKR -100.25", "does not independently verify bank or card settlement"]) assert.ok(html.includes(text));
    });
    await t.test("sidebar links target supported routes or real dashboard sections", () => {
      const html = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(Sidebar)));
      for (const target of ["/customer/dashboard", "/customer/shops", "/customer/credit-accounts", "/customer/transactions", "/customer/notifications"]) assert.ok(html.includes('href="' + target + '"'));
      for (const id of ["my-credit", "transactions"]) assert.ok(render().includes('id="' + id + '"'));
      assert.ok(!html.includes("Planned")); assert.ok(html.includes('href="/customer/settings"')); assert.ok(html.includes('href="/customer/profile"'));
      assert.ok(html.includes('aria-label="Customer menu"')); assert.ok(html.includes("<dialog")); assert.ok(html.includes("LankaPex"));
    });
    await t.test("actual customer route renders through its role guard and new layout", async () => {
      const auth = { isAuthenticated: true, loading: false, token: "fixture-session", user: { user_id: 1, platform_role: "customer", account_status: "active", full_name: "Kumar" }, logout() {} };
      const route = value => renderToStaticMarkup(createElement(MemoryRouter, { initialEntries: ["/customer/dashboard"] }, createElement(AuthContext.Provider, { value }, createElement(Routes, null,
        createElement(Route, { element: createElement(Guard, { allowedRoles: ["customer"] }) }, createElement(Route, { path: "/customer", element: createElement(Layout) }, createElement(Route, { path: "dashboard", element: createElement(Dashboard) })))))));
      assert.ok(route(auth).includes("Customer Dashboard"));
      for (const role of ["shop_owner", "driver", "admin", "unknown"]) assert.ok(!route({ ...auth, user: { ...auth.user, platform_role: role } }).includes("Welcome, Kumar!"));
      assert.ok(!route({ ...auth, isAuthenticated: false }).includes("Welcome, Kumar!"));
      const app = await readFile(new URL('../src/App.jsx', import.meta.url), 'utf8');
      assert.ok(app.includes('<Route path="/customer" element={<CustomerLayout />}>'));
      assert.ok(app.includes('<Route path="dashboard" element={<CustomerDashboard />} />'));
      assert.ok(app.includes('<Route path="notifications" element={<CustomerNotifications />} />'));
      assert.ok(app.includes('path="/driver/dashboard"')); assert.ok(app.includes('element={<DriverDashboard />}'));
    });
    await t.test("new service uses authenticated shared Axios GETs and exact bounded preview params", async () => {
      const { default: api } = await server.ssrLoadModule('/src/services/api.js');
      const service = await server.ssrLoadModule('/src/services/customerDashboardService.js');
      const previous = api.defaults.adapter, previousStorage = globalThis.localStorage;
      const calls = []; globalThis.localStorage = { getItem: () => "fixture-session" };
      api.defaults.adapter = async config => { calls.push(config); return { data: {}, status: 200, statusText: 'OK', headers: {}, config }; };
      try {
        const controller = new AbortController();
        for (const method of ['getCustomerSummary', 'getCustomerShops', 'getCustomerCreditAccounts', 'getCustomerTransactions']) await service[method]({ signal: controller.signal });
        assert.deepEqual(calls.map(call => call.url), ['/customer/dashboard/summary', '/customer/shops', '/customer/credit-accounts', '/customer/transactions']);
        for (const call of calls) { assert.equal(call.method, 'get'); assert.equal(call.headers.Authorization, 'Bearer fixture-session'); assert.equal(call.signal, controller.signal); }
        for (const call of calls.slice(1)) assert.deepEqual(call.params, { page: 1, page_size: 5 });
      } finally { api.defaults.adapter = previous; if (previousStorage === undefined) delete globalThis.localStorage; else globalThis.localStorage = previousStorage; }
    });
    await t.test("new code uses responsive grids and does not persist ledger responses or poll notifications", async () => {
      const source = await readFile(new URL('../src/pages/customer/CustomerDashboard.jsx', import.meta.url), 'utf8');
      for (const cls of ['customer-table-wrap', 'min-w-0', 'overflow-wrap:anywhere', 'CustomerCreditOverview']) assert.ok(source.includes(cls));
      const controller = await readFile(new URL('../src/utils/customerDashboard.js', import.meta.url), 'utf8');
      assert.ok(!controller.includes('localStorage')); assert.ok(!controller.includes('sessionStorage')); assert.ok(!controller.includes('setInterval'));
      assert.ok(source.includes('key={user.user_id + ":" + token}'));
    });
  } finally { await server.close(); }
});
