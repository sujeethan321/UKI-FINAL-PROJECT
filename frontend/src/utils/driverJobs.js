// Purpose: Keep driver jobs data handling and workflow helpers separate from React rendering so callers use consistent rules.
import {parseDestination} from './customerAddress.js';
import {parseDriverResponse,driverReadError,formatAssignedTime} from './driverDashboard.js';
// Accept only supported identifiers before response data is used for lookups or navigation.
const id=value=>Number.isSafeInteger(value)&&value>0;
// Validate count values before the interface uses them for totals or pagination.
const count=value=>Number.isSafeInteger(value)&&value>=0;
// Validate text values at the response boundary before rendering them.
const text=value=>typeof value==='string'&&!!value.trim();
// Project only the named response fields so unrelated API fields do not enter view state.
const pick=(row,keys)=>Object.fromEntries(keys.map(key=>[key,row[key]]));
const base=['delivery_request_id','reference','business_name','pickup_area','delivery_area','status'];
// Validate the available-job row and project the fields permitted in the job list.
function job(row) {
 if(!row||!id(row.delivery_request_id)||!base.slice(1,5).every(key=>text(row[key]))||row.status!=='available'||formatAssignedTime(row.created_at)==='Time unavailable')throw Error('Invalid available job');
 return pick(row,[...base,'created_at']);
}
// Check the driver and profile identity required by this job workflow.
function identity(data,userId){if(!id(userId)||data?.driver_user_id!==userId)throw Error('Driver identity mismatch');}
// Check available jobs before the surrounding workflow uses it.
export function parseAvailableJobs(data,userId,page){
 identity(data,userId);
 if(data.page!==page||data.page_size!==10||!count(data.total)||!Array.isArray(data.jobs)||data.jobs.length>10||data.jobs.length>data.total)throw Error('Invalid job page');
 const items=data.jobs.map(job);if(new Set(items.map(row=>row.delivery_request_id)).size!==items.length)throw Error('Duplicate jobs');
 return {total:data.total,items};
}
// Check available job before the surrounding workflow uses it.
export function parseAvailableJob(data,userId,jobId){identity(data,userId);const result=job(data.job);if(result.delivery_request_id!==jobId)throw Error('Job mismatch');return result;}
// Check assignment before the surrounding workflow uses it.
export function parseAssignment(data,userId,jobId,allowTerminal=false){
 identity(data,userId);const row=data.delivery;
 if(!id(data.assignment_id)||!row||row.delivery_request_id!==jobId||!base.slice(1,5).every(key=>text(row[key]))||!['assigned','picked_up','in_transit',...(allowTerminal?['delivered','cancelled']:[])].includes(row.status)||formatAssignedTime(row.assigned_at)==='Time unavailable')throw Error('Unconfirmed assignment');
 const projected=pick(row,[...base,'assigned_at']);
 if(!['delivered','cancelled'].includes(row.status)&&row.destination!=null)projected.destination=parseDestination(row.destination);
 return {driver_user_id:userId,assignment_id:data.assignment_id,delivery:projected};
}
// Create a resource section with its own data, loading, and error state for independent updates.
const section=()=>({data:null,loading:false,error:''});
// Create independent initial resource state so new readers do not inherit another instance state.
const fresh=()=>({authError:'',page:1,profile:section(),summary:section(),jobs:section(),assigned:section(),detail:{...section(),jobId:null},acceptance:{phase:'idle',jobId:null,error:'',confirmed:null}});
// Represent an operation whose outcome still needs confirmation before another action begins.
const pending=phase=>['submitting','checking','uncertain'].includes(phase);
// Create driver jobs workflow for the driver jobs workflow.
export function createDriverJobsWorkflow(api,userId){
 let state=fresh(),active=false,generation=0,inFlight=null,mutationController;
 const listeners=new Set(),controllers={},versions={};
 // Replace the store snapshot and notify subscribers so React can render the new state.
 const publish=patch=>{if(active){state={...state,...patch};listeners.forEach(fn=>fn());}};
 // Cancel outstanding reads before context or selection changes.
 const abortReads=()=>Object.values(controllers).forEach(controller=>controller.abort());
 // Detect a denied request so the workflow can stop showing inaccessible resources.
 function denied(error){generation++;abortReads();mutationController?.abort();publish({...fresh(),authError:driverReadError(error)});}
 // Read the saved or current resource state used by this workflow.
 async function read(key,fetcher,parse){
  if(!active||state.authError)return null;controllers[key]?.abort();const controller=new AbortController();controllers[key]=controller;
  const version=versions[key]=(versions[key]||0)+1,current=generation;
  // Check valid before the surrounding workflow uses it.
  const valid=()=>active&&!controller.signal.aborted&&generation===current&&versions[key]===version;
  publish({[key]:{...state[key],data:null,loading:true,error:''}});
  try{const response=await fetcher({signal:controller.signal});if(!valid())return null;let data;try{data=parse(response);}catch{throw Object.assign(Error('Invalid response'),{code:'INVALID_DRIVER_RESPONSE'});}publish({[key]:{...state[key],data,loading:false,error:''}});return data;}
  catch(error){if(!valid())return null;if([401,403].includes(error?.response?.status))denied(error);else publish({[key]:{...state[key],data:null,loading:false,error:key==='detail'&&error?.response?.status===404?'This job is no longer available. Refresh the jobs list.':driverReadError(error)}});return null;}
 }
 // Load the current available-job page into the driver reader.
 function jobs(){const page=state.page;if(!state.profile.data?.eligible_for_jobs)return Promise.resolve(null);return read('jobs',options=>api.jobs(page,options),data=>parseAvailableJobs(data,userId,page));}
 // Load summary data separately from list or detail state so each section can refresh independently.
 function summary(){return read('summary',api.summary,data=>parseDriverResponse('summary',data,userId));}
 // Load assigned-delivery state for the current driver context.
 function assigned(){return read('assigned',api.assigned,data=>parseDriverResponse('deliveries',data,userId));}
 // Load the driver profile needed to evaluate current workflow access.
 async function profile(){const data=await read('profile',api.profile,result=>parseDriverResponse('profile',result,userId));if(data?.eligible_for_jobs)await jobs();else if(data){controllers.jobs?.abort();controllers.detail?.abort();publish({jobs:section(),detail:{...section(),jobId:null}});}return data;}
 // Reload driver job and assignment resources after an assignment result.
 const refreshAfterAssignment=()=>Promise.allSettled([jobs(),summary(),assigned()]);
 // Apply a confirmed assignment result and refresh the related driver resources.
 function confirmed(data){publish({detail:{...section(),jobId:null},acceptance:{phase:'confirmed',jobId:data.delivery.delivery_request_id,error:'',confirmed:data}});}
 // Run a resource-changing request while coordinating pending state and the follow-up resource refresh.
 async function mutate(jobId,checking){
  if(inFlight)return inFlight;
  if(!active||state.authError||!id(jobId)||!state.profile.data?.eligible_for_jobs)return null;
  const previous=state.acceptance;
  if(previous.phase==='uncertain'&&previous.jobId!==jobId)return null;
  if(!checking&&previous.jobId!==jobId&&!state.jobs.data?.items.some(row=>row.delivery_request_id===jobId)&&state.detail.data?.delivery_request_id!==jobId)return null;
  const current=generation;mutationController=new AbortController();const {signal}=mutationController;
  // Check valid before the surrounding workflow uses it.
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
 return {/* Expose the current store snapshot to subscribers without starting a request. */ getSnapshot:()=>state,/* Register a state listener and return cleanup so consumers can unsubscribe. */ subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},
  // Start the resource workflow using its current context and selection.
  start(){if(active&&pending(state.acceptance.phase))return Promise.resolve();active=true;generation++;abortReads();publish(fresh());return Promise.allSettled([profile(),summary()]);},
  // Request current resource data instead of continuing to display an earlier result.
  refresh(){if(pending(state.acceptance.phase))return Promise.resolve();return Promise.allSettled([profile(),summary(),...(state.acceptance.confirmed?[assigned()]:[])]);},
  // Change the current page and load its resource records.
  page(page){if(pending(state.acceptance.phase)||!Number.isSafeInteger(page)||page<1||page>1000000)return Promise.resolve();controllers.detail?.abort();publish({page,detail:{...section(),jobId:null}});return jobs();},
  // Load the selected record details within the current resource context.
  details(jobId){if(pending(state.acceptance.phase)||!id(jobId))return Promise.resolve();publish({detail:{...section(),jobId}});return read('detail',options=>api.detail(jobId,options),data=>parseAvailableJob(data,userId,jobId));},
  // Close the selected detail view and release its resource state.
  closeDetails(){controllers.detail?.abort();publish({detail:{...section(),jobId:null}});},
  retryJobs:jobs,/* Apply the acceptance action through the current resource workflow. */ accept:jobId=>mutate(jobId,false),/* Refresh assignment state before treating an uncertain delivery action as resolved. */ checkAssignment:()=>state.acceptance.jobId?mutate(state.acceptance.jobId,true):Promise.resolve(),
  // Release pending work and subscriptions when this resource reader is no longer used.
  dispose(){active=false;generation++;abortReads();mutationController?.abort();state=fresh();},
 };
}
