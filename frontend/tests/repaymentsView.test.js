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
    transactions: [{ entry_id: 1, entry_type: "repayment", payment_method: "bank_transfer", reference: "RP-history", credit: "100.00",
      running_balance: "100.00", recorded_at: "2026-11-03T12:00:00", due_at: "2026-12-03T12:00:00" }] },
  contextLoading: false, customersLoading: false, detailsLoading: false, saving: false,
  contextError: "", customersError: "", detailsError: "", storageError: "", error: "", amount: "50.25", payment_method: "cash", receipt_number: "", notes: "", success: null, uncertain: false,
});

test("repayment React view, routes, navigation and Axios contract", async t => {
  const server = await createServer({ logLevel: "silent", appType: "custom", server: { middlewareMode: true, hmr: false } });
  try {
    const { RepaymentsView } = await server.ssrLoadModule("/src/pages/shopOwner/ShopOwnerRepayments.jsx");
    const render = state => renderToStaticMarkup(createElement(MemoryRouter, null, createElement(RepaymentsView, { state, actions: {} })));
    const disabled = html => /\sdisabled(?:=|\s|>)/.test(html.match(/<button\b[^>]*type="submit"[^>]*>/)?.[0] || "");
    await t.test("existing UI cards, full payment, methods and real history render", () => {
      const html = render(stateFor()); for (const value of ["Repayments", "Outstanding Balance", "Available Credit", "Credit Limit", "Full Payment", "Cash", "Bank transfer", "Card", "RP-history", "LKR 900.00", "bg-[#0BAAB4]", "border-[#E1EAF4]"]) assert.ok(html.includes(value), value);
      assert.equal(disabled(html), false); assert.ok(!html.includes("Sale amount"));
    });
    await t.test("loading, missing business and pending business render", () => {
      const s = stateFor(); s.contextLoading = true; assert.match(render(s), /Loading business information/); assert.equal(disabled(render(s)), true);
      s.contextLoading = false; s.businesses = []; s.businessId = ""; assert.match(render(s), /No business is linked/);
      s.businesses = [{ business_id: 1, approval_status: "pending" }]; s.businessId = "1"; assert.match(render(s), /Business approval is required/);
    });
    await t.test("suspended allowed; no account, zero debt and closed blocked", () => {
      for (const status of ["suspended", "closed", null, "zero"]) {
        const s = stateFor(); if (status === null) s.details.credit_account = null; else if (status === "zero") s.details.outstanding_balance = "0.00"; else s.details.credit_account.account_status = status;
        const html = render(s); assert.equal(disabled(html), status !== "suspended"); if (status === "zero") assert.match(html, /no outstanding debt/);
      }
    });
    await t.test("invalid input and overpayment disable submit with specific feedback", () => {
      for (const amount of ["0", "1.001", "101"]) { const s = stateFor(); s.amount = amount; assert.equal(disabled(render(s)), true); assert.match(render(s), /positive amount|exceeds outstanding/); }
      const s = stateFor(); s.payment_method = "cheque"; assert.equal(disabled(render(s)), true);
    });
    await t.test("saving disables submission, uncertain recovery permits same-payment retry", () => {
      const s = stateFor(); s.saving = true; assert.equal(disabled(render(s)), true); assert.match(render(s), /Recording/);
      s.saving = false; s.uncertain = true; s.details.outstanding_balance = "0.00"; s.details.credit_account.account_status = "closed";
      const html = render(s); assert.equal(disabled(html), false); assert.match(html, /Retry Same Repayment/); assert.match(html, /without recording it twice/); assert.match(html, /After Checking Ledger, Start New Repayment/);
    });
    await t.test("success shows response method, receipt and updated balances", () => {
      const s = stateFor(); s.success = { entry_id: 555, reference: "RP-confirmed", amount: "50.25", payment_method: "bank_transfer", outstanding_balance: "49.75", available_credit: "950.25", recorded_at: "2026-11-03T12:00:00", replayed: false };
      const html = render(s); for (const text of ["Repayment recorded successfully", "Bank transfer", "RP-confirmed", "LKR 49.75", "LKR 950.25"]) assert.ok(html.includes(text), text);
      s.success.replayed = true; assert.match(render(s), /No duplicate entry/);
    });
    await t.test("sidebar retains existing links and enables repayments with unchanged styling", async () => {
      const { default: Sidebar } = await server.ssrLoadModule("/src/components/shopOwner/ShopOwnerSidebar.jsx");
      const html = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(Sidebar)));
      for (const path of ["dashboard", "customers", "credit-sales", "repayments"]) assert.ok(html.includes(`href="/shop-owner/${path}"`));
      assert.ok(html.includes("bg-[#10243E]")); assert.ok(html.includes('href="/shop-owner/products"'));
      await server.ssrLoadModule("/src/App.jsx");
    });
    await t.test("repayment service uses authenticated Axios and exact endpoint/payload", async () => {
      const { default: api } = await server.ssrLoadModule("/src/services/api.js");
      const { createShopOwnerRepayment } = await server.ssrLoadModule("/src/services/shopOwnerRepaymentService.js");
      const adapter = api.defaults.adapter, storage = globalThis.localStorage; let config;
      globalThis.localStorage = { getItem: () => "controlled-test-token" };
      api.defaults.adapter = async request => { config = request; return { data: { entry_id: 555 }, status: 201, statusText: "Created", headers: {}, config: request }; };
      try {
        const payload = { customer_id: 10, amount: "50.25", payment_method: "cash", receipt_number: null, notes: null, idempotency_key: "repayment:controlled-test" };
        assert.equal((await createShopOwnerRepayment("1", payload)).entry_id, 555); assert.equal(config.url, "/shop-owner/repayments"); assert.equal(config.method, "post"); assert.deepEqual(config.params, { business_id: "1" }); assert.deepEqual(JSON.parse(config.data), payload); assert.equal(config.headers.get("Authorization"), "Bearer controlled-test-token");
      } finally { api.defaults.adapter = adapter; if (storage === undefined) delete globalThis.localStorage; else globalThis.localStorage = storage; }
    });
  } finally { await server.close(); }
});
