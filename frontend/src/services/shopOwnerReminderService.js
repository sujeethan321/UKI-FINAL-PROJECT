import api from "./api";

export async function createShopOwnerReminder(businessId, payload) {
  return (await api.post("/shop-owner/payment-reminders", payload, { params: { business_id: businessId } })).data;
}

export async function getShopOwnerReminders(businessId, filters = {}, options = {}) {
  return (await api.get("/shop-owner/payment-reminders", {
    params: { ...filters, business_id: businessId }, signal: options.signal,
  })).data;
}
