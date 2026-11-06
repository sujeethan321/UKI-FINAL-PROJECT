import api from './api';
export async function listDriverDeliveries({history=false,page=1,status='',signal}={}) {
  return (await api.get(history?'/driver/history':'/driver/deliveries', {
    signal,params:{page,page_size:10,...(status?{status}:{})},
  })).data;
}
export async function readDriverDelivery(id,{signal}={}) {
  return (await api.get('/driver/deliveries/'+id,{signal})).data;
}
export async function updateDriverDelivery(id,payload,{signal}={}) {
  return (await api.post('/driver/deliveries/'+id+'/status',payload,{signal})).data;
}
