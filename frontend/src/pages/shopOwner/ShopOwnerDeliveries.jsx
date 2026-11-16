import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import {useEffect,useState,useSyncExternalStore} from 'react';
import {Link,useSearchParams} from 'react-router-dom';
import DeliveryTimeline from '../../components/delivery/DeliveryTimeline';
import {Truck,Package,CheckCircle,RefreshCw,Plus} from 'lucide-react';
import {useAuth} from '../../context/useAuth';
import {getDeliveryBusinesses,listShopDeliveries,getShopDeliverySummary,getShopDelivery,createShopDelivery,cancelShopDelivery} from '../../services/shopOwnerDeliveryService';
import {createShopDeliveryWorkflow,shopDeliveryLabels} from '../../utils/shopOwnerDeliveries';
import {formatAssignedTime} from '../../utils/driverDashboard';

const card='min-w-0 rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm sm:p-5';
const button='inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-[#DAE5F3] bg-white px-4 py-2 text-sm font-semibold text-[#10243E] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#12B8A6] disabled:opacity-50';
const field='mt-1.5 w-full rounded-lg border border-[#DAE5F3] bg-white px-3 py-2.5 text-sm text-[#10243E] outline-none focus:border-[#12B8A6] focus:ring-2 focus:ring-[#12B8A6]/15 disabled:opacity-50';
function Badge({status}) {
  const { tr } = useAppTranslation();return <span className={'inline-block rounded-full px-3 py-1 text-xs font-semibold '+(status==='delivered'?'bg-[#22C55E]/10 text-[#10243E]':status==='cancelled'?'bg-[#DC4545]/10 text-[#DC4545]':status==='available'?'bg-[#F5B544]/15 text-[#10243E]':'bg-[#12B8A6]/10 text-[#10243E]')}>{tr(shopDeliveryLabels[status])}</span>;}
