// Purpose: Wrap order API calls so components use a shared request interface instead of building HTTP requests themselves.
import {notificationChanged} from '../utils/notificationChange';
import api from './api';
// Call POST /customer/orders/quote through the shared client so authentication and API configuration are applied consistently.
export const quoteCart=(payload,signal)=>api.post('/customer/orders/quote',payload,{signal}).then(r=>r.data);
// Call POST /customer/orders through the shared client so authentication and API configuration are applied consistently.
export const placeOrder=payload=>api.post('/customer/orders',payload).then(r=>notificationChanged(r.data));
// Read the filtered order list from the endpoint selected for the active role.
export const listOrders=(owner,params,signal)=>api.get(owner?'/shop-owner/orders':'/customer/orders',{params,signal}).then(r=>r.data);
// Read the selected order through the endpoint selected for the active role.
export const orderDetail=(owner,id,business_id,signal)=>api.get((owner?'/shop-owner/orders/':'/customer/orders/')+id,{params:owner?{business_id}:{},signal}).then(r=>r.data);
// Send the order decision to the role-scoped API endpoint.
export const decideOrder=(owner,id,business_id,action)=>api.post((owner?'/shop-owner/orders/':'/customer/orders/')+id+'/decision',{action},{params:owner?{business_id}:{}}).then(r=>notificationChanged(r.data));

// Read delivery information through the shop-owner order endpoint.
export const ownerOrderDelivery=(id,business_id,signal)=>api.get('/shop-owner/orders/'+id+'/delivery',{params:{business_id},signal}).then(r=>r.data);
// Request a delivery for the selected order through the owner-scoped API.
export const requestOrderDelivery=(id,business_id,payload,signal)=>api.post('/shop-owner/orders/'+id+'/delivery',payload,{params:{business_id},signal}).then(r=>notificationChanged(r.data));

// Read delivery information through the customer-scoped order endpoint.
export const customerOrderDelivery=(id,signal)=>api.get('/customer/orders/'+id+'/delivery',{signal}).then(r=>r.data);
