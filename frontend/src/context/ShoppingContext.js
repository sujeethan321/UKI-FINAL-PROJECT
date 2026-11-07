import {createContext,useContext} from 'react';
export const ShoppingContext=createContext(null);
export function useShopping(){return useContext(ShoppingContext);}
