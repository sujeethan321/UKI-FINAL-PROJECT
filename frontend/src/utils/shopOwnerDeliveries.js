import {formatAssignedTime} from './driverDashboard.js';

export const shopDeliveryLabels={available:'Available',assigned:'Assigned',picked_up:'Picked up',in_transit:'In transit',delivered:'Completed',cancelled:'Cancelled'};
const id=value=>Number.isSafeInteger(value)&&value>0;
const count=value=>Number.isSafeInteger(value)&&value>=0;
const text=value=>typeof value==='string'&&!!value.trim();
const time=value=>formatAssignedTime(value)!=='Time unavailable';
const fields=['delivery_request_id','reference','business_id','pickup_area','delivery_area','status','created_at','updated_at'];
const pick=(data,keys)=>Object.fromEntries(keys.map(key=>[key,data[key]]));
function row(data,businessId) {
  if(!data||!id(data.delivery_request_id)||data.business_id!==businessId||!['reference','pickup_area','delivery_area'].every(key=>text(data[key]))||!Object.hasOwn(shopDeliveryLabels,data.status)||!time(data.created_at)||!time(data.updated_at))throw Error('Invalid delivery');
  return pick(data,fields);
}
export function parseShopDelivery(data,businessId,requestId=null) {
  const delivery=row(data,businessId);
  if(requestId!==null&&delivery.delivery_request_id!==requestId)throw Error('Delivery identity mismatch');
  if(typeof data.can_cancel!=='boolean'||!Array.isArray(data.events))throw Error('Invalid delivery details');
  let driver=null;
  if(data.assigned_driver!==null){
    if(!text(data.assigned_driver?.full_name)||!time(data.assigned_driver.assigned_at))throw Error('Invalid Driver summary');
    driver=pick(data.assigned_driver,['full_name','assigned_at']);
  }
  if(data.can_cancel!==(data.status==='available'&&!driver))throw Error('Invalid cancellation capability');
  if(['assigned','picked_up','in_transit','delivered'].includes(data.status)&&!driver)throw Error('Missing assignment');
  const seen=new Set();
  const events=data.events.map(event=>{
    if(!['assigned','picked_up','in_transit','delivered','cancelled'].includes(event.status)||!time(event.occurred_at)||seen.has(event.status))throw Error('Invalid timeline');
    seen.add(event.status);return pick(event,['status','occurred_at']);
  });
  if(driver&&(!events.length||events[0].status!=='assigned'||events[0].occurred_at!==driver.assigned_at))throw Error('Invalid assignment event');
  return {...delivery,assigned_driver:driver,events,can_cancel:data.can_cancel};
}
export function parseShopDeliveryList(data,businessId,page,status) {
  if(data?.business_id!==businessId||data.page!==page||data.page_size!==10||!count(data.total)||!Array.isArray(data.deliveries)||data.deliveries.length>Math.min(10,data.total))throw Error('Invalid delivery page');
  const deliveries=data.deliveries.map(data=>row(data,businessId));
  if(new Set(deliveries.map(row=>row.delivery_request_id)).size!==deliveries.length||deliveries.some(row=>status&&row.status!==status))throw Error('Invalid filtered deliveries');
  return {total:data.total,deliveries};
}
export function parseShopDeliverySummary(data,businessId) {
  const keys=['total_requests_count','available_requests_count','in_progress_count','completed_count'];
  if(data?.business_id!==businessId||!keys.every(key=>count(data[key]))||data.available_requests_count+data.in_progress_count+data.completed_count>data.total_requests_count)throw Error('Invalid delivery counts');
  return pick(data,['business_id',...keys]);
}
export function validateDeliveryAreas(fields) {
  const result={};
  for(const [key,label] of [['pickup_area','Pickup area'],['delivery_area','Delivery destination']]){
    const value=fields[key]?.trim();
    if(!value||[...value].length>160||[...value].some(char=>char.codePointAt(0)<32||char.codePointAt(0)===127))return {error:label+' must contain 1–160 characters on one line.'};
    result[key]=value;
  }return {payload:result};
}

// Only an unresolved-attempt flag is stored in this tab, never areas or records.
export function deliveryIntentStore(userId) {
  const key=businessId=>'lankapex_delivery_attempt:'+userId+':'+businessId;
  return {read:businessId=>sessionStorage.getItem(key(businessId))!==null,
    mark:businessId=>sessionStorage.setItem(key(businessId),'unconfirmed'),
    clear:businessId=>sessionStorage.removeItem(key(businessId))};
}
const section=()=>({data:null,loading:false,error:''});
const initial=()=>({businesses:[],businessId:null,contextLoading:true,contextError:'',authError:'',page:1,status:'',
  list:section(),summary:section(),detail:{...section(),id:null},form:{pickup_area:'',delivery_area:''},
  busy:false,confirmCancel:false,uncertain:false,reviewed:false,storageError:'',message:'',error:''});
