// Purpose: Render the admin notifications screen and connect its user interactions to shared application state and services.
import NotificationInbox from "../../components/notifications/NotificationInbox";
// Render the admin notifications interface and connect its controls to the state and callbacks defined here.
export default function AdminNotifications() {
  return <div className="space-y-5 pb-8"><div><h2 className="text-[26px] font-extrabold text-[#10243E]">Notifications</h2><p className="text-sm text-[#587098]">Review notifications addressed to your administrator account.</p></div><NotificationInbox /></div>;
}
