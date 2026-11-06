import {parseAssignment} from './driverJobs.js';
import {parseDriverResponse,driverReadError,formatAssignedTime} from './driverDashboard.js';

export const deliveryLabels={assigned:'Assigned',picked_up:'Picked up',in_transit:'In transit',delivered:'Delivered',cancelled:'Cancelled'};
export const deliveryActions={picked_up:'Confirm Pickup',in_transit:'Start Delivery',delivered:'Mark Delivered'};
const next={assigned:'picked_up',picked_up:'in_transit',in_transit:'delivered'};
const time=value=>formatAssignedTime(value)!=='Time unavailable';
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
export function parseDeliveryPage(data,userId,page,history,status='') {
  if(data?.driver_user_id!==userId||data.page!==page||data.page_size!==10||!Number.isSafeInteger(data.total)||data.total<0||!Array.isArray(data.deliveries)||data.deliveries.length>Math.min(10,data.total))throw Error('Invalid delivery page');
  const seen=new Set(),allowed=history?['delivered','cancelled']:['assigned','picked_up','in_transit'];
  const deliveries=data.deliveries.map(row=>{
    const parsed=parseAssignment({driver_user_id:userId,assignment_id:1,delivery:row},userId,row.delivery_request_id,true).delivery;
    if(!Number.isSafeInteger(parsed.delivery_request_id)||parsed.delivery_request_id<1||seen.has(parsed.delivery_request_id)||!allowed.includes(parsed.status)||(status&&parsed.status!==status)||(row.finished_at!==null&&!time(row.finished_at)))throw Error('Invalid delivery record');
    seen.add(parsed.delivery_request_id);return {...parsed,finished_at:row.finished_at};
  });return {total:data.total,deliveries};
}
const section=()=>({data:null,loading:false,error:''});
const initial=()=>({authError:'',page:1,status:'',profile:section(),summary:section(),list:section(),detail:section(),busy:false,uncertain:false,message:''});
export function createDeliveriesWorkflow(api,userId,{history=false,deliveryId=null}={}) {
  let state=initial(),active=false,generation=0,inFlight=null;
  const listeners=new Set(),controllers={},versions={};
  const publish=patch=>{if(active){state={...state,...patch};listeners.forEach(fn=>fn());}};
  const abort=()=>Object.values(controllers).forEach(c=>c.abort());
  function deny(error){generation++;abort();publish({...initial(),authError:driverReadError(error)});}
  async function read(key,fetcher,parse) {
    if(!active||state.authError)return null;
    controllers[key]?.abort();const controller=controllers[key]=new AbortController(),version=versions[key]=(versions[key]||0)+1,current=generation;
    const valid=()=>active&&generation===current&&!controller.signal.aborted&&versions[key]===version;
    publish({[key]:{data:null,loading:true,error:''}});
    try{const response=await fetcher({signal:controller.signal});if(!valid())return null;let data;
      try{data=parse(response);}catch{throw Object.assign(Error('Invalid delivery response'),{code:'INVALID_DRIVER_RESPONSE'});}
      publish({[key]:{data,loading:false,error:''}});return data;
    }catch(error){if(!valid())return null;if([401,403].includes(error?.response?.status))deny(error);
      else publish({[key]:{data:null,loading:false,error:error?.response?.status===404?'Delivery not found or access is unavailable.':driverReadError(error)}});return null;}
  }
  const profile=()=>read('profile',api.profile,data=>parseDriverResponse('profile',data,userId));
  const summary=()=>read('summary',api.summary,data=>parseDriverResponse('summary',data,userId));
  const detail=()=>read('detail',options=>api.detail(deliveryId,options),data=>parseDeliveryProgress(data,userId,deliveryId));
  function list(){const {page,status}=state;return read('list',options=>api.list({history,page,status,...options}),data=>parseDeliveryPage(data,userId,page,history,status));}
  async function refresh(){if(state.busy)return;const result=await Promise.allSettled([profile(),summary(),deliveryId?detail():list()]);if(state.detail.data)publish({uncertain:false});return result;}
  async function update(){
    if(inFlight)return inFlight;
    const data=state.detail.data,target=data?.allowed_next_status;
    if(!active||state.authError||state.uncertain||!target||!state.profile.data?.eligible_for_jobs)return null;
    controllers.detail?.abort();const controller=controllers.mutation=new AbortController(),current=generation;
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
  return {getSnapshot:()=>state,subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},
    start(){active=true;generation++;abort();publish(initial());return refresh();},refresh,update,
    filter(status){if(state.busy)return;publish({status,page:1});return list();},
    page(page){if(state.busy||!Number.isSafeInteger(page)||page<1||page>1000000)return;publish({page});return list();},
    dispose(){active=false;generation++;abort();state=initial();},
  };
}
