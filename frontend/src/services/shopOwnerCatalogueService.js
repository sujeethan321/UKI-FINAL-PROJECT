// Purpose: Wrap shop owner catalogue API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from './api';
// Call GET /shop-owner/business-context through the shared client so authentication and API configuration are applied consistently.
export const getCatalogueBusinesses=async({signal}={})=>(await api.get('/shop-owner/business-context',{signal})).data;
// Call GET /shop-owner/catalogue/summary through the shared client so authentication and API configuration are applied consistently.
export const getCatalogueSummary=async(businessId,{signal}={})=>(await api.get('/shop-owner/catalogue/summary',{signal,params:{business_id:businessId}})).data;
// Call GET /shop-owner/products through the shared client so authentication and API configuration are applied consistently.
export const listProducts=async(businessId,{page=1,filters={},signal}={})=>(await api.get('/shop-owner/products',{signal,params:{business_id:businessId,page,page_size:10,...Object.fromEntries(Object.entries(filters).filter(([,value])=>value!==''))}})).data;
// Get product within the shop owner catalogue workflow.
export const getProduct=async(businessId,id,{signal}={})=>(await api.get('/shop-owner/products/'+id,{signal,params:{business_id:businessId}})).data;
// Call POST /shop-owner/products through the shared client so authentication and API configuration are applied consistently.
export const createProduct=async(businessId,payload,{signal}={})=>(await api.post('/shop-owner/products',payload,{signal,params:{business_id:businessId}})).data;
// Update product within the shop owner catalogue workflow.
export const updateProduct=async(businessId,id,payload,{signal}={})=>(await api.patch('/shop-owner/products/'+id,payload,{signal,params:{business_id:businessId}})).data;
// Call GET /shop-owner/categories through the shared client so authentication and API configuration are applied consistently.
export const listCategories=async(businessId,{page=1,signal}={})=>(await api.get('/shop-owner/categories',{signal,params:{business_id:businessId,page,page_size:10}})).data;
// Call POST /shop-owner/categories through the shared client so authentication and API configuration are applied consistently.
export const createCategory=async(businessId,payload,{signal}={})=>(await api.post('/shop-owner/categories',payload,{signal,params:{business_id:businessId}})).data;
// Update category within the shop owner catalogue workflow.
export const updateCategory=async(businessId,id,payload,{signal}={})=>(await api.patch('/shop-owner/categories/'+id,payload,{signal,params:{business_id:businessId}})).data;
