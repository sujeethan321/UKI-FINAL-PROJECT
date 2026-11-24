import { setImmediate } from "node:timers";
import { test } from "node:test";
import assert from "node:assert/strict";
import { createReminderWorkflow } from "../src/pages/shopOwner/reminderWorkflow.js";
import { draftReminder, reminderError, reminderMoney, reminderValidation, sessionReminderStore } from "../src/utils/reminder.js";
const business = (id = 1, approval_status = "approved") => ({ business_id: id, business_name: "Shop " + id, approval_status });
const customer = (id = 10) => ({ customer_id: id, customer_name: "Customer " + id, phone: "0771234567" });
const details = (b = 1, c = 10) => ({ business_id: b, currency: "LKR", customer: { ...customer(c), business_id: b }, credit_account: { credit_account_id: 100 + c, account_status: "active" }, outstanding_balance: "150.25" });
const record = (b = 1, c = 10, extra = {}) => ({ reminder_id: 4, business_id: b, customer_id: c, credit_account_id: 100 + c, currency: "LKR", outstanding_amount: "150.25", channel: "internal", language: "en", note: null, status: "recorded", message: "Exact server message", created_at: "2026-11-04T08:00:00Z", delivery_allowed: false, replayed: false, ...extra });
const defer = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
function fixture(overrides = {}, saved = null) {
  let value = saved, keys = 0;
  const calls = { record: [], history: [] };
  const store = { read: () => value, write: x => { value = x; }, clear: key => { if (!key || value?.key === key) value = null; } };
  const api = { businesses: async () => ({ businesses: [business(), business(2)] }), customers: async b => ({ business_id: Number(b), customers: [customer(), customer(20)] }), details: async (b, c) => details(Number(b), Number(c)), history: async (b, filters) => { calls.history.push({ b, filters }); return { business_id: Number(b), page: filters.page, page_size: filters.page_size, total: 0, reminders: [] }; }, record: async (b, payload) => { calls.record.push({ b, payload }); return record(Number(b), payload.customer_id, { channel: payload.channel, language: payload.language, note: payload.note }); }, ...overrides };
  const make = () => createReminderWorkflow({ api, store, makeKey: () => "reminder:key" + ++keys, fingerprint: async op => JSON.stringify(op) });
  const workflow = make();
  const ready = async () => { await workflow.loadBusinesses(); await workflow.selectCustomer("10"); };
  return { workflow, api, calls, store, ready, make };
}
test("approved business customers and effective balance load", async () => {
  const f = fixture(); await f.ready(); const s = f.workflow.getSnapshot(); assert.equal(s.businessId, "1"); assert.equal(s.customers.length, 2); assert.equal(s.details.outstanding_balance, "150.25"); assert.equal(s.contextLoading, false);
});
test("unapproved businesses do not fetch customers, details or history", async () => {
  const f = fixture({ businesses: async () => ({ businesses: [business(1, "pending")] }), customers: async () => { throw Error("must not call"); } }); await f.ready(); await f.workflow.submit(); assert.equal(f.workflow.getSnapshot().customers.length, 0); assert.equal(f.calls.history.length, 0); assert.equal(f.calls.record.length, 0);
});
for (const [label, patch, message] of [["no account", { credit_account: null }, /no credit account/], ["zero balance", { outstanding_balance: "0.00" }, /no outstanding balance/], ["closed account", { credit_account: { credit_account_id: 110, account_status: "closed" } }, /active credit account/]]) {
  test(label + " blocks recording", async () => { const f = fixture({ details: async () => ({ ...details(), ...patch }) }); await f.ready(); await f.workflow.submit(); assert.match(f.workflow.getSnapshot().error, message); assert.equal(f.calls.record.length, 0); });
}
test("valid creation sends schema fields only and shows exact server record", async () => {
  const f = fixture(); await f.ready(); f.workflow.edit("language", "ta"); f.workflow.edit("channel", "copy"); f.workflow.edit("note", "  Internal note  "); await f.workflow.submit(); assert.deepEqual(f.calls.record[0], { b: "1", payload: { customer_id: 10, channel: "copy", language: "ta", note: "Internal note", idempotency_key: "reminder:key1" } }); assert.equal(f.workflow.getSnapshot().success.message, "Exact server message"); assert.equal(f.workflow.getSnapshot().success.status, "recorded"); assert.equal(f.store.read(), null); assert.ok(f.calls.history.length > 1);
  await f.workflow.submit(); assert.equal(f.calls.record.length, 1); // A confirmed form cannot submit twice.
});
test("English/Tamil drafts use real balance, shop and customer with no due date", () => {
  const en = draftReminder(details(), business(), "en"), ta = draftReminder(details(), business(), "ta"); for (const text of [en, ta]) { assert.match(text, /Customer 10/); assert.match(text, /Shop 1/); assert.match(text, /LKR 150.25/); assert.doesNotMatch(text, /overdue|due date/i); } assert.match(ta, /நிலுவைத் தொகை/); assert.match(en, /outstanding balance/); assert.equal(reminderMoney("123456789012345678901.25"), "LKR 123,456,789,012,345,678,901.25");
});
test("missing phone restricts channels but permits internal recording", async () => {
  const f = fixture({ details: async () => ({ ...details(), customer: { ...details().customer, phone: null } }) }); await f.ready(); f.workflow.edit("channel", "sms"); await f.workflow.submit(); assert.match(f.workflow.getSnapshot().error, /No contact number/); assert.equal(f.calls.record.length, 0); f.workflow.edit("channel", "internal"); await f.workflow.submit(); assert.equal(f.calls.record.length, 1);
});
test("invalid channel, language and note are rejected", async () => {
  const f = fixture(); await f.ready(); for (const [field, value] of [["channel", "email"], ["language", "fr"], ["note", "x".repeat(1001)], ["note", "bad\u0000"]]) { f.workflow.edit(field, value); await f.workflow.submit(); assert.ok(f.workflow.getSnapshot().error); f.workflow.edit(field, field === "channel" ? "internal" : field === "language" ? "en" : ""); } assert.equal(f.calls.record.length, 0);
});
test("concurrent clicks submit once, and selectors cannot change during submission", async () => {
  const pending = defer(); let count = 0; const f = fixture({ record: async () => { count++; return pending.promise; } }); await f.ready(); const save = f.workflow.submit(); await f.workflow.submit(); await Promise.resolve(); await f.workflow.selectBusiness("2"); f.workflow.edit("note", "changed"); assert.equal(f.workflow.getSnapshot().businessId, "1"); assert.equal(f.workflow.getSnapshot().note, ""); pending.resolve(record()); await save; assert.equal(count, 1);
});
test("timeout keeps key; changed payload is blocked; identical replay reconciles", async () => {
  let calls = []; const f = fixture({ record: async (b, p) => { calls.push(p); if (calls.length === 1) throw { code: "ECONNABORTED" }; return record(1, 10, { replayed: true }); } }); await f.ready(); await f.workflow.submit(); const key = f.store.read().key; assert.equal(f.workflow.getSnapshot().uncertain, true); f.workflow.newReminder(); assert.equal(f.store.read().key, key); f.workflow.edit("note", "different"); await f.workflow.submit(); assert.equal(calls.length, 1); f.workflow.edit("note", ""); await f.workflow.submit(); assert.equal(calls[1].idempotency_key, key); assert.equal(f.workflow.getSnapshot().uncertain, false); assert.equal(f.workflow.getSnapshot().success.replayed, true);
});
test("opaque pending operation survives remount and blocks another business", async () => {
  const f = fixture({ record: async () => { throw Error("network"); } }); await f.ready(); await f.workflow.submit(); const key = f.store.read().key; f.workflow.dispose(); const next = f.make(); await next.loadBusinesses(); await next.selectBusiness("2"); await next.selectCustomer("10"); await next.submit(); assert.equal(next.getSnapshot().uncertain, true); assert.match(next.getSnapshot().error, /earlier reminder is unresolved/); assert.equal(f.store.read().key, key);
});
test("same-key retry remains possible after outstanding falls to zero", async () => {
  let attempts = 0; const f = fixture({ record: async () => { if (++attempts === 1) throw Error("network"); return record(1, 10, { replayed: true }); } }); await f.ready(); await f.workflow.submit(); f.api.details = async () => ({ ...details(), outstanding_balance: "0.00" }); await f.workflow.selectCustomer("10"); await f.workflow.submit(); assert.equal(attempts, 2); assert.ok(f.workflow.getSnapshot().success);
});
test("cooldown conflict is meaningful and identical retry retains key", async () => {
  const requests = []; const f = fixture({ record: async (b, p) => { requests.push(p); throw { response: { status: 409, data: { detail: "Reminder cooldown is active for this customer" } } }; } }); await f.ready(); await f.workflow.submit(); assert.match(f.workflow.getSnapshot().error, /cooldown.*does not provide a retry time/); assert.equal(f.workflow.getSnapshot().uncertain, false); await f.workflow.submit(); assert.equal(requests[0].idempotency_key, requests[1].idempotency_key);
});
test("history filters, order and pagination use backend parameters", async () => {
  const f = fixture(); await f.ready(); await f.workflow.filter("historyCustomerId", "10"); await f.workflow.filter("status", "recorded"); await f.workflow.filter("ordering", "oldest"); await f.workflow.filter("page", 2); assert.deepEqual(f.calls.history.at(-1), { b: "1", filters: { customer_id: 10, status: "recorded", ordering: "oldest", page: 2, page_size: 10 } }); await f.workflow.filter("ordering", "newest"); assert.equal(f.workflow.getSnapshot().page, 1);
});
test("customer switching ignores late detail responses", async () => {
  const pending = defer(); const f = fixture({ details: async (b, c) => Number(c) === 10 ? pending.promise : details(Number(b), Number(c)) }); await f.workflow.loadBusinesses(); const old = f.workflow.selectCustomer("10"); await f.workflow.selectCustomer("20"); pending.resolve(details()); await old; assert.equal(f.workflow.getSnapshot().details.customer.customer_id, 20);
});
test("business switching ignores late customers, details and history", async () => {
  const customersPending = defer(), historyPending = defer(); const f = fixture({ customers: async b => Number(b) === 1 ? customersPending.promise : { business_id: 2, customers: [customer(20)] }, history: async (b, filters) => Number(b) === 1 ? historyPending.promise : { business_id: 2, page: filters.page, page_size: filters.page_size, total: 0, reminders: [] } }); const first = f.workflow.loadBusinesses(); await new Promise(r => setImmediate(r)); await f.workflow.selectBusiness("2"); await f.workflow.selectCustomer("20"); customersPending.resolve({ business_id: 1, customers: [customer()] }); historyPending.resolve({ business_id: 1, page: 1, page_size: 10, total: 1, reminders: [record()] }); await first; const s = f.workflow.getSnapshot(); assert.equal(s.businessId, "2"); assert.equal(s.customers[0].customer_id, 20); assert.equal(s.details.business_id, 2); assert.equal(s.history.business_id, 2);
});
test("stale customer details from another business are ignored", async () => {
  const pending = defer(); const f = fixture({ details: async (b, c) => Number(b) === 1 ? pending.promise : details(Number(b), Number(c)) }); await f.workflow.loadBusinesses(); const old = f.workflow.selectCustomer("10"); await f.workflow.selectBusiness("2"); await f.workflow.selectCustomer("20"); pending.resolve(details()); await old; assert.equal(f.workflow.getSnapshot().details.business_id, 2);
});
test("foreign business responses fail closed", async () => {
  const f = fixture({ details: async () => details(2), history: async () => ({ business_id: 2, page: 1, page_size: 10, total: 1, reminders: [record(2)] }) }); await f.ready(); assert.equal(f.workflow.getSnapshot().details, null); assert.equal(f.workflow.getSnapshot().history, null); await f.workflow.submit(); assert.equal(f.calls.record.length, 0);
});
test("malformed or foreign creation response preserves unresolved key", async () => {
  const f = fixture({ record: async () => record(2) }); await f.ready(); await f.workflow.submit(); assert.equal(f.workflow.getSnapshot().success, null); assert.equal(f.workflow.getSnapshot().uncertain, true); assert.equal(f.store.read().pending, true);
});
for (const status of [401, 403, 404, 409, 422, 500]) {
  test("HTTP " + status + " is sanitized and retains safe request identity", async () => {
    const f = fixture({ record: async () => { throw { response: { status, data: { detail: "SECRET STACK TRACE" } } }; } }); await f.ready(); await f.workflow.submit(); const s = f.workflow.getSnapshot(); assert.ok(s.error); assert.doesNotMatch(s.error, /SECRET|STACK/); assert.equal(s.uncertain, status === 500); assert.ok(f.store.read().key);
  });
}
test("read errors are sanitized for authorization, not found and server failure", async () => {
  for (const status of [401, 403, 404, 422, 500]) { const f = fixture({ details: async () => { throw { response: { status } }; } }); await f.ready(); assert.equal(f.workflow.getSnapshot().details, null); assert.ok(f.workflow.getSnapshot().detailsError); }
  assert.match(reminderError({ response: { status: 500 } }), /Server error/);
});
test("storage failure prevents dispatch", async () => {
  const f = fixture(); await f.ready(); f.store.write = () => { throw Error("disabled"); }; await f.workflow.submit(); assert.equal(f.calls.record.length, 0); assert.match(f.workflow.getSnapshot().error, /session storage/);
});
test("session store is user-scoped, opaque and rejects corrupt records", () => {
  const previous = globalThis.sessionStorage; const map = new Map(); globalThis.sessionStorage = { getItem: k => map.get(k), setItem: (k, v) => map.set(k, v), removeItem: k => map.delete(k) };
  try { const a = sessionReminderStore(1), b = sessionReminderStore(2); const request = { fingerprint: "a".repeat(64), key: "reminder:abc", pending: true }; a.write(request); assert.deepEqual(a.read(), request); assert.equal(b.read(), null); a.clear("other"); assert.ok(a.read()); a.clear(request.key); assert.equal(a.read(), null); map.set("lankapex_reminder_request_1", "bad"); assert.throws(() => a.read()); } finally { if (previous === undefined) delete globalThis.sessionStorage; else globalThis.sessionStorage = previous; }
});
test("validation and draft handle absent customer data", () => { assert.match(reminderValidation({ customerId: "", details: null }), /Select a customer/); assert.match(draftReminder(null, null, "en"), /Select a customer/); });

