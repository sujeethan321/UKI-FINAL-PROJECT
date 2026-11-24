// Purpose: Render the driver deliveries screen and connect its user interactions to shared application state and services.
import {Destination} from '../../components/customer/CustomerAddresses';
import Select from "../../components/ui/Select";
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import {useEffect,useState,useSyncExternalStore} from 'react';
import DeliveryTimeline from '../../components/delivery/DeliveryTimeline';
import {Link,useParams,useSearchParams} from 'react-router-dom';
import {useAuth} from '../../context/useAuth';
import {getDriverProfile,getDriverSummary} from '../../services/driverDashboardService';
import {listDriverDeliveries,readDriverDelivery,updateDriverDelivery} from '../../services/driverDeliveriesService';
import {createDeliveriesWorkflow,deliveryLabels,deliveryActions} from '../../utils/driverDeliveries';
import {driverEligibilityMessages,formatAssignedTime} from '../../utils/driverDashboard';

const card='min-w-0 rounded-2xl border border-[#D4E2EE] bg-white p-5 shadow-sm sm:p-6';
const button='inline-flex min-h-11 items-center justify-center rounded-lg border border-[#DAE5F3] px-4 py-2 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-[#12B8A6] disabled:opacity-50';
// Render the status interface and connect its controls to the state and callbacks defined here.
function Status({value}) {
  const { tr } = useAppTranslation();return <span className={'inline-block rounded-full px-3 py-1 text-xs font-semibold '+(value==='delivered'?'bg-[#22C55E]/10':value==='cancelled'?'bg-[#DC4545]/10':'bg-[#12B8A6]/10')}>{tr(deliveryLabels[value])}</span>;}
// Render the recorded time interface and connect its controls to the state and callbacks defined here.
function RecordedTime({value}) {
  const { tr } = useAppTranslation();return value?<time dateTime={value+'Z'}>{formatAssignedTime(value)}</time>:<>{tr("Date not recorded")}</>;}
