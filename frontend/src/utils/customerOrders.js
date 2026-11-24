// Purpose: Keep customer orders data handling and workflow helpers separate from React rendering so callers use consistent rules.
import {orderStatuses} from './shopping.js';

// Validate new Customer list projections without changing existing order services.
export function parseCustomerOrdersPage(data,page=1,pageSize=10) {
  // Accept only supported identifiers before response data is used for lookups or navigation.
  const id=value=>Number.isSafeInteger(value)&&value>0;
  // Validate or format decimal monetary data at the interface boundary without changing the ledger.
  const money=value=>typeof value==='string'&&/^\d+\.\d{2}$/.test(value);
  if(data?.page!==page||data.page_size!==pageSize||!Number.isSafeInteger(data.total)||data.total<0||!Array.isArray(data.orders)||data.orders.length>Math.min(data.total,pageSize))throw Error('Invalid order page');
  const seen=new Set();
  const orders=data.orders.map(row=>{
    if(!id(row?.order_id)||!id(row.business_id)||seen.has(row.order_id)||typeof row.reference!=='string'||typeof row.business_name!=='string'||!orderStatuses.includes(row.status)||!['cash','credit'].includes(row.payment_method)||!['unpaid','pending','posted'].includes(row.payment_status)||!money(row.total)||!money(row.subtotal)||row.currency!=='LKR'||typeof row.created_at!=='string'||!Number.isFinite(Date.parse(row.created_at))||!Array.isArray(row.items)||!row.items.length)throw Error('Invalid customer order');
    seen.add(row.order_id);
    const items=row.items.map(item=>{
      if(!id(item.product_id)||typeof item.product_name!=='string'||!Number.isInteger(item.quantity)||item.quantity<1||item.quantity>99||!money(item.unit_price)||!money(item.line_total))throw Error('Invalid order item');
      return {product_id:item.product_id,product_name:item.product_name,quantity:item.quantity,unit_price:item.unit_price,line_total:item.line_total};
    });
    return {...Object.fromEntries(['order_id','reference','business_id','business_name','status','payment_method','payment_status','total','subtotal','currency','created_at','updated_at','credit_sale_id'].map(key=>[key,row[key]])),items};
  });
  return {total:data.total,orders};
}
