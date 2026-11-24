// Purpose: Keep reminder data handling and workflow helpers separate from React rendering so callers use consistent rules.
import { repaymentFingerprint, secureRepaymentKey } from "./repayment.js";
export const reminderFingerprint = repaymentFingerprint;
// Generate a cryptographically random reminder key for retry-safe request identity.
export const secureReminderKey = () => secureRepaymentKey().replace("repayment:", "reminder:");
export const CHANNELS = [["internal", "Internal"], ["copy", "Copy"], ["whatsapp", "WhatsApp (intended only)"], ["sms", "SMS (intended only)"]];
export const LANGUAGES = [["en", "English"], ["ta", "Tamil"]];
// Check money valid before the surrounding workflow uses it.
export const moneyValid = value => typeof value === "string" && /^\d{1,23}\.\d{2}$/.test(value);
// Identify an outstanding positive balance before enabling the associated financial action.
export const positiveBalance = value => moneyValid(value) && BigInt(value.replace(".", "")) > 0n;
// Format the reminder amount consistently with the financial values shown elsewhere.
export function reminderMoney(value) {
  if (!moneyValid(value)) return "Unavailable";
  const [whole, fraction] = value.split(".");
  return "LKR " + whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + "." + fraction;
}
// Check reminder validation before the surrounding workflow uses it.
export function reminderValidation(state) {
  if (!state.customerId || !state.details) return "Select a customer and load their current balance.";
  if (!CHANNELS.some(([v]) => v === state.channel) || !LANGUAGES.some(([v]) => v === state.language)) return "Select a valid channel and language.";
  if ([...state.note].length > 1000 || [...state.note].some(char => char.codePointAt(0) < 32 && char !== "\n" && char !== "\t")) return "Use a note of at most 1000 characters without unsupported control characters.";
  if (state.uncertain) return ""; // An identical replay can confirm a record after its balance changes.
  if (!state.details.credit_account) return "This customer has no credit account.";
  if (!positiveBalance(state.details.outstanding_balance)) return "This customer has no outstanding balance.";
  if (state.details.credit_account.account_status !== "active") return "An active credit account is required.";
  if (state.channel !== "internal" && !state.details.customer.phone) return "No contact number is available. Choose Internal.";
  return "";
}
// Build a reminder draft from the selected customer and financial context.
export function draftReminder(details, business, language) {
  if (!details || !business || !moneyValid(details.outstanding_balance)) return "Select a customer to preview a reminder.";
  const name = details.customer.customer_name || "Customer";
  const shop = business.business_name || "your shop";
  const amount = reminderMoney(details.outstanding_balance);
  return language === "ta"
    ? name + ", " + shop + " கடையில் உங்கள் நிலுவைத் தொகை " + amount + ". தயவுசெய்து பணம் செலுத்த ஏற்பாடு செய்யுங்கள். அண்மையில் பணம் செலுத்தியிருந்தால், உறுதிப்படுத்த கடையைத் தொடர்புகொள்ளவும்."
    : "Hello " + name + ", your outstanding balance with " + shop + " is " + amount + ". Please arrange payment. If you have recently paid, please contact the shop to confirm.";
}
// Translate reminder outcomes into display text for the interface.
export function reminderError(error, mutation = false) {
  const status = error?.response?.status;
  if (status === 401) return "Login required. Please sign in again.";
  if (status === 403) return "Access forbidden. Check your role and business approval.";
  if (status === 404) return "Customer, credit account or reminder not found. Refresh the selected business.";
  if (status === 422) return "Invalid request. Check the customer, channel, language and note.";
  if (status === 409) {
    const detail = error.response?.data?.detail;
    const known = {
      "Reminder cooldown is active for this customer": "Reminder cooldown is active for this customer. The server does not provide a retry time. Wait before retrying; changing the request key will not bypass it.",
      "Customer has no outstanding balance": "This customer has no outstanding balance. Refresh their account.",
      "Credit account must be active to record a reminder": "An active credit account is required.",
      "Customer has no contact number; use an internal reminder": "No contact number is available. Choose Internal.",
      "Idempotency key is already used for a different reminder": "This key conflicts with another reminder. Review history and confirm the original operation before continuing.",
    };
    return known[detail] || "Reminder conflicts with an existing operation. Review history before retrying.";
  }
  return mutation
    ? (status >= 500 ? "Server error. " : "") + "Reminder status is uncertain. The server may have saved it. Review history, then retry the identical request to confirm safely."
    : status >= 500 ? "Server error. Unable to load reminder data. Please retry." : "Unable to load reminder data. Check your connection and retry.";
}

// Same opaque hash/key pattern as repayments. No customer data is persisted.
export function sessionReminderStore(userId) {
  const name = "lankapex_reminder_request_" + userId;
  // Read the saved or current resource state used by this workflow.
  const read = () => {
    const raw = sessionStorage.getItem(name);
    if (!raw) return null;
    const value = JSON.parse(raw);
    if (!/^[a-f0-9]{64}$/.test(value?.fingerprint) || !/^reminder:[A-Za-z0-9-]+$/.test(value?.key) || typeof value.pending !== "boolean") throw new Error("Invalid saved request");
    return value;
  };
  return { read, /* Persist the request metadata used by the workflow recovery path. */ write: value => sessionStorage.setItem(name, JSON.stringify(value)),
    // Remove saved state only within the scope checked by this storage adapter.
    clear: key => { if (!key || read()?.key === key) sessionStorage.removeItem(name); } };
}
