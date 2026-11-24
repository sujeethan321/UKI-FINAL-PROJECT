// Purpose: Render the admin dashboard screen and connect its user interactions to shared application state and services.
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { useEffect, useState, useSyncExternalStore } from 'react';
import { Link } from 'react-router-dom';
import { Users, Truck, Store, ShoppingBag, Package, RefreshCw, LoaderCircle, ArrowRight } from 'lucide-react';
import { useAuth } from '../../context/useAuth';
import { getAdminOverview, getRecentAdminActivity } from '../../services/adminDashboardService';
import { adminMetrics, adminActions, adminTimestamp, createAdminDashboardReader } from '../../utils/adminDashboard';

const card = 'min-w-0 rounded-2xl border border-[#D4E2EE] bg-white p-5 shadow-sm sm:p-6';
const button = 'inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-[#D4E2EE] bg-white px-4 py-2 text-sm font-semibold text-[#10243E] hover:border-[#12B8A6] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#12B8A6] disabled:cursor-wait disabled:opacity-50';
const icons = [Users, Users, Truck, Store, Truck, Store, ShoppingBag, Package];
// Render the loading interface and connect its controls to the state and callbacks defined here.
function Loading({ children }) {
  return <p role="status" className="flex items-center gap-2 py-4 text-sm text-[#64748B]"><LoaderCircle size={18} aria-hidden="true" className="animate-spin motion-reduce:animate-none" />{children}</p>;
}
// Render the failure interface and connect its controls to the state and callbacks defined here.
function Failure({ message, retry, label }) {
  const { tr } = useAppTranslation();
  return <div role="alert" className="my-4 space-y-3 border-l-4 border-[#DC4545] pl-3 text-sm"><p>{tr(message)}</p><button type="button" className={button} onClick={retry}>{tr("Retry")}{" "}{tr(label)}</button></div>;
}
// Render the count interface and connect its controls to the state and callbacks defined here.
function Count({ section, field }) {
  const { tr } = useAppTranslation();
  if (section.loading) return <span className="text-base font-medium text-[#64748B]">{tr("Loading…")}</span>;
  const value = section.data?.[field];
  return value === null || value === undefined ? <span className="text-base font-medium text-[#64748B]">{tr("Unavailable")}</span> : value.toLocaleString('en-LK');
}
// Render the admin dashboard view interface and connect its controls to the state and callbacks defined here.
export function AdminDashboardView({ state, actions }) {
  const { tr } = useAppTranslation();
  const { overview, activity, authError } = state;
  const busy = overview.loading || activity.loading;
  if (authError) return <div className="space-y-6 text-[#10243E]"><h2 className="text-2xl font-bold">{tr("Platform Dashboard")}</h2><p role="alert" className={card + ' border-l-4 border-l-[#DC4545]'}>{tr(authError)}</p></div>;
  return <div className="space-y-6 pb-6 text-[#10243E]">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0"><h2 className="text-2xl font-bold">{tr("Platform Dashboard")}</h2><p className="mt-2 text-sm text-[#64748B]">{tr("Monitor and manage LankaPex platform activity.")}</p></div>
      <button type="button" className={button} disabled={busy} onClick={actions.start}><RefreshCw size={17} aria-hidden="true" />{tr("Refresh dashboard")}</button>
    </div>
    <section aria-labelledby="platform-overview-heading" aria-busy={overview.loading}>
      <h2 id="platform-overview-heading" className="sr-only">{tr("Platform overview")}</h2>
      {overview.loading && <Loading>{tr("Loading platform summary…")}</Loading>}
      {overview.error && <Failure message={overview.error} retry={() => actions.load('overview')} label={tr("platform summary")} />}
      {overview.data && Object.values(overview.data).some(value => value === null) && <p role="status" className="mb-4 text-sm text-[#64748B]">{tr("Some metrics are unavailable. Available counts are shown below.")}</p>}
      <div className="grid min-w-0 gap-5 sm:grid-cols-2 xl:grid-cols-4">
        {adminMetrics.map(([field, label], index) => {
          const Icon = icons[index];
          return <article key={field} className={card}><div className="flex items-start justify-between gap-3"><h3 className="text-sm font-semibold">{tr(label)}</h3><span className="shrink-0 rounded-xl bg-[#E8F8F6] p-2 text-[#12B8A6]"><Icon size={20} aria-hidden="true" /></span></div><p className="mt-5 break-words text-3xl font-bold [overflow-wrap:anywhere]"><Count section={overview} field={field} /></p>{overview.data?.[field] === 0 && <p className="mt-2 text-xs text-[#64748B]">{field.startsWith('pending_') ? tr("No pending applications.") : tr("No records yet.")}</p>}</article>;
        })}
      </div>
      <p className="mt-3 text-xs text-[#64748B]">{tr("Platform totals include all account and lifecycle statuses. Approval counts reflect stored application status.")}</p>
    </section>
    <section className={card} aria-labelledby="pending-approvals-heading">
      <h2 id="pending-approvals-heading" className="text-xl font-bold">{tr("Pending Approvals")}</h2>
      <div className="mt-5 grid min-w-0 gap-5 md:grid-cols-2">
        <div className="min-w-0 rounded-xl bg-[#F5F8FC] p-4"><h3 className="font-semibold">{tr("Driver applications")}</h3><p className="my-3 break-words text-2xl font-bold [overflow-wrap:anywhere]"><Count section={overview} field="pending_driver_approvals" /></p>{overview.data?.pending_driver_approvals === 0 && <p className="mb-3 text-sm text-[#64748B]">{tr("No pending Driver applications.")}</p>}<Link to="/admin/drivers" className={button}>{tr("View Driver Applications")}<ArrowRight size={16} aria-hidden="true" /></Link></div>
        <div className="min-w-0 rounded-xl bg-[#F5F8FC] p-4"><h3 className="font-semibold">{tr("Business registrations")}</h3><p className="my-3 break-words text-2xl font-bold [overflow-wrap:anywhere]"><Count section={overview} field="pending_business_approvals" /></p>{overview.data?.pending_business_approvals === 0 && <p className="mb-3 text-sm text-[#64748B]">{tr("No pending Business registrations.")}</p>}<Link to="/admin/businesses" className={button}>{tr("View Business Applications")}<ArrowRight size={16} aria-hidden="true" /></Link></div>
      </div>
    </section>
    <section className={card} aria-labelledby="admin-navigation-heading">
      <h2 id="admin-navigation-heading" className="text-xl font-bold">{tr("Quick Navigation")}</h2>
      <div className="mt-5 grid min-w-0 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <Link to="/admin/businesses" className={button}>{tr("Business Approvals")}<ArrowRight size={16} aria-hidden="true" /></Link>
        <Link to="/admin/dashboard#recent-admin-activity" className={button}>{tr("Activity Logs")}<ArrowRight size={16} aria-hidden="true" /></Link>
        <Link to="/admin/notifications" className={button}>{tr("Notifications")}<ArrowRight size={16} aria-hidden="true" /></Link>
        {[['Shop Owners', '/admin/shop-owners'], ['Customers', '/admin/customers'], ['Delivery Drivers', '/admin/drivers']].map(([label, path]) => <Link key={path} to={path} className={button}>{tr(label)}<ArrowRight size={16} aria-hidden="true" /></Link>)}
        <Link to="/admin/reports" className={button}>{tr("Platform Reports")}<ArrowRight size={16} aria-hidden="true" /></Link>
      </div>
    </section>
    <section id="recent-admin-activity" className={card + ' scroll-mt-6'} aria-labelledby="recent-admin-activity-heading" aria-busy={activity.loading}>
      <h2 id="recent-admin-activity-heading" className="text-xl font-bold">{tr("Recent Administrative Activity")}</h2>
      {activity.loading ? <Loading>{tr("Loading recent activity…")}</Loading> : activity.error ? <Failure message={activity.error} retry={() => actions.load('activity')} label={tr("recent activity")} /> : activity.data ? <>
        {activity.data.events.length ? <ul className="mt-4 divide-y divide-[#D4E2EE]">{activity.data.events.map(row => {
          const stamp = adminTimestamp(row.created_at);
          return <li key={row.source + ':' + row.audit_id} className="grid min-w-0 gap-2 py-4 sm:grid-cols-[minmax(0,1fr)_auto]"><div className="min-w-0"><p className="break-words font-semibold">{tr(adminActions[row.action])}</p><p className="mt-1 break-words text-sm text-[#64748B]">{tr({ user: 'Account', driver: 'Driver', business: 'Business' }[row.target_type])} #{row.target_id}</p></div><div className="min-w-0 text-sm"><span className="inline-block rounded-full bg-[#22C55E]/10 px-2 py-1 text-xs font-semibold">{tr("Recorded")}</span><p className="mt-2 break-words text-xs text-[#64748B]"><time dateTime={stamp.iso}>{tr(stamp.label)}</time></p></div></li>;
        })}</ul> : <p className="py-6 text-sm text-[#64748B]">{tr("No administrative activity recorded yet.")}</p>}
        <p className="mt-3 text-xs text-[#64748B]">{tr("Showing {{shown}} of {{total}} recorded events, newest first.", { shown: activity.data.events.length, total: activity.data.total })}</p>
      </> : <p className="py-4 text-sm text-[#64748B]">{tr("Recent activity unavailable.")}</p>}
    </section>
  </div>;
}
// Render the admin session interface and connect its controls to the state and callbacks defined here.
function AdminSession() {
  const [reader] = useState(() => createAdminDashboardReader({ overview: getAdminOverview, activity: getRecentAdminActivity }));
  const state = useSyncExternalStore(reader.subscribe, reader.getSnapshot, reader.getSnapshot);
  // Start resource work after rendering and cancel or dispose it during cleanup so obsolete work cannot update this view.
  useEffect(() => { reader.start(); return () => reader.dispose(); }, [reader]);
  return <AdminDashboardView state={state} actions={reader} />;
}
// Render the admin dashboard interface and connect its controls to the state and callbacks defined here.
export default function AdminDashboard() {
  const { user, token, isAuthenticated } = useAuth();
  if (!isAuthenticated || user?.platform_role !== 'admin' || user.account_status !== 'active') return null;
  return <AdminSession key={user.user_id + ':' + token} />;
}
