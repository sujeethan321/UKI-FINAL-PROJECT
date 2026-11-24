import {useEffect,useRef,useState} from 'react';
import {useAppTranslation} from '../../i18n/useAppTranslation';
import {readAdminDriverEarnings,verifyDriverCollection} from '../../services/driverFinanceService';
import {parseEarnings,financeLabels} from '../../utils/driverFinance';
import {money} from '../../utils/shopping';

export default function DriverFinanceReview({driverId}){
 const {tr}=useAppTranslation();const [data,setData]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[revision,setRevision]=useState(0);
 const [selection,setSelection]=useState(''),[kind,setKind]=useState('direct_settled'),[evidence,setEvidence]=useState('');
 const [page,setPage]=useState(1);
 const attempt=useRef(null),lock=useRef(false),alive=useRef(true);
 useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
 useEffect(()=>{const controller=new AbortController();readAdminDriverEarnings(driverId,controller.signal,page).then(value=>{
  if(!controller.signal.aborted){
   const verified=parseEarnings(value,driverId),intent=attempt.current;setData(verified);
   if(intent&&verified.earnings.find(row=>row.earning_id===intent.earningId)?.settlement_events.some(event=>event.kind===intent.payload.kind&&event.evidence===intent.payload.evidence)){
    attempt.current=null;setError('');
   }
  }
 }).catch(()=>{if(!controller.signal.aborted)setError('Driver financial review is unavailable.');});return()=>controller.abort();},[driverId,revision,page]);
 async function submit(event){
  event.preventDefault();if(lock.current)return;const row=data?.earnings.find(r=>r.earning_id===selection);if(!row)return;
  const declaration=row.collections.find(c=>c.kind==='declared');
  const fields={kind,evidence,...(kind==='direct_settled'?{collection_id:declaration?.collection_id}: {})};
  const fingerprint=JSON.stringify([selection,fields]);
  if(attempt.current&&attempt.current.fingerprint!==fingerprint){setError('A financial review is unresolved. Refresh history before changing the operation.');return;}
  attempt.current??={fingerprint,earningId:selection,payload:{...fields,request_key:crypto.randomUUID()}};
  lock.current=true;setBusy(true);setError('');
  try{await verifyDriverCollection(selection,attempt.current.payload);if(alive.current){attempt.current=null;setData(null);setRevision(n=>n+1);setEvidence('');}}
  catch(error){if(alive.current){
   if([400,401,403,404,409,422,429].includes(error?.response?.status))attempt.current=null;
   setError('Financial review could not be confirmed. Refresh history; do not create a replacement payment.');
  }}
  finally{lock.current=false;if(alive.current)setBusy(false);}
 }
 return <section className="mt-5 rounded-xl border border-[#D4E2EE] bg-white p-4"><h3 className="font-bold">{tr('Driver payment verification')}</h3><p className="mt-2 text-sm">{tr('Verify independent evidence of Customer-to-Driver collection. This does not send money or create a platform payout.')}</p>
 <button type="button" disabled={busy} onClick={()=>{setData(null);setRevision(n=>n+1);}}>{tr('Refresh')}</button>
 {error&&<p role="alert">{tr(error)}</p>}{!data&&!error&&<p role="status">{tr('Loading earnings...')}</p>}
 {data?.earnings.map(row=><article key={row.earning_id} className="mt-3 border-b p-2"><p>#{row.delivery_request_id} · {money(row.amount)} · {tr(financeLabels[row.status])}</p>{row.collections.map(c=><p className="break-words text-sm" key={c.collection_id}>{tr(c.kind==='declared'?'Collection declared':'Exception review')} · {money(c.amount)} · {c.evidence}</p>)}{row.settlement_events.map(e=><p className="break-words text-sm" key={e.event_id}>{tr({direct_settled:'Collection verified',disputed:'Disputed',reversed:'Reversed — review required',refund_confirmed:'Refund confirmed'}[e.kind])} · {e.evidence}</p>)}</article>)}
 {data&&<div className="flex gap-3"><button type="button" disabled={busy||page<=1} onClick={()=>{setData(null);setPage(n=>n-1);}}>{tr('Previous')}</button><span>{page}</span><button type="button" disabled={busy||page*20>=data.total} onClick={()=>{setData(null);setPage(n=>n+1);}}>{tr('Next')}</button></div>}
 {!!data?.earnings.length&&<form onSubmit={submit} className="mt-3 space-y-3"><fieldset disabled={busy}><label className="block">{tr('Earning')}<select required value={selection} onChange={e=>setSelection(e.target.value)}><option value="">{tr('Select')}</option>{data.earnings.map(row=><option key={row.earning_id} value={row.earning_id}>#{row.delivery_request_id} · {money(row.amount)}</option>)}</select></label>
 <label className="block">{tr('Review action')}<select value={kind} onChange={e=>setKind(e.target.value)}>{[['direct_settled','Verify direct settlement'],['disputed','Disputed'],['reversed','Reversed — review required'],['refund_confirmed','Confirm refund evidence']].map(([value,label])=><option value={value} key={value}>{tr(label)}</option>)}</select></label>
 <label className="block">{tr('Independent evidence reference')}<input required minLength={10} maxLength={1000} value={evidence} onChange={e=>setEvidence(e.target.value)} /></label>
 <label className="block"><input type="checkbox" required/>{tr('I independently checked the recorded evidence. A Driver declaration alone is not verification.')}</label>
 <button type="submit">{tr('Record verification')}</button></fieldset></form>}</section>;
}
