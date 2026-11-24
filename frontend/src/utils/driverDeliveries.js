// Purpose: Keep driver deliveries data handling and workflow helpers separate from React rendering so callers use consistent rules.
import {parseAssignment} from './driverJobs.js';
import {parseDriverResponse,driverReadError,formatAssignedTime} from './driverDashboard.js';

export const deliveryLabels={assigned:'Assigned',picked_up:'Picked up',in_transit:'In transit',delivered:'Delivered',cancelled:'Cancelled'};
export const deliveryActions={picked_up:'Confirm Pickup',in_transit:'Start Delivery',delivered:'Mark Delivered'};
const next={assigned:'picked_up',picked_up:'in_transit',in_transit:'delivered'};
// Check the timestamp representation before it enters delivery view state.
const time=value=>formatAssignedTime(value)!=='Time unavailable';
// Check delivery progress before the surrounding workflow uses it.
export function parseDeliveryProgress(data,userId,id) {
  const result=parseAssignment(data,userId,id,true);
  if(!Array.isArray(data.events)||!data.events.length||data.events[0].status!=='assigned'||data.events[0].occurred_at!==result.delivery.assigned_at)throw Error('Invalid timeline');
  const seen=new Set();let previous='';
  const events=data.events.map(event=>{
    if(!Object.hasOwn(deliveryLabels,event.status)||seen.has(event.status)||!time(event.occurred_at)||event.occurred_at<previous)throw Error('Invalid timeline event');
    seen.add(event.status);previous=event.occurred_at;return {status:event.status,occurred_at:event.occurred_at};
  });
  if(data.allowed_next_status!==null&&(!next[result.delivery.status]||data.allowed_next_status!==next[result.delivery.status]))throw Error('Invalid next action');
  return {...result,events,allowed_next_status:data.allowed_next_status};
}
// Check delivery page before the surrounding workflow uses it.
export function parseDeliveryPage(data,userId,page,history,status='') {
  if(data?.driver_user_id!==userId||data.page!==page||data.page_size!==10||!Number.isSafeInteger(data.total)||data.total<0||!Array.isArray(data.deliveries)||data.deliveries.length>Math.min(10,data.total))throw Error('Invalid delivery page');
  const seen=new Set(),allowed=history?['delivered','cancelled']:['assigned','picked_up','in_transit'];
  const deliveries=data.deliveries.map(row=>{
    const parsed=parseAssignment({driver_user_id:userId,assignment_id:1,delivery:row},userId,row.delivery_request_id,true).delivery;
    if(!Number.isSafeInteger(parsed.delivery_request_id)||parsed.delivery_request_id<1||seen.has(parsed.delivery_request_id)||!allowed.includes(parsed.status)||(status&&parsed.status!==status)||(row.finished_at!==null&&!time(row.finished_at)))throw Error('Invalid delivery record');
    seen.add(parsed.delivery_request_id);return {...parsed,finished_at:row.finished_at};
  });return {total:data.total,deliveries};
}
// Create a resource section with its own data, loading, and error state for independent updates.
const section=()=>({data:null,loading:false,error:''});
// Build initial workflow state before resource loading or user interaction begins.
const initial=()=>({authError:'',page:1,status:'',profile:section(),summary:section(),list:section(),detail:section(),busy:false,uncertain:false,message:''});
// Create deliveries workflow for the driver deliveries workflow.
export function createDeliveriesWorkflow(api,userId,{history=false,deliveryId=null}={}) {
  let state=initial(),active=false,generation=0,inFlight=null;
  const listeners=new Set(),controllers={},versions={};
  // Replace the store snapshot and notify subscribers so React can render the new state.
  const publish=patch=>{if(active){state={...state,...patch};listeners.forEach(fn=>fn());}};
  // Cancel obsolete reads so their responses cannot update the active resource.
  const abort=()=>Object.values(controllers).forEach(c=>c.abort());
  // Clear protected resource state after access is denied so earlier data is not left visible.
  function deny(error){generation++;abort();publish({...initial(),authError:driverReadError(error)});}
  // Read the saved or current resource state used by this workflow.
  async function read(key,fetcher,parse) {
    if(!active||state.authError)return null;
    controllers[key]?.abort();const controller=controllers[key]=new AbortController(),version=versions[key]=(versions[key]||0)+1,current=generation;
    // Check valid before the surrounding workflow uses it.
    const valid=()=>active&&generation===current&&!controller.signal.aborted&&versions[key]===version;
    publish({[key]:{data:null,loading:true,error:''}});
    try{const response=await fetcher({signal:controller.signal});if(!valid())return null;let data;
      try{data=parse(response);}catch{throw Object.assign(Error('Invalid delivery response'),{code:'INVALID_DRIVER_RESPONSE'});}
      publish({[key]:{data,loading:false,error:''}});return data;
    }catch(error){if(!valid())return null;if([401,403].includes(error?.response?.status))deny(error);
      else publish({[key]:{data:null,loading:false,error:error?.response?.status===404?'Delivery not found or access is unavailable.':driverReadError(error)}});return null;}
  }
  // Load the driver profile needed to evaluate current workflow access.
  const profile=()=>read('profile',api.profile,data=>parseDriverResponse('profile',data,userId));
  // Load summary data separately from list or detail state so each section can refresh independently.
  const summary=()=>read('summary',api.summary,data=>parseDriverResponse('summary',data,userId));
  // Load the selected record detail into its resource section.
  const detail=()=>read('detail',options=>api.detail(deliveryId,options),data=>parseDeliveryProgress(data,userId,deliveryId));
  // Load the filtered list into its own loading, data, and error section.
  function list(){const {page,status}=state;return read('list',options=>api.list({history,page,status,...options}),data=>parseDeliveryPage(data,userId,page,history,status));}
  // Load the current resource data and update the state consumed by the interface.
  async function refresh(){if(state.busy)return;const result=await Promise.allSettled([profile(),summary(),deliveryId?detail():list()]);if(state.detail.data)publish({uncertain:false});return result;}
  // Apply the new state and notify the consumers or handlers registered by this workflow.
  async function update(){
    if(inFlight)return inFlight;
    const data=state.detail.data,target=data?.allowed_next_status;
    if(!active||state.authError||state.uncertain||!target||!state.profile.data?.eligible_for_jobs)return null;
    controllers.detail?.abort();const controller=controllers.mutation=new AbortController(),current=generation;
    // Check valid before the surrounding workflow uses it.
    const valid=()=>active&&generation===current&&!controller.signal.aborted;
    publish({busy:true,message:''});
    const operation=(async()=>{try{
      const response=await api.update(deliveryId,{expected_status:data.delivery.status,status:target},{signal:controller.signal});if(!valid())return null;
      const confirmed=parseDeliveryProgress(response,userId,deliveryId);
      if(confirmed.delivery.status!==target)throw Error('Unconfirmed delivery update');
      publish({detail:{data:confirmed,loading:false,error:''},message:'Delivery status updated.',uncertain:false});
      await Promise.allSettled([summary(),detail()]);return confirmed;
    }catch(error){if(!valid())return null;const status=error?.response?.status;
      if([401,403].includes(status)){deny(error);return null;}
      publish({detail:section(),uncertain:true,message:status===409?'This delivery changed. Refresh its details before taking another action.':status===404?'Delivery not found or access is unavailable.':status===422?'The status update was rejected. Refresh delivery details.':'Update could not be confirmed. Refresh delivery details to check its recorded status.'});return null;
    }finally{if(valid())publish({busy:false});}})();
    inFlight=operation;try{return await operation;}finally{if(inFlight===operation)inFlight=null;}
  }
  return {/* Expose the current store snapshot to subscribers without starting a request. */ getSnapshot:()=>state,/* Register a state listener and return cleanup so consumers can unsubscribe. */ subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},
    // Start the resource workflow using its current context and selection.
    start(){active=true;generation++;abort();publish(initial());return refresh();},refresh,update,
    // Change the list filters and reload the requested resource page.
    filter(status){if(state.busy)return;publish({status,page:1});return list();},
    // Change the current page and load its resource records.
    page(page){if(state.busy||!Number.isSafeInteger(page)||page<1||page>1000000)return;publish({page});return list();},
    // Release pending work and subscriptions when this resource reader is no longer used.
    dispose(){active=false;generation++;abort();state=initial();},
  };
}
