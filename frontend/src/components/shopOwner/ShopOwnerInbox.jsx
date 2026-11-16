import { useEffect } from 'react';
import { Bell, CheckCheck, RefreshCw } from 'lucide-react';
import { useNotifications } from '../../context/NotificationContext';
import { NOTIFICATION_TYPES } from '../../utils/notification';
import NotificationItem from '../notifications/NotificationItem';

const button='rounded-lg border border-[#DAE5F3] bg-white px-4 py-2 text-sm font-semibold disabled:opacity-50';
export function ShopOwnerInboxView({state,actions}) {
  const groups = new Map();
  for (const row of state.list?.notifications || []) {
    const date = new Date(row.created_at.endsWith('Z') ? row.created_at : row.created_at+'Z');
    const label = Number.isNaN(date.getTime()) ? 'Date unavailable' : date.toLocaleDateString('en-LK',{timeZone:'Asia/Colombo',day:'numeric',month:'long',year:'numeric'});
    if(!groups.has(label))groups.set(label,[]);
    groups.get(label).push(row);
  }
  return <section aria-label="Notification inbox" className="space-y-4 rounded-xl border border-[#E1EAF4] bg-white p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><h3 className="text-xl font-bold">Recent Notifications</h3><div className="flex flex-wrap items-center gap-3"><span className="rounded-lg bg-[#E7F9F6] px-4 py-2 text-sm font-semibold text-[#087D78]">{state.count ?? '—'} Unread</span><button className={button} disabled={state.mutating||!!state.authError||state.count===0} onClick={actions.markAllRead}><CheckCheck className="mr-2 inline" size={17}/>{state.mutating&&state.markingId===null?'Updating...':'Mark All as Read'}</button></div></div>
    <div className="flex flex-wrap items-center gap-3 border-b border-[#E1EAF4] pb-4"><div role="group" aria-label="Notification read status" className="flex gap-1">{[['all','All'],['unread','Unread'],['read','Read']].map(([value,label])=><button key={value} type="button" aria-pressed={state.readFilter===value} disabled={state.mutating||!!state.authError} onClick={()=>actions.setFilter('readFilter',value)} className={'rounded-lg px-4 py-3 text-sm font-semibold '+(state.readFilter===value?'bg-[#E7F9F6] text-[#008C87]':'text-[#52698A]')}>{label}</button>)}</div><label className="text-sm">Category<select aria-label="Notification category" value={state.typeFilter} disabled={state.mutating||!!state.authError} onChange={e=>actions.setFilter('typeFilter',e.target.value)} className="ml-2 max-w-full rounded-lg border border-[#DAE5F3] px-3 py-2"><option value="">All types</option>{NOTIFICATION_TYPES.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></label><button className={button} disabled={state.mutating||state.listLoading||!!state.authError} onClick={()=>actions.refresh()}><RefreshCw className="mr-2 inline" size={16}/>Refresh inbox</button></div>
    {state.authError&&<p role="alert" className="text-sm text-[#DC4545]">{state.authError}</p>}{state.actionError&&<p role="alert" className="text-sm text-[#DC4545]">{state.actionError}</p>}{state.listLoading&&<p role="status">Loading notifications...</p>}
    {!state.authError&&state.listError&&<div role="alert"><p>{state.listError}</p><button className={button} disabled={state.mutating} onClick={actions.loadList}>Retry notifications</button></div>}
    {!state.authError&&state.list&&<>{groups.size?[...groups].map(([date,rows])=><div key={date}><h4 className="rounded-lg bg-[#EDF4F9] px-4 py-2 text-sm font-semibold text-[#52698A]">{date}</h4><ul className="owner-inbox-list mt-2 space-y-2">{rows.map(row=><NotificationItem key={row.notification_id} notification={row} role="shop_owner" busy={state.mutating} onRead={actions.markRead}/>)}</ul></div>):<div className="owner-unavailable flex items-center justify-center gap-3"><Bell size={23} aria-hidden="true"/><p>{state.readFilter==='all'&&!state.typeFilter?'No notifications yet.':'No notifications match these filters.'}</p></div>}<nav aria-label="Notification pages" className="flex flex-wrap items-center justify-end gap-3"><button className={button} disabled={state.mutating||state.listLoading||state.page<=1} onClick={()=>actions.setFilter('page',state.page-1)}>Previous</button><span className="text-sm">Page {state.page} · {state.list.total} notifications</span><button className={button} disabled={state.mutating||state.listLoading||state.page*state.pageSize>=state.list.total} onClick={()=>actions.setFilter('page',state.page+1)}>Next</button></nav></>}
  </section>;
}
export default function ShopOwnerInbox() {
  const context=useNotifications(),actions=context?.actions;
  useEffect(()=>{if(!actions)return;actions.openInbox();return()=>actions.closeInbox();},[actions]);
  return context?<ShopOwnerInboxView state={context.state} actions={actions}/>:null;
}
