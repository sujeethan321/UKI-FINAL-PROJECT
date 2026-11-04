import NotificationInbox from "../../components/notifications/NotificationInbox";
export default function AdminNotifications() {
  return <div className="space-y-5 pb-8"><div><h2 className="text-[26px] font-extrabold text-[#10243E]">Notifications</h2><p className="text-sm text-[#587098]">Review notifications addressed to your administrator account.</p></div><NotificationInbox /></div>;
}
