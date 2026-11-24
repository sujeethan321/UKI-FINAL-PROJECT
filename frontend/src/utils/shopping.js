// Purpose: Keep shopping data handling and workflow helpers separate from React rendering so callers use consistent rules.
export const orderStatuses=['submitted','approved','rejected','processing','completed','cancelled'];
export const orderButton='inline-flex min-h-11 max-w-full items-center justify-center rounded-lg border border-[#DAE5F3] bg-white px-4 py-2 text-sm font-semibold text-[#10243E] focus-visible:outline-2 focus-visible:outline-[#12B8A6] disabled:opacity-50';
export const orderCard='min-w-0 rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm sm:p-5';
export const orderField='mt-2 w-full min-w-0 rounded-lg border border-[#DAE5F3] bg-white px-3 py-2.5';
// Apply a cart change while retaining the product and quantity rules used by checkout.
export function cartChange(cart,product,quantity,replace=false){
  if(!Number.isSafeInteger(product.product_id)||!Number.isSafeInteger(product.business_id)||!Number.isInteger(quantity)||quantity<0||quantity>99)throw Error('Quantity must be between 1 and 99.');
  if(cart.business_id&&cart.business_id!==product.business_id&&!replace)throw Error('Replace the current shop cart first.');
  const items=(replace?[]:cart.items).filter(i=>i.product_id!==product.product_id);
  if(quantity)items.push({product_id:product.product_id,business_id:product.business_id,name:product.name,quantity});
  if(items.length>50)throw Error('A cart supports up to 50 different products.');
  return {business_id:items.length?product.business_id:null,items};
}
// Project cart state into the item payload expected by the order API.
export function cartPayload(cart){return {business_id:cart.business_id,items:cart.items.map(({product_id,quantity})=>({product_id,quantity}))};}
// Acceptance binds the displayed quote; fee and payable amounts are never submitted as authority.
export function checkoutPayload(cart,quote,method,requestKey,mode){
  if(quote?.finance_enabled===false){
    if(quote.business_id!==cart.business_id||!['cash','credit'].includes(method))throw Error('Refresh current prices before confirming');
    return {...cartPayload(cart),payment_method:method,request_key:requestKey};
  }
  if(quote?.business_id!==cart.business_id||quote.fee_policy!=='direct-driver-3pct-v1'||quote.fulfilment_mode!==mode||
      !['delivery','pickup'].includes(mode)||typeof quote.quote_token!=='string'||!['cash','credit'].includes(method))throw Error('Refresh prices and confirm the delivery fee again');
  const destination=quote.address_checkout_enabled===true&&mode==='delivery'?{address_id:quote.address_id,address_version:quote.address_version}:{};
  if(quote.address_checkout_enabled===true&&mode==='delivery'&&(!Number.isSafeInteger(destination.address_id)||destination.address_id<1||!Number.isSafeInteger(destination.address_version)||destination.address_version<1))throw Error('Refresh prices and confirm the delivery fee again');
  return {...cartPayload(cart),payment_method:method,fulfilment_mode:mode,quote_token:quote.quote_token,request_key:requestKey,...destination};
}
// Validate or format decimal monetary data at the interface boundary without changing the ledger.
export function money(value){
  if(typeof value!=='string'||!/^\d+\.\d{2}$/.test(value))return 'Amount unavailable';
  const [whole,fraction]=value.split('.');return 'LKR '+whole.replace(/\B(?=(\d{3})+(?!\d))/g,',')+'.'+fraction;
}
// Translate order outcomes into display text for the interface.
export function orderError(error){
  const status=error?.response?.status;
  if(status===401)return 'Session expired. Please sign in again.';
  if(status===403)return 'Your account is not authorized for this action.';
  if(status===404)return 'Order or shop not found.';
  if(status===409&&typeof error.response.data?.detail==='string')return error.response.data.detail;
  if(status===422)return 'Check the cart quantities and payment selection.';
  return 'The request could not be confirmed. Retry the same request or review My Orders.';
}
// Derive the actions supported by the current order state for the customer interface.
export function orderActions(order,owner){
  if(!owner)return order.status==='submitted'?['cancel']:[];
  if(order.status==='submitted')return order.payment_method==='credit'?['approve','reject','cancel']:['process','reject','cancel'];
  if(order.status==='approved')return ['process'];
  return order.status==='processing'?['complete']:[];
}
