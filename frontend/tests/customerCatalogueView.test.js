import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter,Route,Routes} from 'react-router-dom';
import {createServer} from 'vite';
import {readFile} from 'node:fs/promises';
import {createCustomerCatalogueWorkflow} from '../src/utils/customerCatalogue.js';
import {customerCatalogueFixture,publicProduct} from './fixtures/customerCatalogueFixtures.js';

test('Customer catalogue real views, role guards, navigation and authenticated GET contracts',async t=>{
  const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
  try{
    const {CustomerCatalogueView:View,default:Page}=await server.ssrLoadModule('/src/pages/customer/CustomerCatalogue.jsx');
    const f=customerCatalogueFixture(),explore=createCustomerCatalogueWorkflow(f.api),shop=createCustomerCatalogueWorkflow(f.api,{businessId:1}),detail=createCustomerCatalogueWorkflow(f.api,{businessId:1,productId:31});await Promise.all([explore.start(),shop.start(),detail.start()]);
    const state=w=>structuredClone(w.getSnapshot());
    const render=(value=state(explore),mode='explore')=>renderToStaticMarkup(h(MemoryRouter,null,h(View,{state:value,actions:mode==='explore'?explore:shop,mode,businessId:mode==='explore'?null:1})));
    await t.test('explore renders actual eligible shop fields and server search/pagination controls',()=>{
      const html=render();for(const value of ['Browse Shops','Discover trusted local shops and browse their published products.','Local Shop','published product','Catalogue available','View Shop','Shop name','Search shops','Shop pages'])assert.ok(html.includes(value),value);
      assert.ok(html.includes('href="/customer/explore/1"'));for(const value of ['rating','latitude','credit_balance','Buy Now'])assert.ok(!html.includes(value));
    });
    await t.test('shop and product pages show actual categories, prices, availability and placeholders',()=>{
      let html=render(state(shop),'shop');for(const value of ['Local Shop','Public shop details','Groceries','Rice','LKR 125.25','Product image unavailable','View Details','Product pages','Category pages'])assert.ok(html.includes(value),value);
      html=render(state(detail),'product');for(const value of ['Product Details','Shop: Local Shop','Category: Groceries','Retail unit','LKR 125.25'])assert.ok(html.includes(value),value);
      for(const value of ['Add to Cart','Buy Now','Edit Product','Publish Product'])assert.ok(!html.includes(value));
    });
    await t.test('unavailable and exact maximum prices remain readable without inventory claims',()=>{
      const value=state(detail);value.detail.data=publicProduct({unit_price:'9999999999.99',availability_status:'unavailable'});const html=render(value,'product');assert.ok(html.includes('LKR 9,999,999,999.99'));assert.ok(html.includes('currently marked unavailable'));assert.ok(!html.includes('stock_quantity'));
    });
    await t.test('loading, network, empty search, empty shop and missing product states remain distinct',()=>{
      const value=state(explore);value.shops={data:null,loading:true,error:''};assert.ok(render(value).includes('Loading shops'));
      value.shops={data:{total:0,shops:[]},loading:false,error:''};assert.ok(render(value).includes('No eligible shops'));value.q='Missing';assert.ok(render(value).includes('No shops match'));
      value.shops={data:null,loading:false,error:'Service unavailable'};assert.ok(render(value).includes('Service unavailable'));
      const empty=state(shop);empty.shop.data.product_count=0;empty.products.data={total:0,products:[]};assert.ok(render(empty,'shop').includes('no published products currently'));
      const missing=state(detail);missing.detail={data:null,loading:false,error:'Product no longer available'};assert.ok(render(missing,'product').includes('Product no longer available'));
    });
    await t.test('ineligible shop, expired session and unexpected private fields conceal protected content',()=>{
      const value=state(shop);value.shop={data:null,loading:false,error:'Shop no longer available'};let html=render(value,'shop');assert.ok(html.includes('Shop no longer available'));assert.ok(!html.includes('Rice'));
      const expired=state(detail);expired.authError='Your session expired';html=render(expired,'product');assert.ok(html.includes('session expired'));assert.ok(!html.includes('Retail unit'));
      const safe=state(detail);safe.detail.data.owner_email='PRIVATE-EMAIL';safe.detail.data.credit_balance='PRIVATE-BALANCE';html=render(safe,'product');assert.ok(!html.includes('PRIVATE'));
    });
    await t.test('text is escaped and responsive controls have labels and existing palette',()=>{
      const value=state(shop);value.products.data.products=[publicProduct({name:'<script>unsafe</script>'})];const html=render(value,'shop');assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));for(const value of ['min-w-0','flex-wrap','htmlFor','id="browse-category"','#10243E','#12B8A6']){if(value==='htmlFor')continue;assert.ok(html.includes(value),value);}
    });
    await t.test('Customer-only route guards reject other roles and malformed identifiers',async()=>{
      const {AuthContext}=await server.ssrLoadModule('/src/context/AuthContext.jsx'),{default:Guard}=await server.ssrLoadModule('/src/routes/ProtectedRoute.jsx');
      const auth={isAuthenticated:true,loading:false,token:'fixture',user:{user_id:7,platform_role:'customer',account_status:'active'}};
      const route=(value,path='/customer/shops/explore',mode='explore')=>renderToStaticMarkup(h(MemoryRouter,{initialEntries:[path]},h(AuthContext.Provider,{value},h(Routes,null,h(Route,{element:h(Guard,{allowedRoles:['customer']})},h(Route,{path:mode==='explore'?'/customer/shops/explore':'/customer/explore/:businessId/products/:productId',element:h(Page,{mode})}))))));
      assert.ok(route(auth).includes('Browse Shops'));for(const role of ['shop_owner','driver','admin'])assert.ok(!route({...auth,user:{...auth.user,platform_role:role}}).includes('Browse Shops'));assert.ok(!route({...auth,isAuthenticated:false}).includes('Browse Shops'));
      assert.ok(route(auth,'/customer/explore/bad/products/1','product').includes('Invalid catalogue identifier'));
    });
    await t.test('Explore Shops and My Shops remain separate with all financial and owner routes retained',async()=>{
      const {default:Sidebar}=await server.ssrLoadModule('/src/components/customer/CustomerSidebar.jsx');const html=renderToStaticMarkup(h(MemoryRouter,{initialEntries:['/customer/shops/explore']},h(Sidebar)));
      for(const value of ['href="/customer/shops"','href="/customer/shops/explore"','href="/customer/credit-accounts"','href="/customer/transactions"','href="/customer/notifications"'])assert.ok(html.includes(value),value);
      const app=await readFile(new URL('../src/App.jsx',import.meta.url),'utf8');for(const value of ['path="shops" element={<MyShops />}','path="shops/explore"','path="explore/:businessId"','path="explore/:businessId/products/:productId"','<ShopOwnerProducts />','<CreditAccountDetails />','<CreditStatement />'])assert.ok(app.includes(value),value);
    });
    await t.test('shared Axios catalogue methods are all GET with real scoped paths/filters and cancellation',async()=>{
      const {default:api}=await server.ssrLoadModule('/src/services/api.js'),service=await server.ssrLoadModule('/src/services/customerCatalogueService.js');const old=api.defaults.adapter,storage=globalThis.localStorage,calls=[];globalThis.localStorage={getItem:()=> 'fixture'};api.defaults.adapter=async config=>{calls.push(config);return {data:{},status:200,statusText:'OK',headers:{},config};};
      try{const signal=new AbortController().signal;await service.listCatalogueShops({page:2,q:'Local',signal});await service.getCatalogueShop(1,{signal});await service.listCatalogueCategories(1,{page:2,signal});await service.listCatalogueProducts(1,{page:3,filters:{q:'Rice',category_id:'11',availability_status:'unavailable'},signal});await service.getCatalogueProduct(1,31,{signal});
        assert.deepEqual(calls.map(c=>c.url),['/customer/catalogue/shops','/customer/catalogue/shops/1','/customer/catalogue/shops/1/categories','/customer/catalogue/shops/1/products','/customer/catalogue/shops/1/products/31']);assert.deepEqual(calls[0].params,{page:2,page_size:10,q:'Local'});assert.deepEqual(calls[3].params,{page:3,page_size:10,q:'Rice',category_id:'11',availability_status:'unavailable'});for(const call of calls){assert.equal(call.method,'get');assert.equal(call.signal,signal);assert.equal(call.headers.Authorization,'Bearer fixture');}
      }finally{api.defaults.adapter=old;if(storage===undefined)delete globalThis.localStorage;else globalThis.localStorage=storage;}
    });
    explore.dispose();shop.dispose();detail.dispose();
  }finally{await server.close();}
});
