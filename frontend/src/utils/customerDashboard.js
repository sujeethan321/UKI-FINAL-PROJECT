// Purpose: Keep customer dashboard data handling and workflow helpers separate from React rendering so callers use consistent rules.
import { formatDocumentMoney } from "./financialDocuments.js";

export const formatCustomerMoney = formatDocumentMoney;
// Accept only supported identifiers before response data is used for lookups or navigation.
const id = value => Number.isSafeInteger(value) && value > 0;
// Validate count values before the interface uses them for totals or pagination.
const count = value => Number.isSafeInteger(value) && value >= 0;
// Validate text values at the response boundary before rendering them.
const text = value => typeof value === "string" && !!value.trim();
// Validate or format decimal monetary data at the interface boundary without changing the ledger.
const money = value => typeof value === "string" && /^\d+\.\d{2}$/.test(value);
// Accept the signed money representation needed for balances and reversals.
const signedMoney = value => typeof value === "string" && /^-?\d+\.\d{2}$/.test(value);
// Check the date representation before it enters the displayed dataset.
const date = value => typeof value === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(value) && !Number.isNaN(Date.parse(value));
// Detect duplicate values before the parsed response is accepted.
const unique = (items, key) => new Set(items.map(row => row[key])).size === items.length;
// Format recorded time for display so screens use a consistent representation.
export function formatRecordedTime(value) { return date(value) ? value.replace("T", " ").split(".")[0] : "Time unavailable"; }
// Validate and project the transaction row used by the customer history view.
function transaction(row) {
  return row && id(row.entry_id) && id(row.credit_account_id) && id(row.business_id) && text(row.business_name) &&
    ["credit_sale", "repayment", "reversal"].includes(row.entry_type) && date(row.recorded_at) && money(row.amount) &&
    signedMoney(row.balance_delta) && text(row.reference) && ["recorded", "reversed", "reversal"].includes(row.status) &&
    (row.entry_type === "reversal" ? row.status === "reversal" : row.status !== "reversal");
}
// Project only the named response fields so unrelated API fields do not enter view state.
const pick = (row, keys) => Object.fromEntries(keys.map(key => [key, row[key]]));
const transactionFields = ["entry_id", "credit_account_id", "business_id", "business_name", "entry_type", "recorded_at", "amount", "balance_delta", "reference", "status"];
// Check customer response before the surrounding workflow uses it.
export function parseCustomerResponse(section, data) {
  if (data?.currency !== "LKR") throw Error("Unconfirmed customer response");
  if (section === "summary") {
    if (!count(data.linked_shop_count) || !count(data.credit_account_count) || !money(data.total_outstanding_balance) ||
        !Array.isArray(data.recent_activity) || data.recent_activity.length > 5 || !data.recent_activity.every(transaction) || !unique(data.recent_activity, "entry_id")) throw Error("Invalid summary");
    const dueStatus=data.due_totals_status ?? 'unavailable';
    if(!['complete','incomplete','unavailable'].includes(dueStatus))throw Error('Invalid due totals status');
    if(dueStatus==='complete'&&(!money(data.due_soon_amount)||!money(data.overdue_amount)||data.due_date_policy!=='fifo_database_wall_clock_today_through_7_days'))throw Error('Unconfirmed due totals');
    return { ...pick(data, ["linked_shop_count", "credit_account_count", "total_outstanding_balance"]),
      due_totals_status:dueStatus,due_soon_amount:dueStatus==='complete'?data.due_soon_amount:null,
      overdue_amount:dueStatus==='complete'?data.overdue_amount:null,
      recent_activity: data.recent_activity.map(row => pick(row, transactionFields)) };
  }
  const key = { shops: "shops", accounts: "credit_accounts", transactions: "transactions" }[section];
  if (!key || data.page !== 1 || data.page_size !== 5 || !count(data.total) || !Array.isArray(data[key]) || data[key].length > 5 || data[key].length > data.total) throw Error("Invalid preview");
  let fields, valid, identity;
  if (section === "shops") {
    fields = ["business_id", "business_name", "credit_account_count", "outstanding_balance"]; identity = "business_id";
    valid = row => row && id(row.business_id) && text(row.business_name) && count(row.credit_account_count) && money(row.outstanding_balance);
  } else if (section === "accounts") {
    fields = ["credit_account_id", "business_id", "business_name", "account_status", "credit_limit", "outstanding_balance", "advance_balance", "available_credit", "opened_at"]; identity = "credit_account_id";
    valid = row => row && id(row.credit_account_id) && id(row.business_id) && text(row.business_name) && text(row.account_status) &&
      ["credit_limit", "outstanding_balance", "advance_balance", "available_credit"].every(key => money(row[key])) && date(row.opened_at);
  } else { fields = transactionFields; valid = transaction; identity = "entry_id"; }
  if (!data[key].every(valid) || !unique(data[key], identity)) throw Error("Invalid preview rows");
  return { total: data.total, items: data[key].map(row => pick(row, fields)) };
}

