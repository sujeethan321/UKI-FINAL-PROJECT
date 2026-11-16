import { test } from 'node:test';
import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers';
import { adminMetrics, adminTimestamp, parseAdminOverview, parseAdminActivity, createAdminDashboardReader, adminReadError } from '../src/utils/adminDashboard.js';

import { overviewFixture, activityFixture } from './fixtures/adminDashboardFixtures.js';
const defer = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
const flush = () => new Promise(resolve => setImmediate(resolve));
function setup(overrides = {}) {
  const calls = { overview: 0, activity: 0 }, signals = {};
  const api = Object.fromEntries(['overview', 'activity'].map(key => [key, async ({ signal }) => { calls[key]++; signals[key] = signal; return (overrides[key] || (key === 'overview' ? overviewFixture : activityFixture))({ signal }); }]));
  const reader = createAdminDashboardReader(api);
  return { reader, calls, signals };
}

test('actual overview counts use only allowlisted fields and preserve zero', () => {
  const result = parseAdminOverview({ ...overviewFixture(), password_hash: 'PRIVATE', balance: '900' });
  assert.deepEqual(Object.keys(result), adminMetrics.map(([key]) => key));
  for (const [key] of adminMetrics) assert.equal(result[key], overviewFixture()[key]);
  const zero = parseAdminOverview(Object.fromEntries(adminMetrics.map(([key]) => [key, 0])));
  assert.ok(Object.values(zero).every(value => value === 0));
});
test('partial responses explicitly mark missing metrics unavailable without deriving totals', () => {
  const result = parseAdminOverview({ total_shop_owners: 3, total_customers: null, users: [{}, {}] });
  assert.equal(result.total_shop_owners, 3); assert.equal(result.total_customers, null); assert.equal(result.total_drivers, null);
  assert.equal(result.total_orders, null);
});
for (const value of [-1, 1.5, '12', false, Number.MAX_SAFE_INTEGER + 1, NaN, Infinity]) {
  test('invalid platform count is rejected: ' + String(value), () => assert.throws(() => parseAdminOverview({ ...overviewFixture(), total_orders: value })));
}
for (const value of [null, [], {}, { users: [] }]) {
  test('missing overview contract never invents zero: ' + JSON.stringify(value), () => assert.throws(() => parseAdminOverview(value)));
}
test('audit projection omits reasons, actor identity, arbitrary URLs and sensitive payloads', () => {
  const input = activityFixture(); Object.assign(input.events[0], { url: 'javascript:alert(1)', email: 'private@example.com', password_hash: 'PRIVATE', ledger: { amount: '900' } });
  const result = parseAdminActivity(input);
  assert.equal(result.events.length, 2);
  assert.deepEqual(Object.keys(result.events[0]), ['source', 'audit_id', 'action', 'target_type', 'target_id', 'created_at']);
  assert.ok(!JSON.stringify(result).includes('PRIVATE'));
  assert.equal(parseAdminActivity({ total: 0, limit: 5, offset: 0, events: [] }).total, 0);
});
for (const patch of [{ limit: 100 }, { offset: 5 }, { total: -1 }, { events: null }, { total: 0 }]) {
  test('unexpected activity envelope rejected: ' + JSON.stringify(patch), () => assert.throws(() => parseAdminActivity({ ...activityFixture(), ...patch })));
}
for (const patch of [{ audit_id: 0 }, { target_id: -1 }, { action: 'delete_user' }, { source: 'public' }, { target_type: 'business' }, { created_at: 'bad' }]) {
  test('malformed activity record rejected: ' + JSON.stringify(patch), () => { const data = activityFixture(); Object.assign(data.events[0], patch); assert.throws(() => parseAdminActivity(data)); });
}
test('activity keys include source; duplicate records and overlong pages are rejected', () => {
  const input = activityFixture(); assert.equal(parseAdminActivity(input).events.length, 2);
  input.events[1] = { ...input.events[0] }; assert.throws(() => parseAdminActivity(input));
  assert.throws(() => parseAdminActivity({ total: 6, limit: 5, offset: 0, events: Array.from({ length: 6 }, () => activityFixture().events[0]) }));
});
test('timestamps follow backend UTC convention and never fabricate a time', () => {
  assert.deepEqual(adminTimestamp('2026-11-07T08:00:00'), { iso: '2026-11-07T08:00:00Z', label: '2026-11-07 08:00:00 UTC' });
  assert.equal(adminTimestamp('2026-11-07T10:00:00+02:00').label, '2026-11-07 08:00:00 UTC');
  assert.equal(adminTimestamp('not-time'), null);
});
test('entry loads both independent resources and refresh obtains new authoritative counts', async () => {
  let orders = 61; const f = setup({ overview: () => ({ ...overviewFixture(), total_orders: orders }) });
  assert.equal(f.reader.getSnapshot().overview.loading, true); assert.equal(f.reader.getSnapshot().overview.data, null);
  await f.reader.start(); assert.deepEqual(f.calls, { overview: 1, activity: 1 }); assert.equal(f.reader.getSnapshot().overview.data.total_orders, 61);
  orders = 62; const refreshing = f.reader.start(); assert.equal(f.reader.getSnapshot().overview.data, null); await refreshing;
  assert.equal(f.reader.getSnapshot().overview.data.total_orders, 62); f.reader.dispose();
});
test('rapid refresh and section retry share pending requests without duplicate dispatch', async () => {
  const pending = defer(), f = setup({ overview: () => pending.promise });
  const first = f.reader.start(), second = f.reader.start(), third = f.reader.load('overview'); await flush();
  assert.equal(f.calls.overview, 1); pending.resolve(overviewFixture()); await Promise.all([first, second, third]);
  assert.equal(f.reader.getSnapshot().overview.data.total_shop_owners, 12); f.reader.dispose();
});
test('failed summary and successful activity remain independent and retryable', async () => {
  let fail = true; const f = setup({ overview: () => { if (fail) throw Error('PRIVATE SQL diagnostics'); return overviewFixture(); } });
  await f.reader.start(); assert.equal(f.reader.getSnapshot().overview.data, null); assert.ok(f.reader.getSnapshot().overview.error); assert.equal(f.reader.getSnapshot().activity.data.events.length, 2);
  assert.ok(!f.reader.getSnapshot().overview.error.includes('PRIVATE'));
  fail = false; await f.reader.load('overview'); assert.equal(f.reader.getSnapshot().overview.error, ''); f.reader.dispose();
});
test('refresh failure clears previously displayed counts rather than presenting stale success', async () => {
  let fail = false; const f = setup({ overview: () => { if (fail) throw Error('Network'); return overviewFixture(); } });
  await f.reader.start(); fail = true; await f.reader.start(); assert.equal(f.reader.getSnapshot().overview.data, null); assert.ok(f.reader.getSnapshot().overview.error); f.reader.dispose();
});
test('activity failure does not hide verified counts; malformed response is safely rejected', async () => {
  const f = setup({ activity: () => ({ total: 2, events: [] }) }); await f.reader.start();
  assert.equal(f.reader.getSnapshot().overview.data.total_orders, 61); assert.equal(f.reader.getSnapshot().activity.data, null); assert.match(f.reader.getSnapshot().activity.error, /could not be verified/); f.reader.dispose();
});
for (const status of [401, 403]) {
  test('HTTP ' + status + ' hides all data, cancels sibling request and blocks further reads', async () => {
    const pending = defer(); const f = setup({ overview: () => pending.promise, activity: () => { throw { response: { status, data: { detail: 'PRIVATE' } } }; } });
    const load = f.reader.start(); await flush(); assert.equal(f.signals.overview.aborted, true);
    pending.resolve(overviewFixture()); await load; assert.ok(f.reader.getSnapshot().authError); assert.equal(f.reader.getSnapshot().overview.data, null); assert.equal(f.reader.getSnapshot().activity.data, null);
    assert.ok(!f.reader.getSnapshot().authError.includes('PRIVATE'));
    await f.reader.start(); assert.equal(f.calls.overview, 1); f.reader.dispose();
  });
}
test('unmount aborts pending requests and late responses cannot update a newer lifecycle', async () => {
  const old = defer(); let calls = 0; const f = setup({ overview: () => ++calls === 1 ? old.promise : { ...overviewFixture(), total_orders: 88 } });
  const first = f.reader.start(); await flush(); const oldSignal = f.signals.overview; f.reader.dispose(); const second = f.reader.start(); await second;
  assert.equal(oldSignal.aborted, true); old.resolve(overviewFixture()); await first; assert.equal(f.reader.getSnapshot().overview.data.total_orders, 88); f.reader.dispose();
});
test('cancel before dispatch prevents requests and unsubscribed observers receive nothing', async () => {
  const f = setup(); let notices = 0; const remove = f.reader.subscribe(() => notices++); remove(); const pending = f.reader.start(); f.reader.dispose(); await pending;
  assert.deepEqual(f.calls, { overview: 0, activity: 0 }); assert.equal(notices, 0); assert.equal(f.reader.getSnapshot().overview.data, null);
});
test('a new identity reader starts without prior account data', async () => {
  const first = setup(); await first.reader.start(); first.reader.dispose(); const next = setup();
  assert.equal(next.reader.getSnapshot().overview.data, null); assert.equal(next.reader.getSnapshot().activity.data, null); next.reader.dispose();
});

