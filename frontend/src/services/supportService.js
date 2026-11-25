// Purpose: Wrap support API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from './api';
// Call GET {parameter}/{parameter} or POST {parameter}/{parameter}/actions or GET {parameter}/{parameter}/history/{parameter} through the shared client so authentication and API configuration are applied consistently.
export function supportApi(prefix='/support/cases'){
  return {
    // Load the current resource list using this reader state.
    list:async(filters,signal)=>(await api.get(prefix,{params:filters,signal})).data,
    // Load the selected record detail within the current resource context.
    detail:async(reference,signal)=>(await api.get(`${prefix}/${encodeURIComponent(reference)}`,{signal})).data,
    // Create the selected resource through this workflow mutation path.
    create:async(payload,signal)=>(await api.post(prefix,payload,{signal})).data,
    action:async(reference,payload,signal)=>(await api.post(`${prefix}/${encodeURIComponent(reference)}/actions`,payload,{signal})).data,
    // Read the history associated with the current resource selection.
    history:async(reference,kind,offset,signal)=>(await api.get(`${prefix}/${encodeURIComponent(reference)}/history/${kind}`,{params:{limit:100,offset},signal})).data
  };
}
export default supportApi();
