// Purpose: Render the driver dashboard screen and connect its user interactions to shared application state and services.
import {money} from '../../utils/shopping';
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { DriverJobsPanel } from "./AvailableJobs";
import { Link } from "react-router-dom";
import { useEffect, useState, useSyncExternalStore } from 'react';
import { Wallet, Truck, CircleCheck, RefreshCw, LoaderCircle } from 'lucide-react';
import { useAuth } from '../../context/useAuth';
import { getDriverProfile, getDriverSummary, getDriverDeliveries } from '../../services/driverDashboardService';
import { createDriverDashboardReader, formatAssignedTime } from '../../utils/driverDashboard';

const card='min-w-0 rounded-2xl border border-[#D4E2EE] bg-white p-5 shadow-sm sm:p-6';
const button='inline-flex items-center gap-2 rounded-lg border border-[#DAE5F3] bg-white px-3 py-2 text-sm font-semibold text-[#36517B] focus-visible:outline-2 focus-visible:outline-[#12B8A6] disabled:opacity-50';
// Render the loading interface and connect its controls to the state and callbacks defined here.
function Loading({children}) {return <p role="status" className="flex items-center gap-2 py-5 text-sm text-[#64748B]"><LoaderCircle size={18} aria-hidden="true" className="animate-spin motion-reduce:animate-none"/>{children}</p>;}
// Render the error state interface and connect its controls to the state and callbacks defined here.
function ErrorState({message,retry,label}) {
  const { tr } = useAppTranslation();return <div role="alert" className="my-4 space-y-3 border-l-4 border-[#DC4545] pl-3 text-sm"><p>{tr(message)}</p><button type="button" className={button} onClick={retry}>{tr("Retry")}{" "}{tr(label)}</button></div>;}