// Render the driver deliveries view interface and connect its controls to the state and callbacks defined here.
export function DriverDeliveriesView({state,actions,history=false,detail=false,initialQuery='',embedded=false}) {
  const { tr } = useAppTranslation();
  const [confirm,setConfirm]=useState(false),[selected,setSelected]=useState(null),[query,setQuery]=useState(initialQuery),[sort,setSort]=useState('newest');
  const rows=(state.list.data?.deliveries||[]).filter(row=>[row.reference,row.business_name,row.pickup_area,row.delivery_area].some(value=>value.toLowerCase().includes(query.toLowerCase()))).toSorted((a,b)=>(sort==='oldest'?1:-1)*((a.assigned_at||'').localeCompare(b.assigned_at||'')||a.delivery_request_id-b.delivery_request_id));
  const title=detail?'Delivery Details':history?'Delivery History':'My Deliveries';
  const row=state.detail.data?.delivery,next=state.detail.data?.allowed_next_status;
  const eligible=state.profile.data?.eligible_for_jobs;
  const loading=state.busy||['profile','summary',detail?'detail':'list'].some(key=>state[key].loading);
  return <div className="space-y-6 pb-6">{!embedded&&<div className="flex flex-wrap items-start justify-between gap-4"><div><h2 className="text-2xl font-bold">{tr(title)}</h2><p className="mt-2 text-sm text-[#64748B]">{history?tr("Your completed and cancelled deliveries."):tr("Manage deliveries assigned to your Driver account.")}</p></div><button type="button" className={button} disabled={loading} onClick={()=>{setConfirm(false);actions.refresh();}}>{tr("Refresh")} {detail?tr("details"):tr("deliveries")}</button></div>}
    {state.authError?<p role="alert" className={card}>{tr(state.authError)}</p>:<>
    <div className="flex flex-wrap gap-3"><Link className={button} to="/driver/dashboard">{tr("Dashboard")}</Link><Link className={button} to={history?"/driver/deliveries":"/driver/history"}>{history?tr("My Deliveries"):tr("Delivery History")}</Link></div>
    {state.profile.error&&<p role="alert">{tr(state.profile.error)}</p>}
    {state.profile.data&&!eligible&&<p className="rounded-xl bg-[#F5B544]/15 p-4 text-sm">{tr(driverEligibilityMessages[state.profile.data.eligibility_reason])} {tr("Status updates are unavailable.")}</p>}
    {state.summary.data&&<p className="text-sm text-[#64748B]">{tr("Active deliveries:")} {state.summary.data.active_deliveries_count} {tr("· Completed deliveries:")} {state.summary.data.completed_deliveries_count}</p>}
    {state.summary.error&&<p role="alert">{tr("Delivery counts are unavailable. Refresh to retry.")}</p>}
    {state.message&&<p role={state.uncertain?"alert":"status"} className={card}>{tr(state.message)}</p>}
    {detail?<section className={card} aria-label={tr("Delivery details")}>
      {state.detail.loading?<p role="status">{tr("Loading delivery details...")}</p>:state.detail.error?<p role="alert">{tr(state.detail.error)}</p>:row?<>
      <div className="flex flex-wrap items-start justify-between gap-3"><h3 className="break-all text-xl font-bold">{row.reference}</h3><Status value={row.status}/></div>
      <dl className="mt-5 grid min-w-0 gap-5 sm:grid-cols-2">{[['Requesting shop',row.business_name],['Pickup area',row.pickup_area],['Delivery area',row.delivery_area],['Assigned Driver',state.profile.data?.full_name||tr("Your Driver account")]].map(([label,value])=><div className="min-w-0" key={label}><dt className="text-sm text-[#64748B]">{tr(label)}</dt><dd className="mt-1 break-words font-semibold">{value}</dd></div>)}</dl>
      <p className="mt-5 text-sm">{tr("Assigned:")} <RecordedTime value={row.assigned_at}/></p>
      <Destination value={row.destination}/><DeliveryTimeline status={row.status} events={state.detail.data.events}/>
      {!row.destination&&<p className="mt-3 text-xs text-[#64748B]">{tr("Only recorded events are shown. Earlier progress dates may be unavailable. Precise addresses, customer contacts, vehicle requirements and operational instructions are not stored in this delivery record.")}</p>}
      {next&&eligible&&!state.uncertain&&<div className="mt-6">{confirm&&next==='delivered'?<div role="group" aria-label={tr("Confirm delivery completion")} className="space-y-3 rounded-xl bg-[#F5F8FC] p-4"><p>{tr("Confirm this delivery has reached its destination?")}</p><div className="flex flex-wrap gap-3"><button type="button" className={button+' bg-[#12B8A6] text-[#10243E]'} disabled={state.busy} onClick={()=>{setConfirm(false);actions.update();}}>{tr("Confirm Delivered")}</button><button type="button" className={button} disabled={state.busy} onClick={()=>setConfirm(false)}>{tr("Cancel")}</button></div></div>:<button type="button" className={button+' bg-[#12B8A6] text-[#10243E]'} disabled={state.busy||state.profile.loading} onClick={()=>next==='delivered'?setConfirm(true):actions.update()}>{state.busy?tr("Updating delivery..."):tr(deliveryActions[next])}</button>}</div>}
      {['delivered','cancelled'].includes(row.status)&&<p className="mt-5 text-sm">{tr("This delivery is")} {tr(deliveryLabels[row.status].toLowerCase())}{tr(". No further status updates are permitted.")}</p>}
      </>:<p className="py-5 text-sm">{tr("Refresh details to check the recorded delivery status.")}</p>}
    </section>:<section className={card} aria-label={tr(title)}>
      <h3 className="mb-4 text-xl font-bold">{history?tr("Completed & Cancelled Deliveries"):tr("Assigned Deliveries")}</h3><div role="group" aria-label={tr("Delivery status tabs")} className="mb-4 flex flex-wrap gap-2 border-b border-[#E1EAF4] pb-4">{(history?['','delivered','cancelled']:['','assigned','picked_up','in_transit']).map(value=><button type="button" key={value} disabled={state.list.loading} aria-pressed={state.status===value} onClick={()=>actions.filter(value)} className={'rounded-lg px-4 py-2 text-sm '+(state.status===value?'bg-[#E7F9F6] font-semibold text-[#008C87]':'text-[#52698A]')}>{value?tr(deliveryLabels[value]):history?tr("All final statuses"):tr("All active statuses")}</button>)}{!history&&<Link className={button} to="/driver/history">{tr("Completed & Cancelled")}</Link>}</div><div className="mb-4 grid gap-3 sm:grid-cols-2"><label className="text-sm">{tr("Search this page")}<input type="search" maxLength={200} value={query} onChange={e=>setQuery(e.target.value)} className="mt-2 w-full rounded-lg border border-[#DAE5F3] px-3 py-2" placeholder={tr("Request ID, shop or area...")}/></label><label className="text-sm">{tr("Sort this page")}<Select className="mt-2 w-full rounded-lg border border-[#DAE5F3] px-3 py-2" value={sort} onChange={e=>setSort(e.target.value)}><option value="newest">{tr("Newest First")}</option><option value="oldest">{tr("Oldest First")}</option></Select></label></div>
      <label className="block text-sm font-semibold" htmlFor="delivery-status">{tr("Filter by status")}</label><Select id="delivery-status" value={state.status} disabled={state.list.loading} onChange={event=>actions.filter(event.target.value)} className="mt-2 min-h-11 max-w-full rounded-lg border border-[#D4E2EE] bg-white px-3"><option value="">{history?tr("All final statuses"):tr("All active statuses")}</option>{(history?['delivered','cancelled']:['assigned','picked_up','in_transit']).map(status=><option key={status} value={status}>{tr(deliveryLabels[status])}</option>)}</Select>
      {state.list.loading?<p role="status" className="py-5">{tr("Loading deliveries...")}</p>:state.list.error?<p role="alert" className="py-5">{tr(state.list.error)}</p>:state.list.data?<>
      {state.list.data.deliveries.length?<div className="driver-table-wrap"><table><thead><tr>{['Shop / Request','Pickup','Drop-off','Status','Action'].map(label=><th key={label}>{tr(label)}</th>)}</tr></thead><tbody>{rows.map(delivery=><tr key={delivery.delivery_request_id}><td><h3 className="break-words font-bold">{delivery.business_name}</h3><p className="mt-1 break-all text-xs text-[#64748B]">{delivery.reference}</p><p className="mt-2 text-xs text-[#64748B]">{tr("Assigned:")} <RecordedTime value={delivery.assigned_at}/></p>{history&&<p className="mt-2 text-xs text-[#64748B]">{tr(deliveryLabels[delivery.status])}: <RecordedTime value={delivery.finished_at}/></p>}</td><td className="max-w-48 break-words">{delivery.pickup_area}</td><td className="max-w-48 break-words">{delivery.delivery_area}</td><td><Status value={delivery.status}/></td><td><div className="flex flex-wrap gap-2"><button type="button" className={button} onClick={()=>setSelected(delivery.delivery_request_id)}>{tr("View Details")}</button><Link className={button} to={'/driver/deliveries/'+delivery.delivery_request_id}>{!history&&eligible?tr("{{action}} ? Details", { action: tr(deliveryActions[{assigned:"picked_up",picked_up:"in_transit",in_transit:"delivered"}[delivery.status]]) }):tr("Open Details")}</Link></div></td></tr>)}</tbody></table>{!rows.length&&<p className="py-5 text-sm text-[#64748B]">{tr("No deliveries match on this page.")}</p>}</div>:<p className="py-6 text-sm text-[#64748B]">{history?tr("No completed or cancelled deliveries match this filter."):tr("No assigned deliveries match this filter.")}</p>}
      <div className="mt-5 flex flex-wrap items-center gap-3"><button className={button} type="button" disabled={state.page===1} onClick={()=>actions.page(state.page-1)}>{tr("Previous")}</button><p className="text-sm">{tr("Page")} {state.page} · {state.list.data.total} {tr("deliveries")}</p><button className={button} type="button" disabled={state.page*10>=state.list.data.total} onClick={()=>actions.page(state.page+1)}>{tr("Next")}</button></div></>:null}
    </section>}
    {!detail&&selected&&state.profile.data&&<DeliverySession key={selected} userId={state.profile.data.driver_user_id} history={history} deliveryId={selected} embedded onConfirmed={actions.refresh}/>}
    </>}
  </div>;
}
// Render the delivery session interface and connect its controls to the state and callbacks defined here.
function DeliverySession({userId,history,deliveryId,initialQuery='',embedded=false,onConfirmed}) {
  const [workflow]=useState(()=>createDeliveriesWorkflow({profile:getDriverProfile,summary:getDriverSummary,list:listDriverDeliveries,detail:readDriverDelivery,update:updateDriverDelivery},userId,{history,deliveryId}));
  const state=useSyncExternalStore(workflow.subscribe,workflow.getSnapshot,workflow.getSnapshot);
  // Start resource work after rendering and cancel or dispose it during cleanup so obsolete work cannot update this view.
  useEffect(()=>{workflow.start();return()=>workflow.dispose();},[workflow]);
  return <DriverDeliveriesView state={state} actions={onConfirmed?{...workflow,/* Apply a draft or state update through the rules of this workflow. */ async update(){const result=await workflow.update();if(result)onConfirmed();return result;}}:workflow} history={history} detail={deliveryId!==null} initialQuery={initialQuery} embedded={embedded}/>;
}
// Render the driver deliveries interface and connect its controls to the state and callbacks defined here.
export default function DriverDeliveries({history=false,detail=false}) {
  const { tr } = useAppTranslation();
  const {user,token,isAuthenticated}=useAuth(),{deliveryId}=useParams(),[search]=useSearchParams();
  const initialQuery=(search.get('q')||'').slice(0,200);
  if(!isAuthenticated||user?.platform_role!=='driver'||user.account_status!=='active')return null;
  const id=detail?Number(deliveryId):null;
  if(detail&&(!/^\d+$/.test(deliveryId)||!Number.isSafeInteger(id)||id<1))return <p role="alert">{tr("Invalid delivery ID.")}</p>;
  return <DeliverySession key={user.user_id+':'+token+':'+history+':'+id+':'+initialQuery} userId={user.user_id} history={history} deliveryId={id} initialQuery={initialQuery}/>;
}
