import {validDeliveryEstimate} from '../../utils/deliveryEstimate';
import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import {useEffect,useRef,useState} from 'react';
import {Link,useNavigate} from 'react-router-dom';
import {useShopping} from '../../context/ShoppingContext';
import {quoteCart,placeOrder} from '../../services/orderService';
import {cartPayload,money,orderError,orderButton as button,orderCard as card,orderField as field} from '../../utils/shopping';
export default function ShoppingCart({checkout=false}){
  const { tr } = useAppTranslation();
  const shopping=useShopping(),{cart,pending}=shopping,navigate=useNavigate();
  const [quoted,setQuote]=useState(null),[error,setError]=useState(''),[method,setMethod]=useState('cash'),[busy,setBusy]=useState(false),[revision,setRevision]=useState(0);
  const selectedMethod=pending?.payment_method||method;
  const quote=quoted?.cart===cart&&quoted?.revision===revision?quoted.data:null;
  const lock=useRef(false),alive=useRef(true);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[]);
  useEffect(()=>{const abort=new AbortController();if(cart.items.length)quoteCart(cartPayload(cart),abort.signal).then(data=>{if(!abort.signal.aborted){setQuote({cart,revision,data});setError('');}}).catch(error=>{if(!abort.signal.aborted){setQuote(null);setError(orderError(error));}});return()=>abort.abort();},[cart,revision]);
  function change(item,quantity){try{shopping.update(item,quantity);}catch(error){setError(error.message);}}
  async function submit(){
    if(lock.current||(!quote&&!pending))return;lock.current=true;setBusy(true);setError('');
    const payload=pending||{...cartPayload(cart),payment_method:method,request_key:crypto.randomUUID()};
    shopping.setPending(payload);
    try{const order=await placeOrder(payload);shopping.placed();if(alive.current)navigate('/customer/orders/'+order.order_id,{state:{estimated:quote?.total,actual:order.total}});}
    catch(error){if(alive.current){setError(orderError(error));if([400,401,403,404,409,422].includes(error.response?.status))shopping.setPending(null);}}
    finally{lock.current=false;if(alive.current)setBusy(false);}
  }
  return <div className="space-y-5 text-[#10243E]"><h2 className="text-2xl font-bold">{tr("Shopping Cart & Checkout")}</h2><Link className={button} to="/customer/shops/explore">{tr("Explore Shops")}</Link><Link className={button} to="/customer/orders">{tr("My Orders")}</Link>
  {error&&<p role="alert" className={card}>{tr(error)}</p>}
  {!cart.items.length?<p className={card}>{tr("Your cart is empty.")}</p>:<>
  <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1.8fr)_minmax(300px,1fr)]"><div className="space-y-5">
  <section className={card}><h3 className="break-words text-lg font-bold">{quote?.business_name||tr("Selected shop")}</h3><p className="mt-2 text-sm">{tr("One shop per order. Prices and totals are estimates until the server confirms submission.")}</p>
  <ul className="divide-y divide-[#E1EAF4]">{cart.items.map(item=>{const line=quote?.items.find(i=>i.product_id===item.product_id);return <li className="grid items-center gap-3 py-4 sm:grid-cols-[minmax(0,1fr)_160px_auto]" key={item.product_id}><h4 className="break-words font-semibold">{line?.product_name||item.name}</h4>{line&&<p>{money(line.unit_price)} {tr("each ·")} {money(line.line_total)}</p>}<label className="block text-sm">{tr("Quantity for")} {item.name}<input className={field} type="number" min="1" max="99" value={item.quantity} disabled={busy||!!pending} onChange={event=>{const q=Number(event.target.value);if(Number.isInteger(q)&&q>=1&&q<=99)change(item,q);}}/></label><button className={button} disabled={busy||!!pending} onClick={()=>change(item,0)}>{tr("Remove")} {item.name}</button></li>;})}</ul>
  {!quote&&!error&&<p role="status">{tr("Checking current prices...")}</p>}{quote&&<p className="mt-4 break-words font-bold">{tr("Actual Order Amount Payable")} {money(quote.total)}</p>}
  <div className="mt-4 flex flex-wrap gap-3"><button className={button} disabled={busy} onClick={()=>setRevision(n=>n+1)}>{tr("Refresh current prices")}</button><button className={button} disabled={busy||!!pending} onClick={shopping.clear}>{tr("Clear cart")}</button>{!checkout&&quote&&<Link className={button} to="/customer/checkout">{tr("Checkout")}</Link>}</div></section>
  <section className={card}><h3 className="text-lg font-bold">{tr("Delivery Options")}</h3><div className="customer-unavailable mt-4">{tr("Delivery or store-pickup selection and saved delivery addresses are not supported at checkout. Delivery coordination is managed separately after order processing.")}</div></section>
  </div><aside className="space-y-5 xl:sticky xl:top-24"><section className={card}><h3 className="text-xl font-bold">{tr("Order Summary")}</h3><CheckoutTotals quote={quote}/><p className="mt-4 text-xs text-[#64748B]">{tr("Current server quote. Final totals are validated again on submission.")}</p></section>
  {checkout&&<section className={card}><h3 className="font-bold">{tr("Payment method")}</h3><label className="mt-4 flex min-h-11 items-center gap-3"><input type="radio" name="payment-method" value="cash" checked={selectedMethod==='cash'} disabled={busy||!!pending} onChange={()=>setMethod('cash')}/>{tr("Cash — offline, unpaid")}</label><label className="flex min-h-11 items-center gap-3"><input type="radio" name="payment-method" value="credit" checked={selectedMethod==='credit'} disabled={busy||!!pending||!quote?.credit_available} onChange={()=>setMethod('credit')}/>{tr("Credit — requires Shop Owner approval")}</label><p className="my-4 text-sm">{tr(quote?.credit_guidance)}</p><p className="mb-4 text-sm">{tr("No online payment, taxes, delivery fees or automatic delivery request. Credit submission creates no debt.")}</p>{pending&&<p role="status" className="mb-4">{tr("An order submission is unconfirmed. Retry the same request; review My Orders before abandoning it.")}</p>}<button className={button+' bg-[#12B8A6]'} disabled={busy||(!pending&&!quote)||(!pending&&method==='credit'&&!quote?.credit_available)} onClick={submit}>{busy?tr("Submitting..."):pending?tr("Retry same order"):tr("Place Order")}</button></section>}
  </aside></div>
  </>}
  </div>;
}

