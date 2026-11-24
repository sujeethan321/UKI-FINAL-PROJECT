// Purpose: Render the admin businesses screen and connect its user interactions to shared application state and services.
import AdminManagement from './AdminManagement';

// Render the admin businesses interface and connect its controls to the state and callbacks defined here.
export default function AdminBusinesses() {
  return <AdminManagement kind="business" />;
}
