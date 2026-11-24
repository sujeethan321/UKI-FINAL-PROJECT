import {useContext,useEffect,useState,useSyncExternalStore} from 'react';
import {AuthContext} from '../../context/AuthContext';
import {useAppTranslation} from '../../i18n/useAppTranslation';
import {getProfile,updateProfile} from '../../services/profileService';
import {createProfileReader} from '../../utils/profile';

const field='mt-2 block min-h-11 w-full rounded-lg border border-[#DAE5F3] bg-white px-3 py-2.5 text-sm text-[#10243E] disabled:bg-[#F5F8FC]';
const button='min-h-11 rounded-lg border border-[#DAE5F3] bg-white px-4 py-2 text-sm font-semibold text-[#10243E] hover:border-[#12B8A6] disabled:opacity-50';
export function ProfileFormView({state,actions}){
 const {tr}=useAppTranslation();const [name,setName]=useState(state.data?.full_name||'');const [language,setLanguage]=useState(state.data?.preferred_language||'en');
 const data=state.data;
 return <section className="rounded-xl border border-[#E1EAF4] bg-white p-5 text-[#10243E]" aria-label={tr('Personal Profile')}>
  <h3 className="text-xl font-bold">{tr('Personal Profile')}</h3><p className="mt-2 text-xs text-[#64748B]">{tr('Display name is not verified legal identity. Email and phone are read-only and no verification is implied.')}</p>
  {state.loading&&<p role="status" className="mt-4">{tr('Loading personal profile…')}</p>}
  {state.error&&<p role="alert" className="mt-4 text-sm text-[#DC4545]">{tr(state.error)}</p>}
  {state.notice&&<p role="status" className="mt-4 text-sm">{tr(state.notice)}</p>}
  {data&&<form className="mt-4 grid gap-4 sm:grid-cols-2" onSubmit={async event=>{event.preventDefault();const saved=await actions.save({full_name:name,preferred_language:language});if(saved){setName(saved.full_name);setLanguage(saved.preferred_language);}}}>
   <label className="text-sm font-semibold">{tr('Display Name')}<input className={field} value={name} required minLength={2} maxLength={150} disabled={state.saving} onChange={event=>setName(event.target.value)} autoComplete="name"/></label>
   <label className="text-sm font-semibold">{tr('Preferred Language')}<select className={field} value={language} disabled={state.saving} onChange={event=>setLanguage(event.target.value)}><option value="en">English</option><option value="ta">தமிழ்</option><option value="si">සිංහල</option></select></label>
   <label className="text-sm">{tr('Email')}<input className={field} readOnly value={data.email}/></label>
   <label className="text-sm">{tr('Phone')}<input className={field} readOnly value={data.phone||tr('Not available')}/></label>
   <button className={button+' justify-self-start'} disabled={state.saving}>{tr(state.saving?'Saving…':'Save Changes')}</button>
  </form>}
  <button type="button" className={button+' mt-4'} disabled={state.saving||state.loading} onClick={()=>actions.load()}>{tr('Reload profile (discard unsaved edits)')}</button>
 </section>;
}
function ProfileSession({identity,refreshIdentity,signalProfileChanged}){
 const [reader]=useState(()=>createProfileReader({identity,api:{getProfile,updateProfile},refreshIdentity,signalProfileChanged}));
 const state=useSyncExternalStore(reader.subscribe,reader.getSnapshot,reader.getSnapshot);
 useEffect(()=>{reader.start();return()=>reader.dispose();},[reader]);
 return <ProfileFormView key={state.data?.revision||'loading'} state={state} actions={reader}/>;
}
export default function ProfileForm(){
 const {user,token,isAuthenticated,refreshIdentity,signalProfileChanged}=useContext(AuthContext)||{};
 if(!isAuthenticated||user?.account_status!=='active')return null;
 return <ProfileSession key={user.user_id+':'+token} identity={user} refreshIdentity={refreshIdentity} signalProfileChanged={signalProfileChanged}/>;
}
