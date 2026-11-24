// Purpose: Keep shop owner catalogue data handling and workflow helpers separate from React rendering so callers use consistent rules.
import {cataloguePrice} from './catalogueMoney.js';
export {cataloguePrice,catalogueMoney} from './catalogueMoney.js';
export const availabilityLabels={available:'Available',unavailable:'Unavailable'};
export const publicationLabels={draft:'Draft',published:'Published',archived:'Archived'};
// Accept only supported identifiers before response data is used for lookups or navigation.
const id=value=>Number.isSafeInteger(value)&&value>0;
// Validate count values before the interface uses them for totals or pagination.
const count=value=>Number.isSafeInteger(value)&&value>=0;
// Validate text values at the response boundary before rendering them.
const text=value=>typeof value==='string'&&!!value.trim();
// Check the date representation before it enters the displayed dataset.
const date=value=>typeof value==='string'&&/^\d{4}-\d\d-\d\dT/.test(value)&&!Number.isNaN(Date.parse(value+'Z'));
// Project only the named response fields so unrelated API fields do not enter view state.
const pick=(row,keys)=>Object.fromEntries(keys.map(key=>[key,row[key]]));
// Check category before the surrounding workflow uses it.
export function parseCategory(row,businessId){
  if(!id(row?.category_id)||row.business_id!==businessId||!text(row.name)||typeof row.is_active!=='boolean'||
    !(row.description===null||typeof row.description==='string')||!date(row.created_at)||!date(row.updated_at))throw Error('Invalid category');
  return pick(row,['category_id','business_id','name','description','is_active','created_at','updated_at']);
}
// Check product before the surrounding workflow uses it.
export function parseProduct(row,businessId,productId=null){
  if(!id(row?.product_id)||row.business_id!==businessId||(productId!==null&&row.product_id!==productId)||!text(row.name)||
    !(row.description===null||typeof row.description==='string')||row.currency!=='LKR'||!cataloguePrice(row.unit_price)||
    !Object.hasOwn(availabilityLabels,row.availability_status)||!Object.hasOwn(publicationLabels,row.publication_status)||
    !date(row.created_at)||!date(row.updated_at)||!(row.category_id===null||id(row.category_id))||
    (row.category_id===null?row.category_name!==null:!text(row.category_name)))throw Error('Invalid product');
  return pick(row,['product_id','business_id','category_id','category_name','name','description','unit_price','currency','availability_status','publication_status','created_at','updated_at']);
}
// Check catalogue page before the surrounding workflow uses it.
export function parseCataloguePage(data,businessId,page,kind,filters={}){
  const key=kind==='product'?'products':'categories',identifier=kind==='product'?'product_id':'category_id';
  if(data?.page!==page||data.page_size!==10||!count(data.total)||!Array.isArray(data[key])||data[key].length>Math.min(data.total,10))throw Error('Invalid catalogue page');
  const rows=data[key].map(row=>kind==='product'?parseProduct(row,businessId):parseCategory(row,businessId));
  if(new Set(rows.map(row=>row[identifier])).size!==rows.length)throw Error('Duplicate catalogue row');
  if(kind==='product'&&rows.some(row=>(filters.category_id&&row.category_id!==Number(filters.category_id))||
    (filters.availability_status&&row.availability_status!==filters.availability_status)||(filters.publication_status&&row.publication_status!==filters.publication_status)))throw Error('Filter mismatch');
  return {total:data.total,[key]:rows};
}
// Check catalogue summary before the surrounding workflow uses it.
export function parseCatalogueSummary(data,businessId){
  const keys=['total_products_count','available_products_count','categories_count','unpublished_products_count'];
  if(data?.business_id!==businessId||!keys.every(key=>count(data[key]))||data.available_products_count>data.total_products_count||data.unpublished_products_count>data.total_products_count)throw Error('Invalid catalogue summary');
  return pick(data,['business_id',...keys]);
}
// Reject unsupported control characters or markup before catalogue text is submitted.
const plain=(value,max,required=false)=>typeof value==='string'&&[...value.trim()].length<=max&&(!required||!!value.trim())&&![...value].some(char=>char.codePointAt(0)<32||char.codePointAt(0)===127)&&!/<\s*(?:\/?[A-Za-z][\w:-]*|!)[^>]*>/.test(value);
// Check catalogue form before the surrounding workflow uses it.
export function validateCatalogueForm(kind,form,categories=[],baseline=null){
  if(!plain(form.name,kind==='product'?200:100,true)||!plain(form.description,kind==='product'?4000:2000))return {error:'Use a name and plain-text description within the displayed limits; HTML and control characters are unsupported.'};
  const payload={name:form.name.trim(),description:form.description.trim()||null};
  if(kind==='category'){
    if(typeof form.is_active!=='boolean')return {error:'Select a valid category status.'};payload.is_active=form.is_active;
  }else{
    const price=cataloguePrice(form.unit_price);if(!price)return {error:'Enter an LKR price from 0.01 to 9999999999.99 with at most two decimal places.'};
    const categoryId=form.category_id===''?null:Number(form.category_id);
    if(categoryId!==null&&(!id(categoryId)||(!categories.some(c=>c.category_id===categoryId)&&baseline?.category_id!==categoryId)))return {error:'Select a category from this business.'};
    if(!Object.hasOwn(availabilityLabels,form.availability_status)||!['draft','published'].includes(form.publication_status))return {error:'Select valid availability and publication states.'};
    if(form.publication_status==='published'&&categories.some(c=>c.category_id===categoryId&&!c.is_active)&&
      (!baseline||baseline.publication_status!=='published'||baseline.category_id!==categoryId))return {error:'Activate the selected category before publishing.'};
    Object.assign(payload,{category_id:categoryId,unit_price:price,availability_status:form.availability_status,publication_status:form.publication_status});
  }
  if(baseline)return {payload:Object.fromEntries(Object.entries(payload).filter(([key,value])=>value!==baseline[key]))};
  return {payload};
}
// Create a blank product draft for the new-product form.
const emptyProduct=()=>({name:'',description:'',category_id:'',unit_price:'',availability_status:'available',publication_status:'draft'});
// Create a blank category draft for the new-category form.
const emptyCategory=()=>({name:'',description:'',is_active:true});
// Create a resource section with its own data, loading, and error state for independent updates.
const section=()=>({data:null,loading:false,error:''});
// Build initial workflow state before resource loading or user interaction begins.
const initial=()=>({businesses:[],businessId:null,contextLoading:true,contextError:'',authError:'',page:1,categoryPage:1,
  filters:{q:'',category_id:'',availability_status:'',publication_status:''},products:section(),categories:section(),summary:section(),
  knownCategories:[],editor:null,categoryEditor:null,archive:null,busy:false,error:'',message:'',uncertain:false,reviewed:false,storageError:''});
