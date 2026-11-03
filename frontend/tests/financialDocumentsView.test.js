import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const business = { business_id: 1, business_name: "Actual Shop", address: "Jaffna", phone: "0211234567" };
const customer = { customer_id: 10, business_id: 1, customer_name: "Customer One", phone: null };
const receipt = { business, customer, entry_id: 55, credit_account_id: 110, receipt_identifier: "ledger-repayment:55", receipt_number: "RP-actual", reference: "RP-actual", amount: "50.25", currency: "LKR", payment_method: "bank_transfer", recorded_at: "2026-11-04T12:30:00", notes: "<script>private</script>", status: "recorded" };

test("financial document JSX, printing and Axios contracts", async t => {
  const server = await createServer({ logLevel: "silent", appType: "custom", server: { middlewareMode: true, hmr: false } });
  try {
    const { ReceiptContent, ReceiptActions, StatementContent, OutstandingView } = await server.ssrLoadModule("/src/pages/shopOwner/FinancialDocuments.jsx");
    const render = (Component, props) => renderToStaticMarkup(createElement(Component, props));
    await t.test("receipt displays actual identity, amount, method and escaped notes", () => {
      const html = render(ReceiptContent, { receipt });
      for (const value of ["LankaPex", "Actual Shop", "Jaffna", "Customer One", "RP-actual", "LKR 50.25", "Bank transfer", "2026-11-04 12:30:00"]) assert.ok(html.includes(value), value);
      assert.ok(!html.includes("<script>")); assert.ok(html.includes("&lt;script&gt;")); assert.ok(!html.includes("REVERSED / VOID"));
    });
    await t.test("reversed receipts are clearly void and preserve the amount/reference", () => {
      const html = render(ReceiptContent, { receipt: { ...receipt, status: "reversed", reversal_entry_id: 56, reversed_at: "2026-11-04T13:00:00" } });
      assert.match(html, /REVERSED \/ VOID/); assert.match(html, /no longer settles debt/); assert.match(html, /RP-actual/); assert.match(html, /LKR 50.25/);
    });
    await t.test("receipt actions never fabricate or pre-render a successful receipt", () => {
      const html = render(ReceiptActions, { businessId: 1, entryId: 55 }); assert.match(html, /View Receipt/); assert.match(html, /Print Receipt/); assert.ok(!html.includes("RP-actual")); assert.ok(!html.includes('role="dialog"'));
    });
    await t.test("statement renders opening/closing and dated reversal impact, with reversed-payment receipt access", () => {
      const statement = { business, customer, start_date: "2026-01-01", end_date: "2026-02-28", opening_balance: "100.10", total_credit_sales: "20.20", total_repayments: "30.05", reversal_impact: "-100.10", closing_balance: "-9.85", outstanding_balance: "0.00", reversal_policy: "Opposite original delta on reversal date", time_basis: "Database recorded clock", historical_limitations: "Not an immutable snapshot", transactions: [{ entry_id: 55, entry_type: "repayment", status: "reversed", reference: "RP-actual", recorded_at: "2026-02-01T10:00:00", debit: "0.00", credit: "30.05", running_balance: "70.05" }, { entry_id: 56, entry_type: "reversal", status: "reversal", reverses_entry_id: 1, reference: "TXN-56", debit: "0.00", credit: "100.10", running_balance: "-9.85" }] };
      const html = render(StatementContent, { statement }); for (const value of ["Opening balance", "Closing balance", "LKR -9.85", "reversed", "reverses #1", "Print Receipt", "Not an immutable snapshot"]) assert.ok(html.includes(value), value);
    });
    await t.test("outstanding uses actual totals, no-account states and unavailable overdue", () => {
      const data = { total_outstanding: "500.20", customers_with_outstanding: 1, overdue_unavailable_reason: "No sale allocations", customers: [{ customer_id: 10, customer_name: "No Account", account_status: "no_account", outstanding_balance: "0.00", credit_limit: null, available_credit: null }] };
      const html = render(OutstandingView, { state: { data }, onSelectCustomer() {} }); for (const value of ["LKR 500.20", "Unavailable", "Not set", "No Account", "Select Customer"]) assert.ok(html.includes(value), value);
      assert.match(render(OutstandingView, { state: { loading: true } }), /Loading outstanding/); assert.match(render(OutstandingView, { state: { error: "Unable to load" } }), /role="alert"/);
      assert.match(render(OutstandingView, { state: { data: { ...data, customers: [] } } }), /No customers match/);
    });
    await t.test("print CSS isolates only the top document without blanking ordinary pages", async () => {
      const css = await readFile(new URL("../src/pages/shopOwner/financialDocuments.css", import.meta.url), "utf8");
      assert.match(css, /@media print/); assert.match(css, /body:has\(> \.lpx-document-overlay\)/); assert.match(css, /:has\(~ \.lpx-document-overlay\)/); assert.match(css, /\.lpx-no-print/); assert.match(css, /table-header-group/);
    });
    await t.test("GET services use existing authenticated Axios and scoped paths/filters", async () => {
      const { default: api } = await server.ssrLoadModule("/src/services/api.js"); const service = await server.ssrLoadModule("/src/services/shopOwnerFinancialDocumentService.js");
      const original = api.defaults.adapter, storage = globalThis.sessionStorage; const calls = []; globalThis.sessionStorage = { getItem: () => "controlled-token" };
      api.defaults.adapter = async request => { calls.push(request); return { data: { ok: true }, status: 200, statusText: "OK", headers: {}, config: request }; };
      try {
        const signal = new AbortController().signal; await service.getRepaymentReceipt(1, 55, { signal }); await service.getCustomerStatement(1, 10, { start_date: "2026-01-01", end_date: "2026-01-31" }, { signal }); await service.getOutstandingPayments(1, { search: "One", outstanding_only: true, page: 1, page_size: 10 }, { signal });
        assert.deepEqual(calls.map(c => c.url), ["/shop-owner/repayments/55/receipt", "/shop-owner/customers/10/statement", "/shop-owner/outstanding-payments"]);
        for (const c of calls) { assert.equal(c.method, "get"); assert.equal(c.params.business_id, 1); assert.equal(c.signal, signal); assert.equal(c.headers.get("Authorization"), "Bearer controlled-token"); }
        assert.equal(calls[1].params.start_date, "2026-01-01"); assert.equal(calls[2].params.outstanding_only, true);
      } finally { api.defaults.adapter = original; if (storage === undefined) delete globalThis.sessionStorage; else globalThis.sessionStorage = storage; }
    });
  } finally { await server.close(); }
});
