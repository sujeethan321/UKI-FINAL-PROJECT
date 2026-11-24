import api from './api';
export function supportApi(prefix='/support/cases'){
  return {
    list:async(filters,signal)=>(await api.get(prefix,{params:filters,signal})).data,
    detail:async(reference,signal)=>(await api.get(`${prefix}/${encodeURIComponent(reference)}`,{signal})).data,
    create:async(payload,signal)=>(await api.post(prefix,payload,{signal})).data,
    action:async(reference,payload,signal)=>(await api.post(`${prefix}/${encodeURIComponent(reference)}/actions`,payload,{signal})).data,
    history:async(reference,kind,offset,signal)=>(await api.get(`${prefix}/${encodeURIComponent(reference)}/history/${kind}`,{params:{limit:100,offset},signal})).data
  };
}
export default supportApi();
