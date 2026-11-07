import {useState} from 'react';
import {useShopping} from '../../context/ShoppingContext';
import {orderButton as button} from '../../utils/shopping';
export default function AddToCart({product}){
 const shopping=useShopping(),[replace,setReplace]=useState(false),[message,setMessage]=useState('');
 if(!shopping)return null;
 function add(replaceCart=false){try{const existing=shopping.cart.items.find(i=>i.product_id===product.product_id);shopping.update(product,replaceCart?1:(existing?.quantity||0)+1,replaceCart);setReplace(false);setMessage('Added to cart.');}catch(error){setMessage(error.message);}}
 return <div className="space-y-3"><button className={button} disabled={product.availability_status!=='available'||!!shopping.pending} onClick={()=>{setMessage('');if(shopping.cart.business_id&&shopping.cart.business_id!==product.business_id)setReplace(true);else add();}}>Add to Cart</button>{replace&&<div role="group" aria-label="Replace shop cart" className="space-y-3"><p>Replace your current cart with an item from this shop?</p><div className="flex flex-wrap gap-3"><button className={button} onClick={()=>add(true)}>Replace cart</button><button className={button} onClick={()=>setReplace(false)}>Keep current cart</button></div></div>}{message&&<p role="status">{message}</p>}</div>;
}
