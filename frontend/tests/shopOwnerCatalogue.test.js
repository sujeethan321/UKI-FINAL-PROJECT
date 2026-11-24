import test from 'node:test';
import assert from 'node:assert/strict';
import {createCatalogueWorkflow,cataloguePrice,catalogueMoney,validateCatalogueForm,parseCatalogueSummary,parseProduct,parseCataloguePage,catalogueIntentStore} from '../src/utils/shopOwnerCatalogue.js';
import {catalogueFixture,productFixture,categoryFixture} from './fixtures/catalogueFixtures.js';
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
async function setup(){const f=catalogueFixture();f.workflow=createCatalogueWorkflow(f.api,7,f.store);await f.workflow.start();return f;}
const productForm={name:' New product ',description:'',category_id:'11',unit_price:'123.40',availability_status:'available',publication_status:'draft'};
test('money remains exact decimal strings including max and rejects non-prices',()=>{
  assert.equal(cataloguePrice('001.2'),'1.20');assert.equal(catalogueMoney('9999999999.99'),'LKR 9,999,999,999.99');
  for(const value of ['0','-1','NaN','1.001','1e3','10000000000.00',1.25,true,''])assert.equal(cataloguePrice(value),null);
});
test('forms validate required plain text, categories, descriptions and publication separately',()=>{
  const valid=validateCatalogueForm('product',productForm,[categoryFixture()]);assert.equal(valid.payload.unit_price,'123.40');assert.equal(valid.payload.name,'New product');
  for(const patch of [{name:''},{description:'x'.repeat(4001)},{description:'<script>x</script>'},{category_id:'999'},{unit_price:'0'},{availability_status:'low_stock'},{publication_status:'archived'}])assert.ok(validateCatalogueForm('product',{...productForm,...patch},[categoryFixture()]).error);
  assert.ok(validateCatalogueForm('product',{...productForm,publication_status:'published'},[categoryFixture({is_active:false})]).error);
  assert.ok(validateCatalogueForm('category',{name:'x',description:'',is_active:'yes'}).error);
});
test('contracts fail closed for foreign scope, malformed counts, missing names and filtered mismatches',()=>{
  assert.throws(()=>parseProduct(productFixture({business_id:2}),1));assert.throws(()=>parseProduct(productFixture({unit_price:125.25}),1));
  assert.throws(()=>parseProduct(productFixture({category_name:null}),1));assert.throws(()=>parseCatalogueSummary({business_id:1,total_products_count:0,available_products_count:1,categories_count:0,unpublished_products_count:0},1));
  assert.throws(()=>parseCataloguePage({page:1,page_size:10,total:1,products:[productFixture()]},1,1,'product',{publication_status:'published'}));
});
test('business-scoped start loads separate global summary, products and categories',async()=>{
  const f=await setup(),s=f.workflow.getSnapshot();assert.equal(s.businessId,1);assert.equal(s.products.data.total,1);assert.equal(s.summary.data.total_products_count,1);assert.equal(s.categories.data.categories[0].name,'Groceries');f.workflow.dispose();
});
test('empty counts are authoritative zero and summary failures stay unknown',async()=>{
  const f=catalogueFixture();f.setProducts([]);f.api.summary=async()=>{throw Error('private');};const w=createCatalogueWorkflow(f.api,7,f.store);await w.start();assert.equal(w.getSnapshot().products.data.total,0);assert.equal(w.getSnapshot().summary.data,null);assert.ok(w.getSnapshot().summary.error);w.dispose();
});
test('creation validates, prevents duplicate submissions and refreshes confirmed records',async()=>{
  const f=await setup();await f.workflow.openProduct();await f.workflow.saveProduct();assert.equal(f.calls.filter(c=>c[0]==='createProduct').length,0);
  for(const [key,value] of Object.entries(productForm))f.workflow.edit('product',key,value);
  const pending=deferred(),original=f.api.createProduct;f.api.createProduct=async(...args)=>{await pending.promise;return original(...args);};
  const a=f.workflow.saveProduct(),b=f.workflow.saveProduct();assert.ok(f.workflow.getSnapshot().busy);pending.resolve();await Promise.all([a,b]);
  assert.equal(f.calls.filter(c=>c[0]==='createProduct').length,1);assert.equal(f.workflow.getSnapshot().products.data.total,2);assert.equal(f.workflow.getSnapshot().editor,null);f.workflow.dispose();
});
test('edit reads current authorized details, sends only changed fields and retains exact prices',async()=>{
  const f=await setup();await f.workflow.openProduct(31);assert.equal(f.workflow.getSnapshot().editor.form.unit_price,'125.25');
  f.workflow.edit('product','unit_price','9999999999.99');await f.workflow.saveProduct();
  assert.deepEqual(f.calls.find(c=>c[0]==='updateProduct')[3],{unit_price:'9999999999.99'});assert.equal(f.workflow.getSnapshot().products.data.products[0].unit_price,'9999999999.99');f.workflow.dispose();
});
test('unchanged edit skips write; failed update retains form and never confirms success',async()=>{
  const f=await setup();await f.workflow.openProduct(31);await f.workflow.saveProduct();assert.ok(!f.calls.some(c=>c[0]==='updateProduct'));
  await f.workflow.openProduct(31);f.workflow.edit('product','name','Changed');f.api.updateProduct=async()=>{throw {response:{status:409}};};await f.workflow.saveProduct();assert.ok(f.workflow.getSnapshot().error.includes('conflict'));assert.equal(f.workflow.getSnapshot().editor.form.name,'Changed');assert.equal(f.workflow.getSnapshot().message,'');f.workflow.dispose();
});
test('availability, publication, unpublication and explicit archive use confirmed PATCH responses',async()=>{
  const f=await setup();const row=()=>f.workflow.getSnapshot().products.data.products[0];
  for(const payload of [{availability_status:'unavailable'},{publication_status:'published'},{publication_status:'draft'}]){await f.workflow.changeProduct(row(),payload);for(const [key,value] of Object.entries(payload))assert.equal(row()[key],value);}
  await f.workflow.archive();assert.equal(row().publication_status,'draft');f.workflow.confirmArchive(row());await f.workflow.archive();assert.equal(row().publication_status,'archived');
  await f.workflow.openProduct(31);assert.equal(f.workflow.getSnapshot().editor,null);assert.ok(f.workflow.getSnapshot().error.includes('Archived'));f.workflow.dispose();
});
test('category creation, duplicate conflict, editing and deactivation preserve backend state',async()=>{
  const f=await setup();f.workflow.openCategory();f.workflow.edit('category','name','Groceries');await f.workflow.saveCategory();assert.ok(f.workflow.getSnapshot().error.includes('unique'));assert.ok(f.workflow.getSnapshot().categoryEditor);
  f.workflow.edit('category','name','Drinks');await f.workflow.saveCategory();assert.equal(f.workflow.getSnapshot().categories.data.total,2);
  const row=f.workflow.getSnapshot().categories.data.categories[0];f.workflow.openCategory(row);f.workflow.edit('category','description','Updated');await f.workflow.saveCategory();
  await f.workflow.changeCategory(f.workflow.getSnapshot().categories.data.categories[0]);assert.equal(f.workflow.getSnapshot().categories.data.categories[0].is_active,false);f.workflow.dispose();
});
test('category pages retain selected options without assuming first page contains all choices',async()=>{
  const f=await setup();f.setCategories(Array.from({length:11},(_,i)=>categoryFixture({category_id:11+i,name:'Category '+i})));
  await f.workflow.refresh();await f.workflow.openProduct();f.workflow.edit('product','category_id','11');await f.workflow.categoryPage(2);assert.ok(f.workflow.getSnapshot().knownCategories.some(c=>c.category_id===11));assert.equal(f.workflow.getSnapshot().categories.data.categories[0].category_id,21);f.workflow.dispose();
});
test('server pagination and filters reset pages and never compute summaries from list length',async()=>{
  const f=await setup();f.setProducts(Array.from({length:23},(_,i)=>productFixture({product_id:31+i})));await f.workflow.refresh();assert.equal(f.workflow.getSnapshot().summary.data.total_products_count,23);
  await f.workflow.page(3);assert.equal(f.workflow.getSnapshot().products.data.products.length,3);await f.workflow.filter({q:'Missing'});assert.equal(f.workflow.getSnapshot().page,1);assert.equal(f.workflow.getSnapshot().products.data.total,0);assert.equal(f.workflow.getSnapshot().summary.data.total_products_count,23);f.workflow.dispose();
});
test('superseded filter responses cannot overwrite newer results',async()=>{
  const f=await setup(),old=deferred(),recent=deferred();f.api.listProducts=async(b,{filters})=>filters.q==='old'?old.promise:recent.promise;
  const a=f.workflow.filter({q:'old'}),b=f.workflow.filter({q:'new'});recent.resolve({page:1,page_size:10,total:0,products:[]});await b;old.resolve({page:1,page_size:10,total:1,products:[productFixture()]});await a;assert.equal(f.workflow.getSnapshot().products.data.total,0);f.workflow.dispose();
});
test('business changes clear forms/cache and late prior-business reads',async()=>{
  const f=await setup(),pending=deferred();f.api.getProduct=()=>pending.promise;const opened=f.workflow.openProduct(31);await f.workflow.selectBusiness(2);pending.resolve(productFixture());await opened;
  assert.equal(f.workflow.getSnapshot().businessId,2);assert.equal(f.workflow.getSnapshot().editor,null);assert.equal(f.workflow.getSnapshot().knownCategories.length,0);assert.equal(f.workflow.getSnapshot().products.data.total,0);await f.workflow.selectBusiness(3);assert.equal(f.workflow.getSnapshot().products.data,null);f.workflow.dispose();
});
test('authentication loss conceals all previously loaded data',async()=>{
  const f=await setup();f.api.listProducts=async()=>{throw {response:{status:401}};};await f.workflow.refresh();const s=f.workflow.getSnapshot();assert.ok(s.authError.includes('expired'));assert.equal(s.products.data,null);assert.equal(s.categories.data,null);assert.equal(s.summary.data,null);f.workflow.dispose();
});
test('ambiguous creation persists a non-sensitive flag across remount and blocks replay until review',async()=>{
  const f=await setup();f.api.createProduct=async()=>{throw Error('network');};await f.workflow.openProduct();for(const [key,value] of Object.entries(productForm))f.workflow.edit('product',key,value);await f.workflow.saveProduct();assert.ok(f.store.read(1));assert.ok(f.workflow.getSnapshot().uncertain);f.workflow.dispose();
  const next=createCatalogueWorkflow(f.api,7,f.store);await next.start();assert.ok(next.getSnapshot().uncertain);await next.refresh();next.acknowledge();assert.equal(next.getSnapshot().uncertain,false);assert.equal(f.store.read(1),false);next.dispose();
});
test('invalid write confirmation never publishes success and storage failure prevents POST',async()=>{
  const f=await setup();await f.workflow.openProduct();for(const [key,value] of Object.entries(productForm))f.workflow.edit('product',key,value);f.api.createProduct=async()=>productFixture({business_id:2});await f.workflow.saveProduct();assert.ok(f.workflow.getSnapshot().uncertain);assert.equal(f.workflow.getSnapshot().message,'');f.workflow.dispose();
  const g=catalogueFixture();g.store.mark=()=>{throw Error('storage');};const w=createCatalogueWorkflow(g.api,7,g.store);await w.start();w.openCategory();w.edit('category','name','New');await w.saveCategory();assert.ok(!g.calls.some(c=>c[0]==='createCategory'));assert.ok(w.getSnapshot().storageError);w.dispose();
});
test('dispose and session replacement suppress slow writes and clear prior state',async()=>{
  const f=await setup(),pending=deferred();f.api.updateProduct=()=>pending.promise;const save=f.workflow.changeProduct(f.workflow.getSnapshot().products.data.products[0],{publication_status:'published'});f.workflow.dispose();pending.resolve(productFixture({publication_status:'published'}));await save;assert.equal(f.workflow.getSnapshot().products.data,null);assert.equal(f.workflow.getSnapshot().message,'');
});
test('intent storage keys contain only identity/business and unresolved flag',()=>{
  const data=new Map();globalThis.sessionStorage={getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v),removeItem:k=>data.delete(k)};
  try{const a=catalogueIntentStore(7),b=catalogueIntentStore(8);a.mark(1);assert.equal(a.read(1),true);assert.equal(b.read(1),false);assert.deepEqual([...data.values()],['unconfirmed']);a.clear(1);assert.equal(a.read(1),false);}finally{delete globalThis.sessionStorage;}
});
