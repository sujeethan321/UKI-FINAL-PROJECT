// Purpose: Render the driver notifications screen and connect its user interactions to shared application state and services.
import NotificationInbox from '../../components/driver/DriverInbox';
// Render the driver notifications interface and connect its controls to the state and callbacks defined here.
export default function DriverNotifications() {
 return <div className="space-y-5"><div><h2>Notifications</h2><p className="mt-2 text-sm text-[#52698A]">Updates addressed to your Driver account.</p></div><NotificationInbox /></div>;
}
