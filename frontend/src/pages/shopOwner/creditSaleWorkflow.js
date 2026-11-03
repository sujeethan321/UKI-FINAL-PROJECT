import { creditSaleError, decimalAmount, minorUnits, saleFingerprint, secureSaleKey } from "../../utils/creditSale.js";

const validId = value => Number.isSafeInteger(value) && value > 0;
const sameId = (left, right) => String(left) === String(right);
const cancelled = error => error?.code === "ERR_CANCELED" || error?.name === "AbortError";

// This store drives the React view and is tested with controlled API promises.
// Read generations prevent old business/customer responses from entering state.
export function createCreditSaleWorkflow({ api, store, makeKey = secureSaleKey, fingerprint = saleFingerprint, initialBusinessId = "" }) {
  let recovery = null;
  let storageError = "";
  try { recovery = store.read(); } catch { storageError = "Browser session storage is unavailable or invalid. Verify any previous sale before resetting the form."; }
  let state = {
    businesses: [], businessId: "", customers: [], customerId: "", details: null,
    contextLoading: true, customersLoading: false, detailsLoading: false, saving: false,
    contextError: "", customersError: "", detailsError: "", error: storageError,
    amount: "", notes: "", success: null, uncertain: !!recovery?.pending, storageError,
  };
  let active = true;
  let contextVersion = 0;
  let readVersion = 0;
  let detailVersion = 0;
  let customerAbort, detailAbort;
  let submitLock = false;
  const listeners = new Set();
  const publish = patch => {
    if (!active) return;
    state = { ...state, ...patch };
    listeners.forEach(listener => listener());
  };
  const approved = () => state.businesses.some(b => sameId(b.business_id, state.businessId) && b.approval_status === "approved");
  const clearIntent = () => {
    if (state.uncertain) return;
    try { store.clear(); } catch { publish({ storageError: "Browser session storage is unavailable. Enable it before recording a sale." }); }
  };

  async function selectCustomer(customerId, { refresh = false } = {}) {
    if (state.saving && !refresh) return;
    const customer = state.customers.find(c => sameId(c.customer_id, customerId));
    detailAbort?.abort();
    const version = ++detailVersion;
    const businessId = state.businessId;
    if (!refresh) {
      if (!sameId(state.customerId, customerId)) clearIntent();
      publish({ customerId: customer ? String(customer.customer_id) : "", details: null,
        amount: "", notes: "", error: "", success: null });
    }
    if (!customer || !approved()) { publish({ details: null, detailsLoading: false }); return; }
    detailAbort = new AbortController();
    const signal = detailAbort.signal;
    publish({ detailsLoading: true, detailsError: "" });
    try {
      const data = await api.details(businessId, customer.customer_id, { signal });
      if (!active || signal.aborted || version !== detailVersion) return;
      if (!sameId(data?.business_id, businessId) || !sameId(data?.customer?.customer_id, customer.customer_id) ||
          !sameId(data?.customer?.business_id, businessId) || !Array.isArray(data?.transactions) ||
          minorUnits(data?.outstanding_balance) === null || minorUnits(data?.advance_balance) === null ||
          (data.credit_account && (!validId(data.credit_account.credit_account_id) ||
            minorUnits(data.credit_account.credit_limit) === null || minorUnits(data.available_credit) === null))) {
        throw new Error("Invalid scoped customer details");
      }
      publish({ details: data });
    } catch (error) {
      if (active && !signal.aborted && version === detailVersion && !cancelled(error)) {
        publish({ detailsError: "Unable to load customer credit data. Refresh and try again." });
      }
    } finally {
      if (!signal.aborted && version === detailVersion) publish({ detailsLoading: false });
    }
  }

  async function loadCustomers({ refresh = false } = {}) {
    customerAbort?.abort();
    const version = ++readVersion;
    const businessId = state.businessId;
    if (!approved()) { publish({ customers: [], customersLoading: false }); return; }
    customerAbort = new AbortController();
    const signal = customerAbort.signal;
    publish({ customersLoading: true, customersError: "" });
    try {
      const data = await api.customers(businessId, { signal });
      if (!active || signal.aborted || version !== readVersion) return;
      if (!sameId(data?.business_id, businessId) || !Array.isArray(data?.customers) ||
          data.customers.some(c => !validId(c.customer_id))) throw new Error("Invalid customer list");
      publish({ customers: data.customers });
      if (refresh && state.customerId) {
        if (data.customers.some(c => sameId(c.customer_id, state.customerId))) {
          await selectCustomer(state.customerId, { refresh: true });
        } else {
          publish({ customerId: "", details: null, detailsError: "The selected customer is no longer available." });
        }
      }
    } catch (error) {
      if (active && !signal.aborted && version === readVersion && !cancelled(error)) {
        publish({ customersError: "Unable to load this business's customers. Refresh and try again." });
      }
    } finally {
      if (!signal.aborted && version === readVersion) publish({ customersLoading: false });
    }
  }

  async function selectBusiness(businessId) {
    if (state.saving) return;
    const business = state.businesses.find(b => sameId(b.business_id, businessId));
    if (!business) return;
    clearIntent();
    customerAbort?.abort(); detailAbort?.abort();
    ++readVersion; ++detailVersion;
    publish({ businessId: String(business.business_id), customers: [], customerId: "", details: null,
      amount: "", notes: "", success: null, error: "", customersError: "", detailsError: "", detailsLoading: false });
    await loadCustomers();
  }

  async function loadBusinesses() {
    active = true;
    const version = ++contextVersion;
    publish({ contextLoading: true, contextError: "" });
    try {
      const data = await api.businesses();
      if (!active || version !== contextVersion) return;
      if (!Array.isArray(data?.businesses) || data.businesses.some(b => !validId(b.business_id))) throw new Error("Invalid business context");
      publish({ businesses: data.businesses });
      // Choose an approved business from trusted context; never URL parameters.
      const next = data.businesses.find(b => sameId(b.business_id, state.businessId)) ||
        data.businesses.find(b => sameId(b.business_id, initialBusinessId) && b.approval_status === "approved") ||
        data.businesses.find(b => b.approval_status === "approved") || data.businesses[0];
      if (next) await selectBusiness(next.business_id);
    } catch {
      if (active && version === contextVersion) publish({ contextError: "Unable to load your businesses. Please retry.", businesses: [], businessId: "", details: null, customers: [] });
    } finally {
      if (version === contextVersion) publish({ contextLoading: false });
    }
  }

  function edit(field, value) {
    if (state.saving || !["amount", "notes"].includes(field)) return;
    if (value !== state[field]) clearIntent();
    publish({ [field]: value, error: "", success: null });
  }

  function newSale() {
    if (state.saving) return;
    try { store.clear(); } catch { publish({ error: "Unable to reset saved request state. Browser session storage must be enabled." }); return; }
    publish({ amount: "", notes: "", error: "", success: null, uncertain: false, storageError: "" });
  }

  async function refresh() {
    if (state.saving) return;
    if (!approved()) { await loadBusinesses(); return; }
    await loadCustomers({ refresh: true });
  }

  async function submit() {
    if (submitLock) return;
    if (!approved() || state.contextLoading || state.customersLoading || state.detailsLoading ||
        state.contextError || state.customersError || state.detailsError || !state.details?.credit_account ||
        !state.customers.some(c => sameId(c.customer_id, state.customerId))) {
      publish({ error: "Select an approved business and load a customer with a credit account first." }); return;
    }
    const amount = decimalAmount(state.amount);
    if (!amount || minorUnits(amount) === 0n) { publish({ error: "Enter a positive amount with at most two decimal places." }); return; }
    if (state.notes.length > 2000) { publish({ error: "Notes must contain at most 2000 characters." }); return; }
    if (state.storageError) { publish({ error: state.storageError }); return; }
    submitLock = true;
    publish({ saving: true, error: "", success: null });
    const businessId = state.businessId;
    const customerId = state.details.customer.customer_id;
    const accountId = state.details.credit_account.credit_account_id;
    const notes = state.notes.trim() || null;
    let key;
    let dispatched = false;
    try {
      const hash = await fingerprint([String(businessId), String(customerId), amount, notes]);
      if (!active) return;
      const previous = store.read();
      if (previous?.pending && previous.fingerprint !== hash) {
        publish({ uncertain: true, error: "A previous sale is unresolved. Re-enter that sale exactly to retry it, or check the ledger before choosing Start New Sale." }); return;
      }
      const replay = previous?.pending && previous.fingerprint === hash;
      if (!replay && state.details.credit_account.account_status !== "active") {
        publish({ error: "Credit account must be active to record a sale." }); return;
      }
      if (!replay && minorUnits(amount) > minorUnits(state.details.available_credit)) {
        publish({ error: "Sale amount exceeds available credit." }); return;
      }
      key = previous?.fingerprint === hash ? previous.key : makeKey();
      store.write({ fingerprint: hash, key, pending: true });
      dispatched = true;
      const result = await api.record(businessId, { customer_id: customerId, amount, notes, idempotency_key: key });
      if (!validId(result?.entry_id) || !sameId(result.business_id, businessId) || !sameId(result.customer_id, customerId) ||
          !sameId(result.credit_account_id, accountId) || decimalAmount(result.amount) !== amount || result.notes !== notes ||
          result.currency !== "LKR" || typeof result.replayed !== "boolean" ||
          typeof result.reference !== "string" || !result.reference.trim() ||
          minorUnits(result.outstanding_balance) === null || minorUnits(result.advance_balance) === null ||
          minorUnits(result.available_credit) === null || !result.recorded_at || Number.isNaN(Date.parse(result.recorded_at))) {
        throw new Error("Unconfirmed sale response");
      }
      // Clear only this operation: a late response must not erase another key.
      store.clear(key);
      publish({ success: result, amount: "", notes: "", uncertain: false,
        details: { ...state.details, outstanding_balance: result.outstanding_balance,
          advance_balance: result.advance_balance, available_credit: result.available_credit } });
      if (active) await loadCustomers({ refresh: true });
    } catch (error) {
      const status = error?.response?.status;
      const rejected = [400, 401, 403, 404, 409, 422].includes(status);
      if (dispatched && rejected && !state.uncertain) {
        try { store.reject(key); } catch { /* Keep the in-memory/persisted key for a safe retry. */ }
      }
      publish({ error: dispatched ? creditSaleError(error) : "Unable to prepare a secure saved request. Enable browser session storage and try again.",
        uncertain: dispatched && !rejected ? true : state.uncertain });
    } finally {
      submitLock = false;
      publish({ saving: false });
    }
  }

  return {
    subscribe: listener => { listeners.add(listener); return () => listeners.delete(listener); },
    getSnapshot: () => state,
    loadBusinesses, selectBusiness, selectCustomer, edit, submit, refresh, newSale,
    dispose: () => { active = false; ++contextVersion; ++readVersion; ++detailVersion; customerAbort?.abort(); detailAbort?.abort(); },
  };
}
