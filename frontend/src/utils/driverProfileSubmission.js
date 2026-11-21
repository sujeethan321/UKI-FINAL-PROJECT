import {driverRegistrationPayload} from './driverRegistration.js';
import {parseDriverResponse} from './driverDashboard.js';
export function createDriverProfileSubmission(api,userId,onSubmitted) {
 let active=true,state={saving:false,error:'',uncertain:false};const listeners=new Set();
 const publish=next=>{if(active){state=next;listeners.forEach(fn=>fn());}};
 return {activate(){active=true;},getSnapshot:()=>state,subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},
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
  }catch(error){const status=error?.response?.status;publish({saving:false,uncertain:![400,401,403,422,429].includes(status),error:status===401?'Your session has expired. Sign in again.':status===403?'Your account cannot submit a Driver profile.':status===422?'Check your vehicle information and try again.':status===429?'Too many requests. Wait before retrying.':'Submission could not be confirmed. Refresh your profile before retrying; an application may already exist.'});}
 },dispose(){active=false;listeners.clear();}};
}
