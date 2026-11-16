import { useEffect, useState, useSyncExternalStore } from "react";
import { Link, useLocation } from "react-router-dom";
import { RefreshCw } from "lucide-react";
import { useAuth } from "../../context/useAuth";
import { getShopOwnerBusinessContext } from "../../services/shopOwnerBusinessService";
import { getShopOwnerCustomers, getShopOwnerCustomerDetails } from "../../services/shopOwnerCustomerService";
import { createShopOwnerReminder, getShopOwnerReminders } from "../../services/shopOwnerReminderService";
import { CHANNELS, LANGUAGES, draftReminder, reminderMoney, reminderValidation, sessionReminderStore } from "../../utils/reminder";
import ReminderCommunication from "./ReminderCommunication";
import NotificationInbox from "../../components/shopOwner/ShopOwnerInbox";
import { createReminderWorkflow } from "./reminderWorkflow";

const api = { businesses: getShopOwnerBusinessContext, customers: getShopOwnerCustomers, details: getShopOwnerCustomerDetails, record: createShopOwnerReminder, history: getShopOwnerReminders };
const field = "mt-1.5 w-full rounded-lg border border-[#DAE5F3] bg-white px-3 py-2.5 text-sm text-[#10243E] outline-none focus:border-[#12B8A6]";
const button = "rounded-lg border border-[#DAE5F3] bg-white px-3 py-2 text-sm font-semibold text-[#36517B] disabled:opacity-50";
const card = "space-y-4 rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm sm:p-5";
const dateLabel = value => new Date(value).toLocaleString("en-LK", { timeZone: "Asia/Colombo" });
const channelLabel = value => CHANNELS.find(([v]) => v === value)?.[1] || value;

