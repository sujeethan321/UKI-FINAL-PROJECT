import {useEffect,useState,useSyncExternalStore} from 'react';
import {Link,useParams} from 'react-router-dom';
import {useAuth} from '../../context/useAuth';
import {getDriverProfile,getDriverSummary} from '../../services/driverDashboardService';
import {listDriverDeliveries,readDriverDelivery,updateDriverDelivery} from '../../services/driverDeliveriesService';
import {createDeliveriesWorkflow,deliveryLabels,deliveryActions} from '../../utils/driverDeliveries';
import {driverEligibilityMessages,formatAssignedTime} from '../../utils/driverDashboard';

const card='min-w-0 rounded-2xl border border-[#D4E2EE] bg-white p-5 shadow-sm sm:p-6';
const button='inline-flex min-h-11 items-center justify-center rounded-lg border border-[#DAE5F3] px-4 py-2 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-[#12B8A6] disabled:opacity-50';
function Status({value}) {return <span className={'inline-block rounded-full px-3 py-1 text-xs font-semibold '+(value==='delivered'?'bg-[#22C55E]/10':value==='cancelled'?'bg-[#DC4545]/10':'bg-[#12B8A6]/10')}>{deliveryLabels[value]}</span>;}
function RecordedTime({value}) {return value?<time dateTime={value+'Z'}>{formatAssignedTime(value)}</time>:<>Date not recorded</>;}
export function DriverDeliveriesView({state,actions,history=false,detail=false}) {
  const [confirm,setConfirm]=useState(false);
  const title=detail?'Delivery Details':history?'Delivery History':'My Deliveries';
  const row=state.detail.data?.delivery,next=state.detail.data?.allowed_next_status;
  const eligible=state.profile.data?.eligible_for_jobs;
  const loading=state.busy||['profile','summary',detail?'detail':'list'].some(key=>state[key].loading);
  return <div className="space-y-6 pb-6"><div className="flex flex-wrap items-start justify-between gap-4"><div><h2 className="text-2xl font-bold">{title}</h2><p className="mt-2 text-sm text-[#64748B]">{history?'Your completed and cancelled deliveries.':'Manage deliveries assigned to your Driver account.'}</p></div><button type="button" className={button} disabled={loading} onClick={()=>{setConfirm(false);actions.refresh();}}>Refresh {detail?'details':'deliveries'}</button></div>
    {state.authError?<p role="alert" className={card}>{state.authError}</p>:<>
    <div className="flex flex-wrap gap-3"><Link className={button} to="/driver/dashboard">Dashboard</Link><Link className={button} to={history?'/driver/deliveries':'/driver/history'}>{history?'My Deliveries':'Delivery History'}</Link></div>
    {state.profile.error&&<p role="alert">{state.profile.error}</p>}
    {state.profile.data&&!eligible&&<p className="rounded-xl bg-[#F5B544]/15 p-4 text-sm">{driverEligibilityMessages[state.profile.data.eligibility_reason]} Status updates are unavailable.</p>}
    {state.summary.data&&<p className="text-sm text-[#64748B]">Active deliveries: {state.summary.data.active_deliveries_count} · Completed deliveries: {state.summary.data.completed_deliveries_count}</p>}
    {state.summary.error&&<p role="alert">Delivery counts are unavailable. Refresh to retry.</p>}
    {state.message&&<p role={state.uncertain?'alert':'status'} className={card}>{state.message}</p>}
    {detail?<section className={card} aria-label="Delivery details">
      {state.detail.loading?<p role="status">Loading delivery details...</p>:state.detail.error?<p role="alert">{state.detail.error}</p>:row?<>
      <div className="flex flex-wrap items-start justify-between gap-3"><h3 className="break-all text-xl font-bold">{row.reference}</h3><Status value={row.status}/></div>
      <dl className="mt-5 grid min-w-0 gap-5 sm:grid-cols-2">{[['Requesting shop',row.business_name],['Pickup area',row.pickup_area],['Delivery area',row.delivery_area],['Assigned Driver',state.profile.data?.full_name||'Your Driver account']].map(([label,value])=><div className="min-w-0" key={label}><dt className="text-sm text-[#64748B]">{label}</dt><dd className="mt-1 break-words font-semibold">{value}</dd></div>)}</dl>
      <p className="mt-5 text-sm">Assigned: <RecordedTime value={row.assigned_at}/></p>
      <h3 className="mt-6 font-bold">Recorded delivery progress</h3><ol className="mt-3 space-y-3 border-l-2 border-[#12B8A6] pl-4">{state.detail.data.events.map(event=><li key={event.status}><p className="font-semibold">{deliveryLabels[event.status]}</p><p className="text-sm text-[#64748B]"><RecordedTime value={event.occurred_at}/></p></li>)}</ol>
      <p className="mt-3 text-xs text-[#64748B]">Only recorded events are shown. Earlier progress dates may be unavailable. Precise addresses, customer contacts, vehicle requirements and operational instructions are not stored in this delivery record.</p>
      {next&&eligible&&!state.uncertain&&<div className="mt-6">{confirm&&next==='delivered'?<div role="group" aria-label="Confirm delivery completion" className="space-y-3 rounded-xl bg-[#F5F8FC] p-4"><p>Confirm this delivery has reached its destination?</p><div className="flex flex-wrap gap-3"><button type="button" className={button+' bg-[#12B8A6] text-[#10243E]'} disabled={state.busy} onClick={()=>{setConfirm(false);actions.update();}}>Confirm Delivered</button><button type="button" className={button} disabled={state.busy} onClick={()=>setConfirm(false)}>Cancel</button></div></div>:<button type="button" className={button+' bg-[#12B8A6] text-[#10243E]'} disabled={state.busy||state.profile.loading} onClick={()=>next==='delivered'?setConfirm(true):actions.update()}>{state.busy?'Updating delivery...':deliveryActions[next]}</button>}</div>}
      {['delivered','cancelled'].includes(row.status)&&<p className="mt-5 text-sm">This delivery is {deliveryLabels[row.status].toLowerCase()}. No further status updates are permitted.</p>}
      </>:<p className="py-5 text-sm">Refresh details to check the recorded delivery status.</p>}
    </section>:<section className={card} aria-label={title}>
      <label className="block text-sm font-semibold" htmlFor="delivery-status">Filter by status</label><select id="delivery-status" value={state.status} disabled={state.list.loading} onChange={event=>actions.filter(event.target.value)} className="mt-2 min-h-11 max-w-full rounded-lg border border-[#D4E2EE] bg-white px-3"><option value="">{history?'All final statuses':'All active statuses'}</option>{(history?['delivered','cancelled']:['assigned','picked_up','in_transit']).map(status=><option key={status} value={status}>{deliveryLabels[status]}</option>)}</select>
      {state.list.loading?<p role="status" className="py-5">Loading deliveries...</p>:state.list.error?<p role="alert" className="py-5">{state.list.error}</p>:state.list.data?<>
      {state.list.data.deliveries.length?<ul className="mt-4 divide-y divide-[#D4E2EE]">{state.list.data.deliveries.map(delivery=><li key={delivery.delivery_request_id} className="grid min-w-0 gap-4 py-5 sm:grid-cols-[minmax(0,1fr)_auto]"><div className="min-w-0"><h3 className="break-all font-bold">{delivery.reference}</h3><p className="mt-1 break-words text-sm">{delivery.business_name}</p><p className="mt-3 break-words text-sm">Pickup area: {delivery.pickup_area}</p><p className="mt-1 break-words text-sm">Delivery area: {delivery.delivery_area}</p><p className="mt-2 text-xs text-[#64748B]">Assigned: <RecordedTime value={delivery.assigned_at}/></p>{history&&<p className="mt-2 text-xs text-[#64748B]">{deliveryLabels[delivery.status]}: <RecordedTime value={delivery.finished_at}/></p>}</div><div className="space-y-3"><Status value={delivery.status}/><p><Link className={button} to={'/driver/deliveries/'+delivery.delivery_request_id}>{!history&&eligible?deliveryActions[{assigned:'picked_up',picked_up:'in_transit',in_transit:'delivered'}[delivery.status]]+' · Details':'View Details'}</Link></p></div></li>)}</ul>:<p className="py-6 text-sm text-[#64748B]">{history?'No completed or cancelled deliveries match this filter.':'No assigned deliveries match this filter.'}</p>}
      <div className="mt-5 flex flex-wrap items-center gap-3"><button className={button} type="button" disabled={state.page===1} onClick={()=>actions.page(state.page-1)}>Previous</button><p className="text-sm">Page {state.page} · {state.list.data.total} deliveries</p><button className={button} type="button" disabled={state.page*10>=state.list.data.total} onClick={()=>actions.page(state.page+1)}>Next</button></div></>:null}
    </section>}
    </>}
  </div>;
}
function DeliverySession({userId,history,deliveryId}) {
  const [workflow]=useState(()=>createDeliveriesWorkflow({profile:getDriverProfile,summary:getDriverSummary,list:listDriverDeliveries,detail:readDriverDelivery,update:updateDriverDelivery},userId,{history,deliveryId}));
  const state=useSyncExternalStore(workflow.subscribe,workflow.getSnapshot,workflow.getSnapshot);
  useEffect(()=>{workflow.start();return()=>workflow.dispose();},[workflow]);
  return <DriverDeliveriesView state={state} actions={workflow} history={history} detail={deliveryId!==null}/>;
}
export default function DriverDeliveries({history=false,detail=false}) {
  const {user,token,isAuthenticated}=useAuth(),{deliveryId}=useParams();
  if(!isAuthenticated||user?.platform_role!=='driver'||user.account_status!=='active')return null;
  const id=detail?Number(deliveryId):null;
  if(detail&&(!/^\d+$/.test(deliveryId)||!Number.isSafeInteger(id)||id<1))return <p role="alert">Invalid delivery ID.</p>;
  return <DeliverySession key={user.user_id+':'+token+':'+history+':'+id} userId={user.user_id} history={history} deliveryId={id}/>;
}
