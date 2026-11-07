export const orderStatuses=['submitted','approved','rejected','processing','completed','cancelled'];
export const orderButton='inline-flex min-h-11 max-w-full items-center justify-center rounded-lg border border-[#DAE5F3] bg-white px-4 py-2 text-sm font-semibold text-[#10243E] focus-visible:outline-2 focus-visible:outline-[#12B8A6] disabled:opacity-50';
export const orderCard='min-w-0 rounded-xl border border-[#E1EAF4] bg-white p-4 shadow-sm sm:p-5';
export const orderField='mt-2 w-full min-w-0 rounded-lg border border-[#DAE5F3] bg-white px-3 py-2.5';
export function cartChange(cart,product,quantity,replace=false){
  if(!Number.isSafeInteger(product.product_id)||!Number.isSafeInteger(product.business_id)||!Number.isInteger(quantity)||quantity<0||quantity>99)throw Error('Quantity must be between 1 and 99.');
  if(cart.business_id&&cart.business_id!==product.business_id&&!replace)throw Error('Replace the current shop cart first.');
  const items=(replace?[]:cart.items).filter(i=>i.product_id!==product.product_id);
  if(quantity)items.push({product_id:product.product_id,business_id:product.business_id,name:product.name,quantity});
  if(items.length>50)throw Error('A cart supports up to 50 different products.');
  return {business_id:items.length?product.business_id:null,items};
}
export function cartPayload(cart){return {business_id:cart.business_id,items:cart.items.map(({product_id,quantity})=>({product_id,quantity}))};}
export function money(value){
  if(typeof value!=='string'||!/^\d+\.\d{2}$/.test(value))return 'Amount unavailable';
  const [whole,fraction]=value.split('.');return 'LKR '+whole.replace(/\B(?=(\d{3})+(?!\d))/g,',')+'.'+fraction;
}
export function orderError(error){
  const status=error?.response?.status;
  if(status===401)return 'Session expired. Please sign in again.';
  if(status===403)return 'Your account is not authorized for this action.';
  if(status===404)return 'Order or shop not found.';
  if(status===409&&typeof error.response.data?.detail==='string')return error.response.data.detail;
  if(status===422)return 'Check the cart quantities and payment selection.';
  return 'The request could not be confirmed. Retry the same request or review My Orders.';
}
export function orderActions(order,owner){
  if(!owner)return order.status==='submitted'?['cancel']:[];
  if(order.status==='submitted')return order.payment_method==='credit'?['approve','reject','cancel']:['process','reject','cancel'];
  if(order.status==='approved')return ['process'];
  return order.status==='processing'?['complete']:[];
}