test("leaving during secure preparation never dispatches a late reminder", async () => {
  const pending = defer(); let count = 0;
  const f = fixture(); const workflow = createReminderWorkflow({ api: { ...f.api, record: async () => { count++; return record(); } }, store: f.store, fingerprint: () => pending.promise, makeKey: () => "reminder:test" });
  await workflow.loadBusinesses(); await workflow.selectCustomer("10"); const saving = workflow.submit(); workflow.dispose(); pending.resolve("hash"); await saving; assert.equal(count, 0);
});
test("customer changes clear prior customer notes and preview immediately", async () => {
  const f = fixture(); await f.ready(); f.workflow.edit("note", "Private note"); f.workflow.edit("language", "ta"); await f.workflow.selectCustomer("20"); assert.equal(f.workflow.getSnapshot().note, ""); assert.equal(f.workflow.getSnapshot().language, "en"); assert.equal(f.workflow.getSnapshot().success, null);
});
test("late filtered history cannot overwrite the latest page", async () => {
  const pending = defer(); const f = fixture(); await f.ready();
  f.api.history = async (b, filters) => filters.page === 2 ? pending.promise : { business_id: 1, page: filters.page, page_size: filters.page_size, total: 31, reminders: [] };
  const old = f.workflow.filter("page", 2); await f.workflow.filter("page", 3); pending.resolve({ business_id: 1, page: 2, page_size: 10, total: 21, reminders: [record()] }); await old; assert.equal(f.workflow.getSnapshot().history.page, 3);
});
test("uncertain authorization rejection preserves pending identity", async () => {
  let attempts = 0; const f = fixture({ record: async () => { if (++attempts === 1) throw Error("network"); throw { response: { status: 401 } }; } }); await f.ready(); await f.workflow.submit(); const key = f.store.read().key; await f.workflow.submit(); assert.equal(f.store.read().key, key); assert.equal(f.store.read().pending, true); assert.equal(f.workflow.getSnapshot().uncertain, true);
});
test("navigation selects only approved business and customer from trusted context", async () => {
  const f = fixture(); const workflow = createReminderWorkflow({ api: f.api, store: f.store, initialBusinessId: "2", initialCustomerId: "20" }); await workflow.loadBusinesses(); assert.equal(workflow.getSnapshot().businessId, "2"); assert.equal(workflow.getSnapshot().customerId, "20");
  const foreign = createReminderWorkflow({ api: f.api, store: f.store, initialBusinessId: "999", initialCustomerId: "999" }); await foreign.loadBusinesses(); assert.equal(foreign.getSnapshot().businessId, "1"); assert.equal(foreign.getSnapshot().customerId, "");
});

test("late reminder confirmation after unmount never starts another authenticated history request", async () => {
  const pending = defer();
  const f = fixture({ record: async () => pending.promise });
  await f.ready();
  const originalReads = f.calls.history.length;
  const saving = f.workflow.submit();
  await Promise.resolve();
  f.workflow.dispose();
  pending.resolve(record());
  await saving;
  assert.equal(f.calls.history.length, originalReads);
});