const message=error=>error?.code==='INVALID_RESPONSE'?'This delivery response could not be verified. Refresh to retry.':error?.response?.status===401?'Your session has expired. Please sign in again.':error?.response?.status===403?'Access is unavailable. Check business approval or sign in with an active Shop Owner account.':error?.response?.status===404?'Delivery not found or access is unavailable.':error?.code==='ECONNABORTED'?'This request is taking too long. Please refresh.':'Delivery information is unavailable. Check your connection and refresh.';

export function createShopDeliveryWorkflow(api,userId,store=deliveryIntentStore(userId)) {
  let state=initial(),active=false,generation=0,inFlight=null;
  const listeners=new Set(),controllers={},versions={};
  const publish=patch=>{if(active){state={...state,...patch};listeners.forEach(fn=>fn());}};
  const abort=()=>Object.values(controllers).forEach(c=>c.abort());
  const approved=()=>state.businesses.some(b=>b.business_id===state.businessId&&b.approval_status==='approved');
  function deny(error){generation++;abort();publish({...initial(),contextLoading:false,authError:message(error)});}
  async function read(key,fetcher,parse){
    if(!active||state.authError)return null;
    controllers[key]?.abort();const controller=controllers[key]=new AbortController(),version=versions[key]=(versions[key]||0)+1,current=generation;
    const valid=()=>active&&generation===current&&!controller.signal.aborted&&versions[key]===version;
    publish({[key]:{...state[key],data:null,loading:true,error:''}});
    try{const response=await fetcher({signal:controller.signal});if(!valid())return null;let data;
      try{data=parse(response);}catch{throw Object.assign(Error('Invalid response'),{code:'INVALID_RESPONSE'});}
      publish({[key]:{...state[key],data,loading:false,error:''}});return data;
    }catch(error){if(!valid())return null;if([401,403].includes(error?.response?.status))deny(error);
      else publish({[key]:{...state[key],data:null,loading:false,error:message(error)}});return null;}
  }
  function list(){const {businessId,page,status}=state;if(!approved())return Promise.resolve(null);return read('list',options=>api.list(businessId,{page,status,...options}),data=>parseShopDeliveryList(data,businessId,page,status));}
  function summary(){const {businessId}=state;if(!approved())return Promise.resolve(null);return read('summary',options=>api.summary(businessId,options),data=>parseShopDeliverySummary(data,businessId));}
  function detail(requestId){if(!approved()||!id(requestId))return Promise.resolve(null);const {businessId}=state;publish({detail:{...section(),id:requestId},confirmCancel:false});return read('detail',options=>api.detail(businessId,requestId,options),data=>parseShopDelivery(data,businessId,requestId));}
  async function selectBusiness(businessId){
    if(state.busy||!state.businesses.some(b=>b.business_id===businessId))return;
    generation++;abort();let uncertain=false,storageError='';
    try{uncertain=store.read(businessId);}catch{storageError='Browser session storage is unavailable. Creation is disabled until it is available.';}
    publish({businessId,page:1,status:'',list:section(),summary:section(),detail:{...section(),id:null},form:{pickup_area:'',delivery_area:''},
      confirmCancel:false,uncertain,reviewed:false,storageError,message:'',error:''});
    return Promise.allSettled([list(),summary()]);
  }
  async function businesses(){
    if(state.busy)return;controllers.context?.abort();const controller=controllers.context=new AbortController(),current=generation;
    publish({contextLoading:true,contextError:''});
    try{const data=await api.businesses({signal:controller.signal});if(!active||controller.signal.aborted||current!==generation)return;
      if(data?.user_id!==userId||!Array.isArray(data.businesses)||data.businesses.some(b=>!id(b.business_id)||!text(b.business_name)||!['approved','pending','rejected'].includes(b.approval_status))||new Set(data.businesses.map(b=>b.business_id)).size!==data.businesses.length)throw Object.assign(Error('Invalid business context'),{code:'INVALID_RESPONSE'});
      const rows=data.businesses.map(b=>pick(b,['business_id','business_name','approval_status']));
      publish({businesses:rows,contextLoading:false});
      const chosen=rows.find(b=>b.business_id===state.businessId)||rows.find(b=>b.approval_status==='approved')||rows[0];
      if(chosen)await selectBusiness(chosen.business_id);
    }catch(error){if(!active||controller.signal.aborted||current!==generation)return;
      if([401,403].includes(error?.response?.status))deny(error);else publish({contextLoading:false,contextError:message(error),businesses:[],businessId:null,list:section(),summary:section(),detail:{...section(),id:null}});}
  }
  async function refresh(){if(state.busy)return;if(state.contextError||!state.businessId)return businesses();
    const results=await Promise.allSettled([list(),summary(),...(state.detail.id?[detail(state.detail.id)]:[])]);
    if(state.uncertain&&state.page===1&&!state.status&&state.list.data)publish({reviewed:true});return results;
  }
  function clearIntent(businessId){try{store.clear(businessId);}catch{publish({storageError:'Unable to clear the unresolved-attempt flag. Review requests before starting another delivery.'});}}
  async function mutate(cancelling){
    if(inFlight)return inFlight;
    if(!active||state.authError||state.contextLoading||!approved())return null;
    const {businessId}=state,requestId=state.detail.id;
    if(cancelling&&(!state.confirmCancel||!state.detail.data?.can_cancel))return null;
    let payload;
    if(!cancelling){if(state.uncertain||state.storageError)return null;const validation=validateDeliveryAreas(state.form);
      if(validation.error){publish({error:validation.error});return null;}payload=validation.payload;
      try{store.mark(businessId);}catch{publish({storageError:'Unable to protect this submission in browser session storage. No request was sent.'});return null;}
    }
    const current=generation,controller=controllers.mutation=new AbortController();
    const valid=()=>active&&generation===current&&!controller.signal.aborted;
    controllers.detail?.abort();publish({busy:true,confirmCancel:false,error:'',message:''});
    const operation=(async()=>{try{
      const response=await(cancelling?api.cancel(businessId,requestId,{signal:controller.signal}):api.create(businessId,payload,{signal:controller.signal}));
      if(!valid())return null;const result=parseShopDelivery(response,businessId,cancelling?requestId:null);
      if(cancelling?result.status!=='cancelled':result.status!=='available'||result.pickup_area!==payload.pickup_area||result.delivery_area!==payload.delivery_area)throw Error('Unconfirmed operation');
      if(!cancelling)clearIntent(businessId);
      publish({detail:{data:result,id:result.delivery_request_id,loading:false,error:''},message:cancelling?'Delivery request cancelled.':'Delivery request created.',
        ...(!cancelling?{form:{pickup_area:'',delivery_area:''},uncertain:false,reviewed:false,page:1,status:''}:{})});
      await Promise.allSettled([list(),summary(),detail(result.delivery_request_id)]);return result;
    }catch(error){if(!valid())return null;const status=error?.response?.status;
      if(!cancelling&&[401,403,404,409,422].includes(status))clearIntent(businessId);
      if([401,403].includes(status)){deny(error);return null;}
      if(cancelling){publish({detail:{...section(),id:requestId},error:status===409?'This request changed or was accepted by a Driver. Refresh its details; cancellation was not confirmed.':'Cancellation could not be confirmed. Refresh details to check the recorded status.'});await Promise.allSettled([list(),summary(),detail(requestId)]);}
      else if([404,409,422].includes(status)){publish({error:status===422?'Check the delivery areas and try again.':'The request was rejected. Refresh the business delivery list before trying again.'});}
      else publish({uncertain:true,reviewed:false,error:'Creation could not be confirmed. Do not submit again yet. Refresh and review your requests first.'});
      return null;
    }finally{if(valid())publish({busy:false});}})();
    inFlight=operation;try{return await operation;}finally{if(inFlight===operation)inFlight=null;}
  }
  return {getSnapshot:()=>state,subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},
    start(){active=true;generation++;abort();publish(initial());return businesses();},refresh,selectBusiness,
    edit(key,value){if(!state.busy&&!state.uncertain&&['pickup_area','delivery_area'].includes(key))publish({form:{...state.form,[key]:value},error:''});},
    filter(status){if(state.busy||(status&&!Object.hasOwn(shopDeliveryLabels,status)))return;publish({status,page:1,reviewed:false});return list();},
    page(page){if(state.busy||!id(page)||page>1000000)return;publish({page,reviewed:false});return list();},
    details(requestId){if(!state.busy)return detail(requestId);},
    closeDetails(){if(!state.busy){controllers.detail?.abort();publish({detail:{...section(),id:null},confirmCancel:false});}},
    confirmCancel(value){if(!state.busy&&state.detail.data?.can_cancel)publish({confirmCancel:!!value});},
    create:()=>mutate(false),cancel:()=>mutate(true),
    reviewUncertain(){if(state.busy)return;publish({status:'',page:1});return refresh();},
    acknowledge(){if(!state.uncertain||!state.reviewed||state.busy)return;clearIntent(state.businessId);publish({uncertain:false,reviewed:false,form:{pickup_area:'',delivery_area:''},error:'',message:'You may start a new request. An earlier request may still finish; avoid submitting it again.'});},
    dispose(){active=false;generation++;abort();state=initial();},
  };
}
