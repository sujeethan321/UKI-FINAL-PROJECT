// Purpose: Encapsulate driver profile state and lifecycle behavior for reuse by React components.
import {useEffect,useState} from 'react';
import {getDriverProfile} from '../services/driverDashboardService';
import {parseDriverResponse,driverReadError} from '../utils/driverDashboard';

// Share driver profile state and lifecycle behavior between React consumers.
export function useDriverProfile(userId) {
  const [revision,setRevision]=useState(0);
  const [result,setResult]=useState(null);
  // Start resource work after rendering and cancel or dispose it during cleanup so obsolete work cannot update this view.
  useEffect(()=>{
    const controller=new AbortController();
    getDriverProfile({signal:controller.signal}).then(data=>{
      let profile;try{profile=parseDriverResponse('profile',data,userId);}catch{throw {code:'INVALID_DRIVER_RESPONSE'};}
      if(!controller.signal.aborted)setResult({userId,revision,data:profile,error:''});
    }).catch(error=>{if(!controller.signal.aborted)setResult({userId,revision,data:null,error:driverReadError(error)});});
    return()=>controller.abort();
  },[userId,revision]);
  const current=result?.userId===userId&&result.revision===revision;
  return {data:current?result.data:null,error:current?result.error:'',loading:!current,/* Reload the active resource after a context or record change. */ reload:()=>setRevision(value=>value+1)};
}
