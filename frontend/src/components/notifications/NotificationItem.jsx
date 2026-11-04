import { Link } from "react-router-dom";
import { notificationDestination, notificationTime } from "../../utils/notification";

export default function NotificationItem({ notification, role, busy, onRead, compact = false, onNavigate }) {
  const time = notificationTime(notification.created_at);
  const destination = notificationDestination(notification, role);
  return <li className={"min-w-0 border-b border-[#E8EEF5] p-4 last:border-0 " + (notification.is_read ? "bg-white" : "bg-[#F0FBF9]")}>
    <div className="flex items-start justify-between gap-3"><h4 className="min-w-0 break-words text-sm font-semibold text-[#10243E]">{notification.title}</h4><span className={"shrink-0 rounded-full px-2 py-0.5 text-[11px] " + (notification.is_read ? "bg-[#EAF2F9] text-[#587098]" : "bg-[#E2F8F4] font-semibold text-[#087D78]")}>{notification.is_read ? "Read" : "Unread"}</span></div>
    <p className={"mt-1 whitespace-pre-wrap break-words text-sm text-[#526887] " + (compact ? "line-clamp-2" : "")}>{notification.message}</p>
    <time dateTime={notification.created_at} title={time.full} aria-label={time.full} className="mt-2 block text-xs text-[#64748B]">{time.relative}</time>
    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs font-semibold">
      {!notification.is_read && <button type="button" disabled={busy} onClick={() => onRead(notification.notification_id)} aria-label={"Mark as read: " + notification.title} className="rounded text-[#087D78] underline underline-offset-2 focus-visible:outline-2 focus-visible:outline-[#12B8A6] disabled:opacity-50">Mark as Read</button>}
      {destination && <Link to={destination.to} onClick={onNavigate} className="rounded text-[#1265D6] underline underline-offset-2">{destination.label}</Link>}
    </div>
  </li>;
}
