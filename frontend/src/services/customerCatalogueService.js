// Purpose: Wrap customer catalogue API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from './api';
// Call GET /customer/catalogue/shops through the shared client so authentication and API configuration are applied consistently.
export const listCatalogueShops=async({page=1,q='',signal}={})=>(await api.get('/customer/catalogue/shops',{signal,params:{page,page_size:10,...(q?{q}:{})}})).data;
// Get catalogue shop within the customer catalogue workflow.
export const getCatalogueShop=async(businessId,{signal}={})=>(await api.get('/customer/catalogue/shops/'+businessId,{signal})).data;
// Call GET /customer/catalogue/shops/{parameter}/categories through the shared client so authentication and API configuration are applied consistently.
export const listCatalogueCategories=async(businessId,{page=1,signal}={})=>(await api.get(`/customer/catalogue/shops/${businessId}/categories`,{signal,params:{page,page_size:10}})).data;
// Call GET /customer/catalogue/shops/{parameter}/products through the shared client so authentication and API configuration are applied consistently.
export const listCatalogueProducts=async(businessId,{page=1,filters={},signal}={})=>(await api.get(`/customer/catalogue/shops/${businessId}/products`,{signal,params:{page,page_size:10,...Object.fromEntries(Object.entries(filters).filter(([,value])=>value!==''))}})).data;
// Call GET /customer/catalogue/shops/{parameter}/products/{parameter} through the shared client so authentication and API configuration are applied consistently.
export const getCatalogueProduct=async(businessId,productId,{signal}={})=>(await api.get(`/customer/catalogue/shops/${businessId}/products/${productId}`,{signal})).data;
