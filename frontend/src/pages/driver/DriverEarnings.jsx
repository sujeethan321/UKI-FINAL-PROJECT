import {Link} from 'react-router-dom';
import {useEffect,useRef,useState} from 'react';
import {Wallet,Clock,BarChart3,Download} from 'lucide-react';
import {useAuth} from '../../context/useAuth';
import {useAppTranslation} from '../../i18n/useAppTranslation';
import {readDriverEarnings,declareDriverCollection} from '../../services/driverFinanceService';
import {parseEarnings,financeLabels} from '../../utils/driverFinance';
import {money} from '../../utils/shopping';
const card='rounded-xl border border-[#E1EAF4] bg-white p-5';
const button='rounded-lg border border-[#DAE5F3] px-4 py-2 text-sm';

export function DriverEarningsView({data,loading,error,period,onPeriod,onRefresh,onDeclare,busy,uncertain}){
 const {tr}=useAppTranslation();
 return <div className="space-y-5"><div className="flex flex-wrap items-start justify-between gap-4"><div><h2>{tr('My Earnings')}</h2><p className="mt-2 text-sm text-[#52698A]">{tr('Customer pays the Driver directly. Declarations require independent Admin verification.')}</p></div><button type="button" disabled className="inline-flex items-center gap-2 rounded-lg border border-[#DAE5F3] bg-white px-4 py-3 text-sm text-[#64748B]"><Download size={18}/>{tr('Export unavailable')}</button></div>
 <button type="button" className={button} onClick={onRefresh} disabled={loading||busy}>{tr('Refresh')}</button>
 {loading&&<p role="status">{tr('Loading earnings...')}</p>}{error&&<p role="alert" className={card}>{tr(error)}</p>}
 <div className="grid gap-4 md:grid-cols-3">{[['Total Earnings','total_earned',Wallet],['Available Balance','available',Wallet],['Pending Earnings','pending',Clock]].map(([title,key,Icon])=><section key={key} className={card+' flex items-center gap-4'}><span className="rounded-xl bg-[#E7F9F6] p-4 text-[#008C87]"><Icon size={29}/></span><div><h3 className="text-sm">{tr(title)}</h3><p className="mt-2 text-xl font-bold">{data?money(data.summary[key]):tr('Unavailable')}</p>{key==='total_earned'&&<p className="mt-1 text-xs text-[#64748B]">{tr('Gross recorded earnings; adjustments and disputes remain visible in history.')}</p>}</div></section>)}</div>
 <section className={card}><div className="flex flex-wrap items-center justify-between gap-3"><h3 className="text-xl font-bold">{tr('Earnings Overview')}</h3><div role="group" aria-label={tr('Earnings period')} className="flex gap-2">{['day','week','month'].map(value=><button type="button" key={value} disabled={busy||loading} aria-pressed={period===value} onClick={()=>onPeriod(value)} className={button}>{tr({day:'Day',week:'Week',month:'Month'}[value])}</button>)}</div></div><div className="mt-4 flex min-h-52 flex-col gap-2"><BarChart3 size={32}/>{data?.daily.map(day=><div key={day.date} className="flex justify-between border-b border-[#E1EAF4] py-1 text-sm"><time>{day.date}</time><span>{money(day.earned)}</span></div>)}</div></section>
 <section className={card}><h3 className="text-xl font-bold">{tr('Earnings History')}</h3>{data?.earnings.length===0&&<p className="mt-4">{tr('No recorded earnings in this pilot. Historical deliveries are not backfilled.')}</p>}
 {data?.earnings.map(row=><article key={row.earning_id} className="mt-4 border-b border-[#E1EAF4] py-3"><p>#{row.delivery_request_id} · {money(row.amount)} · {tr(financeLabels[row.status])}</p><time className="text-xs text-[#64748B]" dateTime={row.created_at+'Z'}>{row.created_at.replace('T',' ')} UTC</time>
 {row.status==='pending'&&<CollectionForm row={row} onDeclare={onDeclare} disabled={busy||uncertain}/>}
 <ul className="mt-2 text-sm">{row.collections.map(event=><li key={event.collection_id}>{tr(event.kind==='declared'?'Collection declared':'Exception review')} · {money(event.amount)} · <time dateTime={event.created_at+'Z'}>{event.created_at.replace('T',' ')} UTC</time></li>)}{row.settlement_events.map(event=><li key={event.event_id}>{tr({direct_settled:'Collection verified',disputed:'Disputed',reversed:'Reversed — review required',refund_confirmed:'Refund confirmed'}[event.kind])} · {money(event.amount)} · <time dateTime={event.created_at+'Z'}>{event.created_at.replace('T',' ')} UTC</time></li>)}</ul></article>)}
 <Link to="/driver/history" className={'mt-4 inline-block '+button}>{tr('View Delivery History')}</Link>
 {data&&<div className="mt-4 flex gap-3"><button type="button" className={button} disabled={loading||busy||data.page<=1} onClick={()=>onRefresh(data.page-1)}>{tr('Previous')}</button><span>{data.page} / {Math.max(1,Math.ceil(data.total/data.page_size))}</span><button type="button" className={button} disabled={loading||busy||data.page*data.page_size>=data.total} onClick={()=>onRefresh(data.page+1)}>{tr('Next')}</button></div>}</section>
 <section className={card}><h3 className="text-xl font-bold">{tr('Payout Information')}</h3><p className="mt-4">{tr('Directly settled fees cannot be paid again by the platform. Platform payouts are unsupported.')}</p>{data&&<dl className="mt-3">{[['Collection declared','declared'],['Directly settled','directly_settled'],['Exception review','review']].map(([label,key])=><div key={key} className="flex justify-between"><dt>{tr(label)}</dt><dd>{money(data.summary[key])}</dd></div>)}</dl>}</section></div>;
}

