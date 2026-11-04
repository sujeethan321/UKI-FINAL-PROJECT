import { repaymentFingerprint, secureRepaymentKey } from "./repayment.js";
export const communicationFingerprint = repaymentFingerprint;
export const communicationKey = () => secureRepaymentKey().replace("repayment:", "communication:");
export function normalizeWhatsAppPhone(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  const clean = value.trim().replace(/[ ()-]/g, "");
  if (/^07[0-9]{8}$/.test(clean)) return "94" + clean.slice(1);
  return /^\+?947[0-9]{8}$/.test(clean) ? clean.replace(/^\+/, "") : null;
}
export function whatsappUrl(phone, message) {
  if (!/^947[0-9]{8}$/.test(phone) || typeof message !== "string" || !message.trim()) throw new Error("Invalid WhatsApp handoff");
  return "https://wa.me/" + phone + "?text=" + encodeURIComponent(message);
}
export function safeHandoffUrl(result, preview) {
  if (result?.channel !== "whatsapp" || result?.normalized_phone !== preview?.normalized_phone || result?.message !== preview?.message || result?.status !== "handoff_requested" || result?.provider_delivery_available !== false) throw new Error("Unconfirmed handoff");
  const expected = whatsappUrl(result.normalized_phone, result.message);
  const actual = new URL(result.handoff_url);
  const wanted = new URL(expected);
  if (actual.origin !== "https://wa.me" || actual.pathname !== wanted.pathname || actual.hash || actual.username || actual.password || [...actual.searchParams.keys()].join() !== "text" || actual.searchParams.get("text") !== result.message) throw new Error("Unsafe handoff URL");
  return expected;
}
export function communicationError(error) {
  const status = error?.response?.status;
  if (status === 401) return "Login required. Please sign in again.";
  if (status === 403) return "Communication access is forbidden. Check business approval and ownership.";
  if (status === 404) return "Saved reminder or customer not found in this business.";
  if (status === 409) return "Handoff or preference update is restricted. Refresh eligibility; check permission, phone and outstanding balance.";
  if (status === 422) return "Check the stated preference, evidence and confirmation before retrying.";
  return "The communication result could not be confirmed. Retry the identical operation safely; no message delivery is confirmed.";
}
export function sessionCommunicationStore(userId) {
  const name = "lankapex_communication_" + userId;
  return {
    read: () => {
      const raw = sessionStorage.getItem(name);
      if (!raw) return null;
      const row = JSON.parse(raw);
      if (!/^[a-f0-9]{64}$/.test(row?.fingerprint) || !/^communication:[A-Za-z0-9-]+$/.test(row?.key) || typeof row.pending !== "boolean") throw new Error("Invalid operation storage");
      return row;
    },
    write: row => sessionStorage.setItem(name, JSON.stringify(row)),
  };
}
