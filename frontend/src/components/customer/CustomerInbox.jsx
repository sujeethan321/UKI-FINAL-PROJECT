// Purpose: Render the reusable customer inbox interface and keep its presentation and interactions together.
import Select from "../ui/Select";
import {useEffect} from 'react';
import {Bell,Truck,ShoppingBag,Wallet,CheckCheck} from 'lucide-react';
import {useNotifications} from '../../context/NotificationContext';
import {NOTIFICATION_TYPES} from '../../utils/notification';
import NotificationItem from '../notifications/NotificationItem';
import {customerButton,customerCard} from './CustomerData';

// Render the customer inbox view interface and connect its controls to the state and callbacks defined here.
export function CustomerInboxView({state,actions}) {
  const blocked=state.mutating||!!state.authError;
  const tabs=[['','All'],['order_submitted','New Orders'],['delivery_in_transit','In Transit'],['repayment_recorded','Repayments']];
  return <section className={customerCard+' space-y-5'} aria-label="Customer notification inbox"><div className="flex flex-wrap items-center justify-between gap-3"><p className="rounded-lg bg-[#E7F9F6] px-4 py-2 text-sm font-semibold text-[#008C87]">{state.authError?'—':state.count??'—'} unread</p><button className={customerButton} disabled={blocked||state.count===0} onClick={actions.markAllRead}><CheckCheck size={18}/>{state.mutating&&state.markingId===null?'Updating...':'Mark All as Read'}</button></div><div className="flex flex-wrap gap-2 border-b border-[#E1EAF4] pb-4" role="group" aria-label="Notification categories">{tabs.map(([value,label])=><button key={value} type="button" disabled={blocked} aria-pressed={state.typeFilter===value} onClick={()=>actions.setFilter('typeFilter',value)} className={'rounded-lg px-4 py-2.5 text-sm '+(state.typeFilter===value?'bg-[#E7F9F6] font-semibold text-[#008C87]':'text-[#52698A]')}>{label}</button>)}</div><div className="flex flex-wrap items-end gap-3"><label className="text-sm">Read status<Select value={state.readFilter} disabled={blocked} onChange={e=>actions.setFilter('readFilter',e.target.value)} className="ml-2 rounded-lg border border-[#DAE5F3] px-3 py-2"><option value="all">All</option><option value="unread">Unread</option><option value="read">Read</option></Select></label><label className="text-sm">Event type<Select value={state.typeFilter} disabled={blocked} onChange={e=>actions.setFilter('typeFilter',e.target.value)} className="ml-2 max-w-full rounded-lg border border-[#DAE5F3] px-3 py-2"><option value="">All types</option>{NOTIFICATION_TYPES.map(([value,label])=><option key={value} value={value}>{label}</option>)}</Select></label><button className={customerButton} disabled={blocked||state.listLoading} onClick={()=>actions.refresh()}>Refresh inbox</button></div>
    {state.authError&&<p role="alert" className="text-sm text-[#DC4545]">{state.authError}</p>}{state.actionError&&<p role="alert" className="text-sm text-[#DC4545]">{state.actionError}</p>}{state.listLoading&&<p role="status">Loading notifications...</p>}{!state.authError&&state.listError&&<div role="alert"><p>{state.listError}</p><button className={customerButton} disabled={state.mutating} onClick={actions.loadList}>Retry notifications</button></div>}
    {!state.authError&&state.list&&<>{state.list.notifications.length?<ul className="customer-inbox-list space-y-2" aria-label="Notification history">{state.list.notifications.map(row=>{
      const Icon=row.notification_type.startsWith('delivery_')?Truck:row.notification_type.startsWith('order_')?ShoppingBag:row.notification_type.includes('repayment')?Wallet:Bell;
      return <NotificationItem key={row.notification_id} notification={row} role="customer" busy={state.mutating} onRead={actions.markRead} leadingIcon={<span className="absolute left-4 top-5 rounded-full bg-[#E2F8F4] p-3 text-[#008C87]"><Icon size={23} aria-hidden="true"/></span>}/>;
    })}</ul>:<p className="customer-unavailable">{state.readFilter==='all'&&!state.typeFilter?'No notifications yet.':'No notifications match these filters.'}</p>}<nav aria-label="Notification pages" className="flex flex-wrap items-center justify-end gap-3 text-sm"><button className={customerButton} disabled={state.mutating||state.listLoading||state.page<=1} onClick={()=>actions.setFilter('page',state.page-1)}>Previous</button><span>Page {state.page} · {state.list.total} notifications</span><button className={customerButton} disabled={state.mutating||state.listLoading||state.page*state.pageSize>=state.list.total} onClick={()=>actions.setFilter('page',state.page+1)}>Next</button></nav></>}
  </section>;
}
// Render the customer inbox interface and connect its controls to the state and callbacks defined here.
export default function CustomerInbox() {
  const context=useNotifications(),actions=context?.actions;
  // Synchronize this component with its external state after rendering, rerunning when the declared dependencies change.
  useEffect(()=>{if(!actions)return;actions.openInbox();return()=>actions.closeInbox();},[actions]);
  return context?<CustomerInboxView state={context.state} actions={actions}/>:null;
}
