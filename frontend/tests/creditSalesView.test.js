import { test } from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { createServer } from "vite";

// Render actual JSX with Vite's existing transform; no DOM package or network API calls.
const stateFor = () => ({
  businesses: [{ business_id: 1, business_name: "Shop One", approval_status: "approved" }],
  businessId: "1", customerId: "10", customers: [{ customer_id: 10, customer_name: "Test Customer" }],
  details: { business_id: 1, customer: { business_id: 1, customer_id: 10, customer_name: "Test Customer" },
    credit_account: { credit_account_id: 110, account_status: "active", credit_limit: "1000.00" },
    outstanding_balance: "100.00", advance_balance: "0.00", available_credit: "900.00",
    transactions: [{ entry_id: 1, entry_type: "credit_sale", reference: "CS-history", debit: "100.00",
      running_balance: "100.00", recorded_at: "2026-11-03T12:00:00", due_at: "2026-12-03T12:00:00" }] },
  contextLoading: false, customersLoading: false, detailsLoading: false, saving: false,
  contextError: "", customersError: "", detailsError: "", storageError: "", error: "", amount: "100.25", notes: "", success: null, uncertain: false,
});

test("credit-sale React view, navigation and Axios contract", async t => {
  const server = await createServer({ logLevel: "silent", appType: "custom", server: { middlewareMode: true, hmr: false } });
  try {
    const { CreditSalesView } = await server.ssrLoadModule("/src/pages/shopOwner/ShopOwnerCreditSales.jsx");
    const render = state => renderToStaticMarkup(createElement(MemoryRouter, null,
      createElement(CreditSalesView, { state, actions: {} })));
    const submitDisabled = html => {
      const tag = html.match(/<button\b[^>]*type="submit"[^>]*>/)?.[0];
      assert.ok(tag, "Expected a credit-sale submit button");
      return /\sdisabled(?:=|\s|>)/.test(tag);
    };
    await t.test("loading and empty states render without financial mock values", () => {
      const state = stateFor(); state.contextLoading = true; state.details = null; state.customers = [];
      assert.match(render(state), /Loading business information/);
      state.contextLoading = false; state.businesses = []; state.businessId = "";
      const html = render(state);
      assert.match(html, /No business is linked/);
      assert.match(html, /href="\/shop-owner\/business\/register"/);
    });
    await t.test("account data, effective history and original design classes render", () => {
      const html = render(stateFor());
      for (const text of ["Outstanding Balance", "Credit Limit", "Available Credit", "LKR 900.00", "CS-history", "bg-[#0BAAB4]", "border-[#E1EAF4]"]) assert.ok(html.includes(text), text);
      assert.equal(submitDisabled(html), false);
      assert.ok(!html.includes('name="due_at"'));
      assert.ok(!html.includes('name="receipt_number"'));
    });
    await t.test("no account, suspended and closed states disable new sales", () => {
      for (const status of [null, "suspended", "closed"]) {
        const state = stateFor();
        if (status) state.details.credit_account.account_status = status;
        else state.details.credit_account = null;
        const html = render(state);
        assert.equal(submitDisabled(html), true);
        assert.match(html, status ? /New credit sales require an active account/ : /no credit account/);
      }
    });
    await t.test("saving disables submissions and labels the loading state", () => {
      const state = stateFor(); state.saving = true;
      const html = render(state);
      assert.equal(submitDisabled(html), true);
      assert.match(html, /Recording/);
    });
    await t.test("uncertain recovery is explicit and allows identical replay on suspended account", () => {
      const state = stateFor(); state.uncertain = true; state.details.credit_account.account_status = "suspended";
      const html = render(state);
      assert.match(html, /Retry Same Sale/);
      assert.match(html, /saved request key will be reused/);
      assert.equal(submitDisabled(html), false);
    });
    await t.test("confirmation displays real response reference and updated amounts", () => {
      const state = stateFor(); state.success = { entry_id: 555, reference: "CS-confirmed", amount: "100.25",
        outstanding_balance: "200.25", available_credit: "799.75", recorded_at: "2026-11-03T12:00:00", due_at: null, replayed: false };
      const html = render(state);
      assert.match(html, /Credit sale recorded successfully/);
      for (const text of ["CS-confirmed", "555", "LKR 100.25", "LKR 200.25", "LKR 799.75"]) assert.ok(html.includes(text));
      state.success.replayed = true;
      assert.match(render(state), /No duplicate entry was created/);
    });
    await t.test("sidebar preserves dashboard/customer links, enables sales, enables repayments", async () => {
      const { default: Sidebar } = await server.ssrLoadModule("/src/components/shopOwner/ShopOwnerSidebar.jsx");
      const html = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(Sidebar)));
      for (const path of ["dashboard", "customers", "credit-sales"]) assert.ok(html.includes(`href="/shop-owner/${path}"`));
      assert.ok(html.includes('href="/shop-owner/repayments"'));
    });
    await t.test("dashboard quick action links to credit sales without enabling unrelated features", async () => {
      const { default: QuickActions } = await server.ssrLoadModule("/src/components/shopOwner/QuickActions.jsx");
      const html = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(QuickActions, { businessId: 1 })));
      assert.match(html, /href="\/shop-owner\/credit-sales"/);
      assert.match(html, /Record Credit Sale/);
      const link = html.match(/<a\b[^>]*href="\/shop-owner\/credit-sales"[^>]*>/)?.[0];
      assert.ok(link);
      assert.ok(!link.includes('aria-disabled="true"'));
      assert.ok(!link.includes("coming soon"));
      assert.ok(!html.includes('href="/shop-owner/products"'));
    });
    await t.test("existing dashboard and customer management components still render", async () => {
      const { default: Dashboard } = await server.ssrLoadModule("/src/pages/shopOwner/ShopOwnerDashboard.jsx");
      const dashboard = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(Dashboard)));
      assert.match(dashboard, /Loading your business information/);
      const { default: Customers } = await server.ssrLoadModule("/src/pages/shopOwner/ShopOwnerCustomers.jsx");
      const customers = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(Customers)));
      assert.match(customers, /Customers/);
      assert.match(customers, /Add Customer/);
      const { default: AddCustomer } = await server.ssrLoadModule("/src/pages/shopOwner/AddCustomerModal.jsx");
      const add = renderToStaticMarkup(createElement(AddCustomer, { businessId: 1, onClose() {}, onCreated() {} }));
      for (const name of ["customer_name", "phone", "address"]) assert.ok(add.includes(`name="${name}"`));
      const { default: ManageCustomer } = await server.ssrLoadModule("/src/pages/shopOwner/ManageCustomerModal.jsx");
      for (const mode of ["edit", "credit"]) {
        const html = renderToStaticMarkup(createElement(ManageCustomer, { businessId: 1, details: stateFor().details, mode, onClose() {}, onSaved() {} }));
        assert.match(html, mode === "edit" ? /Edit Customer/ : /Manage Credit Account/);
      }
    });
    await t.test("sale service uses existing Axios interceptor and exact backend payload location", async () => {
      const { default: api } = await server.ssrLoadModule("/src/services/api.js");
      const { createShopOwnerCreditSale } = await server.ssrLoadModule("/src/services/shopOwnerCreditSaleService.js");
      const originalAdapter = api.defaults.adapter;
      const previousStorage = globalThis.sessionStorage;
      globalThis.sessionStorage = { getItem: () => "controlled-test-token" };
      let config;
      api.defaults.adapter = async request => {
        config = request;
        return { data: { entry_id: 555 }, status: 201, statusText: "Created", headers: {}, config: request };
      };
      try {
        const payload = { customer_id: 10, amount: "100.25", notes: null, idempotency_key: "credit-sale:controlled-test" };
        const result = await createShopOwnerCreditSale("1", payload);
        assert.equal(result.entry_id, 555);
        assert.equal(config.url, "/shop-owner/credit-sales");
        assert.equal(config.method, "post");
        assert.deepEqual(config.params, { business_id: "1" });
        assert.deepEqual(JSON.parse(config.data), payload);
        assert.equal(config.headers.get("Authorization"), "Bearer controlled-test-token");
      } finally {
        api.defaults.adapter = originalAdapter;
        if (previousStorage === undefined) delete globalThis.sessionStorage; else globalThis.sessionStorage = previousStorage;
      }
    });
  } finally { await server.close(); }
});
