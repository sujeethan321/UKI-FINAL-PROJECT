// Purpose: Wrap shop owner financial document API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from "./api";

// Call GET /shop-owner/repayments/{parameter}/receipt through the shared client so authentication and API configuration are applied consistently.
export async function getRepaymentReceipt(businessId, entryId, options = {}) {
  return (await api.get(`/shop-owner/repayments/${entryId}/receipt`, {
    params: { business_id: businessId }, signal: options.signal,
  })).data;
}

// Call GET /shop-owner/customers/{parameter}/statement through the shared client so authentication and API configuration are applied consistently.
export async function getCustomerStatement(businessId, customerId, period, options = {}) {
  return (await api.get(`/shop-owner/customers/${customerId}/statement`, {
    params: { business_id: businessId, ...period }, signal: options.signal,
  })).data;
}

// Call GET /shop-owner/outstanding-payments through the shared client so authentication and API configuration are applied consistently.
export async function getOutstandingPayments(businessId, filters, options = {}) {
  return (await api.get("/shop-owner/outstanding-payments", {
    params: { business_id: businessId, ...filters }, signal: options.signal,
  })).data;
}
