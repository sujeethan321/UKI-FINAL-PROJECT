import api from './api';
export async function getAvailableJobs(page,{signal}={}) {
 return (await api.get('/driver/jobs',{signal,params:{page,page_size:10}})).data;
}
export async function getAvailableJob(jobId,{signal}={}) {
 return (await api.get('/driver/jobs/'+jobId,{signal})).data;
}
export async function acceptDriverJob(jobId,{signal}={}) {
 return (await api.post('/driver/jobs/'+jobId+'/accept',{}, {signal})).data;
}
export async function getAssignedDelivery(jobId,{signal}={}) {
 return (await api.get('/driver/deliveries/'+jobId,{signal})).data;
}
