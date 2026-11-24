// Purpose: Render the reusable customer recent orders interface and keep its presentation and interactions together.
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { Link } from 'react-router-dom';
import { useCustomerRead } from '../../hooks/useCustomerRead';
import { listOrders } from '../../services/orderService';
import { parseCustomerOrdersPage } from '../../utils/customerOrders';
import { formatCustomerMoney, formatRecordedTime } from '../../utils/customerDashboard';
import { CustomerDataState, customerCard, customerButton } from './CustomerData';

// Render the customer recent orders view interface and connect its controls to the state and callbacks defined here.
export function CustomerRecentOrdersView({state,retry}) {
  const { tr, statusLabel } = useAppTranslation();
  return <section className={customerCard}><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-bold">{tr("Recent Orders")}</h2><Link className={customerButton} to="/customer/orders">{tr("View all orders")}</Link></div><CustomerDataState state={state} retry={retry} label={tr("recent orders")}>{state.data&&(state.data.orders.length?<div className="customer-table-wrap"><table><thead><tr>{['Order ID','Shop','Date','Amount','Status'].map(label=><th key={label}>{tr(label)}</th>)}</tr></thead><tbody>{state.data.orders.map(order=><tr key={order.order_id}><td><Link className="font-semibold text-[#008C87] underline" to={'/customer/orders/'+order.order_id}>{order.reference}</Link></td><td>{order.business_name}</td><td>{formatRecordedTime(order.created_at)}</td><td className="font-semibold">{formatCustomerMoney(order.total)}</td><td><span className="rounded-full bg-[#E7F9F6] px-3 py-1 text-xs">{statusLabel(order.status)}</span></td></tr>)}</tbody></table></div>:<p className="py-5 text-sm text-[#64748B]">{tr("No recent orders.")}</p>)}</CustomerDataState></section>;
}
// Render the customer recent orders interface and connect its controls to the state and callbacks defined here.
export default function CustomerRecentOrders() {
  const [state,reader]=useCustomerRead(({signal})=>listOrders(false,{page:1,page_size:5},signal),data=>parseCustomerOrdersPage(data,1,5));
  return <CustomerRecentOrdersView state={state} retry={reader.load}/>;
}
