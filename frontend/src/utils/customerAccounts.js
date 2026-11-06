import { parseCustomerResponse, customerReadError } from "./customerDashboard.js";

export function parseAccountId(value) {
  return typeof value === "string" && /^[1-9]\d*$/.test(value) && Number.isSafeInteger(Number(value)) ? Number(value) : null;
}
export function parseCustomerPage(section, data, page, { businessId, accountId } = {}) {
  const field = { shops: "shops", accounts: "credit_accounts", transactions: "transactions" }[section];
  if (!field || data?.page !== page || data.page_size !== 10 || !Array.isArray(data[field]) || data[field].length > 10 || data.total < data[field].length) throw Error("Invalid page");
  // Reuse the existing row validators in batches while preserving server order.
  const parsed = [];
  for (let offset = 0; offset < Math.max(1, data[field].length); offset += 5) {
    const part = parseCustomerResponse(section, { ...data, page: 1, page_size: 5, [field]: data[field].slice(offset, offset + 5) });
    parsed.push(...part.items);
  }
  const identity = { shops: "business_id", accounts: "credit_account_id", transactions: "entry_id" }[section];
  if (new Set(parsed.map(row => row[identity])).size !== parsed.length ||
      (businessId !== undefined && parsed.some(row => row.business_id !== businessId)) ||
      (accountId !== undefined && parsed.some(row => row.credit_account_id !== accountId))) throw Error("Mismatched customer page");
  return { total: data.total, items: parsed };
}
export function parseAccountDetail(data, accountId) {
  const page = parseCustomerResponse("accounts", { currency: data?.currency, total: 1, page: 1, page_size: 5, credit_accounts: [data?.account] });
  if (page.items[0].credit_account_id !== accountId) throw Error("Mismatched account detail");
  return page.items[0];
}
export function customerAccountError(error) {
  if (error?.response?.status === 404 || error?.response?.status === 422) return "This record is not available to your account. Please return to My Shops.";
  return customerReadError(error);
}
export function createCustomerRead(api, parse, onDenied = () => {}) {
  let state = { data: null, loading: true, error: "", status: null }, active = true, version = 0, controller;
  const listeners = new Set();
  const publish = next => { state = next; if (active) listeners.forEach(fn => fn()); };
  return {
    getSnapshot: () => state,
    subscribe: fn => { listeners.add(fn); return () => listeners.delete(fn); },
    async load() {
      active = true; controller?.abort(); const current = ++version;
      controller = new AbortController(); const { signal } = controller;
      publish({ data: null, loading: true, error: "", status: null });
      try {
        const result = await api({ signal });
        if (!active || signal.aborted || current !== version) return;
        let data; try { data = parse(result); } catch { throw { code: "INVALID_CUSTOMER_RESPONSE" }; }
        publish({ data, loading: false, error: "", status: null });
      } catch (error) {
        if (active && !signal.aborted && current === version) {
          const message = customerAccountError(error);
          if ([401, 403].includes(error?.response?.status)) onDenied(message);
          publish({ data: null, loading: false, error: message, status: error?.response?.status || null });
        }
      }
    },
    dispose() { active = false; version++; controller?.abort(); state = { data: null, loading: false, error: "", status: null }; },
  };
}
