// Purpose: Wrap profile API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from './api';
// Call GET /account/profile through the shared client so authentication and API configuration are applied consistently.
export async function getProfile(signal){return (await api.get('/account/profile',{signal})).data;}
// Call PATCH /account/profile through the shared client so authentication and API configuration are applied consistently.
export async function updateProfile(changes,revision,signal){
  // If-Match carries the displayed revision; AbortSignal lets an unmounted or superseded screen stop waiting.
  return (await api.patch('/account/profile',changes,{signal,headers:{'If-Match':revision}})).data;
}
