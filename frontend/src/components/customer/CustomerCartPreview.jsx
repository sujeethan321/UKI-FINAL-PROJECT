// Purpose: Render the reusable customer cart preview interface and keep its presentation and interactions together.
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import {Link} from 'react-router-dom';
import {ShoppingBag} from 'lucide-react';
import {useShopping} from '../../context/ShoppingContext';
import {customerCard} from './CustomerData';

// Render the customer cart preview interface and connect its controls to the state and callbacks defined here.
export default function CustomerCartPreview() {
  const { tr } = useAppTranslation();
  const shopping=useShopping();
  if(!shopping?.cart.items.length)return null;
  return <section className={customerCard+' flex flex-wrap items-center gap-5'} aria-label={tr("Cart preview")}><ShoppingBag size={28} className="text-[#008C87]" aria-hidden="true"/><div className="min-w-0 flex-1"><h3 className="font-bold">{tr("Your Cart")}</h3><ul className="mt-2 flex flex-wrap gap-x-5 gap-y-2 text-sm">{shopping.cart.items.map(item=><li key={item.product_id} className="break-words">{item.name} {tr("· Quantity:")} {item.quantity}</li>)}</ul><p className="mt-2 text-xs text-[#64748B]">{tr("View your cart to check current server-quoted prices and total.")}</p></div><Link className="customer-primary" to="/customer/cart">{tr("View Cart")}</Link></section>;
}
