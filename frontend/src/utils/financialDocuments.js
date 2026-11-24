// Purpose: Keep financial documents data handling and workflow helpers separate from React rendering so callers use consistent rules.
// Aggregated document balances can exceed an individual Numeric(14,2) entry.
export function formatDocumentMoney(value) {
  if (typeof value !== "string" || !/^-?\d+\.\d{2}$/.test(value)) return "Not available";
  const [whole, fraction] = value.split(".");
  return `LKR ${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${fraction}`;
}

// Compare normalized record identifiers so a response is matched to the requested record.
const sameId = (left, right) => String(left) === String(right);
// Require a positive identifier before associating data with an application record.
const positiveId = value => Number.isSafeInteger(value) && value > 0;
// Validate or format decimal monetary data at the interface boundary without changing the ledger.
const money = value => typeof value === "string" && /^\d+\.\d{2}$/.test(value);
// Accept the signed money representation needed for balances and reversals.
const signedMoney = value => typeof value === "string" && money(value.startsWith("-") ? value.slice(1) : value);

// Check receipt before the surrounding workflow uses it.
export function validateReceipt(data, [businessId, entryId]) {
  return data?.currency === "LKR" && sameId(data.business?.business_id, businessId) && sameId(data.entry_id, entryId) &&
    positiveId(data.customer?.customer_id) && sameId(data.customer.business_id, businessId) && positiveId(data.credit_account_id) &&
    data.receipt_identifier === `ledger-repayment:${entryId}` && typeof data.reference === "string" && !!data.reference.trim() &&
    ["recorded", "reversed"].includes(data.status) && money(data.amount) && !!data.recorded_at &&
    !Number.isNaN(Date.parse(data.recorded_at)) && (data.status !== "reversed" || (positiveId(data.reversal_entry_id) && !!data.reversed_at));
}

// Check statement before the surrounding workflow uses it.
export function validateStatement(data, [businessId, customerId, period]) {
  return data?.currency === "LKR" && sameId(data.business?.business_id, businessId) && sameId(data.customer?.business_id, businessId) &&
    sameId(data.customer.customer_id, customerId) && data.start_date === period.start_date && data.end_date === period.end_date &&
    ["opening_balance", "closing_balance", "reversal_impact"].every(key => signedMoney(data[key])) &&
    ["total_credit_sales", "total_repayments", "outstanding_balance", "advance_balance"].every(key => money(data[key])) &&
    Array.isArray(data.transactions) && data.transactions.every(row => positiveId(row.entry_id) &&
      ["credit_sale", "repayment", "reversal"].includes(row.entry_type) && money(row.debit) && money(row.credit) && signedMoney(row.running_balance));
}

// Check outstanding before the surrounding workflow uses it.
export function validateOutstanding(data, [businessId, filters]) {
  return data?.currency === "LKR" && sameId(data.business_id, businessId) && money(data.total_outstanding) &&
    Number.isSafeInteger(data.customers_with_outstanding) && data.customers_with_outstanding >= 0 &&
    Number.isSafeInteger(data.filtered_customers) && data.filtered_customers >= 0 &&
    data.page === filters.page && data.page_size === filters.page_size && data.overdue_amount === null &&
    Array.isArray(data.customers) && data.customers.every(row => positiveId(row.customer_id) && money(row.outstanding_balance) &&
      (row.credit_limit === null || money(row.credit_limit)) && (row.available_credit === null || money(row.available_credit)));
}

// Translate financial read outcomes into display text for the interface.
export function financialReadError(error) {
  const status = error?.response?.status;
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 403) return "You cannot access financial records for this business. Check your role and business approval.";
  if (status === 404) return "This financial record was not found in the selected business.";
  if (status === 409) return "This ledger history cannot be reconstructed. Ask your administrator to review the recorded reversals.";
  if (status === 422) return "Check the selected date range and search filters.";
  return "Unable to load financial records. Please retry.";
}

// GETs only. Never synthesize a document or issue a financial write.
export function createFinancialReader(api, validate) {
  let state = { data: null, loading: false, error: "" };
  let active = true, version = 0, controller;
  const listeners = new Set();
  // Replace the store snapshot and notify subscribers so React can render the new state.
  const publish = patch => { if (active) { state = { ...state, ...patch }; listeners.forEach(fn => fn()); } };
  // Remove the saved workflow value so it cannot be reused after reset.
  const clear = () => { controller?.abort(); ++version; publish({ data: null, loading: false, error: "" }); };
  return {
    // Expose the current store snapshot to subscribers without starting a request.
    getSnapshot: () => state,
    // Register a state listener and return cleanup so consumers can unsubscribe.
    subscribe: fn => { listeners.add(fn); return () => listeners.delete(fn); },
    clear,
    // Release pending work and subscriptions when this resource reader is no longer used.
    dispose: () => { clear(); active = false; },
    // Load the requested resource section and publish its loading or result state.
    async load(...args) {
      active = true; controller?.abort(); const current = ++version;
      controller = new AbortController(); const { signal } = controller;
      publish({ data: null, loading: true, error: "" });
      try {
        const data = await api(...args, { signal });
        if (!active || signal.aborted || current !== version) return null;
        if (!validate(data, args)) throw Error("Unconfirmed document response");
        publish({ data }); return data;
      } catch (error) {
        if (active && !signal.aborted && current === version) publish({ error: financialReadError(error) });
        return null;
      } finally { if (current === version && !signal.aborted) publish({ loading: false }); }
    },
  };
}
