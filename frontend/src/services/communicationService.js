import api from "./api";
export async function getReminderCommunication(businessId, customerId, reminderId, options = {}) {
  return (await api.get("/shop-owner/payment-reminders/" + reminderId + "/communication", {
    params: { business_id: businessId, customer_id: customerId }, signal: options.signal,
  })).data;
}
export async function recordCustomerCommunicationConsent(businessId, customerId, payload, options = {}) {
  return (await api.post("/shop-owner/customers/" + customerId + "/communication/consent", payload, {
    params: { business_id: businessId }, signal: options.signal,
  })).data;
}
export async function requestWhatsAppHandoff(businessId, reminderId, payload, options = {}) {
  return (await api.post("/shop-owner/payment-reminders/" + reminderId + "/whatsapp-handoff", payload, {
    params: { business_id: businessId }, signal: options.signal,
  })).data;
}
