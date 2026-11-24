// Purpose: Wrap communication API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from "./api";
// Get reminder communication within the communication workflow.
export async function getReminderCommunication(businessId, customerId, reminderId, options = {}) {
  return (await api.get("/shop-owner/payment-reminders/" + reminderId + "/communication", {
    params: { business_id: businessId, customer_id: customerId }, signal: options.signal,
  })).data;
}
// Record customer communication consent within the communication workflow.
export async function recordCustomerCommunicationConsent(businessId, customerId, payload, options = {}) {
  return (await api.post("/shop-owner/customers/" + customerId + "/communication/consent", payload, {
    params: { business_id: businessId }, signal: options.signal,
  })).data;
}
// Request the consent-checked WhatsApp handoff through the communication API.
export async function requestWhatsAppHandoff(businessId, reminderId, payload, options = {}) {
  return (await api.post("/shop-owner/payment-reminders/" + reminderId + "/whatsapp-handoff", payload, {
    params: { business_id: businessId }, signal: options.signal,
  })).data;
}
