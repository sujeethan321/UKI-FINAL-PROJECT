// Purpose: Render the reusable customer addresses interface and keep its presentation and interactions together.
import {useContext,useEffect,useState,useSyncExternalStore} from 'react';
import {AuthContext} from '../../context/AuthContext';
import {useAppTranslation} from '../../i18n/useAppTranslation';
import * as api from '../../services/customerAddressService';
import {createAddressReader} from '../../utils/customerAddress';
import {orderButton as button,orderField as field} from '../../utils/shopping';

const empty={label:'',recipient_name:'',address_line:'',city:'',phone:''};
// Render the destination interface and connect its controls to the state and callbacks defined here.
export function Destination({value}){
 const {tr}=useAppTranslation();
 return value?<div className="mt-3 space-y-1 whitespace-pre-line break-words text-sm"><h4 className="font-semibold">{tr('Confirmed delivery destination')}</h4><p>{value.recipient_name}</p><p>{value.address_line}</p>{value.city&&<p>{value.city}</p>}{value.phone&&<p>{value.phone}</p>}</div>:null;
}
// Render the address book view interface and connect its controls to the state and callbacks defined here.
export function AddressBookView({state,actions,select,onSelect}){
 const {tr}=useAppTranslation();const [draft,setDraft]=useState(null),[editing,setEditing]=useState(null),[key,setKey]=useState(null);
 // Open a fresh address draft or copy the selected address into the editor.
 function begin(row){setEditing(row?.address_id??null);setDraft(row?Object.fromEntries(Object.keys(empty).map(k=>[k,row[k]||''])):{...empty});setKey(crypto.randomUUID());}
 return <div className="mt-4 space-y-3">
  {state.loading&&<p role="status">{tr('Loading addresses…')}</p>}{state.error&&<p role="alert">{tr(state.error)}</p>}
  {state.data&&<><p className="text-xs text-[#64748B]">{tr('Up to 10 saved addresses. Recipient phone is not verified. The shop reviews delivery feasibility.')}</p>
   {!state.data.addresses.length&&<p>{tr('No saved addresses.')}</p>}
   {state.data.addresses.map(row=><div key={row.address_id} className="rounded-lg border border-[#E1EAF4] p-3"><h4 className="font-semibold">{row.label}{row.address_id===state.data.default_address_id?' · '+tr('Default'):''}</h4><Destination value={row}/><div className="mt-3 flex flex-wrap gap-2">{select?<button type="button" className={button} onClick={()=>onSelect({address_id:row.address_id,address_version:state.data.version})}>{tr('Use this address')}</button>:<><button type="button" className={button} disabled={state.saving} onClick={()=>begin(row)}>{tr('Edit address')}</button><button type="button" className={button} disabled={state.saving} onClick={()=>actions.save('default',row.address_id)}>{tr('Set default address')}</button><button type="button" className={button} disabled={state.saving} onClick={()=>actions.save('archive',row.address_id)}>{tr('Archive address')}</button></>}</div></div>)}
   {!select&&<><button type="button" className={button} disabled={state.saving||state.data.addresses.length>=10} onClick={()=>begin(null)}>{tr('Add address')}</button>{state.data.default_address_id&&<button type="button" className={button} disabled={state.saving} onClick={()=>actions.save('default',null)}>{tr('Clear default address')}</button>}</>}
  </>}
  {draft&&<form className="grid gap-3" onSubmit={async event=>{event.preventDefault();if(await actions.save(editing?'edit':'create',editing,{...draft,city:draft.city||null,phone:draft.phone||null,request_key:key})){setDraft(null);setEditing(null);}}}>
   {Object.entries({label:['Address label',50],recipient_name:['Recipient name',150],address_line:['Address line',500],city:['City (optional)',100],phone:['Recipient phone (optional)',20]}).map(([name,[label,max]])=><label className="text-sm" key={name}>{tr(label)}{name==='address_line'?<textarea className={field} required maxLength={max} disabled={state.saving} value={draft[name]} onChange={e=>setDraft({...draft,[name]:e.target.value})}/>:<input className={field} required={!['city','phone'].includes(name)} maxLength={max} disabled={state.saving} value={draft[name]} onChange={e=>setDraft({...draft,[name]:e.target.value})}/>}</label>)}
   <div className="flex gap-2"><button className={button} disabled={state.saving}>{tr('Save address')}</button><button type="button" className={button} disabled={state.saving} onClick={()=>setDraft(null)}>{tr('Cancel')}</button></div>
  </form>}
  <button type="button" className={button} disabled={state.saving||state.loading} onClick={()=>actions.load()}>{tr('Reload addresses')}</button>
 </div>;
}
// Render the address session interface and connect its controls to the state and callbacks defined here.
function AddressSession(props){
 const [reader]=useState(()=>createAddressReader(api));const state=useSyncExternalStore(reader.subscribe,reader.getSnapshot,reader.getSnapshot);
 // Start resource work after rendering and cancel or dispose it during cleanup so obsolete work cannot update this view.
 useEffect(()=>{reader.start();return()=>reader.dispose();},[reader]);
 return <AddressBookView state={state} actions={reader} {...props}/>;
}
// Render the customer addresses interface and connect its controls to the state and callbacks defined here.
export default function CustomerAddresses(props){
 const {user,token,isAuthenticated}=useContext(AuthContext)||{};
 if(!isAuthenticated||user?.platform_role!=='customer'||user.account_status!=='active')return null;
 return <AddressSession key={user.user_id+':'+token} {...props}/>;
}
