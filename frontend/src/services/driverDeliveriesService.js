// Purpose: Wrap driver deliveries API calls so components use a shared request interface instead of building HTTP requests themselves.
import {notificationChanged} from '../utils/notificationChange';
import api from './api';
// Read driver deliveries through the authenticated driver API wrapper.
export async function listDriverDeliveries({history=false,page=1,status='',signal}={}) {
  return (await api.get(history?'/driver/history':'/driver/deliveries', {
    signal,params:{page,page_size:10,...(status?{status}:{})},
  })).data;
}
// Read one delivery through the authenticated driver API wrapper.
export async function readDriverDelivery(id,{signal}={}) {
  return (await api.get('/driver/deliveries/'+id,{signal})).data;
}
// Update driver delivery within the driver deliveries workflow.
export async function updateDriverDelivery(id,payload,{signal}={}) {
  return notificationChanged((await api.post('/driver/deliveries/'+id+'/status',payload,{signal})).data);
}
