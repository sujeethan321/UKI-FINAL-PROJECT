import api from './api';
export async function getDeliveryBusinesses({signal}={}) {
  return (await api.get('/shop-owner/business-context',{signal})).data;
}
export async function listShopDeliveries(businessId,{page=1,status='',signal}={}) {
  return (await api.get('/shop-owner/deliveries',{signal,params:{business_id:businessId,page,page_size:10,...(status?{status}:{})}})).data;
}
export async function getShopDeliverySummary(businessId,{signal}={}) {
  return (await api.get('/shop-owner/deliveries/summary',{signal,params:{business_id:businessId}})).data;
}
export async function getShopDelivery(businessId,id,{signal}={}) {
  return (await api.get('/shop-owner/deliveries/'+id,{signal,params:{business_id:businessId}})).data;
}
export async function createShopDelivery(businessId,payload,{signal}={}) {
  return (await api.post('/shop-owner/deliveries',payload,{signal,params:{business_id:businessId}})).data;
}
export async function cancelShopDelivery(businessId,id,{signal}={}) {
  return (await api.post('/shop-owner/deliveries/'+id+'/cancel',{}, {signal,params:{business_id:businessId}})).data;
}
