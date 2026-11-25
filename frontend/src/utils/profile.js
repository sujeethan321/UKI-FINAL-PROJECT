// Purpose: Validate profile identity and coordinate reads and revision-checked saves while ignoring cancelled or superseded responses.
// Check profile before the surrounding workflow uses it.
export function parseProfile(data,identity){
 // Match both user ID and role before allowing a profile response into a screen belonging to this session.
 if(!data||data.user_id!==identity.user_id||data.platform_role!==identity.platform_role||data.account_status!=='active'||
    typeof data.full_name!=='string'||!['en','ta','si'].includes(data.preferred_language)||typeof data.email!=='string'||
    !(data.phone===null||typeof data.phone==='string')||!/^p1-[a-f0-9]{64}$/.test(data.revision))throw Error('Invalid profile response');
 return Object.fromEntries(['user_id','platform_role','account_status','full_name','preferred_language','email','phone','revision'].map(key=>[key,data[key]]));
}
// Translate profile outcomes into display text for the interface.
export function profileError(error){
 const status=error?.response?.status;
 return status===409?'Profile changed in another tab. Reload before saving again.':status===422||status===413?'Enter a valid display name and supported language.':
  status===401||status===403?'Profile access is unavailable. Check your session.':status===429?'Too many profile requests. Please wait.':'Profile could not be confirmed. Reload before continuing.';
}
// Create profile reader for the profile workflow.
export function createProfileReader({identity,api,refreshIdentity,signalProfileChanged}){
 // Generations distinguish current requests from older ones; cancellation alone cannot prevent every late reply.
 let state={data:null,loading:false,saving:false,error:'',notice:''},disposed=false,version=0,controller=null;
 const listeners=new Set();const update=patch=>{if(!disposed){state={...state,...patch};for(const listener of listeners)listener();}};
 const reader={
  // Register a state listener and return cleanup so consumers can unsubscribe.
  subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},/* Expose the current store snapshot to subscribers without starting a request. */ getSnapshot:()=>state,
  // Start the resource workflow using its current context and selection.
  start(){disposed=false;return reader.load();},
  // Load the requested resource section and publish its loading or result state.
  async load(){
   // Do not replace a pending save with a read; cancel the previous read and give this one a new generation.
   if(disposed||state.saving)return;controller?.abort();const active=new AbortController();controller=active;const generation=++version;
   update({loading:true,data:null,error:'',notice:''});
   try{const data=parseProfile(await api.getProfile(active.signal),identity);if(!disposed&&!active.signal.aborted&&generation===version)update({loading:false,data});}
   catch(error){if(!disposed&&!active.signal.aborted&&generation===version)update({loading:false,data:null,error:profileError(error)});}
  },
  // Validate the draft and send its revision so a stale edit cannot overwrite a changed record.
  async save(changes){
   if(disposed||!state.data||state.saving||state.loading)return;
   // Reject unexpected fields locally as well as on the API; contact details and account privileges are read-only here.
   if(Object.keys(changes).some(key=>!['full_name','preferred_language'].includes(key))||typeof changes.full_name!=='string'||!changes.full_name.trim()||changes.full_name.trim().length>150||!['en','ta','si'].includes(changes.preferred_language)){
    update({error:'Enter a valid display name and supported language.'});return;
   }
   controller?.abort();const active=new AbortController();controller=active;const generation=++version;
   // Save with the revision actually displayed, allowing the server to detect a conflicting edit from another tab.
   const revision=state.data.revision;update({saving:true,error:'',notice:''});
   try{
    const data=parseProfile(await api.updateProfile({full_name:changes.full_name,preferred_language:changes.preferred_language},revision,active.signal),identity);
    if(disposed||active.signal.aborted||generation!==version)return;
    // Refresh shared identity before reporting success so the header and language preference use confirmed account data.
    const verified=await refreshIdentity();
    if(disposed||active.signal.aborted||generation!==version)return;
    if(!verified)throw Error('Identity refresh superseded');
    if(verified.user_id!==identity.user_id||verified.platform_role!==identity.platform_role)throw Error('Identity changed');
    // Other tabs receive an opaque signal and fetch their own authorized profile rather than sharing its contents.
    signalProfileChanged();
    update({saving:false,data,notice:'Updated Successfully'});return data;
   }catch(error){if(!disposed&&!active.signal.aborted&&generation===version)update({saving:false,error:profileError(error),...([401,403].includes(error?.response?.status)?{data:null}:{})});}
  },
  // Release pending work and subscriptions when this resource reader is no longer used.
  dispose(){disposed=true;version++;controller?.abort();state={...state,data:null,saving:false};listeners.clear();}
 };return reader;
}
