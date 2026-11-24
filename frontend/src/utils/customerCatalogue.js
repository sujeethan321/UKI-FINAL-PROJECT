// Purpose: Keep customer catalogue data handling and workflow helpers separate from React rendering so callers use consistent rules.
import {cataloguePrice} from './catalogueMoney.js';
// Check the catalogue identifier before building a product or category request.
export const validCatalogueId=value=>Number.isSafeInteger(value)&&value>0;
// Validate count values before the interface uses them for totals or pagination.
const count=value=>Number.isSafeInteger(value)&&value>=0;
// Validate text values at the response boundary before rendering them.
const text=value=>typeof value==='string'&&!!value.trim();
// Project only the named response fields so unrelated API fields do not enter view state.
const pick=(row,keys)=>Object.fromEntries(keys.map(key=>[key,row[key]]));
// Check public shop before the surrounding workflow uses it.
export function parsePublicShop(row,businessId=null){
  if(!validCatalogueId(row?.business_id)||!text(row.business_name)||!count(row.product_count)||(businessId!==null&&row.business_id!==businessId))throw Error('Invalid public shop');
  return pick(row,['business_id','business_name','product_count']);
}
// Check public product before the surrounding workflow uses it.
export function parsePublicProduct(row,businessId,productId=null){
  if(!validCatalogueId(row?.product_id)||row.business_id!==businessId||(productId!==null&&row.product_id!==productId)||!text(row.name)||
    !(row.description===null||typeof row.description==='string')||row.currency!=='LKR'||!cataloguePrice(row.unit_price)||
    !['available','unavailable'].includes(row.availability_status)||!(row.category_id===null||validCatalogueId(row.category_id))||
    (row.category_id===null?row.category_name!==null:!text(row.category_name))||Object.hasOwn(row,'publication_status'))throw Error('Invalid public product');
  return pick(row,['product_id','business_id','category_id','category_name','name','description','unit_price','currency','availability_status']);
}
// Check public category before the surrounding workflow uses it.
export function parsePublicCategory(row,businessId){
  if(!validCatalogueId(row?.category_id)||row.business_id!==businessId||!text(row.name)||!(row.description===null||typeof row.description==='string')||row.is_active===false)throw Error('Invalid public category');
  return pick(row,['category_id','business_id','name','description']);
}
// Check public page before the surrounding workflow uses it.
export function parsePublicPage(data,key,page,businessId=null,filters={}){
  if(data?.page!==page||data.page_size!==10||!count(data.total)||!Array.isArray(data[key])||data[key].length>Math.min(data.total,10))throw Error('Invalid catalogue page');
  const rows=data[key].map(row=>key==='shops'?parsePublicShop(row):key==='products'?parsePublicProduct(row,businessId):parsePublicCategory(row,businessId));
  const id=key==='shops'?'business_id':key==='products'?'product_id':'category_id';
  if(new Set(rows.map(row=>row[id])).size!==rows.length||(key==='shops'&&rows.some(row=>row.product_count<1)))throw Error('Invalid discovery rows');
  if(key==='products'&&rows.some(row=>(filters.category_id&&row.category_id!==Number(filters.category_id))||(filters.availability_status&&row.availability_status!==filters.availability_status)))throw Error('Product filter mismatch');
  return {total:data.total,[key]:rows};
}
// Create a resource section with its own data, loading, and error state for independent updates.
const section=()=>({data:null,loading:false,error:''});
// Build initial workflow state before resource loading or user interaction begins.
const initial=()=>({shops:section(),shop:section(),products:section(),categories:section(),detail:section(),knownCategories:[],
  shopsPage:1,page:1,categoryPage:1,q:'',filters:{q:'',category_id:'',availability_status:''},authError:''});
