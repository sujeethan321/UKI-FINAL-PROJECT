import { test } from 'node:test';
import assert from 'node:assert/strict';
import { setImmediate } from 'node:timers';
import { managementAreas, createAdminManagement, parseManagementDetail, parseManagementList, parseOwnerBusinesses, parseBusinessHistory, allowedManagementActions } from '../src/utils/adminManagement.js';
import { rowFixture, driverFixture, businessFixture, userFixture, associationFixture, historyFixture } from './fixtures/adminManagementFixtures.js';
import { overviewFixture } from './fixtures/adminDashboardFixtures.js';
const copy = data => structuredClone(data), flush = () => new Promise(resolve => setImmediate(resolve));
const defer = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };
function setup(kind = 'driver', overrides = {}, records = [rowFixture(kind)]) {
  const calls = [], rows = copy(records);
  const api = {
    async list(area, filters, options) { calls.push({ type: 'list', filters: { ...filters }, options }); const selected = rows.filter(row => (!filters.status || (area === 'business' ? row.approval_status : row.account_status) === filters.status) && (!filters.approval_status || (row.profile?.approval_status ?? 'not_submitted') === filters.approval_status) && (!filters.q || (row.full_name ?? row.business_name).includes(filters.q))); return { total: selected.length, limit: 10, offset: filters.offset, [managementAreas[area].collection]: copy(selected.slice(filters.offset, filters.offset + 10)) }; },
    async detail(area, id, options) { calls.push({ type: 'detail', id, options }); const row = rows.find(row => (row.user_id ?? row.business_id) === id); if (!row) throw { response: { status: 404 } }; return copy(row); },
    async associations(id, offset, options) { calls.push({ type: 'associations', id, offset, options }); return { ...associationFixture(id), offset }; },
    async history(id) { calls.push({ type: 'history', id }); return historyFixture(id); },
    async overview() { calls.push({ type: 'overview' }); return { ...overviewFixture(), pending_driver_approvals: kind === 'driver' ? rows.filter(row => row.profile?.approval_status === 'pending').length : 0, pending_business_approvals: kind === 'business' ? rows.filter(row => row.approval_status === 'pending').length : 0 }; },
    async mutate(area, operation, options) { calls.push({ type: 'mutate', operation: { ...operation }, options }); const row = rows.find(row => (row.user_id ?? row.business_id) === operation.id);
      if (['suspend', 'reactivate'].includes(operation.action)) { row.account_status = operation.action === 'suspend' ? 'suspended' : 'active'; return copy(userFixture(area, row.user_id, row.account_status)); }
      const current = area === 'business' ? row : row.profile;
      if (current.approval_status !== 'pending') throw { response: { status: 409 } };
      current.approval_status = operation.action === 'approve' ? 'approved' : 'rejected'; return copy(row);
    }, ...overrides,
  };
  return { api, rows, calls, reader: createAdminManagement(api, kind) };
}
async function ready(kind, overrides, records) { const f = setup(kind, overrides, records); await f.reader.start(); await f.reader.select(7); return f; }
const mutations = f => f.calls.filter(call => call.type === 'mutate');
for (const kind of Object.keys(managementAreas)) {
  test(kind + ' list/detail projections exclude secrets and finance; bind target identity', () => {
    const row = { ...rowFixture(kind), password_hash: 'PRIVATE', access_token: 'PRIVATE', balance: 'PRIVATE' }, filters = { status: '', approval_status: '', offset: 0 };
    assert.ok(!JSON.stringify(parseManagementDetail(kind, row, 7)).includes('PRIVATE'));
    assert.equal(parseManagementList(kind, { total: 1, limit: 10, offset: 0, [managementAreas[kind].collection]: [row] }, filters).rows.length, 1);
    assert.throws(() => parseManagementDetail(kind, row, 8));
  });
  test(kind + ' loads actual list, details and supported related resources', async () => { const f = await ready(kind); assert.equal(f.reader.getSnapshot().list.data.total, 1); assert.ok(f.reader.getSnapshot().detail.data); assert.equal(f.calls.filter(c => c.type === 'associations').length, kind === 'shop_owner' ? 1 : 0); assert.equal(f.calls.filter(c => c.type === 'history').length, kind === 'business' ? 1 : 0); f.reader.dispose(); });
}
test('Admin/wrong-role targets are rejected; unsupported account states stay read-only', () => { assert.throws(() => parseManagementDetail('customer', userFixture('admin'), 7)); assert.throws(() => createAdminManagement({}, 'admin')); assert.deepEqual(allowedManagementActions('customer', userFixture('admin')), []); assert.deepEqual(allowedManagementActions('customer', userFixture('customer', 7, 'disabled')), []); });
test('approval requires pending, active eligible application and real vehicle/owner data', () => {
  assert.ok(allowedManagementActions('driver', driverFixture()).includes('approve'));
  for (const state of ['approved', 'rejected', 'suspended']) assert.ok(!allowedManagementActions('driver', driverFixture(7, state)).includes('approve'));
  assert.deepEqual(allowedManagementActions('driver', driverFixture(7, 'pending', 'suspended')), ['reactivate']);
  const row = driverFixture(); row.profile.vehicle_type = null; assert.ok(!allowedManagementActions('driver', row).includes('approve')); assert.ok(allowedManagementActions('driver', row).includes('reject'));
  assert.deepEqual(allowedManagementActions('business', { ...businessFixture(), owners: [] }), ['reject']); assert.deepEqual(allowedManagementActions('business', businessFixture(7, 'approved')), []);
});
for (const kind of ['driver', 'business']) for (const action of ['approve', 'reject']) test(kind + ' ' + action + ' waits for server confirmation and refreshes status/list/pending counts', async () => {
  const f = await ready(kind); assert.equal(mutations(f).length, 0); f.reader.open(action); f.reader.note(' Reviewed application '); assert.equal(await f.reader.submit(), true);
  const state = f.reader.getSnapshot(); assert.equal(state.feedback.type, 'success'); assert.equal(state.dialog, null); assert.equal(mutations(f)[0].operation.text, 'Reviewed application');
  assert.equal(kind === 'driver' ? state.detail.data.profile.approval_status : state.detail.data.approval_status, action === 'approve' ? 'approved' : 'rejected');
  assert.equal(state.overview.data[kind === 'driver' ? 'pending_driver_approvals' : 'pending_business_approvals'], 0); assert.equal(f.reader.open(action), false); f.reader.dispose();
});
for (const kind of ['shop_owner', 'customer', 'driver']) test(kind + ' suspend/reactivate requires reason and preserves Driver approval', async () => {
  const f = await ready(kind); f.reader.open('suspend'); assert.equal(await f.reader.submit(), false); assert.equal(mutations(f).length, 0); f.reader.note('Operational review'); assert.equal(await f.reader.submit(), true); assert.equal(f.reader.getSnapshot().detail.data.account_status, 'suspended');
  f.reader.open('reactivate'); f.reader.note('Review complete'); assert.equal(await f.reader.submit(), true); assert.equal(f.reader.getSnapshot().detail.data.account_status, 'active'); if (kind === 'driver') assert.equal(f.reader.getSnapshot().detail.data.profile.approval_status, 'pending'); f.reader.dispose();
});
for (const note of ['line\nbreak', 'x'.repeat(501)]) test('invalid review text never dispatches: ' + note.length, async () => { const f = await ready('driver'); f.reader.open('reject'); f.reader.note(note); assert.equal(await f.reader.submit(), false); assert.equal(mutations(f).length, 0); f.reader.dispose(); });
test('duplicate submission shares one request and freezes target, filters and dialog', async () => {
  const pending = defer(), f = await ready('driver', { mutate: () => pending.promise }, [driverFixture(), driverFixture(8)]); f.reader.open('approve'); const first = f.reader.submit(); assert.equal(first, f.reader.submit()); f.reader.select(8); f.reader.filter({ q: 'Changed' }); f.reader.closeDialog(); f.reader.note('Changed');
  assert.equal(f.reader.getSnapshot().selectedId, 7); assert.equal(f.reader.getSnapshot().dialog.text, ''); assert.equal(f.reader.getSnapshot().filters.q, ''); pending.resolve(driverFixture(7, 'approved')); await first; assert.equal(f.reader.getSnapshot().feedback.type, 'success'); f.reader.dispose();
});
for (const kind of ['driver', 'business']) for (const status of [409, 422, 404]) test(kind + ' mutation failure ' + status + ' sanitizes errors and refreshes without success', async () => { const f = await ready(kind, { mutate: () => { throw { response: { status, data: { detail: 'PRIVATE' } } }; } }); f.reader.open('reject'); assert.equal(await f.reader.submit(), false); const state = f.reader.getSnapshot(); assert.equal(state.feedback.type, 'error'); assert.equal(state.uncertain, null); assert.ok(!state.feedback.message.includes('PRIVATE')); assert.ok(f.calls.filter(c => c.type === 'detail').length >= 2); f.reader.dispose(); });
test('concurrent rejection refreshes real state without claiming another actor success', async () => { const f = await ready('business'); f.api.mutate = async () => { f.rows[0].approval_status = 'rejected'; throw { response: { status: 409 } }; }; f.reader.open('approve'); await f.reader.submit(); assert.equal(f.reader.getSnapshot().detail.data.approval_status, 'rejected'); assert.equal(f.reader.getSnapshot().feedback.type, 'error'); f.reader.dispose(); });
test('uncertain response blocks conflicting actions and retries the same frozen target/reason', async () => {
  const f = await ready('driver'), real = f.api.mutate; let first = true; f.api.mutate = async (...args) => { if (first) { first = false; throw Error('PRIVATE'); } return real(...args); };
  f.reader.open('reject'); f.reader.note('Original review'); assert.equal(await f.reader.submit(), false); assert.ok(f.reader.getSnapshot().uncertain); assert.equal(f.reader.open('approve'), false); f.reader.select(8); f.reader.filter({ status: 'suspended' }); assert.equal(f.reader.getSnapshot().selectedId, 7);
  assert.equal(await f.reader.submit(), true); assert.equal(mutations(f)[0].operation.action, 'reject'); assert.equal(mutations(f)[0].operation.text, 'Original review'); f.reader.dispose();
});
test('malformed success is treated as uncertain, never optimistic approval', async () => { const f = await ready('business', { mutate: () => businessFixture(8, 'approved') }); f.reader.open('approve'); assert.equal(await f.reader.submit(), false); assert.ok(f.reader.getSnapshot().uncertain); assert.equal(f.reader.getSnapshot().feedback.type, 'error'); f.reader.dispose(); });
for (const status of [401, 403]) {
  test('mutation HTTP ' + status + ' clears all records and actions', async () => { const f = await ready('driver', { mutate: () => { throw { response: { status } }; } }); f.reader.open('approve'); await f.reader.submit(); const state = f.reader.getSnapshot(); assert.ok(state.authError); assert.equal(state.detail.data, null); assert.equal(state.list.data, null); assert.equal(state.dialog, null); assert.equal(f.reader.open('approve'), false); f.reader.dispose(); });
  test('list HTTP ' + status + ' clears sibling data', async () => { const f = setup('customer', { list: () => { throw { response: { status } }; } }); await f.reader.start(); assert.ok(f.reader.getSnapshot().authError); assert.equal(f.reader.getSnapshot().overview.data, null); f.reader.dispose(); });
}
test('search, status and page changes use server windows, reset page and clear details', async () => {
  const f = setup('customer', {}, Array.from({ length: 12 }, (_, i) => userFixture('customer', i + 1))); await f.reader.start(); await f.reader.page(10); assert.equal(f.reader.getSnapshot().list.data.rows.length, 2); await f.reader.select(11); await f.reader.filter({ q: 'Example 1', status: 'active' });
  assert.equal(f.reader.getSnapshot().filters.offset, 0); assert.equal(f.reader.getSnapshot().selectedId, null); assert.equal(f.reader.getSnapshot().list.data.total, 4); await f.reader.clear(); assert.equal(f.reader.getSnapshot().list.data.total, 12); f.reader.dispose();
});
test('stale list and detail responses cannot overwrite newer filters/selection', async () => {
  const old = defer(), f = setup('customer'); const real = f.api.list; let first = true; f.api.list = (...args) => { if (first) { first = false; return old.promise; } return real(...args); };
  const loading = f.reader.start(); await flush(); await f.reader.filter({ q: 'No results' }); old.resolve({ total: 1, limit: 10, offset: 0, users: [userFixture()] }); await loading; assert.equal(f.reader.getSnapshot().list.data.total, 0); f.reader.dispose();
  const detail = defer(), second = setup('shop_owner', {}, [userFixture('shop_owner'), userFixture('shop_owner', 8)]), actual = second.api.detail; second.api.detail = (kind, id, options) => id === 7 ? detail.promise : actual(kind, id, options); await second.reader.start(); const request = second.reader.select(7); await flush(); await second.reader.select(8); detail.resolve(userFixture('shop_owner')); await request; assert.equal(second.reader.getSnapshot().detail.data.user_id, 8); second.reader.dispose();
});
test('partial related-resource failure preserves safe details; failed list is not a fabricated empty state', async () => { const f = await ready('shop_owner', { associations: () => { throw Error('PRIVATE'); } }); assert.ok(f.reader.getSnapshot().detail.data); assert.ok(f.reader.getSnapshot().associations.error); f.reader.dispose(); const bad = setup('customer', { list: () => { throw Error('Network'); } }); await bad.reader.start(); assert.equal(bad.reader.getSnapshot().list.data, null); assert.ok(bad.reader.getSnapshot().list.error); bad.reader.dispose(); });
test('associated business/history identifiers and page bounds are verified', () => { assert.throws(() => parseOwnerBusinesses(associationFixture(8), 7, 0)); assert.throws(() => parseOwnerBusinesses({ ...associationFixture(7), limit: 100 }, 7, 0)); assert.throws(() => parseBusinessHistory(historyFixture(8), 7)); assert.throws(() => parseBusinessHistory({ ...historyFixture(7), offset: 10 }, 7)); });
test('invalid filters and offsets never dispatch unrestricted reads', async () => { const f = await ready('driver'), before = f.calls.length; for (const patch of [{ q: 'x'.repeat(101) }, { status: 'deleted' }, { approval_status: 'verified' }]) await f.reader.filter(patch); for (const offset of [-1, 1, 1000010]) await f.reader.page(offset); assert.equal(f.calls.length, before); f.reader.dispose(); });
test('pending business pagination clamps when a review empties the final page', async () => { const f = setup('business', {}, Array.from({ length: 11 }, (_, i) => businessFixture(i + 1))); await f.reader.start(); await f.reader.page(10); await f.reader.select(11); f.reader.open('approve'); await f.reader.submit(); assert.equal(f.reader.getSnapshot().filters.offset, 0); assert.equal(f.reader.getSnapshot().list.data.total, 10); f.reader.dispose(); });
test('unmount/account switching suppresses late mutation success and authenticated refresh', async () => { const pending = defer(), f = await ready('driver', { mutate: () => pending.promise }); f.reader.open('approve'); const saving = f.reader.submit(); await flush(); const before = f.calls.length; f.reader.dispose(); pending.resolve(driverFixture(7, 'approved')); await saving; assert.equal(f.calls.length, before); assert.equal(f.reader.getSnapshot().feedback, null); assert.equal(setup('driver').reader.getSnapshot().detail.data, null); });
test('Strict Mode restart ignores old responses without clearing new request locks', async () => { const pending = defer(), f = setup('customer'), real = f.api.list; let first = true; f.api.list = (...args) => { if (first) { first = false; return pending.promise; } return real(...args); }; const old = f.reader.start(); await flush(); f.reader.dispose(); await f.reader.start(); pending.resolve({ total: 0, limit: 10, offset: 0, users: [] }); await old; assert.equal(f.reader.getSnapshot().list.data.total, 1); f.reader.dispose(); });
