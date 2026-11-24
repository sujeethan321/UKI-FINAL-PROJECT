// Purpose: Wrap customer dashboard API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from "./api";

// Call GET /customer/dashboard/summary through the shared client so authentication and API configuration are applied consistently.
export async function getCustomerSummary({ signal } = {}) {
  return (await api.get("/customer/dashboard/summary", { signal })).data;
}
// Call GET /customer/shops through the shared client so authentication and API configuration are applied consistently.
export async function getCustomerShops({ signal } = {}) {
  return (await api.get("/customer/shops", { signal, params: { page: 1, page_size: 5 } })).data;
}
// Call GET /customer/credit-accounts through the shared client so authentication and API configuration are applied consistently.
export async function getCustomerCreditAccounts({ signal } = {}) {
  return (await api.get("/customer/credit-accounts", { signal, params: { page: 1, page_size: 5 } })).data;
}
// Call GET /customer/transactions through the shared client so authentication and API configuration are applied consistently.
export async function getCustomerTransactions({ signal } = {}) {
  return (await api.get("/customer/transactions", { signal, params: { page: 1, page_size: 5 } })).data;
}

// Full pages use the same scoped APIs with explicit bounded pagination.
export async function getMyCreditAccounts(page, { signal } = {}) {
  return (await api.get('/customer/credit-accounts', { signal, params: { page, page_size: 10 } })).data;
}
// Call GET /customer/shops through the shared client so authentication and API configuration are applied consistently.
export async function getMyShops(page, { signal } = {}) {
  return (await api.get("/customer/shops", { signal, params: { page, page_size: 10 } })).data;
}
// Call GET /customer/credit-accounts through the shared client so authentication and API configuration are applied consistently.
export async function getShopCreditAccounts(businessId, page, { signal } = {}) {
  return (await api.get("/customer/credit-accounts", { signal, params: { business_id: businessId, page, page_size: 10 } })).data;
}
// Get customer account detail within the customer dashboard workflow.
export async function getCustomerAccountDetail(accountId, { signal } = {}) {
  return (await api.get("/customer/credit-accounts/" + accountId, { signal })).data;
}
// Call GET /customer/transactions through the shared client so authentication and API configuration are applied consistently.
export async function getAccountTransactions(accountId, page, { signal } = {}) {
  return (await api.get("/customer/transactions", { signal, params: { credit_account_id: accountId, page, page_size: 10 } })).data;
}

// Call GET /customer/transactions through the shared client so authentication and API configuration are applied consistently.
export async function getTransactionHistory(filters, page, { signal } = {}) {
  return (await api.get("/customer/transactions", { signal, params: { ...filters, page, page_size: 10 } })).data;
}
// Get credit statement within the customer dashboard workflow.
export async function getCreditStatement(accountId, period, { signal } = {}) {
  return (await api.get("/customer/credit-accounts/" + accountId + "/statement", { signal, params: period })).data;
}
// Get credit statement pdf within the customer dashboard workflow.
export async function getCreditStatementPdf(accountId, period, { signal } = {}) {
  const response = await api.get("/customer/credit-accounts/" + accountId + "/statement.pdf", { signal, params: period, responseType: "blob" });
  const blob = response.data;
  if (!String(response.headers['content-type']).startsWith('application/pdf') || !(blob instanceof Blob) || await blob.slice(0, 5).text() !== '%PDF-') throw Error('Invalid PDF response');
  return blob;
}
