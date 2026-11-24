// Purpose: Define the shopping context contract used by the provider and cart consumers.
import {createContext,useContext} from 'react';
export const ShoppingContext=createContext(null);
// Share shopping state and lifecycle behavior between React consumers.
export function useShopping(){return useContext(ShoppingContext);}