export function NotificationsView({ state, actions, inbox, onReviewReminder, communicationPanel }) {
  const business = state.businesses.find(b => String(b.business_id) === state.businessId);
  const approved = business?.approval_status === "approved";
  const busy = state.saving || state.contextLoading;
  const validation = reminderValidation(state);
  const blocked = busy || !approved || state.customersLoading || state.detailsLoading || !!state.contextError || !!state.customersError || !!state.detailsError || !!state.storageError || !!validation || !!state.success;
  return <div className="space-y-5 pb-8 text-[#10243E]">
    <div><h2 className="text-[26px] font-extrabold">Notifications</h2><p className="text-sm text-[#587098]">Stay updated with your shop&apos;s important activities.</p></div>
    {inbox}
    <div className="flex flex-wrap items-center gap-3">
      <label className="text-sm font-semibold" htmlFor="reminder-business">Business</label>
      <select id="reminder-business" className="min-w-0 max-w-full rounded-lg border border-[#DAE5F3] bg-white px-3 py-2 text-sm" value={state.businessId} disabled={busy || !state.businesses.length} onChange={e => actions.selectBusiness(e.target.value)}>
        {!state.businesses.length && <option value="">No linked businesses</option>}
        {state.businesses.map(b => <option key={b.business_id} value={b.business_id}>{b.business_name || "Unnamed business"} ({b.approval_status})</option>)}
      </select>
      <button type="button" className={button} disabled={busy || state.customersLoading || state.detailsLoading} onClick={actions.refresh} aria-label="Refresh reminder data"><RefreshCw size={18} /></button>
    </div>
    {state.contextLoading && <p role="status">Loading business information...</p>}
    {[state.contextError, state.storageError, state.error].filter(Boolean).map((error, i) => <p key={i} role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-red-700">{error}</p>)}
    {!state.contextLoading && !state.contextError && !business && <p className={card}>No business is linked to your account. <Link to="/shop-owner/business/register" className="underline">Register a business</Link> first.</p>}
    {business && !approved && <p className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">Business approval is required. Current status: {business.approval_status}.</p>}
    {state.uncertain && <p role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">A reminder may already be recorded. Review history, then re-enter the original business, customer, channel, language and note to retry the identical request. The saved key survives reloads. History cannot identify a request key; a same-key retry confirms the result. New operations remain blocked until it is resolved.</p>}
    {approved && !state.contextError && <>
      <section className={card}>
        <label className="block text-sm font-semibold" htmlFor="reminder-customer">Customer<select id="reminder-customer" className={field} value={state.customerId} disabled={busy || state.customersLoading || !!state.customersError} onChange={e => actions.selectCustomer(e.target.value)}><option value="">Select a customer</option>{state.customers.map(c => <option key={c.customer_id} value={c.customer_id}>{c.customer_name || "Unnamed customer"}</option>)}</select></label>
        {state.customersLoading && <p role="status">Loading customers...</p>}
        {state.customersError && <p role="alert" className="text-sm text-red-700">{state.customersError}</p>}
        {!state.customersLoading && !state.customersError && !state.customers.length && <p className="text-sm text-[#587098]">No customers in this business.</p>}
        {state.detailsLoading && <p role="status">Loading current outstanding balance...</p>}
        {state.detailsError && <p role="alert" className="text-sm text-red-700">{state.detailsError}</p>}
        {state.details && <div className="rounded-xl border border-[#E1EAF4] p-4"><h3 className="font-bold">{state.details.customer.customer_name || "Unnamed customer"}</h3><p className="text-sm text-[#587098]">Phone: {state.details.customer.phone || "Unavailable"}</p><p className="mt-3 text-xs font-semibold text-[#587098]">Outstanding Balance</p><p className="text-xl font-extrabold">{reminderMoney(state.details.outstanding_balance)}</p></div>}
      </section>
      <section className={card}>
        <h3 className="text-lg font-bold">Prepare Reminder</h3>
        <form className="space-y-4" noValidate onSubmit={e => { e.preventDefault(); void actions.submit(); }}>
          <fieldset disabled={state.saving || !!state.success} className="space-y-4 disabled:opacity-60">
            <div className="grid gap-4 sm:grid-cols-2"><label className="text-sm font-semibold" htmlFor="reminder-channel">Intended channel<select id="reminder-channel" className={field} value={state.channel} onChange={e => actions.edit("channel", e.target.value)}>{CHANNELS.map(([v, label]) => <option key={v} value={v} disabled={v !== "internal" && !!state.details && !state.details.customer.phone}>{label}</option>)}</select></label>
            <label className="text-sm font-semibold" htmlFor="reminder-language">Language<select id="reminder-language" className={field} value={state.language} onChange={e => actions.edit("language", e.target.value)}>{LANGUAGES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select></label></div>
            <label className="block text-sm font-semibold" htmlFor="reminder-note">Internal note (optional)<textarea id="reminder-note" className={field} rows={3} maxLength={1000} value={state.note} onChange={e => actions.edit("note", e.target.value)} /></label>
          </fieldset>
          <p className="text-xs text-[#587098]">Recording does not send SMS, WhatsApp or email. WhatsApp eligibility is checked separately for saved reminders; automatic provider delivery is unavailable. The server calculates the amount and records the final message. Internal notes are separate from the message.</p>
          {validation && <p role="status" className="text-sm text-amber-800">{validation}</p>}
          {!state.success && <div className="rounded-lg bg-[#F5F8FC] p-4"><h4 className="mb-2 text-sm font-semibold">Draft preview — unsaved</h4><p lang={state.language} className="whitespace-pre-wrap break-words text-sm">{draftReminder(state.details, business, state.language)}</p><p className="mt-2 text-xs text-[#587098]">The exact message and timestamp are generated when recorded.</p></div>}
          <div className="flex flex-wrap justify-end gap-3"><button type="button" className={button} disabled={state.saving || state.uncertain || !!state.storageError} onClick={actions.newReminder}>New Reminder</button><button type="submit" disabled={blocked} className="rounded-lg bg-[#12B8A6] px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60">{state.saving ? "Recording..." : state.uncertain ? "Retry Same Reminder" : "Record Reminder"}</button></div>
        </form>
        {state.success && <div role="status" className="space-y-2 rounded-lg bg-[#E5F8EF] p-4 text-sm text-[#118456]"><h4 className="font-bold">{state.success.replayed ? "Existing reminder confirmed" : "Reminder recorded"} — no message delivered</h4><p>Record #{state.success.reminder_id} · {reminderMoney(state.success.outstanding_amount)} · Status: {state.success.status}</p><p>Created: {dateLabel(state.success.created_at)} (Asia/Colombo)</p><p lang={state.success.language} className="whitespace-pre-wrap break-words">{state.success.message}</p><button type="button" className={button} disabled={!onReviewReminder} onClick={() => onReviewReminder(state.success)}>Review WhatsApp handoff</button></div>}
      </section>
      {communicationPanel}
      <section className={card}>
        <h3 className="text-lg font-bold">Reminder History</h3>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm" htmlFor="history-customer">Customer<select id="history-customer" className={field} value={state.historyCustomerId} onChange={e => actions.filter("historyCustomerId", e.target.value)}><option value="">All customers</option>{state.customers.map(c => <option key={c.customer_id} value={c.customer_id}>{c.customer_name || "Unnamed customer"}</option>)}</select></label>
          <label className="text-sm" htmlFor="history-status">Status<select id="history-status" className={field} value={state.status} onChange={e => actions.filter("status", e.target.value)}><option value="">All statuses</option><option value="recorded">Recorded</option></select></label>
          <label className="text-sm" htmlFor="history-order">Order<select id="history-order" className={field} value={state.ordering} onChange={e => actions.filter("ordering", e.target.value)}><option value="newest">Newest first</option><option value="oldest">Oldest first</option></select></label>
          <button type="button" className={button} onClick={actions.loadHistory} disabled={state.historyLoading}>Refresh history</button>
        </div>
        {state.historyLoading && <p role="status">Loading reminder history...</p>}
        {state.historyError && <p role="alert" className="text-sm text-red-700">{state.historyError}</p>}
        {state.history && <><div className="overflow-x-auto"><table className="w-full min-w-[780px] text-left text-sm"><thead className="bg-[#EAF2F9]"><tr>{["Customer", "Amount snapshot", "Intended channel", "Language", "Created (Asia/Colombo)", "Status", "Message"].map(label => <th key={label} className="px-3 py-3">{label}</th>)}</tr></thead><tbody>{state.history.reminders.map(row => <tr key={row.reminder_id} className="border-b border-[#E8EEF5]"><td className="px-3 py-3">{state.customers.find(c => c.customer_id === row.customer_id)?.customer_name || "Customer #" + row.customer_id}</td><td className="px-3 py-3">{reminderMoney(row.outstanding_amount)}</td><td className="px-3 py-3">{channelLabel(row.channel)}</td><td className="px-3 py-3">{row.language === "ta" ? "Tamil" : "English"}</td><td className="px-3 py-3">{dateLabel(row.created_at)}</td><td className="px-3 py-3"><span className="rounded-full bg-[#E5F8EF] px-2 py-1 text-xs text-[#118456]">{row.status}</span></td><td className="px-3 py-3"><details><summary className="cursor-pointer">View message</summary><p lang={row.language} className="mt-2 max-w-md whitespace-pre-wrap break-words">{row.message}</p><button type="button" className={button} disabled={!onReviewReminder} onClick={() => onReviewReminder(row)}>Review WhatsApp handoff</button></details></td></tr>)}{!state.history.reminders.length && <tr><td className="p-6 text-center text-[#587098]" colSpan={7}>No reminders match these filters.</td></tr>}</tbody></table></div><div className="flex flex-wrap items-center justify-end gap-3 text-sm"><button type="button" className={button} disabled={state.historyLoading || state.page <= 1} onClick={() => actions.filter("page", state.page - 1)}>Previous</button><span>Page {state.page} · {state.history.total} reminders</span><button type="button" className={button} disabled={state.historyLoading || state.page * state.pageSize >= state.history.total} onClick={() => actions.filter("page", state.page + 1)}>Next</button></div></>}
        <p className="text-xs text-[#587098]">Recorded means saved internally. WhatsApp handoff requests are tracked separately and do not prove sending or delivery.</p>
      </section>
    </>}
  </div>;
}
function NotificationsPage({ userId, initialBusinessId, initialCustomerId }) {
  const [workflow] = useState(() => createReminderWorkflow({ api, store: sessionReminderStore(userId), initialBusinessId, initialCustomerId }));
  const state = useSyncExternalStore(workflow.subscribe, workflow.getSnapshot, workflow.getSnapshot);
  const [reviewed, setReviewed] = useState(null);
  const reviewReminder = row => {
    if (state.saving || !state.customers.some(customer => customer.customer_id === row.customer_id)) return;
    if (String(row.customer_id) !== state.customerId) void workflow.selectCustomer(String(row.customer_id));
    setReviewed(row);
  };
  const communicationPanel = reviewed && String(reviewed.business_id) === state.businessId && String(reviewed.customer_id) === state.customerId
    ? <ReminderCommunication key={reviewed.business_id + ":" + reviewed.reminder_id} businessId={reviewed.business_id} customerId={reviewed.customer_id} reminderId={reviewed.reminder_id} userId={userId} /> : null;
  useEffect(() => {
    void workflow.loadBusinesses();
    const warn = e => { const s = workflow.getSnapshot(); if (s.saving || s.uncertain) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => { workflow.dispose(); window.removeEventListener("beforeunload", warn); };
  }, [workflow]);
  return <NotificationsView state={state} actions={workflow} inbox={<NotificationInbox />} onReviewReminder={reviewReminder} communicationPanel={communicationPanel} />;
}
export default function ShopOwnerNotifications() {
  const { user } = useAuth();
  const location = useLocation();
  return <NotificationsPage key={user.user_id} userId={user.user_id} initialBusinessId={location.state?.businessId} initialCustomerId={location.state?.customerId} />;
}
