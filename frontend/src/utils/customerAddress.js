const fields=['label','recipient_name','address_line','city','phone'];
export function parseDestination(value){
 if(value==null)return null;
 if(typeof value.recipient_name!=='string'||!value.recipient_name.trim()||value.recipient_name.length>150||
 typeof value.address_line!=='string'||!value.address_line.trim()||value.address_line.length>500||
 !(value.phone===null||typeof value.phone==='string'&&value.phone.length<=20)||!(value.city===null||typeof value.city==='string'&&value.city.length<=100))throw Error('Invalid destination');
 return Object.fromEntries(['recipient_name','phone','address_line','city'].map(key=>[key,value[key]]));
}
export function parseAddressBook(data){
 if(!Number.isSafeInteger(data?.version)||data.version<1||!Array.isArray(data.addresses)||data.addresses.length>10||
 data.total!==data.addresses.length||data.page!==1||!Number.isSafeInteger(data.total)||
 !(data.default_address_id===null||Number.isSafeInteger(data.default_address_id)))throw Error('Invalid address book');
 const addresses=data.addresses.map(row=>{
  if(!Number.isSafeInteger(row.address_id)||row.address_id<1||typeof row.label!=='string'||!row.label.trim()||row.label.length>50||row.archived!==false)throw Error('Invalid saved address');
  return {address_id:row.address_id,label:row.label,...parseDestination(row),archived:false};
 });
 if(new Set(addresses.map(r=>r.address_id)).size!==addresses.length||data.default_address_id!==null&&!addresses.some(r=>r.address_id===data.default_address_id))throw Error('Invalid default address');
 return {version:data.version,default_address_id:data.default_address_id,addresses};
}
export function addressError(error){
 const status=error?.response?.status;
 return status===503?'Address management is unavailable on this server.':status===409?'Address book changed. Reload and review before continuing.':
 status===401||status===403?'Address access is unavailable. Check your session.':status===422?'Check the address fields.':'Address request could not be confirmed. Reload before continuing.';
}
export function createAddressReader(api){
 let state={data:null,loading:false,saving:false,error:''},active=false,generation=0,controller;
 const listeners=new Set();const publish=patch=>{if(active){state={...state,...patch};listeners.forEach(fn=>fn());}};
 const reader={subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},getSnapshot:()=>state,
 start(){active=true;return reader.load();},
 async load(){
  if(state.saving)return;controller?.abort();controller=new AbortController();const signal=controller.signal,seq=++generation;
  publish({loading:true,data:null,error:''});
  try{const data=parseAddressBook(await api.listAddresses(signal));if(active&&!signal.aborted&&seq===generation)publish({loading:false,data});}
  catch(error){if(active&&!signal.aborted&&seq===generation)publish({loading:false,error:addressError(error)});}
 },
 async save(operation,id,data){
  if(!active||state.saving||!state.data)return false;
  const version=state.data.version;controller?.abort();controller=new AbortController();const signal=controller.signal,seq=++generation;
  publish({saving:true,error:''});
  try{
   if(operation==='create')await api.createAddress({...Object.fromEntries(fields.map(k=>[k,data[k]])),version,request_key:data.request_key},signal);
   else if(operation==='edit')await api.editAddress(id,{...Object.fromEntries(fields.map(k=>[k,data[k]])),version},signal);
   else if(operation==='archive')await api.archiveAddress(id,version,signal);
   else if(operation==='default')await api.defaultAddress(id,version,signal);
   else throw Error('Invalid operation');
   if(!active||signal.aborted||seq!==generation)return false;
   publish({saving:false});await reader.load();return true;
  }catch(error){if(active&&!signal.aborted&&seq===generation)publish({saving:false,error:addressError(error),...([401,403].includes(error?.response?.status)?{data:null}:{})});return false;}
 },
 dispose(){active=false;generation++;controller?.abort();state={data:null,loading:false,saving:false,error:''};listeners.clear();}
 };return reader;
}
