import api from "./api";

export async function getRepaymentReceipt(businessId, entryId, options = {}) {
  return (await api.get(`/shop-owner/repayments/${entryId}/receipt`, {
    params: { business_id: businessId }, signal: options.signal,
  })).data;
}

export async function getCustomerStatement(businessId, customerId, period, options = {}) {
  return (await api.get(`/shop-owner/customers/${customerId}/statement`, {
    params: { business_id: businessId, ...period }, signal: options.signal,
  })).data;
}

export async function getOutstandingPayments(businessId, filters, options = {}) {
  return (await api.get("/shop-owner/outstanding-payments", {
    params: { business_id: businessId, ...filters }, signal: options.signal,
  })).data;
}
