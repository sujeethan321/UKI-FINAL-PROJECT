const id=value=>Number.isSafeInteger(value)&&value>0;
const count=value=>Number.isSafeInteger(value)&&value>=0;
const text=value=>typeof value==='string'&&!!value.trim();
const pick=(row,keys)=>Object.fromEntries(keys.map(key=>[key,row[key]]));
export const driverApprovalLabels={not_submitted:'Not submitted',pending:'Pending review',approved:'Approved',rejected:'Rejected',suspended:'Suspended'};
export const driverEligibilityMessages={
 profile_required:'Your driver profile has not been submitted. Delivery access requires profile review.',
 approval_pending:'Your driver profile is pending review. You cannot accept jobs yet.',
 approval_rejected:'Your driver profile was not approved. Contact support for guidance.',
 approval_suspended:'Your driver eligibility is suspended. Contact support for guidance.',
 vehicle_required:'Vehicle information is required before delivery work is permitted.',
 eligible:'Your driver profile is approved and eligible for delivery work.',
};
export function formatAssignedTime(value) {
 return typeof value==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(value)&&!Number.isNaN(Date.parse(value)) ? value.replace('T',' ').split('.')[0]+' UTC':'Time unavailable';
}
export function parseDriverResponse(section,data,userId) {
 if(!id(userId)||data?.driver_user_id!==userId)throw Error('Driver identity mismatch');
 if(section==='profile'){
  if(!text(data.full_name)||data.account_status!=='active'||!Object.hasOwn(driverApprovalLabels,data.approval_status)||typeof data.eligible_for_jobs!=='boolean'||!Object.hasOwn(driverEligibilityMessages,data.eligibility_reason))throw Error('Invalid driver profile');
  if(data.vehicle!==null&&(!data.vehicle||!text(data.vehicle.vehicle_type)||!text(data.vehicle.registration_reference)))throw Error('Invalid vehicle');
  const expected=data.approval_status==='not_submitted'?'profile_required':data.approval_status!=='approved'?'approval_'+data.approval_status:data.vehicle?'eligible':'vehicle_required';
  if(data.eligibility_reason!==expected||data.eligible_for_jobs!==(expected==='eligible'))throw Error('Unconfirmed eligibility');
  return {...pick(data,['driver_user_id','full_name','account_status','approval_status','eligible_for_jobs','eligibility_reason']),vehicle:data.vehicle?pick(data.vehicle,['vehicle_type','registration_reference']):null};
 }
 if(section==='summary'){
  const keys=['available_jobs_count','active_deliveries_count','completed_deliveries_count'];
  if(!keys.every(key=>count(data[key])))throw Error('Missing driver counts');
  return pick(data,['driver_user_id',...keys]);
 }
 if(section!=='deliveries'||data.page!==1||data.page_size!==5||!count(data.total)||!Array.isArray(data.deliveries)||data.deliveries.length>5||data.deliveries.length>data.total)throw Error('Invalid delivery page');
 const seen=new Set();const deliveries=data.deliveries.map(row=>{
  if(!row||!id(row.delivery_request_id)||seen.has(row.delivery_request_id)||!['reference','business_name','pickup_area','delivery_area'].every(key=>text(row[key]))||!['assigned','picked_up','in_transit'].includes(row.status)||formatAssignedTime(row.assigned_at)==='Time unavailable')throw Error('Invalid assigned delivery');
  seen.add(row.delivery_request_id);return pick(row,['delivery_request_id','reference','business_name','pickup_area','delivery_area','status','assigned_at']);
 });
 return {total:data.total,deliveries};
}
export function driverReadError(error) {
 if(error?.response?.status===401)return 'Your session has expired. Please sign in again.';
 if(error?.response?.status===403)return 'Driver access is unavailable. Check your account status or sign in with your driver account.';
 if(error?.code==='INVALID_DRIVER_RESPONSE')return 'This driver response could not be verified. Please retry.';
 if(error?.code==='ECONNABORTED')return 'This request is taking too long. Please retry.';
 return 'Driver information is unavailable. Check your connection and retry.';
}
const sections=['profile','summary','deliveries'];
const fresh=loading=>({authError:'',...Object.fromEntries(sections.map(key=>[key,{data:null,loading,error:''}]))});
export function createDriverDashboardReader(api,userId) {
 let state=fresh(true),active=false,generation=0;const listeners=new Set(),controllers={},versions={};
 const publish=next=>{state=next;if(active)listeners.forEach(fn=>fn());};
 const abortAll=()=>Object.values(controllers).forEach(controller=>controller.abort());
 async function load(section){
  if(!active||state.authError||!sections.includes(section))return;
  controllers[section]?.abort();const controller=new AbortController();controllers[section]=controller;
  const version=versions[section]=(versions[section]||0)+1,current=generation;
  const valid=()=>active&&!controller.signal.aborted&&generation===current&&versions[section]===version;
  publish({...state,[section]:{data:null,loading:true,error:''}});
  try{
   const response=await api[section]({signal:controller.signal});if(!valid())return;
   let data;try{data=parseDriverResponse(section,response,userId);}catch{throw Object.assign(Error('Invalid driver response'),{code:'INVALID_DRIVER_RESPONSE'});}
   publish({...state,[section]:{data,loading:false,error:''}});
  }catch(error){if(!valid())return;
   if([401,403].includes(error?.response?.status)){generation++;abortAll();publish({...fresh(false),authError:driverReadError(error)});}
   else publish({...state,[section]:{data:null,loading:false,error:driverReadError(error)}});
  }
 }
 return {getSnapshot:()=>state,subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},load,
  start(){active=true;generation++;abortAll();publish(fresh(true));return Promise.allSettled(sections.map(load));},
  dispose(){active=false;generation++;abortAll();state=fresh(false);}};
}
