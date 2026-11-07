import {useEffect,useRef,useState} from 'react';
import {Link,useNavigate} from 'react-router-dom';
import {useShopping} from '../../context/ShoppingContext';
import {quoteCart,placeOrder} from '../../services/orderService';
import {cartPayload,money,orderError,orderButton as button,orderCard as card,orderField as field} from '../../utils/shopping';
export default function ShoppingCart({checkout=false}){
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
  return <div className="space-y-5 text-[#10243E]"><h2 className="text-2xl font-bold">{checkout?'Checkout':'Shopping Cart'}</h2><Link className={button} to="/customer/shops/explore">Explore Shops</Link><Link className={button} to="/customer/orders">My Orders</Link>
  {error&&<p role="alert" className={card}>{error}</p>}
  {!cart.items.length?<p className={card}>Your cart is empty.</p>:<>
  <section className={card}><h3 className="break-words text-lg font-bold">{quote?.business_name||'Selected shop'}</h3><p className="mt-2 text-sm">One shop per order. Prices and totals are estimates until the server confirms submission.</p>
  <ul className="divide-y divide-[#E1EAF4]">{cart.items.map(item=>{const line=quote?.items.find(i=>i.product_id===item.product_id);return <li className="space-y-3 py-4" key={item.product_id}><h4 className="break-words font-semibold">{line?.product_name||item.name}</h4>{line&&<p>{money(line.unit_price)} each · {money(line.line_total)}</p>}<label className="block text-sm">Quantity for {item.name}<input className={field} type="number" min="1" max="99" value={item.quantity} disabled={busy||!!pending} onChange={event=>{const q=Number(event.target.value);if(Number.isInteger(q)&&q>=1&&q<=99)change(item,q);}}/></label><button className={button} disabled={busy||!!pending} onClick={()=>change(item,0)}>Remove {item.name}</button></li>;})}</ul>
  {!quote&&!error&&<p role="status">Checking current prices...</p>}{quote&&<p className="mt-4 break-words font-bold">Estimated total: {money(quote.total)}</p>}
  <div className="mt-4 flex flex-wrap gap-3"><button className={button} disabled={busy} onClick={()=>setRevision(n=>n+1)}>Refresh current prices</button><button className={button} disabled={busy||!!pending} onClick={shopping.clear}>Clear cart</button>{!checkout&&quote&&<Link className={button} to="/customer/checkout">Checkout</Link>}</div></section>
  {checkout&&<section className={card}><h3 className="font-bold">Payment method</h3><label className="mt-4 flex min-h-11 items-center gap-3"><input type="radio" name="payment-method" value="cash" checked={selectedMethod==='cash'} disabled={busy||!!pending} onChange={()=>setMethod('cash')}/>Cash — offline, unpaid</label><label className="flex min-h-11 items-center gap-3"><input type="radio" name="payment-method" value="credit" checked={selectedMethod==='credit'} disabled={busy||!!pending||!quote?.credit_available} onChange={()=>setMethod('credit')}/>Credit — requires Shop Owner approval</label><p className="my-4 text-sm">{quote?.credit_guidance}</p><p className="mb-4 text-sm">No online payment, taxes, delivery fees or automatic delivery request. Credit submission creates no debt.</p>{pending&&<p role="status" className="mb-4">An order submission is unconfirmed. Retry the same request; review My Orders before abandoning it.</p>}<button className={button+' bg-[#12B8A6]'} disabled={busy||(!pending&&!quote)||(!pending&&method==='credit'&&!quote?.credit_available)} onClick={submit}>{busy?'Submitting...':pending?'Retry same order':'Place Order'}</button></section>}
  </>}
  </div>;
}
