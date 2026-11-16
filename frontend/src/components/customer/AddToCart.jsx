import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import {useState} from 'react';
import {useShopping} from '../../context/ShoppingContext';
import {orderButton as button} from '../../utils/shopping';
export default function AddToCart({product}){
  const { tr } = useAppTranslation();
 const shopping=useShopping(),[replace,setReplace]=useState(false),[message,setMessage]=useState(''),[quantity,setQuantity]=useState(1);
 if(!shopping)return null;
 function add(replaceCart=false){try{const existing=shopping.cart.items.find(i=>i.product_id===product.product_id);shopping.update(product,replaceCart?quantity:(existing?.quantity||0)+quantity,replaceCart);setReplace(false);setMessage('Added to cart.');}catch(error){setMessage(error.message);}}
 return <div className="space-y-3"><label className="block text-sm">{tr("Quantity to add")}<input type="number" min="1" max="99" value={quantity} disabled={product.availability_status!=='available'||!!shopping.pending} onChange={event=>{const value=Number(event.target.value);if(Number.isInteger(value)&&value>=1&&value<=99)setQuantity(value);}} className="mt-2 w-24 rounded-lg border border-[#DAE5F3] px-3 py-2"/></label><button className={button+' customer-primary'} disabled={product.availability_status!=='available'||!!shopping.pending} onClick={()=>{setMessage('');if(shopping.cart.business_id&&shopping.cart.business_id!==product.business_id)setReplace(true);else add();}}>{tr("Add to Cart")}</button>{replace&&<div role="group" aria-label={tr("Replace shop cart")} className="space-y-3"><p>{tr("Replace your current cart with an item from this shop?")}</p><div className="flex flex-wrap gap-3"><button className={button} onClick={()=>add(true)}>{tr("Replace cart")}</button><button className={button} onClick={()=>setReplace(false)}>{tr("Keep current cart")}</button></div></div>}{message&&<p role="status">{tr(message)}</p>}</div>;
}