// Render the driver dashboard view interface and connect its controls to the state and callbacks defined here.
export function DriverDashboardView({state,actions,displayName,availableOrders}) {
  const { tr } = useAppTranslation();
 const summary=state.summary.data,profile=state.profile.data,deliveries=state.deliveries.data;
 const busy=['profile','summary','deliveries'].some(key=>state[key].loading);
 const nextAssigned=deliveries?.deliveries.find(row=>row.status==='assigned');
 const stats=[['Completed Deliveries',summary?.completed_deliveries_count??'\u2014',CircleCheck,'All recorded delivered requests; today-only totals unavailable.'],['Active Deliveries',summary?.active_deliveries_count??'\u2014',Truck,'Your assigned, picked up and in-transit deliveries.'],["Today's Earnings",'Unavailable',Wallet,'Earnings accounting is not available.']];
 return <div className="space-y-6 pb-6"><div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0"><h2 className="text-2xl font-bold">{tr("Driver Dashboard")}</h2><p className="mt-2 text-sm text-[#64748B]">{tr("Manage your deliveries in one place.")}</p><p className="mt-3 break-words font-semibold">{displayName ? tr("Welcome, {{name}}!", { name: displayName }) : tr("Welcome!")}</p></div><button type="button" className={button} disabled={busy} onClick={actions.start}><RefreshCw size={17} aria-hidden="true"/>{tr("Refresh dashboard")}</button></div>
 {state.authError?<p role="alert" className={card+' border-l-4 border-l-[#DC4545]'}>{tr(state.authError)}</p>:<>
 <Link to="/driver/jobs" className={button}>{tr("View Available Jobs")}</Link>
 {profile?.approval_status==='not_submitted'&&!state.profile.loading&&<section className={card} aria-label={tr("Driver application")}><h2 className="text-xl font-bold">{tr("Submit Driver application")}</h2><Link to="/driver/vehicle" className={button}>{tr("Register Vehicle")}</Link></section>}
 <section aria-label={tr("Driver overview")}>{state.summary.loading&&<Loading>{tr("Loading delivery summary...")}</Loading>}{state.summary.error&&<ErrorState message={state.summary.error} retry={()=>actions.load('summary')} label={tr("delivery summary")}/>}<div className="grid min-w-0 gap-5 md:grid-cols-3">{stats.map(([label,value,Icon,description])=><article key={label} className={card}><div className="flex items-start justify-between gap-3"><h3 className="text-sm font-semibold">{tr(label)}</h3><span className="rounded-xl bg-[#E8F8F6] p-2 text-[#12B8A6]"><Icon size={20} aria-hidden="true"/></span></div><p className="mt-5 break-words text-2xl font-bold [overflow-wrap:anywhere]">{typeof value === "string" ? tr(value) : value}</p><p className="mt-2 text-xs text-[#64748B]">{value==='—'?tr("Data unavailable until this section loads."):tr(description)}</p></article>)}</div></section>
 <section className={card} aria-label={tr("Available orders preview")}><h2 className="text-xl font-bold">{tr("Available Orders")}</h2><p className="mt-2 text-sm text-[#52698A]">{tr("Delivery requests you can accept through the existing authorized workflow.")}</p><p className="mt-2 text-xs text-[#64748B]">{tr("Available Jobs:")}{" "}{summary?.available_jobs_count??tr("Unavailable")}{tr(". Fees and distances are not recorded.")}</p><div className="mt-4">{availableOrders||<Link to="/driver/jobs" className={button}>{tr("Review Available Jobs")}</Link>}</div></section>
 <section className={card} aria-label={tr("Next assigned delivery")}><h2 className="text-xl font-bold">{tr("Next Assigned Delivery")}</h2><p className="mt-2 text-xs text-[#64748B]">{tr("An assigned request from your latest assignment preview. No scheduled pickup time or priority is confirmed.")}</p>{nextAssigned?<div className="mt-4 grid items-center gap-4 rounded-lg border border-[#E1EAF4] p-4 sm:grid-cols-2"><div><p className="font-bold">{nextAssigned.reference}</p><p className="mt-1 text-sm">{nextAssigned.business_name}</p></div><div><p className="text-sm">{tr("Pickup:")}{" "}{nextAssigned.pickup_area}</p><p className="mt-1 text-sm">{tr("Drop-off:")}{" "}{nextAssigned.delivery_area}</p></div><Link to={'/driver/deliveries/'+nextAssigned.delivery_request_id} className={button}>{tr("View Delivery Details")}</Link></div>:<p className="mt-4 text-sm text-[#64748B]">{state.deliveries.loading?tr("Loading assignment preview..."):state.deliveries.error?tr("Assignment preview unavailable."):tr("No pending pickup in this preview.")}</p>}</section>

 <section id="active-deliveries" className={card+' scroll-mt-6'} aria-labelledby="active-deliveries-heading"><Link to="/driver/deliveries" className={button}>{tr("View My Deliveries")}</Link><h2 id="active-deliveries-heading" className="text-xl font-bold">{tr("Active Deliveries")}</h2>{state.deliveries.loading?<Loading>{tr("Loading assigned deliveries...")}</Loading>:state.deliveries.error?<ErrorState message={state.deliveries.error} retry={()=>actions.load('deliveries')} label={tr("assigned deliveries")}/>:deliveries?<>{deliveries.deliveries.length?<ul className="mt-4 divide-y divide-[#D4E2EE]">{deliveries.deliveries.map(row=><li key={row.delivery_request_id} className="grid min-w-0 gap-3 py-4 sm:grid-cols-[minmax(0,1fr)_auto]"><div className="min-w-0"><p className="break-all font-semibold">{row.reference}</p><p className="mt-1 break-words text-sm">{row.business_name}</p><dl className="mt-3 space-y-2 text-sm"><div><dt className="text-[#64748B]">{tr("Pickup area")}</dt><dd className="break-words">{row.pickup_area}</dd></div><div><dt className="text-[#64748B]">{tr("Delivery area")}</dt><dd className="break-words">{row.delivery_area}</dd></div><div><dt className="text-[#64748B]">{tr('Estimated Delivery Earning')}</dt><dd>{row.estimated_delivery_earning!==null&&row.estimated_delivery_earning!==undefined?money(row.estimated_delivery_earning):tr('Unavailable')}</dd></div></dl><p className="mt-2 text-xs text-[#64748B]">{tr('3% of this linked order subtotal. Estimate only; not credited, collected or paid.')}</p><p className="mt-3 text-xs text-[#64748B]">{tr("Assigned:")}{" "}<time dateTime={row.assigned_at+'Z'}>{formatAssignedTime(row.assigned_at)}</time></p></div><p><span className="rounded-full bg-[#12B8A6]/10 px-3 py-1 text-xs font-semibold">{tr({assigned:'Assigned',picked_up:'Picked up',in_transit:'In transit'}[row.status])}</span></p></li>)}</ul>:<p className="py-6 text-sm text-[#64748B]">{tr("No active deliveries yet.")}</p>}<p className="mt-4 text-xs text-[#64748B]">{tr("Showing {{shown}} of {{total}} active deliveries, newest assignments first.", { shown: deliveries.deliveries.length, total: deliveries.total })}</p></>:<p className="py-4 text-sm">{tr("Assigned deliveries unavailable.")}</p>}</section>
 </>}
 </div>;
}
// Render the driver session interface and connect its controls to the state and callbacks defined here.
function DriverSession({userId,displayName}) {
 const [reader]=useState(()=>createDriverDashboardReader({profile:getDriverProfile,summary:getDriverSummary,deliveries:getDriverDeliveries},userId));
 const state=useSyncExternalStore(reader.subscribe,reader.getSnapshot,reader.getSnapshot);
 // Start resource work after rendering and cancel or dispose it during cleanup so obsolete work cannot update this view.
 useEffect(()=>{reader.start();return()=>reader.dispose();},[reader]);
 return <DriverDashboardView state={state} actions={reader} displayName={displayName} availableOrders={<DriverJobsPanel userId={userId} embedded onAssigned={reader.start}/>}/>;
}
// Render the driver dashboard interface and connect its controls to the state and callbacks defined here.
export default function DriverDashboard() {
 const {user,token,isAuthenticated}=useAuth();
 if(!isAuthenticated||user?.platform_role!=='driver'||user.account_status!=='active')return null;
 return <DriverSession key={user.user_id+':'+token} userId={user.user_id} displayName={user.full_name}/>;
}