test('missing database structures are distinct from connection failure without exposing diagnostics', async () => {
  const error={response:{status:503,data:{detail:{code:'ADMIN_SCHEMA_UNAVAILABLE',message:'PRIVATE database SQL'}}}};
  assert.equal(adminReadError(error),'Platform database setup is incomplete. Contact the platform operator.');
  const f=setup({overview:async()=>{throw error;}});await f.reader.start();
  assert.equal(f.reader.getSnapshot().overview.data,null);
  assert.equal(f.reader.getSnapshot().overview.error,'Platform database setup is incomplete. Contact the platform operator.');
  assert.ok(!f.reader.getSnapshot().overview.error.includes('PRIVATE'));
  assert.ok(f.reader.getSnapshot().activity.data);
  f.reader.dispose();
  assert.equal(adminReadError({response:{status:503,data:{detail:'PRIVATE'}}}),'Platform information is unavailable. Check your connection and retry.');
});
test('error messages ignore server diagnostics and distinguish session, access, timeout and network', () => {
  for (const status of [401, 403, 404, 422, 429, 503]) assert.ok(!adminReadError({ response: { status, data: { detail: 'PRIVATE' } } }).includes('PRIVATE'));
  assert.match(adminReadError({ code: 'ECONNABORTED' }), /timed out/);
});

