import { reminderError, reminderValidation, reminderFingerprint, secureReminderKey, moneyValid, CHANNELS, LANGUAGES } from "../../utils/reminder.js";
const same = (a, b) => String(a) === String(b);
const id = value => Number.isSafeInteger(value) && value > 0;
const validRecord = (row, businessId) => id(row?.reminder_id) && same(row.business_id, businessId) && id(row.customer_id) && id(row.credit_account_id) && row.currency === "LKR" && moneyValid(row.outstanding_amount) && row.status === "recorded" && typeof row.message === "string" && !!row.message.trim() && CHANNELS.some(([v]) => v === row.channel) && LANGUAGES.some(([v]) => v === row.language) && !Number.isNaN(Date.parse(row.created_at)) && row.delivery_allowed === false;

export function createReminderWorkflow({ api, store, makeKey = secureReminderKey, fingerprint = reminderFingerprint, initialBusinessId = "", initialCustomerId = "" }) {
  let recovery, storageError = "";
  try { recovery = store.read(); } catch { storageError = "Saved request storage is unavailable or invalid. Restore browser session storage before recording reminders."; }
  let state = { businesses: [], businessId: "", customers: [], customerId: "", details: null,
    contextLoading: true, customersLoading: false, detailsLoading: false, historyLoading: false, saving: false,
    contextError: "", customersError: "", detailsError: "", historyError: "", storageError, error: "",
    channel: "internal", language: "en", note: "", success: null, uncertain: !!recovery?.pending,
    history: null, historyCustomerId: "", status: "", ordering: "newest", page: 1, pageSize: 10 };
  let active = true, contextVersion = 0, customerVersion = 0, detailVersion = 0, historyVersion = 0, locked = false;
  let customerAbort, detailAbort, historyAbort;
  const listeners = new Set();
  const publish = patch => { if (active) { state = { ...state, ...patch }; listeners.forEach(fn => fn()); } };
  const approved = () => state.businesses.some(b => same(b.business_id, state.businessId) && b.approval_status === "approved");
  function clearIntent() {
    if (state.uncertain) return;
    try { store.clear(); } catch { publish({ storageError: "Browser session storage must be available before recording reminders." }); }
  }
  async function loadHistory() {
    if (!active) return;
    historyAbort?.abort(); const version = ++historyVersion;
    if (!approved()) { publish({ history: null, historyLoading: false }); return; }
    const businessId = state.businessId;
    const filters = { ordering: state.ordering, page: state.page, page_size: state.pageSize };
    if (state.historyCustomerId) filters.customer_id = Number(state.historyCustomerId);
    if (state.status) filters.status = state.status;
    historyAbort = new AbortController(); const signal = historyAbort.signal;
    publish({ historyLoading: true, historyError: "", history: null });
    try {
      const data = await api.history(businessId, filters, { signal });
      if (!active || signal.aborted || version !== historyVersion) return;
      if (!same(data?.business_id, businessId) || data.page !== filters.page || data.page_size !== filters.page_size || !Number.isSafeInteger(data.total) || data.total < 0 || !Array.isArray(data.reminders) || data.reminders.some(row => !validRecord(row, businessId) || (filters.customer_id && !same(row.customer_id, filters.customer_id)))) throw new Error("Invalid history response");
      publish({ history: data });
    } catch (error) { if (!signal.aborted && version === historyVersion) publish({ historyError: reminderError(error) }); }
    finally { if (!signal.aborted && version === historyVersion) publish({ historyLoading: false }); }
  }
  async function selectCustomer(customerId) {
    if (state.saving) return;
    detailAbort?.abort(); const version = ++detailVersion;
    const businessId = state.businessId;
    const customer = state.customers.find(c => same(c.customer_id, customerId));
    const changed = !same(state.customerId, customerId);
    if (changed) clearIntent();
    publish({ ...(changed ? { note: "", channel: "internal", language: "en" } : {}), customerId: customer ? String(customer.customer_id) : "", details: null, detailsLoading: false, detailsError: "", success: null, error: "" });
    if (!customer || !approved()) return;
    detailAbort = new AbortController(); const signal = detailAbort.signal;
    publish({ detailsLoading: true });
    try {
      const data = await api.details(businessId, customer.customer_id, { signal });
      if (!active || signal.aborted || version !== detailVersion) return;
      if (!same(data?.business_id, businessId) || !same(data?.customer?.business_id, businessId) || !same(data.customer.customer_id, customerId) || data.currency !== "LKR" || !moneyValid(data.outstanding_balance) || (data.credit_account && !id(data.credit_account.credit_account_id))) throw new Error("Invalid customer response");
      publish({ details: data });
    } catch (error) { if (!signal.aborted && version === detailVersion) publish({ detailsError: reminderError(error) }); }
    finally { if (!signal.aborted && version === detailVersion) publish({ detailsLoading: false }); }
  }
  async function loadCustomers() {
    customerAbort?.abort(); const version = ++customerVersion;
    if (!approved()) { publish({ customers: [], customersLoading: false }); return; }
    const businessId = state.businessId;
    customerAbort = new AbortController(); const signal = customerAbort.signal;
    publish({ customersLoading: true, customersError: "" });
    try {
      const data = await api.customers(businessId, { signal });
      if (!active || signal.aborted || version !== customerVersion) return;
      if (!same(data?.business_id, businessId) || !Array.isArray(data.customers) || data.customers.some(c => !id(c.customer_id))) throw new Error("Invalid customer list");
      publish({ customers: data.customers });
    } catch (error) { if (!signal.aborted && version === customerVersion) publish({ customers: [], customersError: reminderError(error) }); }
    finally { if (!signal.aborted && version === customerVersion) publish({ customersLoading: false }); }
  }
  async function selectBusiness(businessId) {
    if (state.saving) return;
    const business = state.businesses.find(b => same(b.business_id, businessId));
    if (!business) return;
    clearIntent(); customerAbort?.abort(); detailAbort?.abort(); historyAbort?.abort();
    ++customerVersion; ++detailVersion; ++historyVersion;
    publish({ businessId: String(business.business_id), customerId: "", customers: [], details: null, history: null,
      detailsLoading: false, customersLoading: false, historyLoading: false, customersError: "", detailsError: "", historyError: "", error: "", success: null,
      historyCustomerId: "", status: "", ordering: "newest", page: 1, channel: "internal", language: "en", note: "" });
    await Promise.all([loadCustomers(), loadHistory()]);
  }
  async function loadBusinesses() {
    active = true; const version = ++contextVersion;
    publish({ contextLoading: true, contextError: "" });
    try {
      const data = await api.businesses();
      if (!active || version !== contextVersion) return;
      if (!Array.isArray(data?.businesses) || data.businesses.some(b => !id(b.business_id))) throw new Error("Invalid business context");
      publish({ businesses: data.businesses });
      const next = data.businesses.find(b => same(b.business_id, state.businessId)) || data.businesses.find(b => same(b.business_id, initialBusinessId) && b.approval_status === "approved") || data.businesses.find(b => b.approval_status === "approved") || data.businesses[0];
      if (next) { await selectBusiness(next.business_id); if (active && version === contextVersion && initialCustomerId) await selectCustomer(initialCustomerId); }
      else publish({ businessId: "", customers: [], details: null, history: null });
    } catch (error) { if (version === contextVersion) publish({ contextError: reminderError(error), businesses: [], businessId: "", customerId: "", customers: [], details: null, history: null }); }
    finally { if (version === contextVersion) publish({ contextLoading: false }); }
  }
  function edit(field, value) {
    if (state.saving || !["channel", "language", "note"].includes(field)) return;
    if (state[field] !== value) clearIntent();
    publish({ [field]: value, error: "", success: null });
  }
  async function filter(field, value) {
    if (!["historyCustomerId", "status", "ordering", "page"].includes(field)) return;
    if (field === "historyCustomerId" && value && !state.customers.some(c => same(c.customer_id, value))) return;
    if (field === "status" && !["", "recorded"].includes(value)) return;
    if (field === "ordering" && !["newest", "oldest"].includes(value)) return;
    if (field === "page" && (!Number.isInteger(value) || value < 1 || value > 1000000)) return;
    publish({ [field]: value, ...(field !== "page" ? { page: 1 } : {}) }); await loadHistory();
  }
  async function submit() {
    if (locked || state.success) return;
    const validation = reminderValidation(state);
    if (!approved() || state.contextLoading || state.customersLoading || state.detailsLoading || state.contextError || state.customersError || state.detailsError || state.storageError || validation) {
      publish({ error: state.storageError || validation || "Load an approved business and customer first." }); return;
    }
    locked = true; publish({ saving: true, error: "" });
    const businessId = state.businessId;
    const payload = { customer_id: Number(state.customerId), channel: state.channel, language: state.language, note: state.note.trim() || null };
    let key, dispatched = false;
    const wasUncertain = state.uncertain;
    try {
      const hash = await fingerprint([String(businessId), payload.customer_id, payload.channel, payload.language, payload.note]);
      if (!active) return;
      const previous = store.read();
      if (previous?.pending && previous.fingerprint !== hash) { publish({ uncertain: true, error: "An earlier reminder is unresolved. Re-enter its original business, customer, channel, language and note to retry the same request. History cannot match a request key." }); return; }
      key = previous?.fingerprint === hash ? previous.key : makeKey();
      store.write({ fingerprint: hash, key, pending: true });
      dispatched = true;
      const result = await api.record(businessId, { ...payload, idempotency_key: key });
      if (!validRecord(result, businessId) || !same(result.customer_id, payload.customer_id) || !same(result.credit_account_id, state.details?.credit_account?.credit_account_id) || result.channel !== payload.channel || result.language !== payload.language || result.note !== payload.note || typeof result.replayed !== "boolean") throw new Error("Unconfirmed response");
      // Exact same-key replay is the only safe reconciliation: history omits keys.
      store.clear(key);
      publish({ success: result, uncertain: false, page: 1 });
      await loadHistory();
    } catch (error) {
      const rejected = [400, 401, 403, 404, 409, 422].includes(error?.response?.status);
      if (dispatched && rejected && !wasUncertain) {
        try { const saved = store.read(); if (saved?.key === key) store.write({ ...saved, pending: false }); } catch { /* Preserve the saved key on storage failure. */ }
      }
      publish({ error: dispatched ? reminderError(error, true) : "Unable to prepare a securely saved request. Restore session storage and retry.", uncertain: wasUncertain || (dispatched && !rejected) });
    } finally { locked = false; publish({ saving: false }); }
  }
  async function refresh() {
    if (state.saving || state.contextLoading) return;
    if (state.contextError || !approved()) return loadBusinesses();
    const selected = state.customerId;
    const businessId = state.businessId;
    // Clear financial details immediately; a failed refresh cannot retain a stale balance.
    detailAbort?.abort(); ++detailVersion;
    publish({ details: null, detailsLoading: !!selected });
    await Promise.all([loadCustomers(), loadHistory()]);
    if (active && same(state.businessId, businessId) && same(state.customerId, selected) && selected) await selectCustomer(selected);
  }
  return { subscribe: fn => { listeners.add(fn); return () => listeners.delete(fn); }, getSnapshot: () => state,
    loadBusinesses, selectBusiness, selectCustomer, edit, filter, submit, loadHistory, refresh,
    newReminder: () => { if (state.saving || state.uncertain || state.storageError) return; clearIntent(); publish({ success: null, note: "", error: "" }); },
    dispose: () => { active = false; ++contextVersion; ++customerVersion; ++detailVersion; ++historyVersion; customerAbort?.abort(); detailAbort?.abort(); historyAbort?.abort(); } };
}
