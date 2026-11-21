import api from './api';
export async function submitDriverProfile(payload) {
  const form = new FormData();
  for (const [name, value] of Object.entries(payload)) form.append(name, value);
  return (await api.post('/driver/vehicle', form, {headers: {'Content-Type': undefined}, timeout: 60000})).data;
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