// Store the catalogue operation intent so retry handling can recognize the same request.
export function catalogueIntentStore(userId){const key=businessId=>'lankapex_catalogue_attempt:'+userId+':'+businessId;
  return {/* Read saved request state for this workflow instance. */ read:b=>sessionStorage.getItem(key(b))!==null,/* Apply the selected notification read-state action through the shared mutation path. */ mark:b=>sessionStorage.setItem(key(b),'unconfirmed'),/* Remove saved state only within the scope checked by this storage adapter. */ clear:b=>sessionStorage.removeItem(key(b))};}
// Translate error message outcomes into display text for the interface.
const errorMessage=error=>error?.response?.status===401?'Your session expired. Please sign in again.':error?.response?.status===403?'Catalogue access is unavailable. Check business approval and account access.':
  error?.response?.status===404?'This business or catalogue record is unavailable.':error?.response?.status===409?'Catalogue conflict. Category names must be unique; check current publication and category status.':
  error?.response?.status===422?'Check the form fields and selected category.':error?.code==='INVALID_RESPONSE'?'The catalogue response could not be verified. Refresh to retry.':'Catalogue information is unavailable. Check your connection and refresh.';
// Create catalogue workflow for the shop owner catalogue workflow.
export function createCatalogueWorkflow(api,userId,store=catalogueIntentStore(userId)){
  let state=initial(),alive=false,generation=0,inFlight=null;const listeners=new Set(),controllers={},versions={};
  // Replace the store snapshot and notify subscribers so React can render the new state.
  const publish=patch=>{if(alive){state={...state,...patch};listeners.forEach(fn=>fn());}};
  // Cancel obsolete reads so their responses cannot update the active resource.
  const abort=()=>Object.values(controllers).forEach(c=>c.abort());
  // Check whether the selected business is approved before enabling owner operations.
  const approved=()=>state.businesses.some(b=>b.business_id===state.businessId&&b.approval_status==='approved');
  // Clear protected resource state after access is denied so earlier data is not left visible.
  const deny=error=>{generation++;abort();publish({...initial(),contextLoading:false,authError:errorMessage(error)});};
  // Read the saved or current resource state used by this workflow.
  async function read(key,fetcher,parse){
    if(!alive||state.authError)return null;controllers[key]?.abort();const controller=controllers[key]=new AbortController(),epoch=generation,version=versions[key]=(versions[key]||0)+1;
    // Check valid before the surrounding workflow uses it.
    const valid=()=>alive&&generation===epoch&&!controller.signal.aborted&&versions[key]===version;
    publish({[key]:{...state[key],data:null,loading:true,error:''}});
    try{const result=await fetcher({signal:controller.signal});if(!valid())return null;let data;try{data=parse(result);}catch{throw Object.assign(Error('Invalid response'),{code:'INVALID_RESPONSE'});}
      publish({[key]:{...state[key],data,loading:false,error:''},...(key==='categories'?{knownCategories:[...new Map([...state.knownCategories,...data.categories].map(row=>[row.category_id,row])).values()]}:{})});return data;
    }catch(error){if(!valid())return null;if([401,403].includes(error?.response?.status))deny(error);else publish({[key]:{...state[key],data:null,loading:false,error:errorMessage(error)}});return null;}
  }
  // Load product data for the selected catalogue scope.
  const products=()=>{const {businessId,page,filters}=state;return approved()?read('products',options=>api.listProducts(businessId,{page,filters,...options}),data=>parseCataloguePage(data,businessId,page,'product',filters)):Promise.resolve(null);};
  // Load category data into the current catalogue resource state.
  const categories=()=>{const {businessId,categoryPage}=state;return approved()?read('categories',options=>api.listCategories(businessId,{page:categoryPage,...options}),data=>parseCataloguePage(data,businessId,categoryPage,'category')):Promise.resolve(null);};
  // Load summary data separately from list or detail state so each section can refresh independently.
  const summary=()=>{const {businessId}=state;return approved()?read('summary',options=>api.summary(businessId,options),data=>parseCatalogueSummary(data,businessId)):Promise.resolve(null);};
  // Load the current resource data and update the state consumed by the interface.
  async function refresh(){if(state.busy||state.authError)return;const results=await Promise.allSettled([products(),categories(),summary()]);
    if(state.uncertain&&state.products.data&&state.categories.data)publish({reviewed:true});return results;}
  // Select business within the shop owner catalogue workflow.
  async function selectBusiness(businessId){if(state.busy||!state.businesses.some(b=>b.business_id===businessId))return;
    generation++;abort();let uncertain=false,storageError='';try{uncertain=store.read(businessId);}catch{storageError='Session storage is unavailable. New catalogue records are disabled.';}
    publish({...initial(),businesses:state.businesses,businessId,contextLoading:false,uncertain,storageError});return refresh();}
  // Start the reader by loading the context and resource sections needed by the screen.
  async function start(){alive=true;generation++;abort();publish(initial());const epoch=generation,controller=controllers.context=new AbortController();
    try{const data=await api.businesses({signal:controller.signal});if(!alive||epoch!==generation||controller.signal.aborted)return;
      if(data?.user_id!==userId||!Array.isArray(data.businesses)||data.businesses.some(b=>!id(b.business_id)||!text(b.business_name)||!['approved','pending','rejected'].includes(b.approval_status)))throw Error('Invalid business context');
      const rows=data.businesses.map(b=>pick(b,['business_id','business_name','approval_status']));if(new Set(rows.map(b=>b.business_id)).size!==rows.length)throw Error('Duplicate business');
      publish({businesses:rows,contextLoading:false});const chosen=rows.find(b=>b.approval_status==='approved')||rows[0];if(chosen)await selectBusiness(chosen.business_id);
    }catch(error){if(alive&&epoch===generation&&!controller.signal.aborted){if([401,403].includes(error?.response?.status))deny(error);else publish({contextLoading:false,contextError:errorMessage(error)});}}
  }
  // Open product within the shop owner catalogue workflow.
  async function openProduct(productId=null){if(state.busy||!approved()||state.authError)return;
    if(productId===null){publish({editor:{id:null,form:emptyProduct(),baseline:null,loading:false,error:''},error:'',message:''});return;}
    if(!id(productId))return;publish({editor:{id:productId,form:emptyProduct(),baseline:null,loading:false,error:''},error:''});
    const businessId=state.businessId,data=await read('editor',options=>api.getProduct(businessId,productId,options),row=>parseProduct(row,businessId,productId));
    if(data&&state.editor?.id===productId){if(data.publication_status==='archived'){publish({editor:null,error:'Archived products cannot be edited.'});return;}
      publish({editor:{id:productId,baseline:data,form:{...pick(data,Object.keys(emptyProduct())),description:data.description||'',category_id:data.category_id===null?'':String(data.category_id)},loading:false,error:''}});}
  }
  // Run a resource-changing request while coordinating pending state and the follow-up resource refresh.
  async function mutate(kind,recordId,payload){
    if(inFlight)return inFlight;if(!alive||state.authError||!approved()||state.uncertain)return null;
    const creating=recordId===null,businessId=state.businessId,epoch=generation;
    if(creating){if(state.storageError)return null;try{store.mark(businessId);}catch{publish({storageError:'Unable to protect this creation attempt. No request was sent.'});return null;}}
    // Check valid before the surrounding workflow uses it.
    const controller=controllers.mutation=new AbortController(),valid=()=>alive&&epoch===generation&&!controller.signal.aborted;
    publish({busy:true,error:'',message:'',archive:null});
    const operation=(async()=>{try{
      const write=kind==='product'?(creating?api.createProduct:api.updateProduct):(creating?api.createCategory:api.updateCategory);
      const args=creating?[businessId,payload,{signal:controller.signal}]:[businessId,recordId,payload,{signal:controller.signal}];
      const response=await write(...args);if(!valid())return null;
      const result=kind==='product'?parseProduct(response,businessId,recordId):parseCategory(response,businessId);
      if((!creating&&kind==='category'&&result.category_id!==recordId)||Object.entries(payload).some(([key,value])=>result[key]!==value))throw Error('Unconfirmed catalogue write');
      if(creating){try{store.clear(businessId);}catch{publish({storageError:'The creation succeeded, but its local flag could not be cleared. Review before creating another record.'});}}
      publish({[kind==='product'?'editor':'categoryEditor']:null,message:creating?'Catalogue record created.':'Catalogue record updated.',...(kind==='category'?{knownCategories:[...new Map([...state.knownCategories,result].map(row=>[row.category_id,row])).values()]}:{})});
      await Promise.allSettled([products(),categories(),summary()]);return result;
    }catch(error){if(!valid())return null;const status=error?.response?.status;
      if(creating&&[401,403,404,409,422].includes(status)){try{store.clear(businessId);}catch{publish({storageError:'Unable to clear the creation flag. Review before starting another record.'});}}
      if([401,403].includes(status)){deny(error);return null;}
      publish({error:creating&&![404,409,422].includes(status)?'Creation could not be confirmed. Refresh and review products and categories before starting another record.':errorMessage(error)+(status?'':' The change was not confirmed. Close and reopen the editor to check current values.'),
        ...(creating&&![404,409,422].includes(status)?{uncertain:true,reviewed:false}:{})});return null;
    }finally{if(valid())publish({busy:false});}})();inFlight=operation;try{return await operation;}finally{if(inFlight===operation)inFlight=null;}
  }
  // Submit the current catalogue draft and reconcile resource state with the confirmed result.
  function save(kind){const editor=kind==='product'?state.editor:state.categoryEditor;if(!editor||editor.loading)return;
    const validation=validateCatalogueForm(kind,editor.form,state.knownCategories,editor.baseline);if(validation.error){publish({error:validation.error});return;}
    if(editor.id!==null&&!Object.keys(validation.payload).length){publish({[kind==='product'?'editor':'categoryEditor']:null,message:'No changes to save.'});return;}
    return mutate(kind,editor.id,validation.payload);}
  return {/* Expose the current store snapshot to subscribers without starting a request. */ getSnapshot:()=>state,/* Register a state listener and return cleanup so consumers can unsubscribe. */ subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},start,selectBusiness,refresh,
    // Change the list filters and reload the requested resource page.
    filter(filters){if(state.busy)return;if(!Object.entries(filters).every(([key,value])=>Object.hasOwn(state.filters,key)&&typeof value==='string')||filters.q?.length>200)return;publish({filters:{...state.filters,...filters},page:1});return products();},
    // Change the current page and load its resource records.
    page(page){if(state.busy||!id(page)||page>1000000)return;publish({page});return products();},/* Change the category page and load its records. */ categoryPage(page){if(state.busy||!id(page)||page>1000000)return;publish({categoryPage:page});return categories();},
    openProduct,/* Close the product editor through its draft and pending-state rules. */ closeProduct(){if(!state.busy){controllers.editor?.abort();publish({editor:null,error:''});}},
    // Open the selected category draft for editing.
    openCategory(row=null){if(state.busy||!approved()||(row&&row.business_id!==state.businessId))return;publish({categoryEditor:{id:row?.category_id??null,baseline:row,form:row?{name:row.name,description:row.description||'',is_active:row.is_active}:emptyCategory()},error:'',message:''});},
    // Close the category editor through its draft and pending-state rules.
    closeCategory(){if(!state.busy)publish({categoryEditor:null,error:''});},
    // Update the editable draft while retaining the current operation context.
    edit(kind,key,value){const name=kind==='product'?'editor':'categoryEditor',editor=state[name];if(!state.busy&&editor&&Object.hasOwn(editor.form,key))publish({[name]:{...editor,form:{...editor.form,[key]:value}},error:''});},
    // Submit the product draft through the catalogue mutation rules.
    saveProduct:()=>save('product'),/* Submit the category draft through the catalogue mutation rules. */ saveCategory:()=>save('category'),
    // Change the product draft while retaining the workflow rules for pending requests.
    changeProduct(row,payload){if(row.business_id!==state.businessId||row.publication_status==='archived'||state.editor)return;return mutate('product',row.product_id,payload);},
    // Change the category draft while retaining the workflow rules for pending requests.
    changeCategory(row){if(row.business_id!==state.businessId)return;return mutate('category',row.category_id,{is_active:!row.is_active});},
    // Apply the explicit archive confirmation before issuing the resource change.
    confirmArchive(row){if(!state.busy&&(!row||row.business_id===state.businessId))publish({archive:row});},
    // Request archival of the selected resource through the workflow action path.
    archive(){const row=state.archive;if(row)return mutate('product',row.product_id,{publication_status:'archived'});},
    // Acknowledge the workflow result before permitting the next operation.
    acknowledge(){if(!state.uncertain||!state.reviewed||state.busy)return;try{store.clear(state.businessId);publish({uncertain:false,reviewed:false,error:'',editor:null,categoryEditor:null});}catch{publish({storageError:'Unable to clear the unresolved creation flag.'});}},
    // Release pending work and subscriptions when this resource reader is no longer used.
    dispose(){alive=false;generation++;abort();state=initial();},
  };
}
