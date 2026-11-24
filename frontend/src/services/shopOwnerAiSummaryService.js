// Purpose: Wrap shop owner ai summary API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from "./api";

const POSITIVE_ID = /^[1-9]\d*$/;

// Validate a record identifier before inserting it into an API path.
function pathId(value) {
  const normalized = String(value ?? "");
  if (!POSITIVE_ID.test(normalized) || !Number.isSafeInteger(Number(normalized))) {
    throw new TypeError("A valid account context is required");
  }
  return encodeURIComponent(normalized);
}

// Call the owner-scoped Tamil summary endpoint for the selected customer and credit account.
export async function generateTamilCreditSummary(businessId, customerId, creditAccountId, options = {}) {
  const path = `/shop-owner/businesses/${pathId(businessId)}/customers/${pathId(customerId)}` +
    `/credit-accounts/${pathId(creditAccountId)}/tamil-credit-summary`;
  const response = await api.request({ method: "post", url: path, signal: options.signal });
  return response.data;
}
