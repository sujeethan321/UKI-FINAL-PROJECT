import Select from "../../components/ui/Select";
import { useEffect, useId, useState, useSyncExternalStore } from "react";
import { getReminderCommunication, recordCustomerCommunicationConsent, requestWhatsAppHandoff } from "../../services/communicationService";
import { sessionCommunicationStore } from "../../utils/communication";
import { reminderMoney } from "../../utils/reminder";
import { createCommunicationWorkflow } from "./communicationWorkflow";
const api = { preview: getReminderCommunication, consent: recordCustomerCommunicationConsent, handoff: requestWhatsAppHandoff };
const button = "rounded-lg border border-[#DAE5F3] px-3 py-2 text-sm font-semibold text-[#36517B] disabled:opacity-50";
const field = "mt-1 block w-full rounded-lg border border-[#DAE5F3] bg-white px-3 py-2 text-sm text-[#10243E]";

export function ReminderCommunicationView({ state, actions }) {
  const id = useId();
  const preview = state.preview;
  return <section aria-label="Customer WhatsApp communication" className="space-y-4 rounded-xl border border-[#E1EAF4] bg-white p-4 text-[#10243E] shadow-sm sm:p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="text-lg font-bold">Review WhatsApp Handoff</h3><button type="button" className={button} disabled={state.saving || state.loading} onClick={actions.load}>Refresh eligibility</button></div>
    {state.loading && <p role="status" className="text-sm text-[#587098]">Checking saved reminder and contact eligibility...</p>}
    {state.error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-[#DC4545]">{state.error}</p>}
    {state.result && <p role="status" className="rounded-lg bg-[#E5F8EF] p-3 text-sm text-[#118456]">{state.result}</p>}
    {preview && <>
      <p className="text-sm">WhatsApp preference: <strong>{preview.consent_status === "granted" ? "Permission recorded by owner" : preview.consent_status === "opted_out" ? "Opted out" : "Unknown — handoff blocked"}</strong>. {preview.consent_source && "Based on an owner-recorded customer statement; not independently verified."}</p>
      <p className="text-sm text-[#587098]">Customer mobile: {preview.normalized_phone || "Unavailable or unsupported"}</p>
      {preview.blocked_reason && <p className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">{preview.blocked_reason}</p>}
      <div className="space-y-2 rounded-lg bg-[#F5F8FC] p-4"><h4 className="text-sm font-semibold">Saved server message — {reminderMoney(preview.outstanding_amount)}</h4><p lang={preview.language} className="whitespace-pre-wrap break-words text-sm">{preview.message}</p></div>
      <p className="text-xs text-[#587098]">Open WhatsApp shares this customer number and saved message with WhatsApp. You must review and send it there yourself. A handoff request does not confirm application launch, sending or delivery. The reminder remains recorded.</p>
      <button type="button" disabled={!preview.eligible || state.saving || state.loading} onClick={actions.openWhatsApp} className="rounded-lg bg-[#12B8A6] px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60">{state.saving ? "Preparing..." : "Open WhatsApp"}</button>
      <details className="lp-disclosure border-t border-[#E1EAF4] pt-3"><summary className="cursor-pointer text-sm font-semibold">Record customer preference or opt-out</summary>
        <p className="mt-3 text-xs text-[#587098]">Record only what the customer actually stated. This does not obtain permission on their behalf. A grant applies to the current mobile number; a changed number requires a new statement. Opt-outs block all WhatsApp handoffs for this customer.</p>
        <form className="mt-3 space-y-3" onSubmit={e => { e.preventDefault(); void actions.saveConsent(); }}>
          <fieldset disabled={state.saving || state.loading} className="space-y-3">
            <label htmlFor={id + "-status"} className="block text-sm font-semibold">Customer's stated preference<Select id={id + "-status"} value={state.consentStatus} onChange={e => actions.edit("consentStatus", e.target.value)} className={field}><option value="">Select the actual preference</option><option value="granted">Customer granted WhatsApp permission</option><option value="opted_out">Customer opted out of WhatsApp</option></Select></label>
            <label htmlFor={id + "-evidence"} className="block text-sm font-semibold">When and how was this stated?<input id={id + "-evidence"} value={state.evidence} maxLength={500} onChange={e => actions.edit("evidence", e.target.value)} className={field} autoComplete="off" /></label>
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={state.confirmed} onChange={e => actions.edit("confirmed", e.target.checked)} className="mt-1" />I confirm this records the customer's actual stated preference for this contact, not an assumption.</label>
            <button type="submit" className={button}>Record Preference</button>
          </fieldset>
        </form>
      </details>
      <div className="border-t border-[#E1EAF4] pt-3"><h4 className="text-sm font-semibold">Recent handoff requests</h4>{preview.attempts.length ? <ul className="mt-2 space-y-2 text-xs text-[#587098]">{preview.attempts.map(attempt => <li key={attempt.attempt_id}>Handoff requested · {new Date(attempt.created_at).toLocaleString("en-LK", { timeZone: "Asia/Colombo" })} (Asia/Colombo) · Sending is not verified.</li>)}</ul> : <p className="mt-2 text-xs text-[#587098]">No handoff requests recorded.</p>}</div>
    </>}
  </section>;
}
export default function ReminderCommunication({ businessId, customerId, reminderId, userId }) {
  const [workflow] = useState(() => createCommunicationWorkflow({ api, store: sessionCommunicationStore(userId), scope: { businessId, customerId, reminderId } }));
  const state = useSyncExternalStore(workflow.subscribe, workflow.getSnapshot, workflow.getSnapshot);
  useEffect(() => { void workflow.load(); return () => workflow.dispose(); }, [workflow]);
  return <ReminderCommunicationView state={state} actions={workflow} />;
}
