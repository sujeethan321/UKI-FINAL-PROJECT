import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Truck, Store } from 'lucide-react';
import { useAuth } from '../../context/useAuth';
import { useCustomerRead } from '../../hooks/useCustomerRead';
import { getMyDeliveryPage } from '../../services/customerDeliveryService';
import { customerDeliveryLabels } from '../../utils/customerOrderTracking';
import { CustomerDataState,CustomerPagination,customerCard,customerButton } from '../../components/customer/CustomerData';
import CustomerOrderTracking from '../../components/customer/CustomerOrderTracking';

export function CustomerDeliveriesView({state,retry,page,onPage,filter,onFilter,query,onQuery,selected,onSelect,children}) {
  const { tr } = useAppTranslation();
  const rows=(state.data?.records||[]).filter(row=>(!filter||row.delivery.status===filter)&&(!query||[row.order.reference,row.order.business_name,row.delivery.reference].some(value=>value.toLowerCase().includes(query.toLowerCase()))));
  return <div className="space-y-5"><div><h2>{tr("My Deliveries")}</h2><p className="mt-2 text-sm text-[#52698A]">{tr("Track recorded deliveries linked to your orders.")}</p></div><div className="grid items-start gap-5 xl:grid-cols-2"><section className={customerCard}><div role="group" aria-label={tr("Delivery status")} className="flex flex-wrap gap-2 border-b border-[#E1EAF4] pb-4">{[['','All Deliveries'],['in_transit','In Transit'],['delivered','Delivered'],['cancelled','Cancelled']].map(([value,label])=><button type="button" key={value} aria-pressed={filter===value} onClick={()=>onFilter(value)} className={'rounded-lg px-3 py-2 text-sm '+(filter===value?'bg-[#E7F9F6] font-semibold text-[#008C87]':'text-[#52698A]')}>{tr(label)}</button>)}</div><label className="mt-4 block text-sm">{tr("Search this order page")}<input type="search" value={query} onChange={e=>onQuery(e.target.value)} maxLength={200} placeholder={tr("Order ID or shop...")} className="mt-2 w-full rounded-lg border border-[#DAE5F3] px-3 py-2"/></label><p className="mt-3 text-xs text-[#64748B]">{tr("Search and status tabs filter deliveries on this order page. More deliveries may appear on other pages.")}</p><CustomerDataState state={state} retry={retry} label={tr("delivery records")}>{state.data&&(rows.length?<ul className="mt-4 space-y-2">{rows.map(({order,delivery})=><li key={order.order_id}><button type="button" aria-pressed={selected===order.order_id} onClick={()=>onSelect(order.order_id)} className={'flex w-full items-center gap-3 rounded-xl border p-4 text-left '+(selected===order.order_id?'border-[#12B8A6] bg-[#EDFAF9]':'border-[#E1EAF4]')}><span className="rounded-full bg-[#E7F9F6] p-3 text-[#008C87]"><Store size={22} aria-hidden="true"/></span><span className="min-w-0 flex-1"><span className="block break-words font-semibold">{order.business_name}</span><span className="mt-1 block break-all text-xs text-[#64748B]">{order.reference}</span></span><span className="rounded-full bg-[#EAF6FF] px-3 py-1 text-xs">{tr(customerDeliveryLabels[delivery.status])}</span></button></li>)}</ul>:<p className="py-6 text-sm text-[#64748B]">{tr("No recorded deliveries match on this order page.")}</p>)}</CustomerDataState><CustomerPagination page={page} total={state.data?.orderTotal??null} loading={state.loading} onPage={onPage}/><p className="mt-2 text-xs text-[#64748B]">{tr("Pagination counts orders, including orders without a delivery request.")}</p></section><div className="space-y-4">{children||<section className={customerCard}><Truck size={35} className="text-[#12B8A6]" aria-hidden="true"/><h3 className="mt-4 text-xl font-bold">{tr("Delivery Details")}</h3><p className="mt-2 text-sm text-[#52698A]">{tr("Select a delivery to view its recorded progress.")}</p></section>}<div className="customer-unavailable">{tr("Live location, arrival estimates, driver contact and delivery addresses are not available in this tracking projection. Order, payment and delivery states are recorded separately.")}</div><Link className={customerButton} to="/customer/orders">{tr("View My Orders")}</Link></div></div></div>;
}
function Page({page,onPage,onDenied}) {
  const [state,reader]=useCustomerRead(options=>getMyDeliveryPage(page,options),data=>data,onDenied);
  const [filter,setFilter]=useState(''),[query,setQuery]=useState(''),[selected,setSelected]=useState(null);
  const visible=state.data?.records.some(row=>row.order.order_id===selected);
  return <CustomerDeliveriesView {...{state,page,filter,query,selected}} retry={reader.load} onPage={onPage} onFilter={setFilter} onQuery={setQuery} onSelect={setSelected}>{visible&&<CustomerOrderTracking key={selected} orderId={selected} onDenied={onDenied}/>}</CustomerDeliveriesView>;
}
function Session() {
  const { tr } = useAppTranslation();
  const [page,setPage]=useState(1),[denied,setDenied]=useState('');
  return denied?<p role="alert" className={customerCard}>{tr(denied)}</p>:<Page key={page} page={page} onPage={setPage} onDenied={setDenied}/>;
}
export default function CustomerDeliveries() {
  const {user,token,isAuthenticated}=useAuth();
  return isAuthenticated&&user?.platform_role==='customer'?<Session key={user.user_id+':'+token}/>:null;
}
