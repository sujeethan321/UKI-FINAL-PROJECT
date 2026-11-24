import api from './api';
export async function getProfile(signal){return (await api.get('/account/profile',{signal})).data;}
export async function updateProfile(changes,revision,signal){
  return (await api.patch('/account/profile',changes,{signal,headers:{'If-Match':revision}})).data;
}
