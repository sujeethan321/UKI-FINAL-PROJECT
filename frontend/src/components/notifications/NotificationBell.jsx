import { useEffect, useId, useRef } from "react";
import { Link } from "react-router-dom";
import { Bell, X } from "lucide-react";
import { useNotifications } from "../../context/NotificationContext";
import { notificationInboxPath } from "../../utils/notification";
import { bindNotificationPopover } from "../../utils/notificationPopover";
import NotificationItem from "./NotificationItem";

export function NotificationBellView({ state, actions, role }) {
  const container = useRef(null), trigger = useRef(null), panel = useRef(null);
  const panelId = useId();
  const close = actions.closeDropdown;
  useEffect(() => {
    if (!state.open) return;
    return bindNotificationPopover({ browserDocument: document, container: container.current, trigger: trigger.current, panel: panel.current, close });
  }, [state.open, close]);
  const known = state.count !== null && !state.countLoading && !state.countError && !state.authError;
  const label = state.authError ? "Notifications: access unavailable" : state.countLoading ? "Notifications: loading unread count" : known ? "Notifications: " + state.count + " unread" : "Notifications: unread count unavailable";
  const inboxPath = notificationInboxPath(role);
  return <div ref={container} className="relative shrink-0">
    <button ref={trigger} type="button" onClick={actions.toggleDropdown} disabled={!!state.authError} aria-label={label} aria-expanded={state.open} aria-controls={state.open ? panelId : undefined} aria-haspopup="dialog" className="relative flex h-10 w-10 items-center justify-center rounded-xl text-[#10243E] hover:bg-[#F5F8FC] focus-visible:outline-2 focus-visible:outline-[#12B8A6] disabled:opacity-50">
      <Bell size={21} aria-hidden="true" />
      {known && state.count > 0 && <span aria-hidden="true" className="absolute -right-1 -top-1 min-w-5 rounded-full bg-[#DC4545] px-1 text-center text-[10px] font-bold leading-5 text-white">{state.count > 99 ? "99+" : state.count}</span>}
      {state.countLoading && <span role="status" className="sr-only">Loading unread notification count...</span>}
      {!state.countLoading && (state.countError || state.authError) && <span className="absolute right-0 top-0 h-2 w-2 rounded-full bg-[#F5B544]" aria-hidden="true" />}
    </button>
    {(state.countError || state.authError) && <span className="sr-only" role="status">{state.authError || state.countError}</span>}
    {state.open && <section ref={panel} id={panelId} role="dialog" aria-label="Recent notifications" className="fixed right-4 top-[82px] z-40 max-h-[min(32rem,calc(100dvh-7rem))] w-[min(24rem,calc(100vw-2rem))] overflow-y-auto rounded-xl border border-[#DFE8F0] bg-white shadow-xl sm:absolute sm:right-0 sm:top-full sm:mt-3">
      <div className="flex items-center justify-between gap-3 border-b border-[#E8EEF5] p-4"><h3 className="font-bold text-[#10243E]">Notifications</h3><button type="button" aria-label="Close notifications" className="rounded p-1 text-[#587098] hover:bg-[#F5F8FC]" onClick={() => { close(); trigger.current?.focus(); }}><X size={18} /></button></div>
      {(state.countError || state.recentError || state.actionError) && <div role="alert" className="space-y-2 p-4 text-sm text-[#DC4545]"><p>{state.recentError || state.actionError || state.countError}</p><button type="button" className="font-semibold underline disabled:opacity-50" disabled={state.mutating || state.recentLoading} onClick={() => actions.refresh()}>Retry notifications</button></div>}
      {state.recentLoading && <p role="status" className="p-4 text-sm text-[#587098]">Loading recent notifications...</p>}
      {state.recent && (state.recent.notifications.length ? <ul aria-label="Recent notification list">{state.recent.notifications.map(row => <NotificationItem key={row.notification_id} notification={row} role={role} busy={state.mutating} onRead={actions.markRead} compact onNavigate={close} />)}</ul> : <p className="p-6 text-center text-sm text-[#587098]">No notifications yet.</p>)}
      {inboxPath && <Link to={inboxPath} onClick={close} className="block border-t border-[#E8EEF5] p-4 text-center text-sm font-semibold text-[#087D78] hover:bg-[#F0FBF9]">View All Notifications</Link>}
    </section>}
  </div>;
}
export default function NotificationBell() {
  const context = useNotifications();
  return context ? <NotificationBellView {...context} /> : null;
}