// Translate catalogue browse outcomes into display text for the interface.
export function catalogueBrowseError(error){
  const status=error?.response?.status;
  return status===401?'Your session expired. Please sign in again.':status===403?'Customer catalogue access is unavailable for this account.':
    status===404?'This shop or product is no longer available.':status===422?'Check the search, filters and page selection.':
    error?.code==='INVALID_RESPONSE'?'The catalogue response could not be verified. Refresh to retry.':'Catalogue service unavailable. Check your connection and refresh.';
}
// Create customer catalogue workflow for the customer catalogue workflow.
export function createCustomerCatalogueWorkflow(api,{businessId=null,productId=null,initialQuery=''}={}){
  let state=initial(),alive=false,generation=0;const listeners=new Set(),controllers={},versions={};
  // Replace the store snapshot and notify subscribers so React can render the new state.
  const publish=patch=>{if(alive){state={...state,...patch};listeners.forEach(fn=>fn());}};
  // Cancel obsolete reads so their responses cannot update the active resource.
  const abort=()=>Object.values(controllers).forEach(c=>c.abort());
  // Clear protected resource state after access is denied so earlier data is not left visible.
  const deny=error=>{generation++;abort();publish({...initial(),authError:catalogueBrowseError(error)});};
  // Read the saved or current resource state used by this workflow.
  async function read(key,fetcher,parse){
    if(!alive||state.authError)return null;controllers[key]?.abort();const controller=controllers[key]=new AbortController(),epoch=generation,version=versions[key]=(versions[key]||0)+1;
    // Check valid before the surrounding workflow uses it.
    const valid=()=>alive&&epoch===generation&&!controller.signal.aborted&&versions[key]===version;
    publish({[key]:{data:null,loading:true,error:''}});
    try{const result=await fetcher({signal:controller.signal});if(!valid())return null;let data;try{data=parse(result);}catch{throw Object.assign(Error('Invalid response'),{code:'INVALID_RESPONSE'});}
      publish({[key]:{data,loading:false,error:''},...(key==='categories'?{knownCategories:[...new Map([...state.knownCategories,...data.categories].map(row=>[row.category_id,row])).values()]}:{})});return data;
    }catch(error){if(!valid())return null;
      if([401,403].includes(error?.response?.status))deny(error);
      else if(error?.response?.status===404&&['shop','products','categories'].includes(key)){
        generation++;abort();publish({shop:{data:null,loading:false,error:catalogueBrowseError(error)},products:section(),categories:section(),detail:section(),knownCategories:[]});
      }else publish({[key]:{data:null,loading:false,error:catalogueBrowseError(error)}});return null;}
  }
  // Load shops available to the current customer context.
  function shops(){const {shopsPage,q}=state;return read('shops',options=>api.shops({page:shopsPage,q,...options}),data=>parsePublicPage(data,'shops',shopsPage));}
  // Load product data for the selected catalogue scope.
  function products(){const {page,filters}=state;if(!state.shop.data)return Promise.resolve(null);return read('products',options=>api.products(businessId,{page,filters,...options}),data=>parsePublicPage(data,'products',page,businessId,filters));}
  // Load category data into the current catalogue resource state.
  function categories(){const {categoryPage}=state;if(!state.shop.data)return Promise.resolve(null);return read('categories',options=>api.categories(businessId,{page:categoryPage,...options}),data=>parsePublicPage(data,'categories',categoryPage,businessId));}
  // Load the current resource data and update the state consumed by the interface.
  async function refresh(){
    if(state.authError)return;
    if(businessId===null)return shops();
    controllers.products?.abort();controllers.categories?.abort();controllers.detail?.abort();
    publish({products:section(),detail:section(),categories:section()});
    const shop=await read('shop',options=>api.shop(businessId,options),data=>parsePublicShop(data,businessId));if(!shop)return;
    if(productId!==null)return read('detail',options=>api.product(businessId,productId,options),data=>parsePublicProduct(data,businessId,productId));
    return Promise.allSettled([products(),categories()]);
  }
  return {/* Expose the current store snapshot to subscribers without starting a request. */ getSnapshot:()=>state,/* Register a state listener and return cleanup so consumers can unsubscribe. */ subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},
    // Start the resource workflow using its current context and selection.
    start(){alive=true;generation++;abort();publish({...initial(),q:typeof initialQuery==='string'?initialQuery.trim().slice(0,200):''});if((businessId!==null&&!validCatalogueId(businessId))||(productId!==null&&!validCatalogueId(productId))){publish({shop:{data:null,loading:false,error:'Invalid catalogue identifier.'}});return Promise.resolve();}return refresh();},refresh,
    // Apply the shop search and load the matching customer-visible results.
    searchShops(q){if(typeof q!=='string'||q.length>200||businessId!==null)return;publish({q:q.trim(),shopsPage:1});return shops();},
    // Change the shop list page and request its results.
    shopsPage(page){if(!validCatalogueId(page)||page>1000000||businessId!==null)return;publish({shopsPage:page});return shops();},
    // Change the list filters and reload the requested resource page.
    filter(changes){if(!state.shop.data||productId!==null||!Object.entries(changes).every(([key,value])=>Object.hasOwn(state.filters,key)&&typeof value==='string'))return;
      const filters={...state.filters,...changes};if(filters.q.length>200||(filters.category_id&&!validCatalogueId(Number(filters.category_id)))||(filters.availability_status&&!['available','unavailable'].includes(filters.availability_status)))return;
      publish({filters,page:1});return products();},
    // Change the current page and load its resource records.
    page(page){if(!validCatalogueId(page)||page>1000000)return;publish({page});return products();},
    // Change the category page and load its records.
    categoryPage(page){if(!validCatalogueId(page)||page>1000000)return;publish({categoryPage:page});return categories();},
    // Release pending work and subscriptions when this resource reader is no longer used.
    dispose(){alive=false;generation++;abort();state=initial();},
  };
}