function RecordedTime({value}) {return <time dateTime={value+'Z'}>{formatAssignedTime(value)}</time>;}
export function ShopOwnerDeliveriesView({state,actions}) {
  const { tr } = useAppTranslation();
  const business=state.businesses.find(b=>b.business_id===state.businessId),approved=business?.approval_status==='approved';
  const detail=state.detail.data,summary=state.summary.data;
  const blocked=state.busy||state.contextLoading||!approved||!!state.contextError;
  const stats=[['Total Requests','total_requests_count',Package],['Available Requests','available_requests_count',Package],['In Progress','in_progress_count',Truck],['Completed','completed_count',CheckCircle]];
  return <div className="space-y-6 pb-6 text-[#10243E]">
    <div className="flex flex-wrap items-start justify-between gap-4"><div className="min-w-0"><h2 className="text-2xl font-bold">{tr("Delivery Management")}</h2><p className="mt-2 text-sm text-[#64748B]">{tr("Create delivery requests and track your shop's deliveries.")}</p></div><button type="button" className={button} disabled={state.busy||state.contextLoading} onClick={state.authError?actions.start:actions.refresh}><RefreshCw size={17} aria-hidden="true"/>{tr("Refresh deliveries")}</button></div>
    {state.authError?<p role="alert" className={card+' border-l-4 border-l-[#DC4545]'}>{tr(state.authError)}</p>:<>
    <div className={card}><label htmlFor="delivery-business" className="text-sm font-semibold">{tr("Business")}</label><select id="delivery-business" value={state.businessId??''} disabled={state.busy||state.contextLoading||!state.businesses.length} onChange={event=>actions.selectBusiness(Number(event.target.value))} className={field}>{!state.businesses.length&&<option value="">{tr("No linked businesses")}</option>}{state.businesses.map(row=><option key={row.business_id} value={row.business_id}>{row.business_name} ({tr(row.approval_status)})</option>)}</select></div>
    {state.contextLoading&&<p role="status">{tr("Loading business information...")}</p>}
    {state.contextError&&<p role="alert" className={card}>{tr(state.contextError)}</p>}
    {!state.contextLoading&&!state.contextError&&!business&&<p className={card}>{tr("No business is linked to your account.")} <Link className="font-semibold text-[#12B8A6] underline" to="/shop-owner/business/register">{tr("Register a business")}</Link> {tr("first.")}</p>}
    {business&&!approved&&<p className={card+' bg-[#F5B544]/10'}>{tr("Business approval is required to manage delivery requests. Current status:")} <strong>{tr(business.approval_status)}</strong>.</p>}
    {approved&&!state.contextError&&<>
      <section aria-label={tr("Delivery summary")} className="grid min-w-0 gap-4 sm:grid-cols-2 xl:grid-cols-4">{stats.map(([label,key,Icon])=><article className={card} key={key}><div className="flex items-start justify-between gap-3"><h3 className="text-sm font-semibold text-[#64748B]">{tr(label)}</h3><Icon size={21} className="shrink-0 text-[#12B8A6]" aria-hidden="true"/></div><p className="mt-4 break-words text-2xl font-bold [overflow-wrap:anywhere]">{summary?.[key]??'—'}</p></article>)}</section>
      {state.summary.loading&&<p role="status">{tr("Loading delivery summary...")}</p>}{state.summary.error&&<p role="alert">{tr("Summary unavailable. Refresh to retry.")}</p>}
      {state.storageError&&<p role="alert" className={card+' border-l-4 border-l-[#DC4545]'}>{tr(state.storageError)}</p>}
      {state.uncertain&&<section role="alert" className={card+' space-y-3 border-l-4 border-l-[#F5B544]'}><p>{tr("A previous creation attempt is unconfirmed. Do not submit it again yet. Refresh and review your requests. An earlier request may still finish after a refresh.")}</p><div className="flex flex-wrap gap-3"><button type="button" className={button} disabled={state.busy} onClick={actions.reviewUncertain}>{tr("Refresh requests for review")}</button><button type="button" className={button} disabled={!state.reviewed||state.busy} onClick={actions.acknowledge}>{tr("I reviewed requests; start a new request")}</button></div></section>}
      {state.error&&<p role="alert" className={card+' border-l-4 border-l-[#DC4545]'}>{tr(state.error)}</p>}
      {state.message&&<p role="status" className={card+' border-l-4 border-l-[#22C55E]'}>{tr(state.message)}</p>}

      <section className={card} aria-labelledby="delivery-list-heading"><div className="flex flex-wrap items-end justify-between gap-4"><h3 id="delivery-list-heading" className="text-lg font-bold">{tr("My Delivery Requests")}</h3><div><label htmlFor="shop-delivery-status" className="text-sm font-semibold">{tr("Filter by status")}</label><select id="shop-delivery-status" value={state.status} disabled={state.busy||state.list.loading} onChange={event=>actions.filter(event.target.value)} className={field}><option value="">{tr("All statuses")}</option>{Object.entries(shopDeliveryLabels).map(([value,label])=><option key={value} value={value}>{tr(label)}</option>)}</select></div></div>
      {state.list.loading?<p role="status" className="py-6">{tr("Loading delivery requests...")}</p>:state.list.error?<p role="alert" className="py-6">{tr(state.list.error)}</p>:state.list.data?<>
        {state.list.data.deliveries.length?<div className="owner-table-wrap"><table className="owner-table" aria-label={tr("Delivery Management")}><thead><tr>{['Delivery ID','Pickup area','Destination area','Created','Status','Action'].map(label=><th key={label}>{tr(label)}</th>)}</tr></thead><tbody>{state.list.data.deliveries.map(row=><tr key={row.delivery_request_id} aria-selected={state.detail.id===row.delivery_request_id}><td className="font-semibold">{row.reference}</td><td className="max-w-48 break-words">{row.pickup_area}</td><td className="max-w-48 break-words">{row.delivery_area}</td><td><RecordedTime value={row.created_at}/></td><td><Badge status={row.status}/></td><td><button className={button} type="button" disabled={state.busy} onClick={()=>actions.details(row.delivery_request_id)}>{tr("View Details")}</button></td></tr>)}</tbody></table></div>:<p className="py-6 text-sm text-[#64748B]">{state.list.data.total?tr("No requests on this page. Use Previous to return."):tr("No delivery requests match this filter.")}</p>}
        <div className="mt-5 flex flex-wrap items-center gap-3"><button className={button} type="button" disabled={state.busy||state.page===1} onClick={()=>actions.page(state.page-1)}>{tr("Previous")}</button><p className="text-sm">{tr("Page")} {state.page} · {state.list.data.total} {tr("requests")}</p><button className={button} type="button" disabled={state.busy||state.page*10>=state.list.data.total} onClick={()=>actions.page(state.page+1)}>{tr("Next")}</button></div>
      </>:null}</section>
      {state.detail.id&&<section className={card} aria-labelledby="shop-delivery-detail-heading"><div className="flex flex-wrap items-start justify-between gap-3"><h3 id="shop-delivery-detail-heading" className="text-lg font-bold">{tr("Delivery Request Details")}</h3><button type="button" className={button} disabled={state.busy} onClick={actions.closeDetails}>{tr("Close details")}</button></div>
        {state.detail.loading?<p role="status" className="py-5">{tr("Loading delivery details...")}</p>:state.detail.error?<p role="alert" className="py-5">{tr(state.detail.error)}</p>:detail?<><div className="mt-4 flex flex-wrap items-center justify-between gap-3"><p className="break-all font-bold">{detail.reference}</p><Badge status={detail.status}/></div><dl className="mt-5 grid min-w-0 gap-4 sm:grid-cols-2">{[['Business',business.business_name],['Pickup area',detail.pickup_area],['Destination area',detail.delivery_area],['Assigned Driver',detail.assigned_driver?.full_name||tr("Not assigned")]].map(([label,value])=><div className="min-w-0" key={label}><dt className="text-sm text-[#64748B]">{tr(label)}</dt><dd className="mt-1 break-words font-semibold">{value}</dd></div>)}</dl><p className="mt-4 text-sm">{tr("Created:")} <RecordedTime value={detail.created_at}/></p><p className="mt-2 text-sm">{tr("Updated:")} <RecordedTime value={detail.updated_at}/></p><DeliveryTimeline status={detail.status} events={detail.events}/>
        {detail.can_cancel&&<div className="mt-6">{state.confirmCancel?<div role="group" aria-label={tr("Confirm request cancellation")} className="space-y-3 rounded-lg bg-[#F5F8FC] p-4"><p>{tr("Cancel this unassigned delivery request?")}</p><div className="flex flex-wrap gap-3"><button type="button" className={button+' text-[#DC4545]'} disabled={state.busy} onClick={actions.cancel}>{tr("Confirm Cancellation")}</button><button type="button" className={button} disabled={state.busy} onClick={()=>actions.confirmCancel(false)}>{tr("Keep Request")}</button></div></div>:<button type="button" className={button+' text-[#DC4545]'} disabled={state.busy} onClick={()=>actions.confirmCancel(true)}>{tr("Cancel Request")}</button>}</div>}
        {!detail.can_cancel&&<p className="mt-5 text-sm text-[#64748B]">{tr("Cancellation is unavailable for this recorded status.")}</p>}
        </>:null}</section>}
      <section className={card} aria-labelledby="new-delivery-heading"><h3 id="new-delivery-heading" className="text-lg font-bold">{tr("New Delivery Request")}</h3><form className="mt-4 space-y-4" onSubmit={event=>{event.preventDefault();actions.create();}}><div className="grid min-w-0 gap-4 md:grid-cols-2"><div className="min-w-0"><label htmlFor="delivery-pickup" className="text-sm font-semibold">{tr("Pickup area")}</label><input id="delivery-pickup" name="pickup_area" required maxLength={160} value={state.form.pickup_area} disabled={blocked||state.uncertain||!!state.storageError} onChange={event=>actions.edit('pickup_area',event.target.value)} placeholder={tr("Enter the pickup area")} className={field}/></div><div className="min-w-0"><label htmlFor="delivery-destination" className="text-sm font-semibold">{tr("Delivery destination")}</label><input id="delivery-destination" name="delivery_area" required maxLength={160} value={state.form.delivery_area} disabled={blocked||state.uncertain||!!state.storageError} onChange={event=>actions.edit('delivery_area',event.target.value)} placeholder={tr("Enter the destination area")} className={field}/></div></div><p className="text-xs text-[#64748B]">{tr("Use area names only. Do not include private addresses or contact details in Driver job previews.")}</p><button type="submit" disabled={blocked||state.uncertain||!!state.storageError} className={button+' border-[#12B8A6] bg-[#12B8A6]'}><Plus size={17} aria-hidden="true"/>{state.busy?tr("Saving delivery..."):tr("Create Delivery Request")}</button></form></section>
    </>}
    </>}
  </div>;
}
function DeliverySession({userId,businessId,deliveryId}) {
  const [workflow]=useState(()=>createShopDeliveryWorkflow({businesses:getDeliveryBusinesses,list:listShopDeliveries,summary:getShopDeliverySummary,detail:getShopDelivery,create:createShopDelivery,cancel:cancelShopDelivery},userId));
  const state=useSyncExternalStore(workflow.subscribe,workflow.getSnapshot,workflow.getSnapshot);
  useEffect(()=>{let active=true;
    void (async()=>{await workflow.start();if(!active)return;
      if(Number.isSafeInteger(businessId)&&businessId>0)await workflow.selectBusiness(businessId);
      if(active&&workflow.getSnapshot().businessId===businessId&&Number.isSafeInteger(deliveryId)&&deliveryId>0)await workflow.details(deliveryId);
    })();return()=>{active=false;workflow.dispose();};},[workflow,businessId,deliveryId]);
  return <ShopOwnerDeliveriesView state={state} actions={workflow}/>;
}
export default function ShopOwnerDeliveries() {
  const {user,token,isAuthenticated}=useAuth();
  const [params]=useSearchParams(),businessId=Number(params.get("business_id")),deliveryId=Number(params.get("delivery_id"));
  if(!isAuthenticated||user?.platform_role!=='shop_owner'||user.account_status!=='active')return null;
  return <DeliverySession key={user.user_id+':'+token+':'+businessId+':'+deliveryId} userId={user.user_id} businessId={businessId} deliveryId={deliveryId}/>;
}
