import test from 'node:test';
import assert from 'node:assert/strict';
import {createCustomerCatalogueWorkflow,parsePublicShop,parsePublicProduct,parsePublicCategory,parsePublicPage,catalogueBrowseError} from '../src/utils/customerCatalogue.js';
import {catalogueMoney} from '../src/utils/catalogueMoney.js';
import {customerCatalogueFixture,publicShop,publicProduct,publicCategory} from './fixtures/customerCatalogueFixtures.js';
const defer=()=>{let resolve;const promise=new Promise(a=>{resolve=a;});return {promise,resolve};};
async function setup(options={}){const f=customerCatalogueFixture();f.workflow=createCustomerCatalogueWorkflow(f.api,options);await f.workflow.start();return f;}
test('public projections exclude private metadata and reject owner draft/archive DTOs',()=>{
  assert.deepEqual(parsePublicShop({...publicShop(),owner_email:'PRIVATE'}),publicShop());
  assert.deepEqual(parsePublicProduct({...publicProduct(),credit_balance:'PRIVATE'},1),publicProduct());
  for(const publication_status of ['draft','archived','published'])assert.throws(()=>parsePublicProduct(publicProduct({publication_status}),1));
  assert.throws(()=>parsePublicProduct(publicProduct({business_id:2}),1));assert.throws(()=>parsePublicProduct(publicProduct({unit_price:125.25}),1));
  assert.throws(()=>parsePublicCategory(publicCategory({is_active:false}),1));assert.throws(()=>parsePublicCategory(publicCategory({business_id:2}),1));
});
test('bounded page parsers reject duplicates, zero-catalogue discoveries and filter mismatch',()=>{
  assert.throws(()=>parsePublicPage({page:1,page_size:10,total:2,shops:[publicShop(),publicShop()]},'shops',1));
  assert.throws(()=>parsePublicPage({page:1,page_size:10,total:1,shops:[publicShop({product_count:0})]},'shops',1));
  assert.throws(()=>parsePublicPage({page:1,page_size:10,total:1,products:[publicProduct()]},'products',1,1,{availability_status:'unavailable'}));
});
test('explore loads eligible shops, server search resets pagination and no-results is authoritative',async()=>{
  const f=await setup();assert.equal(f.workflow.getSnapshot().shops.data.total,2);await f.workflow.shopsPage(2);assert.equal(f.workflow.getSnapshot().shopsPage,2);
  await f.workflow.searchShops('Missing');assert.equal(f.workflow.getSnapshot().shopsPage,1);assert.equal(f.workflow.getSnapshot().shops.data.total,0);assert.deepEqual(f.calls.at(-1),['shops',1,'Missing']);f.workflow.dispose();
});
test('shop detail loads public metadata, categories and shop-specific products',async()=>{
  const f=await setup({businessId:1});const state=f.workflow.getSnapshot();assert.equal(state.shop.data.business_name,'Local Shop');assert.equal(state.products.data.total,1);assert.equal(state.categories.data.total,1);assert.equal(state.products.data.products[0].business_id,1);f.workflow.dispose();
});
test('product detail loads only authorized shop and actual details with exact LKR display',async()=>{
  const f=await setup({businessId:1,productId:31});assert.equal(f.workflow.getSnapshot().detail.data.name,'Rice');assert.ok(!f.calls.some(c=>c[0]==='products'));
  assert.equal(catalogueMoney('9999999999.99'),'LKR 9,999,999,999.99');f.workflow.dispose();
});
test('search, category and availability filters are server-side and reset product page',async()=>{
  const f=await setup({businessId:1});await f.workflow.page(3);await f.workflow.filter({q:'rice',category_id:'11',availability_status:'unavailable'});
  assert.equal(f.workflow.getSnapshot().page,1);assert.equal(f.workflow.getSnapshot().products.data.total,0);assert.deepEqual(f.calls.at(-1),['products',1,1,{q:'rice',category_id:'11',availability_status:'unavailable'}]);f.workflow.dispose();
});
test('product pagination stays bounded and additional category pages retain choices',async()=>{
  const f=await setup({businessId:1});f.setProducts(Array.from({length:23},(_,i)=>publicProduct({product_id:31+i})));f.setCategories(Array.from({length:11},(_,i)=>publicCategory({category_id:11+i,name:'Category '+i})));
  await f.workflow.refresh();await f.workflow.page(3);assert.equal(f.workflow.getSnapshot().products.data.products.length,3);assert.equal(f.workflow.getSnapshot().products.data.total,23);
  await f.workflow.categoryPage(2);assert.equal(f.workflow.getSnapshot().categories.data.categories.length,1);assert.equal(f.workflow.getSnapshot().knownCategories.length,11);f.workflow.dispose();
});
test('approved empty shop opens without fabricated products',async()=>{
  const f=customerCatalogueFixture();f.setShops([publicShop({product_count:0})]);f.setProducts([]);const w=createCustomerCatalogueWorkflow(f.api,{businessId:1});await w.start();assert.equal(w.getSnapshot().shop.data.product_count,0);assert.equal(w.getSnapshot().products.data.total,0);w.dispose();
});
test('ineligible shop clears all related content and prevents unauthorized follow-up reads',async()=>{
  const f=await setup({businessId:1});f.api.shop=async()=>{throw {response:{status:404}};};await f.workflow.refresh();const state=f.workflow.getSnapshot();assert.equal(state.shop.data,null);assert.equal(state.products.data,null);assert.equal(state.categories.data,null);assert.ok(state.shop.error.includes('no longer'));f.workflow.dispose();
});
test('product not found conceals product but retains still-public shop context',async()=>{
  const f=await setup({businessId:1,productId:999});assert.equal(f.workflow.getSnapshot().detail.data,null);assert.ok(f.workflow.getSnapshot().detail.error.includes('no longer'));assert.ok(f.workflow.getSnapshot().shop.data);f.workflow.dispose();
});
test('unavailable products remain visible as unavailable, never invented inventory',async()=>{
  const f=customerCatalogueFixture();f.setProducts([publicProduct({availability_status:'unavailable'})]);const w=createCustomerCatalogueWorkflow(f.api,{businessId:1});await w.start();assert.equal(w.getSnapshot().products.data.products[0].availability_status,'unavailable');w.dispose();
});
test('newer shop search wins over late previous results',async()=>{
  const f=await setup(),old=defer(),recent=defer();f.api.shops=({q})=>q==='old'?old.promise:recent.promise;
  const a=f.workflow.searchShops('old'),b=f.workflow.searchShops('new');recent.resolve({page:1,page_size:10,total:0,shops:[]});await b;old.resolve({page:1,page_size:10,total:1,shops:[publicShop()]});await a;assert.equal(f.workflow.getSnapshot().shops.data.total,0);f.workflow.dispose();
});
test('newer product filter wins over late previous products',async()=>{
  const f=await setup({businessId:1}),old=defer(),recent=defer();f.api.products=(id,{filters})=>filters.q==='old'?old.promise:recent.promise;
  const a=f.workflow.filter({q:'old'}),b=f.workflow.filter({q:'new'});recent.resolve({page:1,page_size:10,total:0,products:[]});await b;old.resolve({page:1,page_size:10,total:1,products:[publicProduct()]});await a;assert.equal(f.workflow.getSnapshot().products.data.total,0);f.workflow.dispose();
});
for(const status of [401,403])test(`HTTP ${status} clears all session content and late responses`,async()=>{
  const f=await setup({businessId:1});f.api.products=async()=>{throw {response:{status}};};await f.workflow.filter({q:'x'});const s=f.workflow.getSnapshot();assert.ok(s.authError);assert.equal(s.shop.data,null);assert.equal(s.products.data,null);assert.equal(s.categories.data,null);assert.equal(s.knownCategories.length,0);f.workflow.dispose();
});
test('unmount and shop/session replacement discard former requests and category cache',async()=>{
  const f=await setup({businessId:1}),slow=defer();f.api.products=()=>slow.promise;const load=f.workflow.filter({q:'old'});f.workflow.dispose();const next=createCustomerCatalogueWorkflow({...f.api,products:customerCatalogueFixture().api.products},{businessId:2});await next.start();slow.resolve({page:1,page_size:10,total:1,products:[publicProduct()]});await load;
  assert.equal(f.workflow.getSnapshot().products.data,null);assert.equal(next.getSnapshot().products.data.products[0].business_id,2);assert.equal(next.getSnapshot().knownCategories.length,0);next.dispose();
});
test('network errors, malformed products and invalid identifiers fail closed',async()=>{
  const f=await setup({businessId:1});f.api.products=async()=>{throw Error('private backend diagnostic');};await f.workflow.filter({q:'x'});assert.ok(f.workflow.getSnapshot().products.error.includes('unavailable'));assert.ok(!f.workflow.getSnapshot().products.error.includes('diagnostic'));f.workflow.dispose();
  const g=customerCatalogueFixture();g.api.product=async()=>publicProduct({publication_status:'draft'});const w=createCustomerCatalogueWorkflow(g.api,{businessId:1,productId:31});await w.start();assert.equal(w.getSnapshot().detail.data,null);assert.ok(w.getSnapshot().detail.error.includes('verified'));w.dispose();
  const invalid=createCustomerCatalogueWorkflow(g.api,{businessId:-1});await invalid.start();assert.ok(invalid.getSnapshot().shop.error.includes('Invalid'));invalid.dispose();assert.ok(!catalogueBrowseError(Error('PRIVATE')).includes('PRIVATE'));
});
test('refresh aborts an older product read before revalidating the shop',async()=>{
  const f=await setup({businessId:1}),slow=defer(),shop=defer();let signal;f.api.products=(id,options)=>{signal=options.signal;return slow.promise;};const old=f.workflow.filter({q:'old'});f.api.shop=()=>shop.promise;const fresh=f.workflow.refresh();assert.equal(signal.aborted,true);slow.resolve({page:1,page_size:10,total:1,products:[publicProduct()]});await old;assert.equal(f.workflow.getSnapshot().products.data,null);f.workflow.dispose();shop.resolve(publicShop());await fresh;
});
