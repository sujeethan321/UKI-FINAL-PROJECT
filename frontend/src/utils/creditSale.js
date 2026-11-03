import { customerErrorMessage } from "./customerError.js";

const MAX_MINOR = 99999999999999n;

export function minorUnits(value) {
  if (typeof value !== "string" || !/^\d+(?:\.\d{1,2})?$/.test(value.trim())) return null;
  const [whole, fraction = ""] = value.trim().split(".");
  if (whole.replace(/^0+/, "").length > 12) return null;
  const minor = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
  return minor <= MAX_MINOR ? minor : null;
}

export function decimalAmount(value) {
  const minor = minorUnits(value);
  return minor === null ? null : `${minor / 100n}.${String(minor % 100n).padStart(2, "0")}`;
}

export function formatCreditMoney(value) {
  const negative = typeof value === "string" && value.startsWith("-");
  const normalized = decimalAmount(negative ? value.slice(1) : value);
  if (normalized === null) return "?";
  const [whole, fraction] = normalized.split(".");
  return `LKR ${negative ? "-" : ""}${whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}.${fraction}`;
}

export function creditSaleError(error) {
  const status = error?.response?.status;
  if (status === 400) return "This sale could not be recorded. Check the selected customer and account.";
  if (status === 403) return "You cannot record credit sales for this business. Check your role and business approval.";
  if ([401, 404, 409, 422].includes(status)) return customerErrorMessage(error);
  return "The sale result is uncertain. Refresh the customer ledger to verify it before starting another sale. Retrying this same sale will reuse its request key.";
}

export function secureSaleKey() {
  if (globalThis.crypto?.randomUUID) return `credit-sale:${globalThis.crypto.randomUUID()}`;
  if (!globalThis.crypto?.getRandomValues) throw new Error("Secure request identifiers are unavailable.");
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
  return `credit-sale:${Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("")}`;
}

export async function saleFingerprint(operation) {
  if (!globalThis.crypto?.subtle) throw new Error("Secure request verification is unavailable.");
  const bytes = new TextEncoder().encode(JSON.stringify(operation));
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, "0")).join("");
}

// Store only an opaque operation hash and request key, never customer/ledger data.
// Scope by authenticated user; sessionStorage is isolated to this browser tab.
export function sessionSaleStore(userId) {
  const storageKey = `lankapex_credit_sale_request_${userId}`;
  const read = () => {
    const raw = sessionStorage.getItem(storageKey);
    if (!raw) return null;
    const record = JSON.parse(raw);
    if (!/^[a-f0-9]{64}$/.test(record?.fingerprint) ||
        !/^credit-sale:[A-Za-z0-9-]+$/.test(record?.key) || typeof record.pending !== "boolean") {
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