function CollectionForm({row,onDeclare,disabled}){
 const {tr}=useAppTranslation();const [evidence,setEvidence]=useState(''),[amount,setAmount]=useState(row.amount),[kind,setKind]=useState('declared');
 return <form onSubmit={e=>{e.preventDefault();onDeclare(row,{kind,amount,evidence});}} className="mt-3 space-y-2"><fieldset disabled={disabled}>
 <label className="block text-sm">{tr('Collection action')}<select value={kind} onChange={e=>setKind(e.target.value)} className={button}><option value="declared">{tr('Declare full collection')}</option><option value="exception">{tr('Report partial collection or dispute')}</option></select></label>
 <label className="block text-sm">{tr('Amount collected')}<input required inputMode="decimal" pattern="[0-9]+\.[0-9]{2}" value={amount} onChange={e=>setAmount(e.target.value)} className={button}/></label>
 <label className="block text-sm">{tr('Evidence reference / review note')}<input required minLength={10} maxLength={1000} value={evidence} onChange={e=>setEvidence(e.target.value)} className={button}/></label>
 <button type="submit" className={button}>{tr('Submit declaration')}</button></fieldset></form>;
}

export default function DriverEarnings(){
 const {user,token}=useAuth();const [period,setPeriod]=useState('month'),[page,setPage]=useState(1),[revision,setRevision]=useState(0);
 const [result,setResult]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[uncertain,setUncertain]=useState(false);
 const attempt=useRef(null),lock=useRef(false),alive=useRef(true);const context=`${user?.user_id}:${token}:${period}:${page}:${revision}`;
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 useEffect(()=>{const controller=new AbortController();readDriverEarnings({period,page,page_size:20},controller.signal).then(data=>{
  if(!controller.signal.aborted){
   const verified=parseEarnings(data,user.user_id),intent=attempt.current;
   setResult({context,data:verified});
   if(intent&&verified.earnings.find(row=>row.earning_id===intent.earningId)?.collections.some(event=>event.kind===intent.payload.kind&&event.amount===intent.payload.amount)){
    attempt.current=null;setUncertain(false);setError('');
   }
  }
 }).catch(error=>{if(!controller.signal.aborted)setResult({context,error:error?.response?.data?.detail?.code==='DRIVER_FINANCE_NOT_ENABLED'?'Driver finance is not enabled.':error?.response?.data?.detail?.code==='DRIVER_FINANCE_SCHEMA_NOT_READY'?'Driver finance requires verified schema readiness.':'Earnings could not be verified. Refresh recorded history before retrying.'});});return()=>controller.abort();},[context,period,page,user.user_id]);
 const current=result?.context===context?result:null;
 async function declare(row,fields){
  if(lock.current||uncertain)return;lock.current=true;setBusy(true);setError('');
  const key=JSON.stringify([row.earning_id,fields]);if(attempt.current?.key!==key)attempt.current={key,earningId:row.earning_id,payload:{...fields,request_key:crypto.randomUUID()}};
  try{await declareDriverCollection(row.earning_id,attempt.current.payload);if(alive.current){attempt.current=null;setRevision(n=>n+1);}}
  catch(error){if(alive.current){
   const rejected=[400,401,403,404,409,422,429].includes(error?.response?.status);
   if(rejected)attempt.current=null;
   setUncertain(!rejected);setError('Declaration could not be confirmed. Refresh recorded history before another submission.');
  }}
  finally{lock.current=false;if(alive.current)setBusy(false);}
 }
 return <DriverEarningsView data={current?.data??null} loading={!current} error={error||current?.error||''} period={period} onPeriod={setPeriod} busy={busy} uncertain={uncertain}
 onDeclare={declare} onRefresh={next=>{if(typeof next==='number')setPage(next);setRevision(n=>n+1);}}/>;
}
