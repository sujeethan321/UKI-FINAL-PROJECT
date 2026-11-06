import {parseDriverResponse,driverReadError,formatAssignedTime} from './driverDashboard.js';
const id=value=>Number.isSafeInteger(value)&&value>0;
const count=value=>Number.isSafeInteger(value)&&value>=0;
const text=value=>typeof value==='string'&&!!value.trim();
const pick=(row,keys)=>Object.fromEntries(keys.map(key=>[key,row[key]]));
const base=['delivery_request_id','reference','business_name','pickup_area','delivery_area','status'];
function job(row) {
 if(!row||!id(row.delivery_request_id)||!base.slice(1,5).every(key=>text(row[key]))||row.status!=='available'||formatAssignedTime(row.created_at)==='Time unavailable')throw Error('Invalid available job');
 return pick(row,[...base,'created_at']);
}
function identity(data,userId){if(!id(userId)||data?.driver_user_id!==userId)throw Error('Driver identity mismatch');}
export function parseAvailableJobs(data,userId,page){
 identity(data,userId);
 if(data.page!==page||data.page_size!==10||!count(data.total)||!Array.isArray(data.jobs)||data.jobs.length>10||data.jobs.length>data.total)throw Error('Invalid job page');
 const items=data.jobs.map(job);if(new Set(items.map(row=>row.delivery_request_id)).size!==items.length)throw Error('Duplicate jobs');
 return {total:data.total,items};
}
export function parseAvailableJob(data,userId,jobId){identity(data,userId);const result=job(data.job);if(result.delivery_request_id!==jobId)throw Error('Job mismatch');return result;}
export function parseAssignment(data,userId,jobId,allowTerminal=false){
 identity(data,userId);const row=data.delivery;
 if(!id(data.assignment_id)||!row||row.delivery_request_id!==jobId||!base.slice(1,5).every(key=>text(row[key]))||!['assigned','picked_up','in_transit',...(allowTerminal?['delivered','cancelled']:[])].includes(row.status)||formatAssignedTime(row.assigned_at)==='Time unavailable')throw Error('Unconfirmed assignment');
 return {driver_user_id:userId,assignment_id:data.assignment_id,delivery:pick(row,[...base,'assigned_at'])};
}
const section=()=>({data:null,loading:false,error:''});
const fresh=()=>({authError:'',page:1,profile:section(),summary:section(),jobs:section(),assigned:section(),detail:{...section(),jobId:null},acceptance:{phase:'idle',jobId:null,error:'',confirmed:null}});
const pending=phase=>['submitting','checking','uncertain'].includes(phase);
export function createDriverJobsWorkflow(api,userId){
 let state=fresh(),active=false,generation=0,inFlight=null,mutationController;
 const listeners=new Set(),controllers={},versions={};
 const publish=patch=>{if(active){state={...state,...patch};listeners.forEach(fn=>fn());}};
 const abortReads=()=>Object.values(controllers).forEach(controller=>controller.abort());
 function denied(error){generation++;abortReads();mutationController?.abort();publish({...fresh(),authError:driverReadError(error)});}
 async function read(key,fetcher,parse){
  if(!active||state.authError)return null;controllers[key]?.abort();const controller=new AbortController();controllers[key]=controller;
  const version=versions[key]=(versions[key]||0)+1,current=generation;
  const valid=()=>active&&!controller.signal.aborted&&generation===current&&versions[key]===version;
  publish({[key]:{...state[key],data:null,loading:true,error:''}});
  try{const response=await fetcher({signal:controller.signal});if(!valid())return null;let data;try{data=parse(response);}catch{throw Object.assign(Error('Invalid response'),{code:'INVALID_DRIVER_RESPONSE'});}publish({[key]:{...state[key],data,loading:false,error:''}});return data;}
  catch(error){if(!valid())return null;if([401,403].includes(error?.response?.status))denied(error);else publish({[key]:{...state[key],data:null,loading:false,error:key==='detail'&&error?.response?.status===404?'This job is no longer available. Refresh the jobs list.':driverReadError(error)}});return null;}
 }
 function jobs(){const page=state.page;if(!state.profile.data?.eligible_for_jobs)return Promise.resolve(null);return read('jobs',options=>api.jobs(page,options),data=>parseAvailableJobs(data,userId,page));}
 function summary(){return read('summary',api.summary,data=>parseDriverResponse('summary',data,userId));}
 function assigned(){return read('assigned',api.assigned,data=>parseDriverResponse('deliveries',data,userId));}
 async function profile(){const data=await read('profile',api.profile,result=>parseDriverResponse('profile',result,userId));if(data?.eligible_for_jobs)await jobs();else if(data){controllers.jobs?.abort();controllers.detail?.abort();publish({jobs:section(),detail:{...section(),jobId:null}});}return data;}
 const refreshAfterAssignment=()=>Promise.allSettled([jobs(),summary(),assigned()]);
 function confirmed(data){publish({detail:{...section(),jobId:null},acceptance:{phase:'confirmed',jobId:data.delivery.delivery_request_id,error:'',confirmed:data}});}
 async function mutate(jobId,checking){
  if(inFlight)return inFlight;
  if(!active||state.authError||!id(jobId)||!state.profile.data?.eligible_for_jobs)return null;
  const previous=state.acceptance;
  if(previous.phase==='uncertain'&&previous.jobId!==jobId)return null;
  if(!checking&&previous.jobId!==jobId&&!state.jobs.data?.items.some(row=>row.delivery_request_id===jobId)&&state.detail.data?.delivery_request_id!==jobId)return null;
  const current=generation;mutationController=new AbortController();const {signal}=mutationController;
  const valid=()=>active&&!signal.aborted&&generation===current;
  publish({acceptance:{phase:checking?'checking':'submitting',jobId,error:'',confirmed:null}});
  const operation=(async()=>{
   try{const response=await (checking?api.assignment:api.accept)(jobId,{signal});if(!valid())return null;
    let data;try{data=parseAssignment(response,userId,jobId,checking);}catch{throw Error('Unconfirmed assignment response');}
    confirmed(data);await refreshAfterAssignment();return data;
   }catch(error){if(!valid())return null;const status=error?.response?.status;
    if([401,403].includes(status)){denied(error);return null;}
    if(!checking&&[404,409,422].includes(status)){publish({detail:{...section(),jobId:null},acceptance:{phase:'conflict',jobId,confirmed:null,error:'This job is no longer available or the request was rejected. Refresh the list before choosing another job.'}});await Promise.allSettled([jobs(),summary()]);}
    else publish({acceptance:{phase:'uncertain',jobId,confirmed:null,error:checking&&status===404?'No assignment is confirmed yet. Retry this same job; the first request may still be processing.':'Assignment could not be confirmed. Retry this same job or check your assignment before accepting another.'}});
    return null;
   }
  })();inFlight=operation;
  try{return await operation;}finally{if(inFlight===operation)inFlight=null;}
 }
 return {getSnapshot:()=>state,subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},
  start(){if(active&&pending(state.acceptance.phase))return Promise.resolve();active=true;generation++;abortReads();publish(fresh());return Promise.allSettled([profile(),summary()]);},
  refresh(){if(pending(state.acceptance.phase))return Promise.resolve();return Promise.allSettled([profile(),summary(),...(state.acceptance.confirmed?[assigned()]:[])]);},
  page(page){if(pending(state.acceptance.phase)||!Number.isSafeInteger(page)||page<1||page>1000000)return Promise.resolve();controllers.detail?.abort();publish({page,detail:{...section(),jobId:null}});return jobs();},
  details(jobId){if(pending(state.acceptance.phase)||!id(jobId))return Promise.resolve();publish({detail:{...section(),jobId}});return read('detail',options=>api.detail(jobId,options),data=>parseAvailableJob(data,userId,jobId));},
  closeDetails(){controllers.detail?.abort();publish({detail:{...section(),jobId:null}});},
  retryJobs:jobs,accept:jobId=>mutate(jobId,false),checkAssignment:()=>state.acceptance.jobId?mutate(state.acceptance.jobId,true):Promise.resolve(),
  dispose(){active=false;generation++;abortReads();mutationController?.abort();state=fresh();},
 };
}
