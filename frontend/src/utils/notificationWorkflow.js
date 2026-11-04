import { NOTIFICATION_TYPES, notificationError, validCount, validNotification, validNotificationId, validNotificationPage } from "./notification.js";

const initialState = () => ({ count: null, countLoading: false, countError: "", authError: "",
  open: false, recent: null, recentLoading: false, recentError: "", list: null, listLoading: false, listError: "",
  readFilter: "all", typeFilter: "", page: 1, pageSize: 20, mutating: false, markingId: null, actionError: "" });

// One store per authenticated session; no notification content is persisted.
export function createNotificationWorkflow({ api, timers = globalThis, now = () => Date.now(), pollMs = 60000 }) {
  let state = initialState(), alive = false, generation = 0, visible = true, pageActive = false;
  let countVersion = 0, listVersion = 0, recentVersion = 0, countAbort, listAbort, recentAbort, writeAbort;
  let countTask = null, timer = null, failures = 0, locked = false, lastReturn = -Infinity;
  const listeners = new Set();
  const publish = patch => { if (alive) { state = { ...state, ...patch }; listeners.forEach(fn => fn()); } };
  const current = epoch => alive && generation === epoch && !state.authError;
  const clearTimer = () => { if (timer !== null) timers.clearTimeout(timer); timer = null; };
  function invalidateReads() {
    ++countVersion; ++listVersion; ++recentVersion;
    countAbort?.abort(); listAbort?.abort(); recentAbort?.abort(); countTask = null;
    clearTimer();
  }
  function authFailure(error) {
    if (![401, 403].includes(error?.response?.status)) return false;
    invalidateReads(); writeAbort?.abort(); ++generation; locked = false;
    publish({ ...initialState(), authError: notificationError(error) });
    return true;
  }
  function schedule() {
    clearTimer();
    if (!alive || !visible || state.authError || locked || state.countLoading) return;
    const epoch = generation;
    timer = timers.setTimeout(() => {
      timer = null;
      if (current(epoch) && visible) void loadCount();
    }, Math.min(pollMs * (2 ** Math.min(failures, 3)), 300000));
  }
  function loadCount(force = false) {
    if (!alive || state.authError || (locked && !force)) return Promise.resolve();
    if (countTask) return countTask;
    const epoch = generation, version = ++countVersion;
    countAbort = new AbortController(); const signal = countAbort.signal;
    clearTimer(); publish({ countLoading: true, countError: "" });
    countTask = (async () => {
      try {
        const data = await api.count({ signal });
        if (!current(epoch) || signal.aborted || version !== countVersion) return;
        if (!validCount(data?.unread_count)) throw new Error("Invalid unread count");
        failures = 0; publish({ count: data.unread_count });
      } catch (error) {
        if (!current(epoch) || signal.aborted || version !== countVersion) return;
        if (!authFailure(error)) { failures++; publish({ count: null, countError: notificationError(error) }); }
      } finally {
        if (current(epoch) && version === countVersion) {
          countTask = null; publish({ countLoading: false }); schedule();
        }
      }
    })();
    return countTask;
  }
  async function loadFeed(kind, force = false) {
    if (!alive || state.authError || (locked && !force)) return;
    const isList = kind === "list";
    if ((isList && !pageActive) || (!isList && !state.open)) return;
    const epoch = generation;
    const version = isList ? ++listVersion : ++recentVersion;
    if (isList) listAbort?.abort(); else recentAbort?.abort();
    const controller = new AbortController(); const signal = controller.signal;
    if (isList) listAbort = controller; else recentAbort = controller;
    const filters = { page: isList ? state.page : 1, page_size: isList ? state.pageSize : 5 };
    if (isList && state.readFilter !== "all") filters.is_read = state.readFilter === "read";
    if (isList && state.typeFilter) filters.notification_type = state.typeFilter;
    publish(isList ? { listLoading: true, listError: "", list: null } : { recentLoading: true, recentError: "", recent: null });
    const fresh = () => current(epoch) && !signal.aborted && version === (isList ? listVersion : recentVersion);
    try {
      const data = await api.list(filters, { signal });
      if (!fresh()) return;
      if (!validNotificationPage(data, filters)) throw new Error("Invalid notification page");
      if (isList && data.page > 1 && !data.notifications.length) {
        publish({ page: Math.max(1, Math.min(data.page - 1, Math.ceil(data.total / data.page_size))) });
        await loadFeed("list", force); return;
      }
      publish(isList ? { list: data } : { recent: data });
    } catch (error) {
      if (fresh() && !authFailure(error)) publish(isList ? { listError: notificationError(error) } : { recentError: notificationError(error) });
    } finally {
      if (fresh()) publish(isList ? { listLoading: false } : { recentLoading: false });
    }
  }
  async function refresh(force = false) {
    if (!alive || state.authError || (locked && !force)) return;
    await Promise.all([loadCount(force), loadFeed("recent", force), loadFeed("list", force)]);
  }
  async function setFilter(field, value) {
    if (locked || !alive || state.authError) return;
    if (field === "readFilter" && !["all", "read", "unread"].includes(value)) return;
    if (field === "typeFilter" && value !== "" && !NOTIFICATION_TYPES.some(([v]) => v === value)) return;
    if (field === "page" && (!Number.isInteger(value) || value < 1 || value > 1000000)) return;
    if (!["page", "readFilter", "typeFilter"].includes(field)) return;
    publish({ [field]: value, ...(field !== "page" ? { page: 1 } : {}), actionError: "" });
    await loadFeed("list");
  }
  async function toggleDropdown() {
    if (!alive || state.authError) return;
    if (state.open) { closeDropdown(); return; }
    publish({ open: true });
    await loadFeed("recent");
  }
  function closeDropdown() {
    recentAbort?.abort(); ++recentVersion;
    publish({ open: false, recent: null, recentLoading: false, recentError: "" });
  }
  async function markRead(notificationId = null) {
    if (!alive || state.authError || locked) return;
    const all = notificationId === null;
    const original = all ? null : [...(state.list?.notifications || []), ...(state.recent?.notifications || [])].find(row => row.notification_id === notificationId);
    if (!all && (!validNotificationId(notificationId) || !original || original.is_read)) return;
    locked = true; invalidateReads();
    publish({ mutating: true, markingId: notificationId, actionError: "", countLoading: false, listLoading: false, recentLoading: false });
    const epoch = generation;
    writeAbort = new AbortController(); const signal = writeAbort.signal;
    try {
      const result = all ? await api.markAll({ signal }) : await api.markOne(notificationId, { signal });
      if (!current(epoch) || signal.aborted) return;
      if (all ? !validCount(result?.updated_count) : !validNotification(result) || result.notification_id !== notificationId || !result.is_read || result.notification_type !== original.notification_type || result.business_id !== original.business_id || result.related_entity_id !== original.related_entity_id) throw new Error("Unconfirmed read response");
      const update = feed => feed ? { ...feed, notifications: feed.notifications.map(row =>
        (all || row.notification_id === notificationId) ? (all ? { ...row, is_read: true } : result) : row) } : null;
      // Confirmed changes appear immediately; count and filtered pagination come
      // from new server reads rather than client-side decrement arithmetic.
      publish({ list: update(state.list), recent: update(state.recent), count: null, actionError: "" });
      await refresh(true);
    } catch (error) {
      if (current(epoch) && !signal.aborted && !authFailure(error)) {
        publish({ actionError: notificationError(error, true), count: null, countError: "Refresh to confirm the current unread count." });
      }
    } finally {
      if (current(epoch)) { locked = false; publish({ mutating: false, markingId: null }); schedule(); }
    }
  }
  function start(isVisible = true) {
    if (alive) return;
    alive = true; ++generation; visible = isVisible; locked = false; failures = 0;
    lastReturn = now(); publish(initialState());
    if (visible) void loadCount();
    if (pageActive) void loadFeed("list");
  }
  function setVisible(value) {
    visible = value;
    if (!value) { clearTimer(); return; }
    returnToTab();
  }
  function returnToTab() {
    if (!alive || !visible || state.authError || locked || now() - lastReturn < 5000) { schedule(); return; }
    lastReturn = now(); void refresh();
  }
  function dispose() {
    alive = false; ++generation; invalidateReads(); writeAbort?.abort(); locked = false; pageActive = false;
    state = initialState(); // No listener notifications after unmount.
  }
  return { subscribe: fn => { listeners.add(fn); return () => listeners.delete(fn); }, getSnapshot: () => state,
    start, dispose, refresh, loadCount, loadRecent: () => loadFeed("recent"), loadList: () => loadFeed("list"),
    toggleDropdown, closeDropdown, setFilter, markRead, markAllRead: () => markRead(), setVisible, returnToTab,
    openInbox: () => { pageActive = true; void loadFeed("list"); },
    closeInbox: () => { pageActive = false; listAbort?.abort(); ++listVersion; publish({ list: null, listLoading: false, listError: "" }); } };
}

export function bindNotificationLifecycle(workflow, browserWindow, browserDocument) {
  const visibility = () => workflow.setVisible(!browserDocument.hidden);
  const focus = () => { if (!browserDocument.hidden) workflow.returnToTab(); };
  workflow.start(!browserDocument.hidden);
  browserDocument.addEventListener("visibilitychange", visibility);
  browserWindow.addEventListener("focus", focus);
  return () => {
    browserDocument.removeEventListener("visibilitychange", visibility);
    browserWindow.removeEventListener("focus", focus);
    workflow.dispose();
  };
}
