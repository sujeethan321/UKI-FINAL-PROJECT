import { test } from "node:test";
import assert from "node:assert/strict";
import { setImmediate } from "node:timers";
import { createNotificationWorkflow, bindNotificationLifecycle } from "../src/utils/notificationWorkflow.js";
import { notificationDestination, notificationError, notificationTime, validNotification } from "../src/utils/notification.js";
import { bindNotificationPopover } from "../src/utils/notificationPopover.js";

const flush = () => new Promise(resolve => setImmediate(resolve));
const row = (id = 1, patch = {}) => ({ notification_id: id, business_id: 12, notification_type: "repayment_recorded", title: "Repayment recorded", message: "A manual repayment was recorded.", related_entity_type: "ledger_entry", related_entity_id: 100 + id, is_read: false, created_at: "2026-11-04T08:00:00Z", read_at: null, ...patch });
const defer = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
class FakeClock {
  time = 0; sequence = 0; jobs = new Map();
  setTimeout = (callback, ms) => { const id = ++this.sequence; this.jobs.set(id, { callback, at: this.time + ms }); return id; };
  clearTimeout = id => this.jobs.delete(id);
  async advance(ms) {
    const target = this.time + ms;
    for (;;) {
      const next = [...this.jobs.entries()].filter(([, job]) => job.at <= target).sort((a, b) => a[1].at - b[1].at)[0];
      if (!next) break;
      this.time = next[1].at; this.jobs.delete(next[0]); next[1].callback(); await flush();
    }
    this.time = target; await flush();
  }
}
function fixture(overrides = {}, rows = [row(), row(2)]) {
  const clock = new FakeClock(); const calls = { count: 0, list: [], mark: [], all: 0 };
  let records = rows.map(value => ({ ...value }));
  const api = {
    count: async () => { calls.count++; return { unread_count: records.filter(r => !r.is_read).length }; },
    list: async filters => {
      calls.list.push({ ...filters });
      const filtered = records.filter(r => (filters.is_read === undefined || r.is_read === filters.is_read) && (!filters.notification_type || r.notification_type === filters.notification_type)).sort((a, b) => b.notification_id - a.notification_id);
      return { page: filters.page, page_size: filters.page_size, total: filtered.length, notifications: filtered.slice((filters.page - 1) * filters.page_size, filters.page * filters.page_size).map(r => ({ ...r })) };
    },
    markOne: async id => { calls.mark.push(id); const result = records.find(r => r.notification_id === id); result.is_read = true; result.read_at = "2026-11-04T09:00:00Z"; return { ...result }; },
    markAll: async () => { calls.all++; const unread = records.filter(r => !r.is_read); records = records.map(r => ({ ...r, is_read: true, read_at: r.read_at || "2026-11-04T09:00:00Z" })); return { updated_count: unread.length }; },
    ...overrides,
  };
  const workflow = createNotificationWorkflow({ api, timers: clock, now: () => clock.time });
  return { workflow, clock, api, calls, ready: async () => { workflow.start(); await flush(); workflow.openInbox(); await flush(); } };
}

