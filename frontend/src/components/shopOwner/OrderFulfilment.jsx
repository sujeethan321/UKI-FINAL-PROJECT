// Purpose: Render the reusable order fulfilment interface and keep its presentation and interactions together.
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import {useEffect,useState,useSyncExternalStore} from 'react';
import {Link} from 'react-router-dom';
import {ownerOrderDelivery,requestOrderDelivery,orderDetail} from '../../services/orderService';
import {createOrderFulfilment} from '../../utils/orderFulfilment';
import {orderCard as card,orderButton as button,orderField as field} from '../../utils/shopping';
import {formatAssignedTime} from '../../utils/driverDashboard';
import DeliveryTimeline from '../delivery/DeliveryTimeline';

// Render the order fulfilment view interface and connect its controls to the state and callbacks defined here.
export function OrderFulfilmentView({state,actions,businessId,compact=false}) {
  const { tr } = useAppTranslation();
 const data=state.data,delivery=data?.delivery;
 return <section className={card+' space-y-4'} aria-label={tr("Order delivery")}>
  <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="font-bold">{tr("Delivery")}</h3><button type="button" className={button} disabled={state.busy||state.loading} onClick={actions.refresh}>{tr("Refresh delivery")}</button></div>
  {state.loading&&<p role="status">{tr("Loading delivery eligibility and progress...")}</p>}
  {state.error&&<p role="alert" className="break-words text-[#DC4545]">{tr(state.error)}</p>}
  {state.message&&<p role="status">{tr(state.message)}</p>}
  {delivery?<><p className="break-all font-semibold">{delivery.reference}</p><p>{tr("Delivery status:")} <strong>{delivery.status==='delivered'?tr("Delivered"):delivery.status.replaceAll('_',' ')}</strong></p>
   {!compact&&<><dl className="grid min-w-0 gap-4 sm:grid-cols-2">{[['Pickup area',delivery.pickup_area],['Delivery destination',delivery.delivery_area],['Assigned Driver',delivery.assigned_driver?.full_name||tr("Not assigned")]].map(([label,value])=><div className="min-w-0" key={label}><dt className="text-sm text-[#64748B]">{tr(label)}</dt><dd className="break-words font-semibold [overflow-wrap:anywhere]">{value}</dd></div>)}</dl>
   <p className="text-sm">{tr("Request created:")} {formatAssignedTime(delivery.created_at)}</p><p className="text-sm">{tr("Last updated:")} {formatAssignedTime(delivery.updated_at)}</p>{delivery.assigned_driver&&<p className="text-sm">{tr("Assigned:")} {formatAssignedTime(delivery.assigned_driver.assigned_at)}</p>}<DeliveryTimeline status={delivery.status} events={delivery.events}/>
   <p className="text-sm text-[#64748B]">{tr("Delivery progress does not record payment or complete the order automatically.")}</p>{delivery.status==='cancelled'&&<p>{tr("This cancelled delivery remains linked. Replacement delivery requests are not supported.")}</p>}</>}
   <Link className={button} to={'/shop-owner/deliveries?business_id='+businessId+'&delivery_id='+delivery.delivery_request_id}>{tr("View Delivery")}</Link>
  </>:data&&<><p>{tr("No delivery has been requested.")}</p>{data.can_request_delivery?(compact?<p className="text-sm">{tr("Eligible to request delivery. Open Order Details to provide the areas.")}</p>:!state.formOpen&&<button type="button" className={button+' border-[#12B8A6]'} disabled={state.busy||state.loading} onClick={actions.open}>{tr("Request Delivery")}</button>):<p className="text-sm text-[#64748B]">{tr(data.delivery_unavailable_reason)}</p>}</>}
  {!compact&&state.formOpen&&!delivery&&data?.can_request_delivery&&<form aria-label={tr("Request order delivery")} className="space-y-4" onSubmit={event=>{event.preventDefault();actions.create();}}>
   <p className="text-sm">{tr("Enter public area names. No saved delivery destination is available; provide both areas explicitly. Do not include private addresses or contact details in Driver job previews.")}</p>
   {state.uncertain&&<p role="alert">{tr("The last attempt is unconfirmed. Refresh to find an existing link, or retry these same areas. They are locked until the outcome is known.")}</p>}
   <div className="grid min-w-0 gap-4 sm:grid-cols-2">{[['pickup_area','Pickup area'],['delivery_area','Delivery destination']].map(([key,label])=><label className="min-w-0 text-sm font-semibold" key={key}>{tr(label)}<input name={key} className={field} required maxLength={160} value={state.form[key]} disabled={state.busy||state.uncertain} onChange={event=>actions.edit(key,event.target.value)}/></label>)}</div>
   <div className="flex flex-wrap gap-3"><button type="submit" className={button+' border-[#12B8A6]'} disabled={state.busy||state.loading}>{state.busy?tr("Requesting delivery..."):state.uncertain?tr("Retry same delivery request"):tr("Confirm Request Delivery")}</button><button type="button" className={button} disabled={state.busy||state.uncertain} onClick={actions.close}>{tr("Keep Order")}</button></div>
  </form>}
 </section>;
}
// Render the order fulfilment interface and connect its controls to the state and callbacks defined here.
export default function OrderFulfilment({orderId,businessId,compact=false,onConfirmed,blocked=false}) {
 const [workflow]=useState(()=>createOrderFulfilment({summary:ownerOrderDelivery,create:requestOrderDelivery,/* Load the selected order within the active reader context. */ order:(id,business,signal)=>orderDetail(true,id,business,signal)},orderId,businessId));
 const state=useSyncExternalStore(workflow.subscribe,workflow.getSnapshot,workflow.getSnapshot);
 // Start resource work after rendering and cancel or dispose it during cleanup so obsolete work cannot update this view.
 useEffect(()=>{workflow.start();return()=>workflow.dispose();},[workflow]);
 const actions={...workflow,/* Create the selected resource through this workflow mutation path. */ create:async()=>{if(blocked)return;const result=await workflow.create();if(result)onConfirmed?.();}};
 return <OrderFulfilmentView state={{...state,busy:state.busy||blocked}} actions={actions} businessId={businessId} compact={compact}/>;
}
