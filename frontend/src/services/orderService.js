import {notificationChanged} from '../utils/notificationChange';
import api from './api';
export const quoteCart=(payload,signal)=>api.post('/customer/orders/quote',payload,{signal}).then(r=>r.data);
export const placeOrder=payload=>api.post('/customer/orders',payload).then(r=>notificationChanged(r.data));
export const listOrders=(owner,params,signal)=>api.get(owner?'/shop-owner/orders':'/customer/orders',{params,signal}).then(r=>r.data);
export const orderDetail=(owner,id,business_id,signal)=>api.get((owner?'/shop-owner/orders/':'/customer/orders/')+id,{params:owner?{business_id}:{},signal}).then(r=>r.data);
export const decideOrder=(owner,id,business_id,action)=>api.post((owner?'/shop-owner/orders/':'/customer/orders/')+id+'/decision',{action},{params:owner?{business_id}:{}}).then(r=>notificationChanged(r.data));

export const ownerOrderDelivery=(id,business_id,signal)=>api.get('/shop-owner/orders/'+id+'/delivery',{params:{business_id},signal}).then(r=>r.data);
export const requestOrderDelivery=(id,business_id,payload,signal)=>api.post('/shop-owner/orders/'+id+'/delivery',payload,{params:{business_id},signal}).then(r=>notificationChanged(r.data));

export const customerOrderDelivery=(id,signal)=>api.get('/customer/orders/'+id+'/delivery',{signal}).then(r=>r.data);
