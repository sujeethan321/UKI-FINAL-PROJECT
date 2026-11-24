import { test } from "node:test";
import assert from "node:assert/strict";
import { createCreditSaleWorkflow } from "../src/pages/shopOwner/creditSaleWorkflow.js";
import { decimalAmount, minorUnits, formatCreditMoney, secureSaleKey, sessionSaleStore } from "../src/utils/creditSale.js";

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
  notes: payload.notes, outstanding_balance: "200.25", advance_balance: "0.00", available_credit: "799.75",
  recorded_at: "2026-11-03T12:00:00", due_at: "2026-12-03T12:00:00", receipt_number: "CS-confirmed",
  reference: "CS-confirmed", replayed: false,
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
        data.transactions.push({ entry_id: recorded.entry_id, entry_type: "credit_sale", debit: recorded.amount,
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
  const workflow = createCreditSaleWorkflow({ api, store, makeKey: () => `credit-sale:test-${++keys}` });
  return { workflow, api, calls, store, setRecord: behavior => { recordBehavior = behavior; },
    ready: async () => { await workflow.loadBusinesses(); await workflow.selectCustomer("10"); },
    fill: (amount = "100.25", notes = "Goods supplied") => { workflow.edit("amount", amount); workflow.edit("notes", notes); } };
}

for (const input of ["0", "-1", "1.001", "1e2", "NaN", "Infinity", "", "1000000000000", "1,000"] ) {
  test(`invalid sale amount ${JSON.stringify(input)} never reaches API`, async () => {
    const h = harness(); await h.ready(); h.fill(input); await h.workflow.submit();
    assert.equal(h.calls.record.length, 0);
    assert.ok(h.workflow.getSnapshot().error);
  });
}

test("money uses exact minor units and formats large and negative balances", () => {
  assert.equal(minorUnits("0.10") + minorUnits("0.20"), 30n);
  assert.equal(decimalAmount("0001.2"), "1.20");
  assert.equal(decimalAmount("999999999999.99"), "999999999999.99");
  assert.equal(formatCreditMoney("999999999999.99"), "LKR 999,999,999,999.99");
  assert.equal(formatCreditMoney("-100.05"), "LKR -100.05");
  assert.equal(formatCreditMoney(null), "?");
});

test("secure keys are unique and satisfy backend syntax", () => {
  const first = secureSaleKey(), second = secureSaleKey();
  assert.notEqual(first, second);
  assert.match(first, /^credit-sale:[a-f0-9-]+$/);
  assert.ok(first.length <= 100);
});

test("initial loading uses trusted business context and no customer is silently selected", async () => {
  const gate = deferred(); const h = harness({ businesses: () => gate.promise });
  const pending = h.workflow.loadBusinesses();
  assert.equal(h.workflow.getSnapshot().contextLoading, true);
  assert.equal(h.workflow.getSnapshot().details, null);
  gate.resolve({ businesses: [{ business_id: 3, approval_status: "pending" }, { business_id: 2, approval_status: "approved" }] });
  await pending;
  assert.equal(h.workflow.getSnapshot().businessId, "2");
  assert.equal(h.calls.customers[0][0], "2");
  assert.equal(h.workflow.getSnapshot().customerId, "");
  assert.equal(h.workflow.getSnapshot().contextLoading, false);
});

test("empty or failed context does not request customers", async () => {
  for (const businesses of [async () => ({ businesses: [] }), async () => { throw rejectWith(401); }]) {
    const h = harness({ businesses }); await h.workflow.loadBusinesses();
    assert.equal(h.calls.customers.length, 0);
    assert.equal(h.workflow.getSnapshot().details, null);
  }
});

test("pending business never loads customer financial data", async () => {
  const h = harness(); await h.ready(); await h.workflow.selectBusiness("3");
  assert.equal(h.workflow.getSnapshot().details, null);
  assert.deepEqual(h.workflow.getSnapshot().customers, []);
  h.fill(); await h.workflow.submit();
  assert.equal(h.calls.record.length, 0);
});

test("customer selection loads only the selected scoped details", async () => {
  const h = harness(); await h.ready(); await h.workflow.selectCustomer("11");
  assert.equal(h.workflow.getSnapshot().details.customer.customer_id, 11);
  assert.deepEqual(h.calls.details.at(-1).slice(0, 2), ["1", 11]);
  await h.workflow.selectCustomer("999");
  assert.equal(h.workflow.getSnapshot().details, null);
  assert.equal(h.calls.details.length, 2);
});

for (const status of [null, "suspended", "closed"]) {
  test(`ineligible credit account ${status} blocks new sales`, async () => {
    const h = harness({ details: async () => {
      const data = customerDetails();
      if (status) data.credit_account.account_status = status;
      else { data.credit_account = null; data.available_credit = null; }
      return data;
    } });
    await h.ready(); h.fill(); await h.workflow.submit();
    assert.equal(h.calls.record.length, 0);
    assert.equal(h.workflow.getSnapshot().success, null);
  });
}

test("available-credit comparison is exact and permits the boundary", async () => {
  const h = harness(); await h.ready(); h.fill("900.01"); await h.workflow.submit();
  assert.equal(h.calls.record.length, 0);
  assert.match(h.workflow.getSnapshot().error, /exceeds available credit/);
  h.fill("900.00"); await h.workflow.submit();
  assert.equal(h.calls.record.length, 1);
});

test("successful response clears the form, shows confirmation and refreshes balances/history", async () => {
  const h = harness(); await h.ready(); h.fill(); await h.workflow.submit();
  const state = h.workflow.getSnapshot();
  assert.equal(state.success.reference, "CS-confirmed");
  assert.equal(state.success.amount, "100.25");
  assert.equal(state.amount, ""); assert.equal(state.notes, "");
  assert.equal(state.details.outstanding_balance, "200.25");
  assert.equal(state.details.available_credit, "799.75");
  assert.equal(state.details.transactions.at(-1).entry_id, 555);
  assert.equal(h.store.read(), null);
  assert.equal(h.calls.customers.length, 2);
  assert.equal(h.calls.details.length, 2);
  const [business, payload] = h.calls.record[0];
  assert.equal(business, "1");
  assert.deepEqual(Object.keys(payload).sort(), ["amount", "customer_id", "idempotency_key", "notes"]);
  assert.equal(payload.customer_id, 10); assert.equal(typeof payload.amount, "string");
});

test("double clicks and context changes during POST cannot dispatch another operation", async () => {
  const gate = deferred(), started = deferred();
  const h = harness({ record: (business, payload) => { started.resolve(); return gate.promise.then(() => successFor(business, payload)); } });
  await h.ready(); h.fill();
  const first = h.workflow.submit(); await started.promise;
  await h.workflow.submit(); await h.workflow.selectBusiness("2"); await h.workflow.selectCustomer("11"); h.workflow.edit("amount", "1");
  assert.equal(h.calls.record.length, 1);
  assert.equal(h.workflow.getSnapshot().businessId, "1");
  assert.equal(h.workflow.getSnapshot().customerId, "10");
  assert.equal(h.workflow.getSnapshot().amount, "100.25");
  gate.resolve(); await first;
});

for (const status of [400, 401, 403, 404, 409, 422]) {
  test(`HTTP ${status} is handled safely without success or clearing inputs`, async () => {
    const h = harness({ record: async () => { throw rejectWith(status); } });
    await h.ready(); h.fill(); await h.workflow.submit();
    assert.equal(h.workflow.getSnapshot().success, null);
    assert.equal(h.workflow.getSnapshot().amount, "100.25");
    assert.ok(h.workflow.getSnapshot().error);
    assert.ok(!h.workflow.getSnapshot().error.includes("private server diagnostic"));
    assert.equal(h.store.read().pending, false);
    await h.workflow.submit();
    assert.equal(h.calls.record[0][1].idempotency_key, h.calls.record[1][1].idempotency_key);
  });
}

for (const failure of [{ code: "ECONNABORTED" }, new Error("network failure"), rejectWith(500)]) {
  test(`uncertain outcome ${failure.code || failure.message || failure.response.status} retains request identity`, async () => {
    const h = harness({ record: async () => { throw failure; } });
    await h.ready(); h.fill(); await h.workflow.submit();
    assert.equal(h.workflow.getSnapshot().uncertain, true);
    assert.equal(h.workflow.getSnapshot().success, null);
    assert.match(h.workflow.getSnapshot().error, /uncertain/);
    assert.equal(h.store.read().pending, true);
    h.setRecord((business, payload) => ({ ...successFor(business, payload), replayed: true }));
    await h.workflow.refresh(); await h.workflow.submit();
    assert.equal(h.calls.record[0][1].idempotency_key, h.calls.record[1][1].idempotency_key);
    assert.equal(h.workflow.getSnapshot().success.replayed, true);
  });
}

test("editing customer, amount or notes after rejection rotates the key for a new operation", async () => {
  for (const edit of [h => h.fill("101.25"), h => h.workflow.edit("notes", "Different goods"), h => h.workflow.selectCustomer("11")]) {
    const h = harness({ record: async () => { throw rejectWith(409); } });
    await h.ready(); h.fill(); await h.workflow.submit();
    const key = h.calls.record[0][1].idempotency_key;
    await edit(h);
    if (!h.workflow.getSnapshot().amount) h.fill();
    await h.workflow.submit();
    assert.notEqual(h.calls.record[1][1].idempotency_key, key);
  }
});

test("uncertain edits cannot silently become a different financial operation", async () => {
  const h = harness({ record: async () => { throw new Error("network failure"); } });
  await h.ready(); h.fill(); await h.workflow.submit();
  h.workflow.edit("amount", "101.25"); await h.workflow.submit();
  assert.equal(h.calls.record.length, 1);
  assert.match(h.workflow.getSnapshot().error, /previous sale is unresolved/);
  const oldKey = h.calls.record[0][1].idempotency_key;
  h.workflow.newSale(); h.fill("101.25"); await h.workflow.submit();
  assert.notEqual(h.calls.record[1][1].idempotency_key, oldKey);
});

test("an unresolved key survives remount without persisting customer or financial records", async () => {
  const first = harness({ record: async () => { throw new Error("network failure"); } });
  await first.ready(); first.fill(); await first.workflow.submit();
  const saved = first.store.read();
  assert.deepEqual(Object.keys(saved).sort(), ["fingerprint", "key", "pending"]);
  assert.match(saved.fingerprint, /^[a-f0-9]{64}$/);
  first.workflow.dispose();
  const second = harness({}, first.store); await second.ready(); second.fill();
  await second.workflow.submit();
  assert.equal(second.calls.record[0][1].idempotency_key, saved.key);
});

test("unresolved retry can confirm a now-suspended fully-used account", async () => {
  let unavailable = false;
  const h = harness({ record: async () => { throw new Error("timeout"); }, details: async () => {
    const data = customerDetails();
    if (unavailable) { data.credit_account.account_status = "suspended"; data.available_credit = "0.00"; }
    return data;
  } });
  await h.ready(); h.fill(); await h.workflow.submit(); unavailable = true;
  await h.workflow.refresh();
  h.setRecord((business, payload) => ({ ...successFor(business, payload), replayed: true }));
  await h.workflow.submit();
  assert.equal(h.calls.record.length, 2);
  assert.equal(h.calls.record[0][1].idempotency_key, h.calls.record[1][1].idempotency_key);
});

test("a mismatched or malformed success response is uncertain, never confirmed", async () => {
  for (const invalid of [{ business_id: 2 }, { reference: { unexpected: "object" } }, { reference: "" }, { available_credit: "invalid" }]) {
    const h = harness({ record: async (business, payload) => ({ ...successFor(business, payload), ...invalid }) });
    await h.ready(); h.fill(); await h.workflow.submit();
    assert.equal(h.workflow.getSnapshot().success, null);
    assert.equal(h.workflow.getSnapshot().uncertain, true);
    assert.equal(h.workflow.getSnapshot().amount, "100.25");
  }
});

test("customer switch aborts and ignores a stale detail response", async () => {
  const old = deferred();
  const h = harness({ details: async (business, customer) => customer === 10 ? old.promise : customerDetails(business, customer) });
  await h.workflow.loadBusinesses(); const first = h.workflow.selectCustomer("10");
  const oldSignal = h.calls.details[0][2].signal;
  await h.workflow.selectCustomer("11");
  assert.equal(oldSignal.aborted, true);
  old.resolve(customerDetails("1", 10)); await first;
  assert.equal(h.workflow.getSnapshot().details.customer.customer_id, 11);
});

test("business switch clears data immediately and ignores old customer lists", async () => {
  const old = deferred(), started = deferred();
  const h = harness({ customers: async business => {
    if (business === "1") { started.resolve(); return old.promise; }
    return { business_id: 2, customers: [{ customer_id: 20, customer_name: "Second business customer" }] };
  } });
  const loading = h.workflow.loadBusinesses(); await started.promise;
  const oldSignal = h.calls.customers[0][1].signal;
  await h.workflow.selectBusiness("2");
  old.resolve({ business_id: 1, customers: [{ customer_id: 10 }] }); await loading;
  assert.equal(oldSignal.aborted, true);
  assert.equal(h.workflow.getSnapshot().businessId, "2");
  assert.deepEqual(h.workflow.getSnapshot().customers.map(c => c.customer_id), [20]);
  assert.equal(h.workflow.getSnapshot().details, null);
});

test("foreign detail responses are rejected and never displayed or submitted", async () => {
  const h = harness({ details: async () => customerDetails("2", 20) });
  await h.ready(); h.fill(); await h.workflow.submit();
  assert.equal(h.workflow.getSnapshot().details, null);
  assert.ok(h.workflow.getSnapshot().detailsError);
  assert.equal(h.calls.record.length, 0);
});

test("confirmed sale survives a subsequent refresh failure", async () => {
  let fail = false;
  const h = harness({ details: async () => { if (fail) throw new Error("read failed"); return customerDetails(); } });
  await h.ready(); h.fill(); fail = true; await h.workflow.submit();
  assert.equal(h.workflow.getSnapshot().success.entry_id, 555);
  assert.equal(h.workflow.getSnapshot().details.outstanding_balance, "200.25");
  assert.ok(h.workflow.getSnapshot().detailsError);
  assert.equal(h.workflow.getSnapshot().uncertain, false);
});

test("new confirmed sale starts with a fresh key", async () => {
  const h = harness(); await h.ready(); h.fill(); await h.workflow.submit();
  h.fill(); await h.workflow.submit();
  assert.notEqual(h.calls.record[0][1].idempotency_key, h.calls.record[1][1].idempotency_key);
});

test("storage failure prevents dispatch rather than risking an unrecoverable sale", async () => {
  const store = { read: () => null, clear: () => {}, write: () => { throw new Error("denied"); } };
  const h = harness({}, store); await h.ready(); h.fill(); await h.workflow.submit();
  assert.equal(h.calls.record.length, 0);
  assert.equal(h.workflow.getSnapshot().success, null);
  assert.match(h.workflow.getSnapshot().error, /session storage/);
});

test("session storage is user scoped and late completion cannot erase a newer operation", () => {
  const data = new Map();
  const previous = globalThis.sessionStorage;
  globalThis.sessionStorage = { getItem: key => data.get(key) ?? null, setItem: (key, value) => data.set(key, value), removeItem: key => data.delete(key) };
  try {
    const one = sessionSaleStore(1), two = sessionSaleStore(2);
    one.write({ fingerprint: "a".repeat(64), key: "credit-sale:original", pending: true });
    assert.equal(two.read(), null);
    one.write({ fingerprint: "b".repeat(64), key: "credit-sale:newer", pending: true });
    one.clear("credit-sale:original");
    assert.equal(one.read().key, "credit-sale:newer");
    assert.deepEqual(Object.keys(JSON.parse([...data.values()][0])).sort(), ["fingerprint", "key", "pending"]);
  } finally {
    if (previous === undefined) delete globalThis.sessionStorage;
    else globalThis.sessionStorage = previous;
  }
});


test("dashboard navigation context is honored only when it names a trusted approved business", async () => {
  for (const [initialBusinessId, expected] of [[2, "2"], [999, "1"], [3, "1"]]) {
    const h = harness();
    const workflow = createCreditSaleWorkflow({ api: h.api, store: h.store, initialBusinessId });
    await workflow.loadBusinesses();
    assert.equal(workflow.getSnapshot().businessId, expected);
  }
});


test("leaving during secure request preparation does not dispatch a late sale", async () => {
  const h = harness(); const gate = deferred();
  const workflow = createCreditSaleWorkflow({ api: h.api, store: h.store, fingerprint: () => gate.promise });
  await workflow.loadBusinesses(); await workflow.selectCustomer("10"); workflow.edit("amount", "100.25");
  const pending = workflow.submit(); workflow.dispose(); gate.resolve("a".repeat(64)); await pending;
  assert.equal(h.calls.record.length, 0);
  assert.equal(h.store.read(), null);
});

test("refresh rechecks approval before enabling financial reads", async () => {
  let approved = false;
  const h = harness({ businesses: async () => ({ businesses: [{ business_id: 1, business_name: "Shop", approval_status: approved ? "approved" : "pending" }] }) });
  await h.workflow.loadBusinesses(); assert.equal(h.calls.customers.length, 0);
  approved = true; await h.workflow.refresh();
  assert.equal(h.calls.customers.length, 1);
  assert.equal(h.workflow.getSnapshot().businesses[0].approval_status, "approved");
});

for (const status of [401, 403, 404, 409, 422]) {
  test(`uncertain sale retains pending identity after retry HTTP ${status}`, async () => {
    const h = harness({ record: async () => { throw { code: "ECONNABORTED" }; } });
    await h.ready(); h.fill(); await h.workflow.submit();
    const key = h.store.read().key;
    h.setRecord(async () => { throw rejectWith(status); }); await h.workflow.submit();
    assert.equal(h.store.read().pending, true);
    h.workflow.edit("amount", "10.00"); h.setRecord(null); await h.workflow.submit();
    assert.equal(h.calls.record.length, 2); assert.equal(h.store.read().key, key);
    assert.match(h.workflow.getSnapshot().error, /unresolved/);
  });
}

test("confirmed sale stays busy until refreshed customer data finishes", async () => {
  const h = harness(); await h.ready(); h.fill(); const gate = deferred(), started = deferred();
  h.api.customers = async () => { started.resolve(); return gate.promise; };
  const submission = h.workflow.submit(); await started.promise;
  assert.equal(h.workflow.getSnapshot().saving, true);
  h.workflow.edit("amount", "5"); await h.workflow.selectBusiness("2");
  assert.equal(h.workflow.getSnapshot().amount, ""); assert.equal(h.workflow.getSnapshot().businessId, "1");
  gate.resolve({ business_id: 1, customers: [{ customer_id: 10, customer_name: "Test Customer" }] });
  await submission; assert.equal(h.workflow.getSnapshot().saving, false);
});
