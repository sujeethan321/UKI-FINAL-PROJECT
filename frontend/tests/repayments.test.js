import { test } from "node:test";
import assert from "node:assert/strict";
import { createRepaymentWorkflow } from "../src/pages/shopOwner/repaymentWorkflow.js";
import { decimalAmount, minorUnits, formatCreditMoney, secureRepaymentKey, sessionRepaymentStore } from "../src/utils/repayment.js";

const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
const rejectWith = status => ({ response: { status, data: { detail: status === 422
  ? [{ loc: ["body", "amount"], msg: "Invalid amount" }] : status === 409 ? "Sale amount exceeds available credit" : "private server diagnostic" } } });
const customerDetails = (business = "1", customer = 10) => ({
  business_id: Number(business), customer: { business_id: Number(business), customer_id: customer, customer_name: "Test Customer" },
  credit_account: { credit_account_id: customer + 100, credit_limit: "1000.00", account_status: "active", payment_term_days: 30 },
  outstanding_balance: "100.00", advance_balance: "0.00", available_credit: "900.00",
  transactions: [{ entry_id: 1, entry_type: "credit_sale", reference: "CS-previous", debit: "100.00", running_balance: "100.00", recorded_at: "2026-11-03T10:00:00", due_at: "2026-12-03T10:00:00" }],
});
const successFor = (business, payload) => ({
  entry_id: 555, business_id: Number(business), customer_id: payload.customer_id,
  credit_account_id: payload.customer_id + 100, currency: "LKR", amount: payload.amount,
  notes: payload.notes, payment_method: payload.payment_method, outstanding_balance: "49.75", advance_balance: "0.00", available_credit: "950.25",
  recorded_at: "2026-11-03T12:00:00", due_at: "2026-12-03T12:00:00", receipt_number: "RP-confirmed",
  reference: "RP-confirmed", replayed: false,
});

function harness(overrides = {}, sharedStore = null) {
  let slot = null;
  const store = sharedStore || {
    read: () => slot && { ...slot }, write: value => { slot = { ...value }; },
    clear: key => { if (!key || slot?.key === key) slot = null; },
    reject: key => { if (slot?.key === key) slot = { ...slot, pending: false }; },
  };
  const calls = { businesses: [], customers: [], details: [], record: [] };
  let recorded = null;
  let recordBehavior = overrides.record;
  const api = {
    businesses: async () => { calls.businesses.push(true); return overrides.businesses ? overrides.businesses() : { businesses: [
      { business_id: 1, business_name: "Shop One", approval_status: "approved" },
      { business_id: 2, business_name: "Shop Two", approval_status: "approved" },
      { business_id: 3, business_name: "Pending Shop", approval_status: "pending" },
    ] }; },
    customers: async (business, options) => {
      calls.customers.push([business, options]);
      if (overrides.customers) return overrides.customers(business, options);
      return { business_id: Number(business), customers: [
        { customer_id: Number(business) * 10, customer_name: "Test Customer", phone: "0771234567" },
        { customer_id: Number(business) * 10 + 1, customer_name: "Second Customer", phone: null },
      ] };
    },
    details: async (business, customer, options) => {
      calls.details.push([business, customer, options]);
      if (overrides.details) return overrides.details(business, customer, options);
      const data = customerDetails(business, customer);
      if (recorded && recorded.customer_id === customer) {
        Object.assign(data, { outstanding_balance: recorded.outstanding_balance, available_credit: recorded.available_credit });
        data.transactions.push({ entry_id: recorded.entry_id, entry_type: "repayment", credit: recorded.amount, payment_method: recorded.payment_method,
          reference: recorded.reference, running_balance: recorded.outstanding_balance,
          recorded_at: recorded.recorded_at, due_at: recorded.due_at });
      }
      return data;
    },
    record: async (business, payload) => {
      calls.record.push([business, payload]);
      const data = recordBehavior ? await recordBehavior(business, payload) : successFor(business, payload);
      recorded = data;
      return data;
    },
  };
  let keys = 0;
  const workflow = createRepaymentWorkflow({ api, store, initialBusinessId: overrides.initialBusinessId, initialCustomerId: overrides.initialCustomerId, makeKey: () => `repayment:test-${++keys}` });
  return { workflow, api, calls, store, setRecord: behavior => { recordBehavior = behavior; },
    ready: async () => { await workflow.loadBusinesses(); await workflow.selectCustomer("10"); },
    fill: (amount = "50.25", notes = "Goods supplied") => { workflow.edit("amount", amount); workflow.edit("notes", notes); } };
}

