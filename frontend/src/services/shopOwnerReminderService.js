// Purpose: Wrap shop owner reminder API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from "./api";

// Call POST /shop-owner/payment-reminders through the shared client so authentication and API configuration are applied consistently.
export async function createShopOwnerReminder(businessId, payload) {
  return (await api.post("/shop-owner/payment-reminders", payload, { params: { business_id: businessId } })).data;
}

// Call GET /shop-owner/payment-reminders through the shared client so authentication and API configuration are applied consistently.
export async function getShopOwnerReminders(businessId, filters = {}, options = {}) {
  return (await api.get("/shop-owner/payment-reminders", {
    params: { ...filters, business_id: businessId }, signal: options.signal,
  })).data;
}
