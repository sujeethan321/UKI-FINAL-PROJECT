// Purpose: Wrap driver jobs API calls so components use a shared request interface instead of building HTTP requests themselves.
import {notificationChanged} from '../utils/notificationChange';
import api from './api';
// Call GET /driver/jobs through the shared client so authentication and API configuration are applied consistently.
export async function getAvailableJobs(page,{signal}={}) {
 return (await api.get('/driver/jobs',{signal,params:{page,page_size:10}})).data;
}
// Get available job within the driver jobs workflow.
export async function getAvailableJob(jobId,{signal}={}) {
 return (await api.get('/driver/jobs/'+jobId,{signal})).data;
}
// Accept driver job within the driver jobs workflow.
export async function acceptDriverJob(jobId,{signal}={}) {
 return notificationChanged((await api.post('/driver/jobs/'+jobId+'/accept',{}, {signal})).data);
}
// Get assigned delivery within the driver jobs workflow.
export async function getAssignedDelivery(jobId,{signal}={}) {
 return (await api.get('/driver/deliveries/'+jobId,{signal})).data;
}
