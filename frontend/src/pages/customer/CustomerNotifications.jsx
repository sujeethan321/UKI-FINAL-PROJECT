// Purpose: Render the customer notifications screen and connect its user interactions to shared application state and services.
import NotificationInbox from "../../components/customer/CustomerInbox";
// Render the customer notifications interface and connect its controls to the state and callbacks defined here.
export default function CustomerNotifications() {
  return <div className="space-y-5 pb-8"><div><h2 className="text-2xl font-bold text-[#10243E]">Notifications</h2><p className="mt-2 text-sm text-[#64748B]">Updates addressed to your customer account.</p></div><NotificationInbox /></div>;
}
