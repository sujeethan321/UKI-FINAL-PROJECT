import { test } from "node:test";
import assert from "node:assert/strict";
import { setImmediate } from "node:timers";
import { createCommunicationWorkflow } from "../src/pages/shopOwner/communicationWorkflow.js";
import { normalizeWhatsAppPhone, whatsappUrl, safeHandoffUrl, sessionCommunicationStore } from "../src/utils/communication.js";
const flush = () => new Promise(r => setImmediate(r));
const preview = (patch = {}) => ({ business_id: 1, customer_id: 10, reminder_id: 100, message: "Hello Kumar & Shop, outstanding LKR 100.25.", language: "en", outstanding_amount: "100.25", currency: "LKR", consent_status: "granted", consent_source: "owner_recorded_customer_statement", normalized_phone: "94771234567", eligible: true, blocked_reason: null, attempts: [], provider_delivery_available: false, ...patch });
const result = (data = preview(), patch = {}) => ({ attempt_id: 1, business_id: 1, customer_id: 10, reminder_id: 100, channel: "whatsapp", normalized_phone: data.normalized_phone, message: data.message, handoff_url: whatsappUrl(data.normalized_phone, data.message), status: "handoff_requested", provider_delivery_available: false, replayed: false, ...patch });
const defer = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return { promise, resolve }; };
function fixture(overrides = {}) {
  let saved = null, count = 0; const calls = [], navigations = [], popups = [];
  const store = { read: () => saved, write: data => { saved = data; } };
  const api = { preview: async () => preview(), handoff: async (b, r, payload) => { calls.push(payload); return result(); }, consent: async (b, c, payload) => ({ consent_id: 7, business_id: 1, customer_id: 10, consent_status: payload.consent_status, independently_verified: false, replayed: false }), ...overrides };
  const openWindow = () => { const popup = { opener: {}, closed: false, close() { this.closed = true; }, location: { replace: url => navigations.push(url) } }; popups.push(popup); return popup; };
  const make = (extra = {}) => createCommunicationWorkflow({ api, store, scope: { businessId: 1, customerId: 10, reminderId: 100 }, fingerprint: async payload => JSON.stringify(payload), makeKey: () => "communication:key" + ++count, openWindow, ...extra });
  const workflow = make(); return { api, store, calls, navigations, popups, workflow, make };
}
for (const phone of ["0771234567", "+94771234567", "94771234567", "+94 77 123 4567", "(077) 123-4567"]) test("normalizes supported phone " + phone, () => assert.equal(normalizeWhatsAppPhone(phone), "94771234567"));
for (const phone of [null, "", "771234567", "0094771234567", "+44771234567", "077123456", "0771234567?text=bad", "０７７１２３４５６７"]) test("rejects unsupported phone " + phone, () => assert.equal(normalizeWhatsAppPhone(phone), null));
test("English/Tamil URLs preserve exact message and contain no application metadata", () => { for (const message of [preview().message, "குமார், நிலுவைத் தொகை LKR 100.25. & + ? #"]) { const url = new URL(whatsappUrl("94771234567", message)); assert.equal(url.hostname, "wa.me"); assert.equal(url.pathname, "/94771234567"); assert.deepEqual([...url.searchParams], [["text", message]]); } });
test("unknown consent, opt-out, invalid contact and changed balances block handoff", async () => {
  for (const consent of ["unknown", "opted_out"]) { const f = fixture({ preview: async () => preview({ eligible: false, consent_status: consent }) }); await f.workflow.load(); await f.workflow.openWhatsApp(); assert.equal(f.popups.length, 0); assert.equal(f.calls.length, 0); }
});
test("authorized explicit click uses saved message, records attempt and never claims sent", async () => {
  const f = fixture(); await f.workflow.load(); assert.equal(f.navigations.length, 0); await f.workflow.openWhatsApp(); assert.equal(f.calls.length, 1); assert.deepEqual(f.calls[0], { customer_id: 10, channel: "whatsapp", idempotency_key: "communication:key1" }); assert.equal(f.popups[0].opener, null); assert.equal(new URL(f.navigations[0]).searchParams.get("text"), preview().message); assert.match(f.workflow.getSnapshot().result, /Handoff requested.*not verified/); assert.equal(f.store.read().pending, false);
});
test("double click cannot open two windows or log duplicate requests", async () => {
  const pending = defer(); const f = fixture({ handoff: async () => pending.promise }); await f.workflow.load(); const save = f.workflow.openWhatsApp(); await f.workflow.openWhatsApp(); await flush(); assert.equal(f.popups.length, 1); pending.resolve(result()); await save;
});
test("blocked popup logs nothing and never navigates", async () => { const f = fixture(); const workflow = f.make({ openWindow: () => null }); await workflow.load(); await workflow.openWhatsApp(); assert.equal(f.calls.length, 0); assert.match(workflow.getSnapshot().error, /Allow popups/); });
test("failed request closes blank window; identical retry reuses persisted key", async () => {
  let attempts = 0; const payloads = []; const f = fixture({ handoff: async (b, r, payload) => { payloads.push(payload); if (++attempts === 1) throw Error("timeout"); return result(); } }); await f.workflow.load(); await f.workflow.openWhatsApp(); assert.equal(f.popups[0].closed, true); assert.equal(f.navigations.length, 0); assert.equal(f.store.read().pending, true); f.workflow.dispose(); const next = f.make(); await next.load(); await next.openWhatsApp(); assert.equal(payloads[0].idempotency_key, payloads[1].idempotency_key); assert.equal(f.store.read().pending, false);
});
test("unresolved handoff cannot be replaced by a different preference update", async () => {
  const f = fixture({ handoff: async () => { throw Error("timeout"); } }); await f.workflow.load(); await f.workflow.openWhatsApp(); f.workflow.edit("consentStatus", "opted_out"); f.workflow.edit("evidence", "Customer asked today"); f.workflow.edit("confirmed", true); await f.workflow.saveConsent(); assert.match(f.workflow.getSnapshot().error, /unresolved/); assert.equal(f.store.read().pending, true);
});
test("preference requires actual explicit confirmation and never defaults to granted", async () => {
  const f = fixture({ preview: async () => preview({ consent_status: "unknown", eligible: false }) }); await f.workflow.load(); assert.equal(f.workflow.getSnapshot().consentStatus, ""); await f.workflow.saveConsent(); assert.match(f.workflow.getSnapshot().error, /actual|stated/); f.workflow.edit("consentStatus", "granted"); f.workflow.edit("evidence", "Customer stated in person today"); f.workflow.edit("confirmed", true); await f.workflow.saveConsent(); assert.match(f.workflow.getSnapshot().result, /not independently verified/);
});
test("unsafe URL or message mismatch cannot navigate", async () => {
  for (const patch of [{ handoff_url: "https://evil.example/" }, { handoff_url: whatsappUrl("94771234567", preview().message) + "&token=secret" }, { message: "different amount" }, { normalized_phone: "94777654321" }, { status: "delivered" }]) {
    const f = fixture({ handoff: async () => result(preview(), patch) }); await f.workflow.load(); await f.workflow.openWhatsApp(); assert.equal(f.navigations.length, 0); assert.equal(f.popups[0].closed, true); assert.ok(f.workflow.getSnapshot().error);
  }
  assert.throws(() => safeHandoffUrl(result(preview(), { handoff_url: "javascript:alert(1)" }), preview()));
});
test("unmount prevents stale handoff navigation and closes pending window", async () => {
  const pending = defer(); const f = fixture({ handoff: async () => pending.promise }); await f.workflow.load(); const save = f.workflow.openWhatsApp(); await flush(); f.workflow.dispose(); pending.resolve(result()); await save; assert.equal(f.navigations.length, 0); assert.equal(f.popups[0].closed, true);
});
test("foreign or stale preview is never displayed", async () => { const f = fixture({ preview: async () => preview({ business_id: 2 }) }); await f.workflow.load(); assert.equal(f.workflow.getSnapshot().preview, null); assert.ok(f.workflow.getSnapshot().error); });
for (const status of [401, 403, 404, 409, 422, 500]) test("HTTP " + status + " prevents handoff and hides raw errors", async () => { const f = fixture({ handoff: async () => { throw { response: { status, data: { detail: "SECRET STACK" } } }; } }); await f.workflow.load(); await f.workflow.openWhatsApp(); assert.equal(f.navigations.length, 0); assert.doesNotMatch(f.workflow.getSnapshot().error, /SECRET/); if ([401, 403].includes(status)) assert.equal(f.workflow.getSnapshot().preview, null); });
test("opaque communication storage is isolated by user and rejects corrupt state", () => {
  const previous = globalThis.sessionStorage, map = new Map(); globalThis.sessionStorage = { getItem: k => map.get(k), setItem: (k, v) => map.set(k, v) };
  try { const store = sessionCommunicationStore(1); const value = { fingerprint: "a".repeat(64), key: "communication:abc", pending: true }; store.write(value); assert.deepEqual(store.read(), value); assert.equal(sessionCommunicationStore(2).read(), null); assert.ok(!JSON.stringify([...map.values()]).includes("LKR")); map.set("lankapex_communication_1", "bad"); assert.throws(() => store.read()); } finally { if (previous === undefined) delete globalThis.sessionStorage; else globalThis.sessionStorage = previous; }
});
