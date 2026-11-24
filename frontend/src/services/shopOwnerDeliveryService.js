// Purpose: Wrap shop owner delivery API calls so components use a shared request interface instead of building HTTP requests themselves.
import {notificationChanged} from '../utils/notificationChange';
import api from './api';
// Call GET /shop-owner/business-context through the shared client so authentication and API configuration are applied consistently.
export async function getDeliveryBusinesses({signal}={}) {
  return (await api.get('/shop-owner/business-context',{signal})).data;
}
// Call GET /shop-owner/deliveries through the shared client so authentication and API configuration are applied consistently.
export async function listShopDeliveries(businessId,{page=1,status='',signal}={}) {
  return (await api.get('/shop-owner/deliveries',{signal,params:{business_id:businessId,page,page_size:10,...(status?{status}:{})}})).data;
}
// Call GET /shop-owner/deliveries/summary through the shared client so authentication and API configuration are applied consistently.
export async function getShopDeliverySummary(businessId,{signal}={}) {
  return (await api.get('/shop-owner/deliveries/summary',{signal,params:{business_id:businessId}})).data;
}
// Get shop delivery within the shop owner delivery workflow.
export async function getShopDelivery(businessId,id,{signal}={}) {
  return (await api.get('/shop-owner/deliveries/'+id,{signal,params:{business_id:businessId}})).data;
}
// Call POST /shop-owner/deliveries through the shared client so authentication and API configuration are applied consistently.
export async function createShopDelivery(businessId,payload,{signal}={}) {
  return notificationChanged((await api.post('/shop-owner/deliveries',payload,{signal,params:{business_id:businessId}})).data);
}
// Cancel shop delivery within the shop owner delivery workflow.
export async function cancelShopDelivery(businessId,id,{signal}={}) {
  return notificationChanged((await api.post('/shop-owner/deliveries/'+id+'/cancel',{}, {signal,params:{business_id:businessId}})).data);
}
