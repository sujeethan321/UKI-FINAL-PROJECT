// Purpose: Render the reusable notification bell interface and keep its presentation and interactions together.
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { useId, useRef } from "react";
import { Link } from "react-router-dom";
import { Bell, X } from "lucide-react";
import { useNotifications } from "../../context/NotificationContext";
import { notificationInboxPath } from "../../utils/notification";
import Popover from "../ui/Popover";
import NotificationItem from "./NotificationItem";

// Render the notification bell view interface and connect its controls to the state and callbacks defined here.
export function NotificationBellView({ state, actions, role }) {
  const { tr } = useAppTranslation();
  const trigger = useRef(null);
  const panelId = useId();
  const close = actions.closeDropdown;
  const known = state.count !== null && !state.countLoading && !state.countError && !state.authError;
  const label = state.authError ? tr("Notifications: access unavailable") : state.countLoading ? tr("Notifications: loading unread count") : known ? tr("Notifications: {{count}} unread", { count: state.count }) : tr("Notifications: unread count unavailable");
  const inboxPath = notificationInboxPath(role);
  return <div className="relative shrink-0">
    <button ref={trigger} type="button" onClick={actions.toggleDropdown} disabled={!!state.authError} aria-label={label} aria-expanded={state.open} aria-controls={state.open ? panelId : undefined} aria-haspopup="dialog" className="lp-notification-trigger relative flex h-10 w-10 items-center justify-center rounded-xl text-[#10243E] hover:bg-[#F5F8FC] focus-visible:outline-2 focus-visible:outline-[#12B8A6] disabled:opacity-50">
      <Bell size={21} aria-hidden="true" />
      {known && state.count > 0 && <span aria-hidden="true" className="absolute -right-1 -top-1 min-w-5 rounded-full bg-[#DC4545] px-1 text-center text-[10px] font-bold leading-5 text-white">{state.count > 99 ? "99+" : state.count}</span>}
      {state.countLoading && <span role="status" className="sr-only">{tr("Loading unread notification count...")}</span>}
      {!state.countLoading && (state.countError || state.authError) && <span className="absolute right-0 top-0 h-2 w-2 rounded-full bg-[#F5B544]" aria-hidden="true" />}
    </button>
    {(state.countError || state.authError) && <span className="sr-only" role="status">{tr(state.authError || state.countError)}</span>}
    <Popover open={state.open} onClose={close} triggerRef={trigger} id={panelId} label={tr("Recent notifications")} className="lp-notification-panel">
      <div className="flex items-center justify-between gap-3 border-b border-[#E8EEF5] p-4"><h3 className="font-bold text-[#10243E]">{tr("Notifications")}</h3><button type="button" aria-label={tr("Close notifications")} className="rounded p-1 text-[#587098] hover:bg-[#F5F8FC]" onClick={() => { close(); trigger.current?.focus(); }}><X size={18} /></button></div>
      {(state.countError || state.recentError || state.actionError) && <div role="alert" className="space-y-2 p-4 text-sm text-[#DC4545]"><p>{tr(state.recentError || state.actionError || state.countError)}</p><button type="button" className="font-semibold underline disabled:opacity-50" disabled={state.mutating || state.recentLoading} onClick={() => actions.refresh()}>{tr("Retry notifications")}</button></div>}
      {state.recentLoading && <p role="status" className="p-4 text-sm text-[#587098]">{tr("Loading recent notifications...")}</p>}
      {state.recent && (state.recent.notifications.length ? <ul aria-label={tr("Recent notification list")}>{state.recent.notifications.map(row => <NotificationItem key={row.notification_id} notification={row} role={role} busy={state.mutating} onRead={actions.markRead} compact onNavigate={close} />)}</ul> : <p className="p-6 text-center text-sm text-[#587098]">{tr("No notifications yet.")}</p>)}
      {inboxPath && <Link to={inboxPath} onClick={close} className="block border-t border-[#E8EEF5] p-4 text-center text-sm font-semibold text-[#087D78] hover:bg-[#F0FBF9]">{tr("View All Notifications")}</Link>}
    </Popover>
  </div>;
}
// Render the notification bell interface and connect its controls to the state and callbacks defined here.
export default function NotificationBell() {
  const context = useNotifications();
  return context ? <NotificationBellView {...context} /> : null;
}
