import api from './api';
export async function submitDriverProfile(payload) {
  return (await api.post('/driver/profile', payload)).data;
}
export async function getDriverProfile({signal}={}) {
  return (await api.get('/driver/profile',{signal})).data;
}
export async function getDriverSummary({signal}={}) {
  return (await api.get('/driver/dashboard/summary',{signal})).data;
}
export async function getDriverDeliveries({signal}={}) {
  return (await api.get('/driver/deliveries',{signal,params:{page:1,page_size:5}})).data;
}
