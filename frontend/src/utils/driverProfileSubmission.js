// Purpose: Keep driver profile submission data handling and workflow helpers separate from React rendering so callers use consistent rules.
import {driverRegistrationPayload} from './driverRegistration.js';
import {parseDriverResponse} from './driverDashboard.js';
// Translate driver submission outcomes into display text for the interface.
export function driverSubmissionError(error) {
 const status=error?.response?.status,detail=error?.response?.data?.detail;
 if(status===401)return 'Your session has expired. Sign in again.';
 if(status===403)return 'Your account cannot submit a Driver profile.';
 if(status===422)return 'Check your vehicle information and try again.';
 if(status===429)return 'Too many requests. Wait before retrying.';
 if(status===409)return 'A vehicle application already exists or conflicts with this submission. Refresh your profile before submitting again.';
 if(status===503&&detail==='Driver document submission is not configured')return 'Driver document uploads are not configured on the running server. Contact the operator; do not submit again yet.';
 if(status===503&&detail==='Document submission unavailable')return 'Secure document storage or validation is unavailable. Contact the operator and refresh your profile before retrying.';
 if(status===413)return 'The document upload exceeds the request size limit. Each document must be at most 5 MiB.';
 if(status===415)return 'The server could not accept the document upload format. Refresh the page and contact the operator if this continues.';
 return 'Submission could not be confirmed. Refresh your profile before retrying; an application may already exist.';
}
// Create driver profile submission for the driver profile submission workflow.
export function createDriverProfileSubmission(api,userId,onSubmitted) {
 let active=true,state={saving:false,error:'',uncertain:false};const listeners=new Set();
 // Replace the store snapshot and notify subscribers so React can render the new state.
 const publish=next=>{if(active){state=next;listeners.forEach(fn=>fn());}};
 return {/* Activate the selected resource through the workflow action path. */ activate(){active=true;},/* Expose the current store snapshot to subscribers without starting a request. */ getSnapshot:()=>state,/* Register a state listener and return cleanup so consumers can unsubscribe. */ subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},
 // Submit the current operation through the workflow validation and pending-state handling.
 async submit(fields){
  if(!active||state.saving||state.uncertain)return;
  let payload;
  try {payload=driverRegistrationPayload(fields);}
  catch(error){publish({saving:false,error:error.message,uncertain:false});return;}
  publish({saving:true,error:'',uncertain:false});
  try{
   const result=parseDriverResponse('profile',await api(payload),userId);
   if(result.approval_status!=='pending'||result.eligible_for_jobs||result.vehicle?.vehicle_type!==payload.vehicle_type||result.vehicle?.registration_reference!==payload.registration_reference)throw Error('Unconfirmed profile');
   if(active){publish({saving:false,error:'',uncertain:false});await onSubmitted();}
  }catch(error){const status=error?.response?.status;publish({saving:false,uncertain:![400,401,403,422,429].includes(status),error:driverSubmissionError(error)});}
 },/* Release pending work and subscriptions when this resource reader is no longer used. */ dispose(){active=false;listeners.clear();}};
}
