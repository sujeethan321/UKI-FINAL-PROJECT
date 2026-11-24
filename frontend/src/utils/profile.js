export function parseProfile(data,identity){
 if(!data||data.user_id!==identity.user_id||data.platform_role!==identity.platform_role||data.account_status!=='active'||
    typeof data.full_name!=='string'||!['en','ta','si'].includes(data.preferred_language)||typeof data.email!=='string'||
    !(data.phone===null||typeof data.phone==='string')||!/^p1-[a-f0-9]{64}$/.test(data.revision))throw Error('Invalid profile response');
 return Object.fromEntries(['user_id','platform_role','account_status','full_name','preferred_language','email','phone','revision'].map(key=>[key,data[key]]));
}
export function profileError(error){
 const status=error?.response?.status;
 return status===409?'Profile changed in another tab. Reload before saving again.':status===422||status===413?'Enter a valid display name and supported language.':
  status===401||status===403?'Profile access is unavailable. Check your session.':status===429?'Too many profile requests. Please wait.':'Profile could not be confirmed. Reload before continuing.';
}
export function createProfileReader({identity,api,refreshIdentity,signalProfileChanged}){
 let state={data:null,loading:false,saving:false,error:'',notice:''},disposed=false,version=0,controller=null;
 const listeners=new Set();const update=patch=>{if(!disposed){state={...state,...patch};for(const listener of listeners)listener();}};
 const reader={
  subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},getSnapshot:()=>state,
  start(){disposed=false;return reader.load();},
  async load(){
   if(disposed||state.saving)return;controller?.abort();const active=new AbortController();controller=active;const generation=++version;
   update({loading:true,data:null,error:'',notice:''});
   try{const data=parseProfile(await api.getProfile(active.signal),identity);if(!disposed&&!active.signal.aborted&&generation===version)update({loading:false,data});}
   catch(error){if(!disposed&&!active.signal.aborted&&generation===version)update({loading:false,data:null,error:profileError(error)});}
  },
  async save(changes){
   if(disposed||!state.data||state.saving||state.loading)return;
   if(Object.keys(changes).some(key=>!['full_name','preferred_language'].includes(key))||typeof changes.full_name!=='string'||!changes.full_name.trim()||changes.full_name.trim().length>150||!['en','ta','si'].includes(changes.preferred_language)){
    update({error:'Enter a valid display name and supported language.'});return;
   }
   controller?.abort();const active=new AbortController();controller=active;const generation=++version;
   const revision=state.data.revision;update({saving:true,error:'',notice:''});
   try{
    const data=parseProfile(await api.updateProfile({full_name:changes.full_name,preferred_language:changes.preferred_language},revision,active.signal),identity);
    if(disposed||active.signal.aborted||generation!==version)return;
    const verified=await refreshIdentity();
    if(disposed||active.signal.aborted||generation!==version)return;
    if(!verified)throw Error('Identity refresh superseded');
    if(verified.user_id!==identity.user_id||verified.platform_role!==identity.platform_role)throw Error('Identity changed');
    signalProfileChanged();
    update({saving:false,data,notice:'Updated Successfully'});return data;
   }catch(error){if(!disposed&&!active.signal.aborted&&generation===version)update({saving:false,error:profileError(error),...([401,403].includes(error?.response?.status)?{data:null}:{})});}
  },
  dispose(){disposed=true;version++;controller?.abort();state={...state,data:null,saving:false};listeners.clear();}
 };return reader;
}
