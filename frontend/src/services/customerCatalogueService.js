import api from './api';
export const listCatalogueShops=async({page=1,q='',signal}={})=>(await api.get('/customer/catalogue/shops',{signal,params:{page,page_size:10,...(q?{q}:{})}})).data;
export const getCatalogueShop=async(businessId,{signal}={})=>(await api.get('/customer/catalogue/shops/'+businessId,{signal})).data;
export const listCatalogueCategories=async(businessId,{page=1,signal}={})=>(await api.get(`/customer/catalogue/shops/${businessId}/categories`,{signal,params:{page,page_size:10}})).data;
export const listCatalogueProducts=async(businessId,{page=1,filters={},signal}={})=>(await api.get(`/customer/catalogue/shops/${businessId}/products`,{signal,params:{page,page_size:10,...Object.fromEntries(Object.entries(filters).filter(([,value])=>value!==''))}})).data;
export const getCatalogueProduct=async(businessId,productId,{signal}={})=>(await api.get(`/customer/catalogue/shops/${businessId}/products/${productId}`,{signal})).data;
