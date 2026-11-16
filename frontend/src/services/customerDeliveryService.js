import {listOrders,customerOrderDelivery} from './orderService';
import {parseCustomerOrdersPage} from '../utils/customerOrders';
import {parseCustomerOrderDelivery} from '../utils/customerOrderTracking';

// There is no aggregate Customer delivery endpoint. Join only one bounded page
// of authenticated owned orders to the existing scoped tracking endpoints.
export async function getMyDeliveryPage(page,{signal}={}) {
  const orders=parseCustomerOrdersPage(await listOrders(false,{page,page_size:10},signal),page);
  const records=await Promise.all(orders.orders.map(async order=>{
    const progress=parseCustomerOrderDelivery(await customerOrderDelivery(order.order_id,signal),order.order_id);
    return progress.delivery?{order,delivery:progress.delivery}:null;
  }));
  return {orderTotal:orders.total,records:records.filter(Boolean)};
}
