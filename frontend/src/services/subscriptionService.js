// Purpose: Wrap subscription API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from "./api";

// Call GET /subscriptions/current through the shared client so authentication and API configuration are applied consistently.
export async function getSubscription(businessId, signal) {
  return (await api.get("/subscriptions/current", { params: { business_id: businessId }, signal })).data;
}

// Call GET /subscriptions/plans through the shared client so authentication and API configuration are applied consistently.
export async function getSubscriptionPlans(signal) {
  return (await api.get("/subscriptions/plans", { signal })).data;
}

// Call GET /subscriptions/history through the shared client so authentication and API configuration are applied consistently.
export async function getSubscriptionHistory(businessId, signal) {
  return (await api.get("/subscriptions/history", { params: { business_id: businessId }, signal })).data;
}

// Call POST /subscriptions/checkout through the shared client so authentication and API configuration are applied consistently.
export async function createCheckout(businessId, plan, interval, requestId) {
  return (await api.post('/subscriptions/checkout', { plan, billing_interval: interval, request_id: requestId },
    { params: { business_id: businessId } })).data;
}

// Call POST /subscriptions/checkout/reconcile through the shared client so authentication and API configuration are applied consistently.
export async function reconcileCheckout(businessId) {
  return (await api.post('/subscriptions/checkout/reconcile', null, { params: { business_id: businessId } })).data;
}

// Call POST /subscriptions/portal through the shared client so authentication and API configuration are applied consistently.
export async function createPortal(businessId) {
  return (await api.post('/subscriptions/portal', null, { params: { business_id: businessId } })).data;
}
