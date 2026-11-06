import { test } from "node:test";
import assert from "node:assert/strict";
import { createCustomerDashboardReader, parseCustomerResponse, formatCustomerMoney, formatRecordedTime, customerReadError } from "../src/utils/customerDashboard.js";

import { fixtures, transaction } from "./fixtures/customerDashboardFixtures.js";
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
const harness = (overrides = {}) => {
  const values = fixtures();
  const api = Object.fromEntries(Object.entries(values).map(([key, data]) => [key, async () => data]));
  return { values, reader: createCustomerDashboardReader({ ...api, ...overrides }) };
};

test("loads four independently validated sections with real summary values", async () => {
  const { reader } = harness(); assert.equal(reader.getSnapshot().summary.loading, true);
  await reader.start(); const state = reader.getSnapshot();
  assert.equal(state.summary.data.total_outstanding_balance, "100.25");
  assert.equal(state.summary.data.linked_shop_count, 1); assert.equal(state.summary.data.credit_account_count, 1);
  assert.equal(state.summary.data.recent_activity.length, 1); assert.equal(state.accounts.data.items[0].business_name, "Linked Shop");
});
test("currency formatting is exact for large values, zero and negative adjustments", () => {
  assert.equal(formatCustomerMoney("1999999999999.98"), "LKR 1,999,999,999,999.98");
  assert.equal(formatCustomerMoney("0.00"), "LKR 0.00"); assert.equal(formatCustomerMoney("-100.25"), "LKR -100.25");
  assert.equal(formatCustomerMoney(undefined), "Not available");
  assert.equal(formatRecordedTime("2026-11-06T10:00:00.123456"), "2026-11-06 10:00:00");
});
test("empty contracts preserve explicit zero and empty arrays", async () => {
  const values = fixtures(); values.summary = { currency: "LKR", linked_shop_count: 0, credit_account_count: 0, total_outstanding_balance: "0.00", recent_activity: [] };
  values.shops.total = 0; values.shops.shops = []; values.accounts.total = 0; values.accounts.credit_accounts = []; values.transactions.total = 0; values.transactions.transactions = [];
  const reader = createCustomerDashboardReader(Object.fromEntries(Object.entries(values).map(([key, value]) => [key, async () => value])));
  await reader.start(); assert.equal(reader.getSnapshot().summary.data.total_outstanding_balance, "0.00"); assert.deepEqual(reader.getSnapshot().accounts.data.items, []);
});
test("one failed section never fabricates zero or discards successful sections", async () => {
  const { reader } = harness({ summary: async () => { throw { response: { status: 500, data: { detail: "private SQL" } } }; } });
  await reader.start(); const state = reader.getSnapshot(); assert.equal(state.summary.data, null); assert.match(state.summary.error, /unavailable/);
  assert.equal(state.accounts.data.total, 1); assert.ok(!state.summary.error.includes("SQL"));
});
test("section retry succeeds independently", async () => {
  let fail = true; const { reader, values } = harness({ accounts: async () => { if (fail) throw Error("offline"); return fixtures().accounts; } });
  await reader.start(); assert.equal(reader.getSnapshot().accounts.data, null); fail = false; await reader.load("accounts");
  assert.equal(reader.getSnapshot().accounts.data.total, values.accounts.total); assert.equal(reader.getSnapshot().summary.data.linked_shop_count, 1);
});
for (const status of [401, 403]) test("auth failure " + status + " clears every section and ignores later responses", async () => {
  const gate = deferred(); const { reader } = harness({ shops: () => gate.promise, accounts: async () => { throw { response: { status } }; } });
  const pending = reader.start(); await Promise.resolve(); await Promise.resolve(); gate.resolve(fixtures().shops); await pending;
  const state = reader.getSnapshot(); assert.ok(state.authError); for (const key of ["summary", "shops", "accounts", "transactions"]) { assert.equal(state[key].data, null); assert.equal(state[key].loading, false); }
});
test("dispose aborts pending calls and clears all sensitive state", async () => {
  const gate = deferred(); let signal; const { reader } = harness({ summary: options => { signal = options.signal; return gate.promise; } });
  const pending = reader.start(); reader.dispose(); assert.equal(signal.aborted, true); gate.resolve(fixtures().summary); await pending;
  assert.equal(reader.getSnapshot().summary.data, null); assert.equal(reader.getSnapshot().shops.data, null);
});
test("account-switch isolation uses a new empty reader and suppresses the former response", async () => {
  const gate = deferred(); const { reader: first } = harness({ summary: () => gate.promise }); const pending = first.start(); first.dispose();
  const { reader: second } = harness(); await second.start(); gate.resolve({ ...fixtures().summary, total_outstanding_balance: "99999.00" }); await pending;
  assert.equal(first.getSnapshot().summary.data, null); assert.equal(second.getSnapshot().summary.data.total_outstanding_balance, "100.25");
});
test("refresh and StrictMode restart ignore older request generations", async () => {
  const stale = deferred(); let count = 0;
  const { reader } = harness({ summary: () => ++count === 1 ? stale.promise : Promise.resolve(fixtures().summary) });
  const first = reader.start(); reader.dispose(); await reader.start(); stale.resolve({ ...fixtures().summary, total_outstanding_balance: "999.00" }); await first;
  assert.equal(reader.getSnapshot().summary.data.total_outstanding_balance, "100.25");
});
test("retry ignores a superseded same-section response", async () => {
  const old = deferred(); let count = 0; const { reader } = harness({ summary: () => ++count === 1 ? old.promise : Promise.resolve(fixtures().summary) });
  const initial = reader.start(); await reader.load("summary"); old.resolve({ ...fixtures().summary, total_outstanding_balance: "999.00" }); await initial;
  assert.equal(reader.getSnapshot().summary.data.total_outstanding_balance, "100.25");
});
test("malformed or missing summary data never becomes displayed account data", async () => {
  for (const invalid of [null, {}, { ...fixtures().summary, total_outstanding_balance: 0 }, { ...fixtures().summary, linked_shop_count: -1 }, { ...fixtures().summary, recent_activity: [transaction(), transaction()] }]) {
    const { reader } = harness({ summary: async () => invalid }); await reader.start();
    assert.equal(reader.getSnapshot().summary.data, null); assert.match(reader.getSnapshot().summary.error, /could not be verified/);
  }
});
test("response validation enforces currency, pagination, dates and unique records", () => {
  for (const section of ["shops", "accounts", "transactions"]) {
    for (const patch of [{ currency: "USD" }, { page: 2 }, { page_size: 100 }, { total: -1 }]) assert.throws(() => parseCustomerResponse(section, { ...fixtures()[section], ...patch }));
  }
  const data = fixtures(); data.accounts.credit_accounts[0].opened_at = "invalid"; assert.throws(() => parseCustomerResponse("accounts", data.accounts));
  const history = fixtures().transactions; history.transactions.push(transaction()); assert.throws(() => parseCustomerResponse("transactions", history));
});
test("parser drops private/unknown response fields and preserves server ordering", () => {
  const data = fixtures().transactions; data.total = 2; data.transactions = [transaction({ entry_id: 42, notes: "private note" }), transaction()]; data.access_token = "must not retain";
  const result = parseCustomerResponse("transactions", data); assert.deepEqual(result.items.map(row => row.entry_id), [42, 41]); assert.ok(!JSON.stringify(result).includes("private note")); assert.ok(!JSON.stringify(result).includes("access_token"));
});
test("friendly errors distinguish permission, expiry, timeout and reconstruction failures", () => {
  assert.match(customerReadError({ response: { status: 401 } }), /expired/); assert.match(customerReadError({ response: { status: 403 } }), /permission/);
  assert.match(customerReadError({ response: { status: 409 } }), /review/); assert.match(customerReadError({ code: "ECONNABORTED" }), /taking too long/);
});
