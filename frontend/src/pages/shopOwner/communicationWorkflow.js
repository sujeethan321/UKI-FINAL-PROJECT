// Purpose: Keep communication workflow data handling and workflow helpers separate from React rendering so callers use consistent rules.
import { communicationError, communicationFingerprint, communicationKey, safeHandoffUrl } from "../../utils/communication.js";
// Compare the relevant record identities before reusing current workflow state.
const same = (a, b) => String(a) === String(b);
// Check identifier shape and range before the caller uses it as a record reference.
const validId = value => Number.isSafeInteger(value) && value > 0;

// Create communication workflow for the communication workflow workflow.
export function createCommunicationWorkflow({ api, store, scope, makeKey = communicationKey, fingerprint = communicationFingerprint,
  openWindow = () => window.open("about:blank", "_blank") }) {
  let state = { preview: null, loading: false, saving: false, error: "", consentStatus: "", evidence: "", confirmed: false, result: null };
  let active = true, version = 0, readAbort, writeAbort, popup, locked = false;
  const listeners = new Set();
  // Replace the store snapshot and notify subscribers so React can render the new state.
  const publish = patch => { if (active) { state = { ...state, ...patch }; listeners.forEach(fn => fn()); } };
  // Check that returned data belongs to the resource scope expected by this reader.
  const scoped = row => same(row?.business_id, scope.businessId) && same(row?.customer_id, scope.customerId) && same(row?.reminder_id, scope.reminderId);
  // Load the current resource data and update the state consumed by the interface.
  async function load() {
    active = true; readAbort?.abort(); const revision = ++version;
    readAbort = new AbortController(); const signal = readAbort.signal;
    publish({ preview: null, loading: true, error: "" });
    try {
      const data = await api.preview(scope.businessId, scope.customerId, scope.reminderId, { signal });
      if (!active || signal.aborted || revision !== version) return;
      if (!scoped(data) || typeof data.message !== "string" || !data.message.trim() || !["en", "ta"].includes(data.language) || data.currency !== "LKR" || !["unknown", "granted", "opted_out"].includes(data.consent_status) || typeof data.eligible !== "boolean" || !Array.isArray(data.attempts) || data.provider_delivery_available !== false || (data.eligible && (data.consent_status !== "granted" || !/^947[0-9]{8}$/.test(data.normalized_phone)))) throw new Error("Invalid eligibility response");
      publish({ preview: data });
    } catch (error) { if (active && !signal.aborted && revision === version) publish({ error: communicationError(error) }); }
    finally { if (!signal.aborted && revision === version) publish({ loading: false }); }
  }
  // Populate the editable form from the selected record instead of starting a new record.
  function edit(field, value) { if (!locked && ["consentStatus", "evidence", "confirmed"].includes(field)) publish({ [field]: value, error: "" }); }
  // Submit the current form through its workflow and expose pending, success, or error state to the interface.
  async function submit(kind) {
    if (!active || locked || state.loading || !state.preview) return;
    const handoff = kind === "handoff";
    if (handoff && !state.preview.eligible) return;
    if (!handoff && (!["granted", "opted_out"].includes(state.consentStatus) || !state.evidence.trim() || [...state.evidence].length > 500 || state.confirmed !== true)) { publish({ error: "Select the customer's stated preference, describe when/how it was given, and confirm the record." }); return; }
    // Open only in the explicit click handler, before awaits. A blank window
    // prevents popup blockers from requiring an unsafe cached-link fallback.
    if (handoff) {
      try { popup = openWindow(); if (!popup) throw new Error("Popup blocked"); popup.opener = null; }
      catch { popup?.close(); popup = null; publish({ error: "The browser did not provide a handoff window. Allow popups and retry." }); return; }
    }
    locked = true; publish({ saving: true, error: "", result: null });
    const reviewed = state.preview;
    const payload = handoff ? { customer_id: Number(scope.customerId), channel: "whatsapp" } : { channel: "whatsapp", consent_status: state.consentStatus, evidence: state.evidence.trim(), confirmed: true };
    let dispatched = false, previous;
    writeAbort = new AbortController(); const signal = writeAbort.signal;
    try {
      const hash = await fingerprint([kind, String(scope.businessId), String(scope.customerId), String(scope.reminderId), payload, handoff ? [reviewed.normalized_phone, reviewed.message] : null]);
      if (!active || signal.aborted) { popup?.close(); return; }
      previous = store.read();
      if (previous?.pending && previous.fingerprint !== hash) throw new Error("Pending operation");
      const key = previous?.fingerprint === hash ? previous.key : makeKey();
      store.write({ fingerprint: hash, key, pending: true });
      dispatched = true;
      const result = handoff ? await api.handoff(scope.businessId, scope.reminderId, { ...payload, idempotency_key: key }, { signal }) : await api.consent(scope.businessId, scope.customerId, { ...payload, idempotency_key: key }, { signal });
      if (!active || signal.aborted) { popup?.close(); return; }
      if (!same(result?.business_id, scope.businessId) || !same(result?.customer_id, scope.customerId) || typeof result.replayed !== "boolean") throw new Error("Unconfirmed response");
      if (handoff) {
        if (!scoped(result) || !validId(result.attempt_id)) throw new Error("Unconfirmed handoff");
        const url = safeHandoffUrl(result, reviewed);
        store.write({ fingerprint: hash, key, pending: false });
        // A navigation request is not proof that WhatsApp launched or sent.
        popup.location.replace(url); popup = null;
        publish({ result: "Handoff requested. WhatsApp launch, sending and delivery are not verified." });
      } else {
        if (!validId(result.consent_id) || result.consent_status !== payload.consent_status || result.independently_verified !== false) throw new Error("Unconfirmed preference");
        store.write({ fingerprint: hash, key, pending: false });
        publish({ evidence: "", confirmed: false, consentStatus: "", result: "Customer statement recorded by the Shop Owner; it is not independently verified." });
      }
      await load();
    } catch (error) {
      popup?.close(); popup = null;
      if (active && !signal.aborted) {
        if (dispatched && [401, 403, 404, 409, 422].includes(error?.response?.status) && !previous?.pending) {
          try { const record = store.read(); store.write({ ...record, pending: false }); } catch { /* Preserve pending identity when storage is unavailable. */ }
        }
        publish({ error: dispatched ? communicationError(error) : "An operation may be unresolved or secure storage is unavailable. Re-enter the identical original preference/handoff to retry; a different operation cannot replace it." });
        if ([401, 403].includes(error?.response?.status)) publish({ preview: null });
      }
    } finally { locked = false; publish({ saving: false }); }
  }
  return { /* Register a state listener and return cleanup so consumers can unsubscribe. */ subscribe: fn => { listeners.add(fn); return () => listeners.delete(fn); }, /* Expose the current store snapshot to subscribers without starting a request. */ getSnapshot: () => state,
    load, edit, /* Submit the explicit communication preference and reconcile the confirmed consent state. */ saveConsent: () => submit("consent"), /* Run the explicit messaging handoff after the workflow eligibility checks. */ openWhatsApp: () => submit("handoff"),
    // Release pending work and subscriptions when this resource reader is no longer used.
    dispose: () => { active = false; ++version; readAbort?.abort(); writeAbort?.abort(); popup?.close(); popup = null; } };
}
