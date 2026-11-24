// Purpose: Keep shopping/cart state available to customer screens within the current application context.
import {useState} from 'react';
import {ShoppingContext} from './ShoppingContext';
import {cartChange} from '../utils/shopping';
const empty={business_id:null,items:[]};
// Render the shopping provider interface and connect its controls to the state and callbacks defined here.
export default function ShoppingProvider({children}){
  const [cart,setCart]=useState(empty),[pending,setPending]=useState(null);
  // Apply the new state and notify the consumers or handlers registered by this workflow.
  function update(product,quantity,replace=false){if(pending)throw Error('Resolve the pending checkout before changing the cart.');setCart(cartChange(cart,product,quantity,replace));}
  return <ShoppingContext.Provider value={{cart,update,pending,setPending,/* Remove saved state only within the scope checked by this storage adapter. */ clear(){if(!pending)setCart(empty);},/* Reconcile shopping state after an order is confirmed as placed. */ placed(){setPending(null);setCart(empty);}}}>{children}</ShoppingContext.Provider>;
}
