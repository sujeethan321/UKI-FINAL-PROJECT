import api from "./api";

export async function getSubscription(businessId, signal) {
  return (await api.get("/subscriptions/current", { params: { business_id: businessId }, signal })).data;
}

export async function getSubscriptionPlans(signal) {
  return (await api.get("/subscriptions/plans", { signal })).data;
}

export async function getSubscriptionHistory(businessId, signal) {
  return (await api.get("/subscriptions/history", { params: { business_id: businessId }, signal })).data;
}

export async function createCheckout(businessId, plan, interval, requestId) {
  return (await api.post('/subscriptions/checkout', { plan, billing_interval: interval, request_id: requestId },
    { params: { business_id: businessId } })).data;
}

export async function reconcileCheckout(businessId) {
  return (await api.post('/subscriptions/checkout/reconcile', null, { params: { business_id: businessId } })).data;
}

export async function createPortal(businessId) {
  return (await api.post('/subscriptions/portal', null, { params: { business_id: businessId } })).data;
}