// Translate customer read outcomes into display text for the interface.
export function customerReadError(error) {
  const status = error?.response?.status;
  if (error?.code === "INVALID_CUSTOMER_RESPONSE") return "This response could not be verified. Please retry.";
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 403) return "You do not have permission to view customer records. Log out and sign in with your customer account.";
  if (status === 409) return "These records need review before they can be displayed. Please contact your shop.";
  if (error?.code === "ECONNABORTED") return "This request is taking too long. Please retry.";
  return status >= 500 ? "The customer service is unavailable. Please retry." : "Unable to load this section. Check your connection and retry.";
}
const sections = ["summary", "shops", "accounts", "transactions"];
// Create independent initial resource state so new readers do not inherit another instance state.
const fresh = loading => ({ authError: "", ...Object.fromEntries(sections.map(key => [key, { data: null, loading, error: "" }])) });
// Create customer dashboard reader for the customer dashboard workflow.
export function createCustomerDashboardReader(api) {
  let state = fresh(true), active = false, generation = 0;
  const listeners = new Set(), controllers = {}, versions = {};
  // Replace the store snapshot and notify subscribers so React can render the new state.
  const publish = next => { state = next; if (active) listeners.forEach(listener => listener()); };
  // Cancel outstanding reads before the reader is reset or disposed.
  const abortAll = () => Object.values(controllers).forEach(controller => controller.abort());
  // Load the current resource data and update the state consumed by the interface.
  async function load(section) {
    if (!active || state.authError || !sections.includes(section)) return;
    controllers[section]?.abort();
    const controller = new AbortController(); controllers[section] = controller;
    const version = versions[section] = (versions[section] || 0) + 1, current = generation;
    // Check valid before the surrounding workflow uses it.
    const valid = () => active && !controller.signal.aborted && current === generation && version === versions[section];
    publish({ ...state, [section]: { data: null, loading: true, error: "" } });
    try {
      const response = await api[section]({ signal: controller.signal });
      if (!valid()) return;
      let data;
      try { data = parseCustomerResponse(section, response); }
      catch { throw Object.assign(new Error("Invalid customer response"), { code: "INVALID_CUSTOMER_RESPONSE" }); }
      publish({ ...state, [section]: { data, loading: false, error: "" } });
    } catch (error) {
      if (!valid()) return;
      if ([401, 403].includes(error?.response?.status)) {
        generation++; abortAll(); publish({ ...fresh(false), authError: customerReadError(error) });
      } else publish({ ...state, [section]: { data: null, loading: false, error: customerReadError(error) } });
    }
  }
  return {
    // Expose the current store snapshot to subscribers without starting a request.
    getSnapshot: () => state,
    // Register a state listener and return cleanup so consumers can unsubscribe.
    subscribe: listener => { listeners.add(listener); return () => listeners.delete(listener); },
    load,
    // Start the resource workflow using its current context and selection.
    start() { active = true; generation++; abortAll(); publish(fresh(true)); return Promise.allSettled(sections.map(load)); },
    // Release pending work and subscriptions when this resource reader is no longer used.
    dispose() { active = false; generation++; abortAll(); state = fresh(false); },
  };
}
