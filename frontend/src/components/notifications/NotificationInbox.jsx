import Select from "../ui/Select";
import { useEffect } from "react";
import { useNotifications } from "../../context/NotificationContext";
import { NOTIFICATION_TYPES } from "../../utils/notification";
import NotificationItem from "./NotificationItem";

const button = "rounded-lg border border-[#DAE5F3] bg-white px-3 py-2 text-sm font-semibold text-[#36517B] disabled:opacity-50";
const field = "mt-1 block max-w-full rounded-lg border border-[#DAE5F3] bg-white px-3 py-2 text-sm text-[#10243E]";

export function NotificationInboxView({ state, actions, role }) {
  return <section aria-label="Notification inbox" className="space-y-4 rounded-xl border border-[#E1EAF4] bg-white p-4 text-[#10243E] shadow-sm sm:p-5">
    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="text-lg font-bold">Your Notifications</h3><p className="text-sm text-[#587098]">Your personal inbox across businesses, newest first.</p></div><button type="button" className={button} disabled={state.mutating || !!state.authError || state.count === 0} onClick={actions.markAllRead}>{state.mutating && state.markingId === null ? "Updating..." : "Mark All as Read"}</button></div>
    <div className="flex flex-wrap items-end gap-3"><label htmlFor="notification-read-filter" className="text-sm font-semibold">Read status<Select id="notification-read-filter" className={field} value={state.readFilter} disabled={state.mutating || !!state.authError} onChange={e => actions.setFilter("readFilter", e.target.value)}><option value="all">All</option><option value="unread">Unread</option><option value="read">Read</option></Select></label><label htmlFor="notification-type-filter" className="text-sm font-semibold">Type<Select id="notification-type-filter" className={field} value={state.typeFilter} disabled={state.mutating || !!state.authError} onChange={e => actions.setFilter("typeFilter", e.target.value)}><option value="">All types</option>{NOTIFICATION_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select></label><button type="button" className={button} disabled={state.mutating || state.listLoading || !!state.authError} onClick={() => actions.refresh()}>Refresh inbox</button></div>
    {state.authError && <p role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-[#DC4545]">{state.authError}</p>}
    {state.actionError && <p role="alert" className="rounded-lg bg-red-50 p-4 text-sm text-[#DC4545]">{state.actionError}</p>}
    {state.listLoading && <p role="status" className="p-4 text-sm text-[#587098]">Loading notifications...</p>}
    {!state.authError && state.listError && <div role="alert" className="flex flex-wrap items-center gap-3 text-sm text-[#DC4545]"><p>{state.listError}</p><button type="button" className={button} disabled={state.mutating} onClick={actions.loadList}>Retry notifications</button></div>}
    {!state.authError && state.list && <>
      {state.list.notifications.length ? <ul aria-label="Notification history" className="overflow-hidden rounded-lg border border-[#E1EAF4]">{state.list.notifications.map(row => <NotificationItem key={row.notification_id} notification={row} role={role} busy={state.mutating} onRead={actions.markRead} />)}</ul> : <p className="p-6 text-center text-sm text-[#587098]">{state.readFilter === "all" && !state.typeFilter ? "No notifications yet." : "No notifications match these filters."}</p>}
      <div className="flex flex-wrap items-center justify-end gap-3 text-sm"><button type="button" className={button} disabled={state.mutating || state.listLoading || state.page <= 1} onClick={() => actions.setFilter("page", state.page - 1)}>Previous</button><span>Page {state.page} · {state.list.total} notifications</span><button type="button" className={button} disabled={state.mutating || state.listLoading || state.page * state.pageSize >= state.list.total} onClick={() => actions.setFilter("page", state.page + 1)}>Next</button></div>
    </>}
  </section>;
}
export default function NotificationInbox() {
  const context = useNotifications();
  const actions = context?.actions;
  useEffect(() => { if (!actions) return; actions.openInbox(); return () => actions.closeInbox(); }, [actions]);
  return context ? <NotificationInboxView {...context} /> : null;
}
