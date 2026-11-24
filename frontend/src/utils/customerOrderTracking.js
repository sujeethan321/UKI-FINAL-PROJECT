// Purpose: Keep customer order tracking data handling and workflow helpers separate from React rendering so callers use consistent rules.
import {formatAssignedTime} from './driverDashboard.js';
const statuses=['available','assigned','picked_up','in_transit','delivered','cancelled'];
export const customerDeliveryLabels={available:'Awaiting Driver assignment',assigned:'Driver assigned',picked_up:'Picked up',in_transit:'In transit',delivered:'Delivered',cancelled:'Cancelled'};
// Validate the recorded time before the order timeline uses it.
const timestamp=value=>{
 if(value===null||value===undefined)return null;
 if(formatAssignedTime(value)==='Time unavailable')throw Error('Invalid recorded time');
 return value;
};
// Check customer order delivery before the surrounding workflow uses it.
export function parseCustomerOrderDelivery(data,orderId) {
 if(data?.order_id!==orderId||typeof data.delivery_requested!=='boolean'||data.delivery_requested!==(data.delivery!==null))throw Error('Invalid order delivery identity');
 if(!data.delivery_requested)return {order_id:orderId,delivery_requested:false,delivery:null};
 const row=data.delivery;
 if(typeof row?.reference!=='string'||!row.reference.trim()||!statuses.includes(row.status)||!Array.isArray(row.events))throw Error('Invalid delivery progress');
 const seen=new Set();
 const events=row.events.map(event=>{
  if(!event||!statuses.slice(1).includes(event.status)||seen.has(event.status))throw Error('Invalid delivery event');
  seen.add(event.status);return {status:event.status,occurred_at:timestamp(event.occurred_at)};
 });
 // Allowlist the Customer DTO; never retain operational/Driver fields.
 return {order_id:orderId,delivery_requested:true,delivery:{reference:row.reference,status:row.status,created_at:timestamp(row.created_at),updated_at:timestamp(row.updated_at),events}};
}
// Translate tracking outcomes into display text for the interface.
export function trackingError(state) {
 if(state.status===401)return 'Session expired. Please sign in again.';
 if(state.status===403)return 'Customer access is unavailable. Please check your account or sign in again.';
 if([404,422].includes(state.status))return 'This order tracking record is not available to your account.';
 return 'Delivery tracking is unavailable. Refresh to try again. No delivery status has been confirmed.';
}
// Explain the order state and available next step in customer-facing text.
export function customerOrderExplanation(order) {
 if(order.status==='submitted')return order.payment_method==='credit'?'Awaiting Shop Owner credit approval. No credit approval or repayment is confirmed.':'Submitted for Shop Owner review. Cash was selected; payment has not been recorded.';
 if(order.status==='approved')return 'The Shop Owner approved credit for this order. Approval does not mean delivery or repayment is complete.';
 if(order.status==='processing')return order.payment_method==='credit'?'The Shop Owner is processing this approved Credit order. Credit approval does not mean credit has been repaid.':'The Shop Owner is processing this Cash order. Payment has not been recorded.';
 if(order.status==='completed')return 'The Shop Owner marked this order completed. Delivery progress and payment are recorded separately.';
 if(order.status==='rejected')return 'The Shop Owner rejected this order.';
 if(order.status==='cancelled')return 'This order was cancelled. Any recorded delivery outcome is shown separately.';
 return 'Order status is unavailable. Refresh your orders.';
}
