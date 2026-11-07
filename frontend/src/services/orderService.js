import api from './api';
export const quoteCart=(payload,signal)=>api.post('/customer/orders/quote',payload,{signal}).then(r=>r.data);
export const placeOrder=payload=>api.post('/customer/orders',payload).then(r=>r.data);
export const listOrders=(owner,params,signal)=>api.get(owner?'/shop-owner/orders':'/customer/orders',{params,signal}).then(r=>r.data);
export const orderDetail=(owner,id,business_id,signal)=>api.get((owner?'/shop-owner/orders/':'/customer/orders/')+id,{params:owner?{business_id}:{},signal}).then(r=>r.data);
export const decideOrder=(owner,id,business_id,action)=>api.post((owner?'/shop-owner/orders/':'/customer/orders/')+id+'/decision',{action},{params:owner?{business_id}:{}}).then(r=>r.data);
