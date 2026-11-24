// Purpose: Wrap driver dashboard API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from './api';
// Call POST /driver/vehicle through the shared client so authentication and API configuration are applied consistently.
export async function submitDriverProfile(payload) {
  const form = new FormData();
  for (const [name, value] of Object.entries(payload)) form.append(name, value);
  return (await api.post('/driver/vehicle', form, {headers: {'Content-Type': undefined}, timeout: 60000})).data;
}
// Call GET /driver/profile through the shared client so authentication and API configuration are applied consistently.
export async function getDriverProfile({signal}={}) {
  return (await api.get('/driver/profile',{signal})).data;
}
// Call GET /driver/dashboard/summary through the shared client so authentication and API configuration are applied consistently.
export async function getDriverSummary({signal}={}) {
  return (await api.get('/driver/dashboard/summary',{signal})).data;
}
// Call GET /driver/deliveries through the shared client so authentication and API configuration are applied consistently.
export async function getDriverDeliveries({signal}={}) {
  return (await api.get('/driver/deliveries',{signal,params:{page:1,page_size:5}})).data;
}