export function CheckoutTotals({quote}) {
  const {tr}=useAppTranslation();
  const available=quote&&validDeliveryEstimate(quote.subtotal,quote.estimated_delivery_fee,quote.estimated_total_with_delivery);
  return <><dl className="mt-5 space-y-4 text-sm">
    <div className="flex justify-between gap-3"><dt>{tr('Items Subtotal')}</dt><dd>{quote?money(quote.subtotal):tr('Amount unavailable')}</dd></div>
    <div className="flex justify-between gap-3"><dt>{tr('Estimated Delivery Fee (3%)')}</dt><dd>{available?money(quote.estimated_delivery_fee):tr('Amount unavailable')}</dd></div>
    <div className="flex justify-between gap-3"><dt>{tr('Estimated Total Including Delivery')}</dt><dd>{available?money(quote.estimated_total_with_delivery):tr('Amount unavailable')}</dd></div>
    <div className="flex justify-between gap-3 border-t border-[#E1EAF4] pt-4 text-xl font-bold"><dt>{tr('Actual Order Amount Payable')}</dt><dd>{quote?money(quote.total):tr('Amount unavailable')}</dd></div>
  </dl><p className="mt-3 text-xs text-[#64748B]">{tr('Delivery estimates are informational only, not charged or recorded as earnings.')}</p></>;
}
