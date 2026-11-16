import NotificationInbox from "../../components/customer/CustomerInbox";
export default function CustomerNotifications() {
  return <div className="space-y-5 pb-8"><div><h2 className="text-2xl font-bold text-[#10243E]">Notifications</h2><p className="mt-2 text-sm text-[#64748B]">Updates addressed to your customer account.</p></div><NotificationInbox /></div>;
}