for (const amount of ["0", "-1", "1.001", "1e2", "NaN", "Infinity", "", "1000000000000", "1,000", "100.01"]) {
  test(`invalid or excessive repayment ${JSON.stringify(amount)} blocked`, async () => {
    const h = harness(); await h.ready(); h.fill(amount); await h.workflow.submit();
    assert.equal(h.calls.record.length, 0); assert.ok(h.workflow.getSnapshot().error);
  });
}
test("business selection scopes customers; pending business cannot submit", async () => {
  const h = harness(); await h.ready(); assert.equal(h.calls.details[0][0], "1"); assert.equal(h.calls.details[0][1], 10);
  await h.workflow.selectBusiness("3"); h.fill(); await h.workflow.submit(); assert.equal(h.calls.record.length, 0); assert.deepEqual(h.workflow.getSnapshot().customers, []);
});
for (const mode of ["none", "zero", "closed", "unknown", "suspended", "active"]) {
  test(`account policy: ${mode}`, async () => {
    const h = harness({ details: async () => { const d = customerDetails(); if (mode === "none") d.credit_account = null; else if (mode === "zero") d.outstanding_balance = "0.00"; else d.credit_account.account_status = mode; return d; } });
    await h.ready(); h.fill(); await h.workflow.submit(); assert.equal(h.calls.record.length, ["suspended", "active"].includes(mode) ? 1 : 0);
  });
}
for (const method of ["cash", "bank_transfer", "card"]) {
  test(`partial repayment: ${method}, exact payload and refreshed history`, async () => {
    const h = harness(); await h.ready(); h.fill(); h.workflow.edit("payment_method", method); h.workflow.edit("receipt_number", " BANK-123 ");
    h.setRecord(async (b, p) => ({ ...successFor(b, p), reference: "BANK-123", receipt_number: "BANK-123" }));
    await h.workflow.submit(); const [business, payload] = h.calls.record[0]; assert.equal(business, "1");
    assert.deepEqual(Object.keys(payload).sort(), ["amount", "customer_id", "idempotency_key", "notes", "payment_method", "receipt_number"].sort());
    assert.equal(payload.amount, "50.25"); assert.equal(payload.payment_method, method); assert.equal(payload.receipt_number, "BANK-123");
    const s = h.workflow.getSnapshot(); assert.equal(s.success.payment_method, method); assert.equal(s.amount, "");
    assert.equal(s.details.outstanding_balance, "49.75"); assert.equal(s.details.available_credit, "950.25"); assert.equal(s.details.transactions.at(-1).entry_type, "repayment");
    assert.equal(h.calls.details.length, 2); assert.equal(h.store.read(), null);
  });
}
test("Full Payment uses exact outstanding decimal string", async () => {
  const h = harness(); await h.ready(); h.workflow.fullPayment(); assert.equal(h.workflow.getSnapshot().amount, "100.00");
  h.setRecord(async (b, p) => ({ ...successFor(b, p), outstanding_balance: "0.00", available_credit: "1000.00" }));
  await h.workflow.submit(); assert.equal(h.workflow.getSnapshot().details.outstanding_balance, "0.00");
});
for (const [field, value] of [["payment_method", "cheque"], ["receipt_number", "RP-reserved"], ["receipt_number", "CS-reserved"], ["receipt_number", "a".repeat(61)], ["receipt_number", "bad\nref"], ["notes", "x".repeat(2001)]]) {
  test(`invalid ${field}: ${value.slice(0, 20)}`, async () => { const h = harness(); await h.ready(); h.fill(); h.workflow.edit(field, value); await h.workflow.submit(); assert.equal(h.calls.record.length, 0); });
}
test("duplicate clicks and edits during submission cannot create a second operation", async () => {
  const gate = deferred(); const h = harness({ record: (b, p) => gate.promise.then(() => successFor(b, p)) }); await h.ready(); h.fill();
  const one = h.workflow.submit(), two = h.workflow.submit(); await new Promise(resolve => setTimeout(resolve, 15)); assert.equal(h.calls.record.length, 1);
  h.workflow.edit("amount", "1"); await h.workflow.selectBusiness("2"); await h.workflow.selectCustomer("11"); assert.equal(h.workflow.getSnapshot().amount, "50.25");
  gate.resolve(); await Promise.all([one, two]); assert.ok(h.workflow.getSnapshot().success);
});
for (const error of [{ code: "ECONNABORTED" }, {}, { response: { status: 500, data: { detail: "private SQL" } } }]) {
  test(`uncertain ${error.code || error.response?.status || "network"} retains key and permits replay after settlement`, async () => {
    const h = harness({ record: async () => { throw error; } }); await h.ready(); h.fill(); await h.workflow.submit(); const key = h.store.read().key;
    assert.equal(h.store.read().pending, true); assert.equal(h.workflow.getSnapshot().uncertain, true); assert.match(h.workflow.getSnapshot().error, /uncertain/);
    assert.ok(!h.workflow.getSnapshot().error.includes("private SQL"));
    h.api.details = async () => { const d = customerDetails(); d.outstanding_balance = "0.00"; d.credit_account.account_status = "closed"; return d; };
    await h.workflow.refresh(); h.setRecord(async (b, p) => ({ ...successFor(b, p), replayed: true, outstanding_balance: "0.00" })); await h.workflow.submit();
    assert.equal(h.calls.record[1][1].idempotency_key, key); assert.equal(h.workflow.getSnapshot().success.replayed, true);
  });
}
for (const [field, value] of [["amount", "10"], ["payment_method", "card"], ["receipt_number", "OTHER"], ["notes", "Changed"]]) {
  test(`uncertain payment prevents changed ${field} until explicit ledger verification`, async () => {
    const h = harness({ record: async () => { throw {}; } }); await h.ready(); h.fill(); await h.workflow.submit(); const key = h.store.read().key;
    h.workflow.edit(field, value); await h.workflow.submit(); assert.equal(h.calls.record.length, 1); assert.equal(h.store.read().key, key); assert.match(h.workflow.getSnapshot().error, /unresolved/);
    h.workflow.newRepayment(); h.fill(); h.setRecord(null); await h.workflow.submit(); assert.equal(h.calls.record.length, 2); assert.notEqual(h.calls.record[1][1].idempotency_key, key);
  });
}
test("pending operation survives remount and blocks business/customer changes", async () => {
  const h = harness({ record: async () => { throw {}; } }); await h.ready(); h.fill(); await h.workflow.submit(); const key = h.store.read().key; h.workflow.dispose();
  const next = harness({}, h.store); await next.ready(); assert.equal(next.workflow.getSnapshot().uncertain, true); await next.workflow.selectCustomer("11"); next.fill(); await next.workflow.submit();
  assert.equal(next.calls.record.length, 0); await next.workflow.selectBusiness("2"); await next.workflow.selectCustomer("20"); next.fill(); await next.workflow.submit();
  assert.equal(next.calls.record.length, 0); assert.equal(next.store.read().key, key);
});
for (const status of [401, 403, 404, 409, 422]) {
  test(`HTTP ${status} safe feedback preserves form`, async () => {
    const h = harness({ record: async () => { throw rejectWith(status); } }); await h.ready(); h.fill(); await h.workflow.submit(); const s = h.workflow.getSnapshot();
    assert.equal(s.amount, "50.25"); assert.ok(s.error); assert.ok(!s.error.includes("private server diagnostic")); assert.equal(s.uncertain, status === 409);
  });
}
test("malformed success remains uncertain", async () => {
  const h = harness({ record: async (b, p) => ({ ...successFor(b, p), payment_method: "cheque" }) }); await h.ready(); h.fill(); await h.workflow.submit();
  assert.equal(h.workflow.getSnapshot().success, null); assert.equal(h.store.read().pending, true);
});
test("customer switching ignores late response even if transport ignores abort", async () => {
  const gate = deferred(); const h = harness({ details: async (b, c) => c === 10 ? gate.promise : customerDetails(b, c) }); await h.workflow.loadBusinesses();
  const first = h.workflow.selectCustomer("10"); await h.workflow.selectCustomer("11"); gate.resolve(customerDetails()); await first; assert.equal(h.workflow.getSnapshot().details.customer.customer_id, 11);
});
test("business switching ignores late customer list", async () => {
  const gate = deferred(); const h = harness({ customers: async b => b === "1" ? gate.promise : { business_id: 2, customers: [{ customer_id: 20 }] } });
  const first = h.workflow.loadBusinesses(); await new Promise(resolve => setTimeout(resolve, 0)); await h.workflow.selectBusiness("2"); gate.resolve({ business_id: 1, customers: [{ customer_id: 10 }] }); await first;
  assert.equal(h.workflow.getSnapshot().businessId, "2"); assert.equal(h.workflow.getSnapshot().customers[0].customer_id, 20);
});
test("failed refresh preserves success and updated response balances", async () => {
  const h = harness(); await h.ready(); h.fill(); h.api.details = async () => { throw rejectWith(404); }; await h.workflow.submit(); const s = h.workflow.getSnapshot();
  assert.ok(s.success); assert.equal(s.amount, ""); assert.equal(s.details.outstanding_balance, "49.75"); assert.ok(s.detailsError); assert.equal(s.uncertain, false);
});
test("storage unavailable prevents recording", async () => {
  const h = harness({}, { read() { throw Error(); }, clear() { throw Error(); } }); await h.ready(); h.fill(); await h.workflow.submit(); assert.equal(h.calls.record.length, 0);
});
test("missing or inaccessible businesses cannot dispatch", async () => {
  for (const businesses of [async () => ({ businesses: [] }), async () => { throw rejectWith(403); }]) { const h = harness({ businesses }); await h.ready(); h.fill(); await h.workflow.submit(); assert.equal(h.calls.record.length, 0); }
});
test("session storage is scoped by user and excludes financial data", () => {
  const original = globalThis.sessionStorage; const data = new Map(); globalThis.sessionStorage = { getItem: k => data.get(k) || null, setItem: (k, v) => data.set(k, v), removeItem: k => data.delete(k) };
  try { const s = sessionRepaymentStore(1); s.write({ key: secureRepaymentKey(), fingerprint: "a".repeat(64), pending: true }); assert.equal(s.read().pending, true); assert.equal(sessionRepaymentStore(2).read(), null); assert.match([...data.keys()][0], /repayment/); assert.ok(![...data.values()][0].includes("customer")); s.clear(); assert.equal(s.read(), null); }
  finally { if (original === undefined) delete globalThis.sessionStorage; else globalThis.sessionStorage = original; }
});
test("Customer Details navigation selects only trusted business/customer IDs", async () => {
  const h = harness({ initialBusinessId: "2", initialCustomerId: "20" }); await h.workflow.loadBusinesses();
  assert.equal(h.workflow.getSnapshot().businessId, "2"); assert.equal(h.workflow.getSnapshot().customerId, "20");
  const foreign = harness({ initialBusinessId: "2", initialCustomerId: "10" }); await foreign.workflow.loadBusinesses(); assert.equal(foreign.workflow.getSnapshot().customerId, "");
});
test("foreign-scoped details never enter state", async () => {
  const h = harness({ details: async () => customerDetails("2", 20) }); await h.ready(); h.fill(); await h.workflow.submit();
  assert.equal(h.workflow.getSnapshot().details, null); assert.ok(h.workflow.getSnapshot().detailsError); assert.equal(h.calls.record.length, 0);
});
test("authorization failure while confirming uncertainty cannot erase pending identity", async () => {
  const h = harness({ record: async () => { throw {}; } }); await h.ready(); h.fill(); await h.workflow.submit(); const key = h.store.read().key;
  h.setRecord(async () => { throw rejectWith(403); }); await h.workflow.submit(); assert.equal(h.store.read().pending, true);
  h.workflow.edit("amount", "10"); h.setRecord(null); await h.workflow.submit(); assert.equal(h.calls.record.length, 2); assert.equal(h.store.read().key, key);
});
