import { decimalAmount, minorUnits } from "./creditSale.js";
export { decimalAmount, minorUnits, formatCreditMoney } from "./creditSale.js";
export const PAYMENT_METHODS = [["cash", "Cash"], ["bank_transfer", "Bank transfer"], ["card", "Card"]];

export function repaymentValidation(state) {
  const amount = decimalAmount(state.amount);
  if (!amount || minorUnits(amount) === 0n) return "Enter a positive amount with at most two decimal places.";
  if (!PAYMENT_METHODS.some(([value]) => value === state.payment_method)) return "Select cash, bank transfer, or card.";
  const reference = state.receipt_number || "";
  if (reference.length > 60 || /^(CS-|RP-)/i.test(reference.trim()) || /[\p{C}\p{Zl}\p{Zp}]/u.test(reference.trim())) return "Use a printable reference of at most 60 characters without a CS- or RP- prefix.";
  if (state.notes.length > 2000) return "Notes must contain at most 2000 characters.";
  if (!state.uncertain && state.details?.credit_account) {
    if (!["active", "suspended"].includes(state.details.credit_account.account_status)) return "This account cannot receive new repayments.";
    const debt = minorUnits(state.details.outstanding_balance);
    if (debt === null || minorUnits(amount) > debt) return "Repayment amount exceeds outstanding balance.";
  }
  return "";
}

export function repaymentError(error) {
  const status = error?.response?.status;
  if (status === 401) return "Your session has expired. Please sign in again.";
  if (status === 403) return "You cannot record repayments for this business. Check your role and business approval.";
  if (status === 404) return "The customer or credit account was not found. Refresh customer data.";
  if (status === 422) return "Check the amount, payment method, reference and notes before retrying.";
  if (status === 409) {
    const detail = error?.response?.data?.detail;
    if (detail === "Repayment amount exceeds current outstanding balance") return "Repayment amount exceeds current outstanding balance. Refresh the ledger.";
    if (detail === "Closed or unsupported credit accounts cannot receive repayments") return "This account cannot receive new repayments.";
    if (detail === "Idempotency key is already used for a different operation") return "This request conflicts with an earlier transaction. Verify the ledger before starting another payment.";
    return "The payment conflicts with an existing transaction or reference. Verify the ledger and reference before retrying.";
  }
  if (status === 400) return "Check the selected customer and credit account before retrying.";
  return "The payment result is uncertain. Verify the customer ledger before starting another payment, or retry the identical payment to confirm its result.";
}

export function secureRepaymentKey() {
  if (globalThis.crypto?.randomUUID) return `repayment:${globalThis.crypto.randomUUID()}`;
  if (!globalThis.crypto?.getRandomValues) throw new Error("Secure request identifiers are unavailable.");
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
  return `repayment:${Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("")}`;
}

export async function repaymentFingerprint(operation) {
  if (!globalThis.crypto?.subtle) throw new Error("Secure request verification is unavailable.");
  const bytes = new TextEncoder().encode(JSON.stringify(operation));
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
}

// Store only an opaque operation hash and request key, never customer/ledger data.
// Scope by authenticated user; sessionStorage is isolated to this browser tab.
export function sessionRepaymentStore(userId) {
  const storageKey = `lankapex_repayment_request_${userId}`;
  const read = () => {
    const raw = sessionStorage.getItem(storageKey);
    if (!raw) return null;
    const record = JSON.parse(raw);
    if (!/^[a-f0-9]{64}$/.test(record?.fingerprint) ||
        !/^repayment:[A-Za-z0-9-]+$/.test(record?.key) || typeof record.pending !== "boolean") {
      throw new Error("Invalid saved request state");
    }
    return record;
  };
  return {
    read,
    write: record => sessionStorage.setItem(storageKey, JSON.stringify(record)),
    clear: key => { if (!key || read()?.key === key) sessionStorage.removeItem(storageKey); },
    reject: key => { const record = read(); if (record?.key === key) sessionStorage.setItem(storageKey, JSON.stringify({ ...record, pending: false })); },
  };
}
