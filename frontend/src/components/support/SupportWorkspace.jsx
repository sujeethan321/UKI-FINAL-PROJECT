import {useEffect,useState,useSyncExternalStore} from 'react';
import {useAuth} from '../../context/useAuth';
import {useAppTranslation} from '../../i18n/useAppTranslation';
import supportApi from '../../services/supportService';
import adminApi from '../../services/adminSupportService';
import {categories,statuses,priorities,supportLabels,createSupportReader} from '../../utils/support';

const card='min-w-0 rounded-2xl border border-[#D4E2EE] bg-white p-5 shadow-sm sm:p-6';
const button='inline-flex min-h-11 items-center justify-center rounded-lg border border-[#D4E2EE] bg-white px-4 py-2 text-sm font-semibold text-[#10243E] hover:border-[#12B8A6] disabled:opacity-50';
const field='mt-2 min-h-11 w-full rounded-lg border border-[#D4E2EE] bg-white p-3 text-sm text-[#10243E]';
const blank={category:'account',subject:'',description:'',business_id:'',business_shared:false,kind:'',record_id:''};
export function SupportView({state,actions,admin=false}){
 const {tr}=useAppTranslation();const [form,setForm]=useState(blank);const [reply,setReply]=useState('');const [note,setNote]=useState(false);
 const [filters,setFilters]=useState({status:'',category:'',priority:'',start_date:'',end_date:''});
 const [action,setAction]=useState('status');const [value,setValue]=useState('investigating');const [reason,setReason]=useState('');
 const locked=state.busy||!!state.pending;const row=state.detail?.case;const label=value=>tr(supportLabels[value]||value);
 const edit=(key,value)=>setForm(previous=>({...previous,[key]:value}));
 const selection=()=>({...Object.fromEntries(Object.entries(filters).filter(([,value])=>value)),limit:20,offset:0});
 const command=payload=>actions.send({kind:'action',reference:row.reference,payload:{...payload,expected_version:row.version}});
 const unavailable=!state.loading&&!state.list&&!state.detail&&!!state.error;
 return <div className="space-y-6 pb-6 text-[#10243E]"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-2xl font-bold">{tr(admin?'Support & Disputes':'My Support Tickets')}</h2><button className={button} disabled={locked||state.loading} onClick={()=>actions.load()}>{tr('Refresh')}</button></div>
  <p className="text-sm text-[#64748B]">{tr('Support investigates concerns. Resolving a case does not change financial records or confirm a payment.')}</p>
  {state.loading&&<p role="status">{tr('Loading support cases…')}</p>}{state.error&&<p role="alert" className={card}>{tr(state.error)}</p>}{state.notice&&<p role="status" className={card}>{tr(state.notice)}</p>}
  {state.pending&&!state.busy&&<div className={card}><p>{tr('An action may already have been recorded. Retry the same request to confirm its result.')}</p><button className={button+' mt-3'} onClick={()=>actions.retry()}>{tr('Retry same request')}</button></div>}
  {!unavailable&&!state.loading&&<>
   {admin?<form className={card+' grid gap-4 sm:grid-cols-3'} onSubmit={event=>{event.preventDefault();actions.load(selection());}}>
    {[['status',statuses],['category',categories],['priority',priorities]].map(([key,values])=><label key={key}>{tr({status:'Status',category:'Category',priority:'Priority'}[key])}<select className={field} value={filters[key]} onChange={event=>setFilters({...filters,[key]:event.target.value})}><option value="">{tr('All')}</option>{values.map(value=><option key={value} value={value}>{label(value)}</option>)}</select></label>)}
    {['start_date','end_date'].map(key=><label key={key}>{tr(key==='start_date'?'Start date':'End date')}<input type="date" className={field} value={filters[key]} onChange={event=>setFilters({...filters,[key]:event.target.value})}/></label>)}<button className={button+' self-end'} disabled={locked}>{tr('Apply filters')}</button>
   </form>:<section className={card}><h3 className="text-xl font-bold">{tr('Create support ticket')}</h3><form className="mt-4 grid gap-4 sm:grid-cols-2" onSubmit={event=>{event.preventDefault();actions.send({kind:'create',payload:{category:form.category,subject:form.subject,description:form.description,business_shared:form.business_shared,...(form.business_id?{business_id:Number(form.business_id)}:{}),...(form.kind?{related:{kind:form.kind,record_id:form.record_id}}:{})}});}}>
    <label>{tr('Category')}<select className={field} value={form.category} disabled={locked} onChange={event=>edit('category',event.target.value)}>{categories.map(value=><option key={value} value={value}>{label(value)}</option>)}</select></label>
    <label>{tr('Subject')}<input className={field} minLength={3} maxLength={120} required disabled={locked} value={form.subject} onChange={event=>edit('subject',event.target.value)}/></label>
    <label className="sm:col-span-2">{tr('Description')}<textarea className={field} minLength={10} maxLength={4000} required disabled={locked} value={form.description} onChange={event=>edit('description',event.target.value)}/></label>
    <p className="text-xs text-[#64748B] sm:col-span-2">{tr('Do not include passwords, identity documents or payment-card details. Attachments are not supported.')}</p>
    <label>{tr('Business ID (optional)')}<input type="number" min="1" max="9007199254740991" className={field} disabled={locked} value={form.business_id} onChange={event=>edit('business_id',event.target.value)}/></label>
    <label>{tr('Related record (optional)')}<select className={field} disabled={locked} value={form.kind} onChange={event=>edit('kind',event.target.value)}><option value="">{tr('None')}</option>{['order','delivery','credit_account','ledger_entry','earning'].map(value=><option key={value} value={value} disabled={value==='earning'&&state.list?.financial_links!=='available'}>{label(value)}</option>)}</select></label>
    {form.kind&&<label>{tr('Related record ID')}<input className={field} maxLength={36} required disabled={locked} value={form.record_id} onChange={event=>edit('record_id',event.target.value)}/></label>}
    <label className="flex items-start gap-3 text-sm sm:col-span-2"><input type="checkbox" disabled={locked} checked={form.business_shared} onChange={event=>edit('business_shared',event.target.checked)}/>{tr('Share this case and all public replies with authorized owners of the related business. Otherwise only you and Admin can access it.')}</label>
    <button className={button+' justify-self-start'} disabled={locked}>{tr('Submit support ticket')}</button>
   </form></section>}
   {state.list&&<section className={card}><h3 className="text-xl font-bold">{tr(admin?'Support queue':'My Tickets')}</h3>{!state.list.cases.length?<p className="mt-4">{tr('No support cases found.')}</p>:<ul className="mt-3 divide-y divide-[#D4E2EE]">{state.list.cases.map(item=><li key={item.reference} className="py-3"><button className="text-left font-semibold hover:underline disabled:opacity-50" disabled={locked} onClick={()=>actions.open(item.reference)}>{item.subject}</button><p className="mt-1 break-all text-xs text-[#64748B]">{item.reference} · {label(item.status)} · {label(item.priority)}</p></li>)}</ul>}<nav className="mt-4 flex items-center gap-3" aria-label={tr('Support pagination')}><button className={button} disabled={locked||state.list.offset===0} onClick={()=>actions.load({...state.filters,offset:Math.max(0,state.list.offset-state.list.limit)})}>{tr('Previous')}</button><span>{state.list.offset} / {state.list.total}</span><button className={button} disabled={locked||state.list.offset+state.list.limit>=state.list.total} onClick={()=>actions.load({...state.filters,offset:state.list.offset+state.list.limit})}>{tr('Next')}</button></nav><p className="mt-3 text-xs">{tr('Driver financial links')}: {tr(state.list.financial_links==='unavailable'?'Unavailable':'Requires verified finance schema')}</p></section>}
  </>}
  {state.detailLoading&&<p role="status">{tr('Loading support case…')}</p>}
  {row&&<section className={card}><h3 className="text-xl font-bold">{row.subject}</h3><p className="mt-2 break-all text-sm">{row.reference} · {label(row.status)} · {label(row.priority)}</p><p className="mt-4 whitespace-pre-wrap break-words text-sm">{row.description}</p>{row.resolution&&<p className="mt-4 whitespace-pre-wrap text-sm"><strong>{tr('Resolution')}: </strong>{row.resolution}</p>}
   {state.detail.references.map(ref=><p key={ref.kind} className="mt-2 text-xs">{label(ref.kind)}: {ref.record_id}</p>)}
   <h4 className="mt-6 font-semibold">{tr('Replies')}</h4><ul className="mt-3 space-y-3">{state.detail.messages.items.map((message,index)=><li key={index} className="rounded-lg bg-[#F5F8FC] p-3 text-sm"><p className="text-xs font-semibold">{tr(message.visibility==='internal'?'Internal Admin note':message.from_admin?'Admin reply':'User reply')}</p><p className="mt-2 whitespace-pre-wrap break-words">{message.body}</p><time className="mt-2 block text-xs">{message.created_at} UTC</time></li>)}</ul>
   {state.detail.messages.items.length<state.detail.messages.total&&<button className={button+' mt-3'} onClick={()=>actions.more('messages')} disabled={locked}>{tr('Load more replies')}</button>}
   {!['closed','resolved'].includes(row.status)&&<form className="mt-4" onSubmit={async event=>{event.preventDefault();if(await command({action:note&&admin?'internal_note':'message',body:reply}))setReply('');}}><label>{tr('Reply')}<textarea className={field} maxLength={4000} required disabled={locked} value={reply} onChange={event=>setReply(event.target.value)}/></label>{admin&&<label className="mt-2 flex gap-2 text-sm"><input type="checkbox" checked={note} disabled={locked} onChange={event=>setNote(event.target.checked)}/>{tr('Internal Admin note')}</label>}<button className={button+' mt-3'} disabled={locked}>{tr('Send reply')}</button></form>}
   {admin&&!['closed','resolved'].includes(row.status)&&<form className="mt-6 grid gap-4 sm:grid-cols-2" onSubmit={event=>{event.preventDefault();command(action==='assignment'?{action,admin_id:Number(value)}:action==='priority'?{action,priority:value}:{action,status:value,reason});}}>
    <label>{tr('Admin action')}<select className={field} disabled={locked} value={action} onChange={event=>{setAction(event.target.value);setValue(event.target.value==='priority'?'normal':event.target.value==='assignment'?'':'investigating');}}>{['status','assignment','priority'].map(value=><option key={value} value={value}>{label(value)}</option>)}</select></label>
    <label>{tr(action==='assignment'?'Active Admin user ID':'New value')}{action==='assignment'?<input className={field} type="number" min="1" required disabled={locked} value={value} onChange={event=>setValue(event.target.value)}/>:<select className={field} disabled={locked} value={value} onChange={event=>setValue(event.target.value)}>{(action==='priority'?priorities:['assigned','investigating','awaiting_user','resolved']).map(value=><option key={value} value={value}>{label(value)}</option>)}</select>}</label>
    {action==='status'&&<label className="sm:col-span-2">{tr('Reason / resolution')}<textarea className={field} required minLength={3} maxLength={2000} disabled={locked} value={reason} onChange={event=>setReason(event.target.value)}/></label>}<button className={button} disabled={locked}>{tr('Apply Admin action')}</button>
   </form>}
   {row.status==='resolved'&&<form className="mt-5" onSubmit={event=>{event.preventDefault();command({action:'reopen',reason});}}><label>{tr('Reopening reason (within 14 days)')}<textarea className={field} required minLength={3} maxLength={2000} disabled={locked} value={reason} onChange={event=>setReason(event.target.value)}/></label><button className={button+' mt-3'} disabled={locked}>{tr('Request reopening')}</button>{admin&&<button type="button" className={button+' ml-3 mt-3'} disabled={locked||reason.trim().length<3} onClick={()=>command({action:'status',status:'closed',reason})}>{tr('Close case')}</button>}</form>}
   {row.status==='closed'&&<p className="mt-4 text-sm">{tr('Closed cases require a new case or separately authorized review.')}</p>}
   <h4 className="mt-6 font-semibold">{tr('Activity history')}</h4><ul className="mt-3 space-y-2 text-sm">{state.detail.events.items.map((event,index)=><li key={index}>{label(event.action)}{event.previous_value?' · '+label(event.previous_value):''}{event.new_value?' → '+label(event.new_value):''}{event.reason&&<p className="whitespace-pre-wrap text-xs">{event.reason}</p>}<time className="block text-xs text-[#64748B]">{event.created_at} UTC</time></li>)}</ul>{state.detail.events.items.length<state.detail.events.total&&<button className={button+' mt-3'} onClick={()=>actions.more('events')} disabled={locked}>{tr('Load more activity')}</button>}
  </section>}
 </div>;
}
function SupportSession({admin}){
 const [reader]=useState(()=>createSupportReader(admin?adminApi:supportApi));
 const state=useSyncExternalStore(reader.subscribe,reader.getSnapshot,reader.getSnapshot);
 useEffect(()=>{reader.start();return()=>reader.dispose();},[reader]);
 return <SupportView key={state.detail?.case.reference||'queue'} state={state} actions={reader} admin={admin}/>;
}
export default function SupportWorkspace({role}){
 const {user,token,isAuthenticated}=useAuth();
 if(!isAuthenticated||user?.account_status!=='active'||user?.platform_role!==role)return null;
 return <SupportSession key={user.user_id+':'+token} admin={role==='admin'}/>;
}
