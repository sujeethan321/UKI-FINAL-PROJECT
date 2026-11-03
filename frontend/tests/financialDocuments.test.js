import { test } from "node:test";
import assert from "node:assert/strict";
import { createFinancialReader, validateReceipt, validateStatement, validateOutstanding, formatDocumentMoney } from "../src/utils/financialDocuments.js";

const business = { business_id: 1, business_name: "Actual Shop", address: "Jaffna", phone: "0211234567" };
const customer = { customer_id: 10, business_id: 1, customer_name: "Customer One", phone: null, address: null };
const receipt = () => ({ business, customer, entry_id: 55, credit_account_id: 110, receipt_identifier: "ledger-repayment:55", receipt_number: "RP-actual", reference: "RP-actual", amount: "50.25", currency: "LKR", payment_method: "bank_transfer", recorded_at: "2026-11-04T12:30:00", notes: "Manual record", status: "recorded", reversal_entry_id: null, reversed_at: null });
const period = { start_date: "2026-01-01", end_date: "2026-01-31" };
const statement = () => ({ business, customer, currency: "LKR", ...period, opening_balance: "100.00", closing_balance: "49.75", total_credit_sales: "0.00", total_repayments: "50.25", reversal_impact: "0.00", outstanding_balance: "49.75", advance_balance: "0.00", transactions: [] });
const outstanding = () => ({ business_id: 1, currency: "LKR", total_outstanding: "49.75", customers_with_outstanding: 1, filtered_customers: 1, page: 1, page_size: 10, overdue_amount: null, customers: [{ customer_id: 10, outstanding_balance: "49.75", credit_limit: "1000.00", available_credit: "950.25" }] });
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };

test("receipt response must match business, committed transaction identity and status", () => {
  assert.equal(validateReceipt(receipt(), [1, 55]), true);
  for (const patch of [{ business: { ...business, business_id: 2 } }, { customer: { ...customer, business_id: 2 } }, { entry_id: 56 }, { receipt_identifier: "invented" }, { status: "pending" }, { amount: 50.25 }, { amount: "NaN" }, { recorded_at: "bad" }, { status: "reversed" }]) assert.equal(validateReceipt({ ...receipt(), ...patch }, [1, 55]), false);
  assert.equal(validateReceipt({ ...receipt(), status: "reversed", reversal_entry_id: 56, reversed_at: "2026-11-04T13:00:00" }, [1, 55]), true);
});
test("statements validate scope, selected period and signed balances", () => {
  assert.equal(validateStatement(statement(), [1, 10, period]), true);
  assert.equal(validateStatement({ ...statement(), closing_balance: "-5.15", reversal_impact: "-100.10" }, [1, 10, period]), true);
  for (const patch of [{ customer: { ...customer, customer_id: 11 } }, { end_date: "2026-02-01" }, { opening_balance: "bad" }, { transactions: [{ entry_id: 1, entry_type: "unknown" }] }]) assert.equal(validateStatement({ ...statement(), ...patch }, [1, 10, period]), false);
});
test("outstanding validates pagination scope and unavailable overdue", () => {
  assert.equal(validateOutstanding(outstanding(), [1, { page: 1, page_size: 10 }]), true);
  for (const patch of [{ business_id: 2 }, { page: 2 }, { overdue_amount: "49.75" }, { customers: [{ customer_id: 10, outstanding_balance: "NaN" }] }]) assert.equal(validateOutstanding({ ...outstanding(), ...patch }, [1, { page: 1, page_size: 10 }]), false);
});
test("document formatting supports exact large aggregates and negative statement balances", () => {
  assert.equal(formatDocumentMoney("1000000000000.10"), "LKR 1,000,000,000,000.10"); assert.equal(formatDocumentMoney("-100.05"), "LKR -100.05"); assert.equal(formatDocumentMoney(null), "Not available");
});
test("receipt remains absent until backend retrieval succeeds", async () => {
  const gate = deferred(), calls = []; const reader = createFinancialReader((...args) => { calls.push(args); return gate.promise; }, validateReceipt);
  const task = reader.load(1, 55); assert.equal(reader.getSnapshot().data, null); assert.equal(reader.getSnapshot().loading, true);
  assert.ok(calls[0][2].signal instanceof AbortSignal); gate.resolve(receipt()); assert.deepEqual(await task, receipt()); assert.equal(reader.getSnapshot().loading, false);
});
test("late business/customer responses cannot replace a newer read", async () => {
  const first = deferred(); const reader = createFinancialReader((b, id) => id === 55 ? first.promise : Promise.resolve({ ...receipt(), entry_id: 56, receipt_identifier: "ledger-repayment:56" }), validateReceipt);
  const old = reader.load(1, 55); await reader.load(1, 56); first.resolve(receipt()); await old; assert.equal(reader.getSnapshot().data.entry_id, 56);
});
test("closing or unmounting aborts reads and clears sensitive documents", async () => {
  const gate = deferred(); const reader = createFinancialReader(() => gate.promise, validateReceipt); const task = reader.load(1, 55); reader.dispose(); gate.resolve(receipt()); await task;
  assert.equal(reader.getSnapshot().data, null); assert.equal(reader.getSnapshot().loading, false);
});
test("failed and malformed responses never become printable documents", async () => {
  for (const payload of [null, { ...receipt(), entry_id: 99 }, { ...receipt(), status: "pending" }]) { const reader = createFinancialReader(async () => payload, validateReceipt); assert.equal(await reader.load(1, 55), null); assert.equal(reader.getSnapshot().data, null); assert.ok(reader.getSnapshot().error); }
});
for (const status of [401, 403, 404, 409, 422, 500, undefined]) {
  test(`document read error ${status || "network"} is safe and retryable`, async () => {
    let fail = true; const reader = createFinancialReader(async () => { if (fail) throw { response: { status, data: { detail: "private SQL secret" } } }; return receipt(); }, validateReceipt);
    await reader.load(1, 55); assert.equal(reader.getSnapshot().data, null); assert.ok(reader.getSnapshot().error); assert.ok(!reader.getSnapshot().error.includes("secret")); fail = false;
    await reader.load(1, 55); assert.ok(reader.getSnapshot().data); assert.equal(reader.getSnapshot().error, "");
  });
}
test("filter changes discard old outstanding responses", async () => {
  const gate = deferred(); const reader = createFinancialReader((b, filters) => filters.page === 1 ? gate.promise : Promise.resolve({ ...outstanding(), page: 2, customers: [] }), validateOutstanding);
  const first = reader.load(1, { page: 1, page_size: 10 }); await reader.load(1, { page: 2, page_size: 10 }); gate.resolve(outstanding()); await first; assert.equal(reader.getSnapshot().data.page, 2);
});
