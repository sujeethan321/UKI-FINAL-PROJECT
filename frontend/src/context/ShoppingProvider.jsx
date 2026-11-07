import {useState} from 'react';
import {ShoppingContext} from './ShoppingContext';
import {cartChange} from '../utils/shopping';
const empty={business_id:null,items:[]};
export default function ShoppingProvider({children}){
  const [cart,setCart]=useState(empty),[pending,setPending]=useState(null);
  function update(product,quantity,replace=false){if(pending)throw Error('Resolve the pending checkout before changing the cart.');setCart(cartChange(cart,product,quantity,replace));}
  return <ShoppingContext.Provider value={{cart,update,pending,setPending,clear(){if(!pending)setCart(empty);},placed(){setPending(null);setCart(empty);}}}>{children}</ShoppingContext.Provider>;
}