test("real unread count starts unknown then loads; no invented zero", async () => {
  const pending = defer(); const f = fixture({ count: () => pending.promise }); f.workflow.start(); assert.equal(f.workflow.getSnapshot().count, null); assert.equal(f.workflow.getSnapshot().countLoading, true); pending.resolve({ unread_count: 123 }); await flush(); assert.equal(f.workflow.getSnapshot().count, 123); f.workflow.dispose();
});
test("dropdown opens/closes, fetches only five recent records and never marks read", async () => {
  const f = fixture(); await f.ready(); await f.workflow.toggleDropdown(); assert.equal(f.workflow.getSnapshot().open, true); assert.equal(f.workflow.getSnapshot().recent.total, 2); assert.deepEqual(f.calls.list.at(-1), { page: 1, page_size: 5 }); assert.equal(f.calls.mark.length, 0); assert.equal(f.calls.all, 0); await f.workflow.toggleDropdown(); assert.equal(f.workflow.getSnapshot().open, false); assert.equal(f.workflow.getSnapshot().recent, null); f.workflow.dispose();
});
test("mark one waits for backend confirmation and refreshes authoritative count", async () => {
  const pending = defer(); const f = fixture(); await f.ready(); const original = f.api.markOne; f.api.markOne = async id => { await pending.promise; return original(id); };
  const saving = f.workflow.markRead(1); assert.equal(f.workflow.getSnapshot().list.notifications.find(r => r.notification_id === 1).is_read, false); pending.resolve(); await saving; assert.equal(f.workflow.getSnapshot().list.notifications.find(r => r.notification_id === 1).is_read, true); assert.equal(f.workflow.getSnapshot().count, 1); assert.equal(f.workflow.getSnapshot().mutating, false); f.workflow.dispose();
});
test("mark-one failure preserves history/read state and exposes safe retry", async () => {
  const f = fixture({ markOne: async () => { throw Error("private stack"); } }); await f.ready(); const original = f.workflow.getSnapshot().list; await f.workflow.markRead(1); assert.deepEqual(f.workflow.getSnapshot().list, original); assert.equal(f.workflow.getSnapshot().count, null); assert.match(f.workflow.getSnapshot().actionError, /could not be confirmed/); assert.doesNotMatch(f.workflow.getSnapshot().actionError, /private/); f.workflow.dispose();
});
test("mark all preserves history, confirms all rows and reloads count", async () => {
  const f = fixture(); await f.ready(); await f.workflow.markAllRead(); assert.equal(f.calls.all, 1); assert.equal(f.workflow.getSnapshot().list.total, 2); assert.ok(f.workflow.getSnapshot().list.notifications.every(r => r.is_read)); assert.equal(f.workflow.getSnapshot().count, 0); f.workflow.dispose();
});
test("failed mark-all does not optimistically remove unread rows", async () => {
  const f = fixture({ markAll: async () => { throw { response: { status: 500, data: { detail: "SQL password" } } }; } }); await f.ready(); await f.workflow.markAllRead(); assert.equal(f.workflow.getSnapshot().list.total, 2); assert.ok(f.workflow.getSnapshot().list.notifications.every(r => !r.is_read)); assert.match(f.workflow.getSnapshot().actionError, /could not be confirmed/); f.workflow.dispose();
});
test("duplicate and simultaneous single/all clicks share one mutation lock", async () => {
  const pending = defer(); let count = 0; const f = fixture({ markOne: async id => { count++; return pending.promise.then(() => row(id, { is_read: true, read_at: "2026-11-04T09:00:00Z" })); } }); await f.ready(); const saving = f.workflow.markRead(1); await f.workflow.markRead(1); await f.workflow.markRead(2); await f.workflow.markAllRead(); assert.equal(count, 1); assert.equal(f.calls.all, 0); pending.resolve(); await saving; f.workflow.dispose();
});
test("malformed/mismatched mutation response never confirms a read", async () => {
  for (const result of [row(2, { is_read: true, read_at: "2026-11-04T09:00:00Z" }), row(), {}]) {
    const f = fixture({ markOne: async () => result }); await f.ready(); await f.workflow.markRead(1); assert.ok(f.workflow.getSnapshot().actionError); assert.equal(f.workflow.getSnapshot().list.notifications.find(r => r.notification_id === 1).is_read, false); f.workflow.dispose();
  }
});
test("failed/malformed mark-all response is never treated as success", async () => {
  const f = fixture({ markAll: async () => ({ updated_count: -1 }) }); await f.ready(); await f.workflow.markAllRead(); assert.ok(f.workflow.getSnapshot().actionError); assert.equal(f.workflow.getSnapshot().list.total, 2); f.workflow.dispose();
});
test("pagination and filters use backend params and reset pages", async () => {
  const f = fixture({}, Array.from({ length: 25 }, (_, i) => row(i + 1))); await f.ready(); await f.workflow.setFilter("page", 2); assert.equal(f.workflow.getSnapshot().list.notifications.length, 5); await f.workflow.setFilter("readFilter", "unread"); assert.equal(f.workflow.getSnapshot().page, 1); await f.workflow.setFilter("typeFilter", "repayment_recorded"); await f.workflow.setFilter("page", 2); assert.deepEqual(f.calls.list.at(-1), { page: 2, page_size: 20, is_read: false, notification_type: "repayment_recorded" }); await f.workflow.setFilter("readFilter", "read"); assert.equal(f.workflow.getSnapshot().page, 1); assert.equal(f.workflow.getSnapshot().list.total, 0); f.workflow.dispose();
});
test("mark all on an unread-filtered later page reconciles pagination", async () => {
  const f = fixture({}, Array.from({ length: 21 }, (_, i) => row(i + 1))); await f.ready(); await f.workflow.setFilter("readFilter", "unread"); await f.workflow.setFilter("page", 2); await f.workflow.markAllRead(); assert.equal(f.workflow.getSnapshot().page, 1); assert.equal(f.workflow.getSnapshot().list.total, 0); assert.equal(f.workflow.getSnapshot().count, 0); f.workflow.dispose();
});
test("stale filter/page responses cannot overwrite current selection", async () => {
  const pending = defer(); const f = fixture(); await f.ready(); const original = f.api.list; let oldSignal;
  f.api.list = async (filters, options) => { if (filters.page === 2) { oldSignal = options.signal; return pending.promise; } return original(filters, options); };
  const old = f.workflow.setFilter("page", 2); await f.workflow.setFilter("readFilter", "read"); pending.resolve({ page: 2, page_size: 20, total: 21, notifications: [row()] }); await old; assert.equal(oldSignal.aborted, true); assert.equal(f.workflow.getSnapshot().page, 1); assert.equal(f.workflow.getSnapshot().list.total, 0); f.workflow.dispose();
});
test("stale counts cannot overwrite confirmed mutation reconciliation", async () => {
  const pending = defer(); const f = fixture(); await f.ready(); const original = f.api.count; let calls = 0;
  f.api.count = async () => ++calls === 1 ? pending.promise : original();
  const old = f.workflow.loadCount(); await f.workflow.markRead(1); assert.equal(f.workflow.getSnapshot().count, 1); pending.resolve({ unread_count: 99 }); await old; assert.equal(f.workflow.getSnapshot().count, 1); f.workflow.dispose();
});
test("empty state and failed list are distinct and retryable", async () => {
  let fail = true; const f = fixture({ list: async filters => { if (fail) throw Error("network"); return { ...filters, total: 0, notifications: [] }; } }); await f.ready(); assert.equal(f.workflow.getSnapshot().list, null); assert.ok(f.workflow.getSnapshot().listError); fail = false; await f.workflow.loadList(); assert.equal(f.workflow.getSnapshot().list.total, 0); assert.equal(f.workflow.getSnapshot().listError, ""); f.workflow.dispose();
});
test("polling waits 60s, never overlaps and stops on dispose", async () => {
  const f = fixture(); f.workflow.start(); await flush(); assert.equal(f.calls.count, 1); await f.clock.advance(59999); assert.equal(f.calls.count, 1); await f.clock.advance(1); assert.equal(f.calls.count, 2);
  const pending = defer(); let calls = 0; f.api.count = async () => { calls++; return pending.promise; };
  await f.clock.advance(60000); assert.equal(calls, 1); await f.clock.advance(300000); assert.equal(calls, 1); f.workflow.returnToTab(); assert.equal(calls, 1); pending.resolve({ unread_count: 2 }); await flush(); f.workflow.dispose(); await f.clock.advance(300000); assert.equal(calls, 1); assert.equal(f.clock.jobs.size, 0);
});
test("poll errors use bounded backoff and never show a fabricated zero", async () => {
  let count = 0; const f = fixture({ count: async () => { count++; throw { response: { status: 500 } }; } }); f.workflow.start(); await flush(); assert.equal(f.workflow.getSnapshot().count, null); await f.clock.advance(60000); assert.equal(count, 1); await f.clock.advance(60000); assert.equal(count, 2); await f.clock.advance(239999); assert.equal(count, 2); await f.clock.advance(1); assert.equal(count, 3); await f.clock.advance(300000); assert.equal(count, 4); f.workflow.dispose();
});
test("background tab pauses polling; return refresh is throttled", async () => {
  const f = fixture(); await f.ready(); f.workflow.setVisible(false); await f.clock.advance(120000); assert.equal(f.calls.count, 1); f.workflow.setVisible(true); f.workflow.returnToTab(); await flush(); assert.equal(f.calls.count, 2); assert.equal(f.calls.list.length, 2); f.workflow.dispose();
});
test("lifecycle listeners handle focus/visibility and are removed on logout/unmount", async () => {
  const f = fixture(); const win = new EventTarget(), doc = new EventTarget(); doc.hidden = false; const cleanup = bindNotificationLifecycle(f.workflow, win, doc); await flush(); doc.hidden = true; doc.dispatchEvent(new Event("visibilitychange")); await f.clock.advance(120000); assert.equal(f.calls.count, 1); doc.hidden = false; doc.dispatchEvent(new Event("visibilitychange")); win.dispatchEvent(new Event("focus")); await flush(); assert.equal(f.calls.count, 2); cleanup(); await f.clock.advance(300000); win.dispatchEvent(new Event("focus")); assert.equal(f.calls.count, 2); assert.equal(f.workflow.getSnapshot().count, null);
});
test("user switching and late requests clear all prior-session data", async () => {
  const pending = defer(); const first = fixture({ list: () => pending.promise }); first.workflow.start(); first.workflow.openInbox(); first.workflow.dispose();
  const next = fixture({}, [row(30)]); await next.ready(); pending.resolve({ page: 1, page_size: 20, total: 1, notifications: [row(1, { message: "Previous private user" })] }); await flush(); assert.equal(first.workflow.getSnapshot().list, null); assert.equal(next.workflow.getSnapshot().list.notifications[0].notification_id, 30); next.workflow.dispose();
});
for (const status of [401, 403]) {
  test("HTTP " + status + " clears list, recent/count and stops polling", async () => {
    const f = fixture(); await f.ready(); await f.workflow.toggleDropdown(); f.api.count = async () => { throw { response: { status, data: { detail: "private" } } }; }; await f.workflow.loadCount(); const state = f.workflow.getSnapshot(); assert.ok(state.authError); assert.equal(state.list, null); assert.equal(state.recent, null); assert.equal(state.open, false); assert.equal(state.count, null); const calls = f.calls.list.length; await f.clock.advance(600000); await f.workflow.refresh(); assert.equal(f.calls.list.length, calls); assert.equal(f.clock.jobs.size, 0); f.workflow.dispose();
  });
}
test("mutation authorization loss clears previously displayed content", async () => {
  const f = fixture({ markAll: async () => { throw { response: { status: 403 } }; } }); await f.ready(); await f.workflow.markAllRead(); assert.equal(f.workflow.getSnapshot().list, null); assert.ok(f.workflow.getSnapshot().authError); f.workflow.dispose();
});
test("late mutations after unmount cannot update state or start polling", async () => {
  const pending = defer(); const f = fixture({ markOne: () => pending.promise }); await f.ready(); let updates = 0; f.workflow.subscribe(() => { updates++; }); const save = f.workflow.markRead(1); f.workflow.dispose(); const atDispose = updates; pending.resolve(row(1, { is_read: true, read_at: "2026-11-04T09:00:00Z" })); await save; assert.equal(updates, atDispose); assert.equal(f.workflow.getSnapshot().list, null); assert.equal(f.clock.jobs.size, 0);
});
test("strict-effect restart ignores responses from prior lifecycle", async () => {
  const pending = defer(); const f = fixture({ count: () => pending.promise }); f.workflow.start(); f.workflow.dispose(); f.api.count = async () => ({ unread_count: 3 }); f.workflow.start(); await flush(); pending.resolve({ unread_count: 100 }); await flush(); assert.equal(f.workflow.getSnapshot().count, 3); f.workflow.dispose();
});
test("child inbox may register before provider effect starts", async () => {
  const f = fixture(); f.workflow.openInbox(); f.workflow.start(); await flush(); assert.equal(f.workflow.getSnapshot().list.total, 2); f.workflow.dispose();
});
test("safe route allowlist ignores injected URLs and unavailable financial destinations", () => {
  const approval = row(1, { notification_type: "business_approved", related_entity_type: "business_approval_audit", url: "https://evil.example", metadata: { url: "javascript:alert(1)" }, message: "https://evil.example" }); assert.deepEqual(notificationDestination(approval, "shop_owner"), { to: "/shop-owner/dashboard", label: "View my businesses" }); assert.equal(notificationDestination(approval, "customer"), null); assert.equal(notificationDestination(row(), "customer"), null); assert.equal(notificationDestination(row(), "shop_owner"), null); assert.equal(notificationDestination(row(1, { notification_type: "bogus" }), "admin"), null); assert.equal(notificationDestination({ ...approval, business_id: null }, "admin"), null);
});
test("relative time has accessible full local timestamp", () => { const time = notificationTime("2026-11-04T08:00:00Z", Date.parse("2026-11-04T09:00:00Z")); assert.equal(time.relative, "1h ago"); assert.ok(time.full.includes("Asia/Colombo")); });
test("unknown/malformed contracts and negative counts fail closed", async () => {
  for (const count of [-1, "2", 1.5]) { const f = fixture({ count: async () => ({ unread_count: count }) }); f.workflow.start(); await flush(); assert.equal(f.workflow.getSnapshot().count, null); assert.ok(f.workflow.getSnapshot().countError); f.workflow.dispose(); }
  assert.equal(validNotification(row(1, { notification_type: "unknown" })), false);
});
test("invalid filters and unknown notification IDs cannot dispatch", async () => { const f = fixture(); await f.ready(); const before = f.calls.list.length; await f.workflow.setFilter("page", 0); await f.workflow.setFilter("typeFilter", "email"); await f.workflow.setFilter("readFilter", "secret"); await f.workflow.markRead(999); assert.equal(f.calls.list.length, before); assert.equal(f.calls.mark.length, 0); f.workflow.dispose(); });
test("popover supports Escape, outside pointer, focus and listener cleanup", () => {
  const doc = new EventTarget(), container = new EventTarget(); const inside = {}; container.contains = target => target === inside; let closed = 0, focused = 0, firstFocused = 0; const cleanup = bindNotificationPopover({ browserDocument: doc, container, trigger: { focus: () => focused++ }, panel: { querySelector: () => ({ focus: () => firstFocused++ }) }, close: () => closed++ }); assert.equal(firstFocused, 1); const key = new Event("keydown", { cancelable: true }); Object.defineProperty(key, "key", { value: "Escape" }); container.dispatchEvent(key); assert.equal(key.defaultPrevented, true); assert.equal(closed, 1); assert.equal(focused, 1); doc.dispatchEvent(new Event("pointerdown")); assert.equal(closed, 2); cleanup(); doc.dispatchEvent(new Event("pointerdown")); assert.equal(closed, 2);
});
test("HTTP error messages never expose raw backend diagnostics", () => { for (const status of [401, 403, 404, 422, 429, 500]) { const text = notificationError({ response: { status, data: { detail: "SECRET" } } }); assert.ok(text); assert.doesNotMatch(text, /SECRET/); } });
