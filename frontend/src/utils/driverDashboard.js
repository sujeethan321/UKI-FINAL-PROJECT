// Purpose: Keep driver dashboard data handling and workflow helpers separate from React rendering so callers use consistent rules.
import {validDeliveryEstimate} from './deliveryEstimate.js';
// Accept only supported identifiers before response data is used for lookups or navigation.
const id=value=>Number.isSafeInteger(value)&&value>0;
// Validate count values before the interface uses them for totals or pagination.
const count=value=>Number.isSafeInteger(value)&&value>=0;
// Validate text values at the response boundary before rendering them.
const text=value=>typeof value==='string'&&!!value.trim();
// Project only the named response fields so unrelated API fields do not enter view state.
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
// Format assigned time for display so screens use a consistent representation.
export function formatAssignedTime(value) {
 return typeof value==='string'&&/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(value)&&!Number.isNaN(Date.parse(value)) ? value.replace('T',' ').split('.')[0]+' UTC':'Time unavailable';
}
// Check driver response before the surrounding workflow uses it.
export function parseDriverResponse(section,data,userId) {
 if(!id(userId)||data?.driver_user_id!==userId)throw Error('Driver identity mismatch');
 if(section==='profile'){
  if(!text(data.full_name)||data.account_status!=='active'||!Object.hasOwn(driverApprovalLabels,data.approval_status)||typeof data.eligible_for_jobs!=='boolean'||!Object.hasOwn(driverEligibilityMessages,data.eligibility_reason))throw Error('Invalid driver profile');
  if(data.vehicle!==null&&(!data.vehicle||!text(data.vehicle.vehicle_type)||!text(data.vehicle.registration_reference)))throw Error('Invalid vehicle');
  const expected=data.approval_status==='not_submitted'?'profile_required':data.approval_status!=='approved'?'approval_'+data.approval_status:data.vehicle?'eligible':'vehicle_required';
  if(data.eligibility_reason!==expected||data.eligible_for_jobs!==(expected==='eligible'))throw Error('Unconfirmed eligibility');
  const vehicleStatus=data.vehicle_registration_status ?? (data.approval_status==='not_submitted'?'not_registered':data.approval_status);
  if(!['not_registered','pending','approved','rejected','suspended'].includes(vehicleStatus))throw Error('Invalid vehicle status');
  const documentStatuses=data.document_statuses ?? {};
  if(!documentStatuses||typeof documentStatuses!=='object'||Array.isArray(documentStatuses)||Object.entries(documentStatuses).some(([key,value])=>!['DRIVING_LICENCE','VEHICLE_OWNERSHIP_PROOF'].includes(key)||!['PENDING','APPROVED','REJECTED'].includes(value)))throw Error('Invalid document status');
  return {...pick(data,['driver_user_id','full_name','account_status','approval_status','eligible_for_jobs','eligibility_reason']),vehicle_registration_status:vehicleStatus,document_statuses:{...documentStatuses},legacy_document_exempt:data.legacy_document_exempt===true,vehicle:data.vehicle?pick(data.vehicle,['vehicle_type','registration_reference']):null};
 }
 if(section==='summary'){
  const keys=['available_jobs_count','active_deliveries_count','completed_deliveries_count'];
  if(!keys.every(key=>count(data[key])))throw Error('Missing driver counts');
  return pick(data,['driver_user_id',...keys]);
 }
 if(section!=='deliveries'||data.page!==1||data.page_size!==5||!count(data.total)||!Array.isArray(data.deliveries)||data.deliveries.length>5||data.deliveries.length>data.total)throw Error('Invalid delivery page');
 const seen=new Set();const deliveries=data.deliveries.map(row=>{
  if(!row||!id(row.delivery_request_id)||seen.has(row.delivery_request_id)||!['reference','business_name','pickup_area','delivery_area'].every(key=>text(row[key]))||!['assigned','picked_up','in_transit'].includes(row.status)||formatAssignedTime(row.assigned_at)==='Time unavailable')throw Error('Invalid assigned delivery');
  const subtotal=row.linked_order_subtotal??null,estimate=row.estimated_delivery_earning??null;
  if((subtotal!==null||estimate!==null)&&!validDeliveryEstimate(subtotal,estimate))throw Error('Unconfirmed delivery estimate');
  seen.add(row.delivery_request_id);return {...pick(row,['delivery_request_id','reference','business_name','pickup_area','delivery_area','status','assigned_at']),linked_order_subtotal:subtotal,estimated_delivery_earning:estimate};
 });
 return {total:data.total,deliveries};
}
// Translate driver read outcomes into display text for the interface.
export function driverReadError(error) {
 if(error?.response?.status===401)return 'Your session has expired. Please sign in again.';
 if(error?.response?.status===403)return 'Driver access is unavailable. Check your account status or sign in with your driver account.';
 if(error?.code==='INVALID_DRIVER_RESPONSE')return 'This driver response could not be verified. Please retry.';
 if(error?.code==='ECONNABORTED')return 'This request is taking too long. Please retry.';
 return 'Driver information is unavailable. Check your connection and retry.';
}
const sections=['profile','summary','deliveries'];
// Create independent initial resource state so new readers do not inherit another instance state.
const fresh=loading=>({authError:'',...Object.fromEntries(sections.map(key=>[key,{data:null,loading,error:''}]))});
// Create driver dashboard reader for the driver dashboard workflow.
export function createDriverDashboardReader(api,userId) {
 let state=fresh(true),active=false,generation=0;const listeners=new Set(),controllers={},versions={};
 // Replace the store snapshot and notify subscribers so React can render the new state.
 const publish=next=>{state=next;if(active)listeners.forEach(fn=>fn());};
 // Cancel outstanding reads before the reader is reset or disposed.
 const abortAll=()=>Object.values(controllers).forEach(controller=>controller.abort());
 // Load the current resource data and update the state consumed by the interface.
 async function load(section){
  if(!active||state.authError||!sections.includes(section))return;
  controllers[section]?.abort();const controller=new AbortController();controllers[section]=controller;
  const version=versions[section]=(versions[section]||0)+1,current=generation;
  // Check valid before the surrounding workflow uses it.
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
 return {/* Expose the current store snapshot to subscribers without starting a request. */ getSnapshot:()=>state,/* Register a state listener and return cleanup so consumers can unsubscribe. */ subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},load,
  // Start the resource workflow using its current context and selection.
  start(){active=true;generation++;abortAll();publish(fresh(true));return Promise.allSettled(sections.map(load));},
  // Release pending work and subscriptions when this resource reader is no longer used.
  dispose(){active=false;generation++;abortAll();state=fresh(false);}};
}
