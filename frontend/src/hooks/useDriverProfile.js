import {useEffect,useState} from 'react';
import {getDriverProfile} from '../services/driverDashboardService';
import {parseDriverResponse,driverReadError} from '../utils/driverDashboard';

export function useDriverProfile(userId) {
  const [revision,setRevision]=useState(0);
  const [result,setResult]=useState(null);
  useEffect(()=>{
    const controller=new AbortController();
    getDriverProfile({signal:controller.signal}).then(data=>{
      let profile;try{profile=parseDriverResponse('profile',data,userId);}catch{throw {code:'INVALID_DRIVER_RESPONSE'};}
      if(!controller.signal.aborted)setResult({userId,revision,data:profile,error:''});
    }).catch(error=>{if(!controller.signal.aborted)setResult({userId,revision,data:null,error:driverReadError(error)});});
    return()=>controller.abort();
  },[userId,revision]);
  const current=result?.userId===userId&&result.revision===revision;
  return {data:current?result.data:null,error:current?result.error:'',loading:!current,reload:()=>setRevision(value=>value+1)};
}
