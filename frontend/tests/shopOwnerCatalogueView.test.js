import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter,Route,Routes} from 'react-router-dom';
import {createServer} from 'vite';
import {readFile} from 'node:fs/promises';
import {createCatalogueWorkflow} from '../src/utils/shopOwnerCatalogue.js';
import {catalogueFixture,productFixture} from './fixtures/catalogueFixtures.js';

test('Shop & Products real views, existing routes and Axios catalogue contract',async t=>{
  const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
  try{
    const {ShopOwnerProductsView:View,default:Page}=await server.ssrLoadModule('/src/pages/shopOwner/ShopOwnerProducts.jsx');
    const f=catalogueFixture(),workflow=createCatalogueWorkflow(f.api,7,f.store);await workflow.start();
    const ready=()=>structuredClone(workflow.getSnapshot());
    const render=(state=ready())=>renderToStaticMarkup(h(MemoryRouter,null,h(View,{state,actions:workflow})));
    await t.test('catalogue title, backend counts, category labels and actual actions render',()=>{
      const html=render();for(const text of ['Shop &amp; Products','Total Products','Available Products','Unpublished Products','Groceries','Rice','LKR 125.25','Edit Product','Publish Product','Mark Unavailable','Manage Categories','Page 1'])assert.ok(html.includes(text),text);
      assert.ok(!html.includes('name="stock_quantity"'));assert.ok(!html.includes('type="file"'));
    });
    await t.test('summary unknown is distinct from zero; list loading, errors and empty states are truthful',()=>{
      const state=ready();state.summary.data=null;state.summary.error='failure';state.products={data:null,loading:true,error:''};let html=render(state);assert.ok(html.includes('Loading products'));assert.ok(html.includes('Catalogue summary unavailable'));assert.ok(html.includes('—'));
      state.products={data:{total:0,products:[]},loading:false,error:''};assert.ok(render(state).includes('No products match'));
      state.products={data:null,loading:false,error:'Network unavailable'};assert.ok(render(state).includes('Network unavailable'));
    });
    await t.test('add/edit forms use decimal text, real fields, current data and paginated category choices',async()=>{
      await workflow.openProduct();let html=render();for(const value of ['Add Product','id="product-name"','id="product-price"','inputMode="decimal"','id="product-category"','Draft / unpublished','Product category choices'])assert.ok(html.includes(value),value);
      await workflow.openProduct(31);html=render();assert.ok(html.includes('Edit Product'));assert.ok(html.includes('value="125.25"'));assert.ok(!html.includes('name="business_id"'));
      workflow.closeProduct();
    });
    await t.test('category forms support add/edit/active status without delete and archive requires confirmation',()=>{
      workflow.openCategory();let html=render();for(const value of ['Add Category','category-active','Create Category','Deactivation hides'])assert.ok(html.includes(value),value);workflow.closeCategory();
      workflow.confirmArchive(productFixture());html=render();assert.ok(html.includes('Confirm product archive'));assert.ok(html.includes('Confirm Archive'));assert.ok(html.includes('Keep Product'));workflow.confirmArchive(null);
      const state=ready();state.products.data.products=[productFixture({publication_status:'archived'})];html=render(state);assert.ok(html.includes('Archived record'));assert.ok(!html.includes('>Edit Product<'));
    });
    await t.test('category save errors appear beside the category submit control',async()=>{
      workflow.openCategory();workflow.edit('category','name','<invalid>');await workflow.saveCategory();
      const html=render(),form=html.slice(html.indexOf('id="category-editor-heading"'));
      assert.ok(form.includes('role="alert"'));assert.ok(form.includes('HTML and control characters are unsupported'));
      assert.ok(form.indexOf('role="alert"')<form.indexOf('Create Category'));
      workflow.closeCategory();
    });
    await t.test('product save errors appear beside the product submit control',async()=>{
      await workflow.openProduct();workflow.edit('product','name','Demo rice');workflow.edit('product','unit_price','invalid');
      await workflow.saveProduct();const html=render(),form=html.slice(html.indexOf('id="product-editor-heading"'));
      assert.ok(form.includes('role="alert"'));assert.ok(form.includes('Enter an LKR price'));
      assert.ok(form.indexOf('role="alert"')<form.indexOf('Create Product'));
      workflow.closeProduct();
    });
    await t.test('busy, uncertain, pending, no-business and authorization states disable or conceal controls',()=>{
      const state=ready();state.busy=true;assert.ok(render(state).includes('disabled'));state.busy=false;state.uncertain=true;assert.ok(render(state).includes('A creation attempt is unconfirmed'));
      state.businessId=3;let html=render(state);assert.ok(html.includes('Business approval is required'));assert.ok(!html.includes('Product Catalogue'));
      state.businessId=null;state.businesses=[];assert.ok(render(state).includes('No business is linked'));
      state.authError='Your session expired';html=render(state);assert.ok(html.includes('session expired'));assert.ok(!html.includes('Rice'));
    });
    await t.test('text is escaped and responsive classes retain existing colors',()=>{
      const state=ready();state.products.data.products=[productFixture({name:'<script>PRIVATE</script>'})];const html=render(state);assert.ok(html.includes('&lt;script&gt;'));assert.ok(!html.includes('<script>'));for(const value of ['min-w-0','flex-wrap','#10243E','#12B8A6','#F5B544','#DC4545'])assert.ok(html.includes(value),value);
    });
    await t.test('existing Shop Owner guard, one real route and sidebar retain other modules',async()=>{
      const {AuthContext}=await server.ssrLoadModule('/src/context/AuthContext.jsx'),{default:Guard}=await server.ssrLoadModule('/src/routes/ProtectedRoute.jsx');
      const auth={isAuthenticated:true,loading:false,token:'fixture',user:{user_id:7,platform_role:'shop_owner',account_status:'active'}};
      const route=value=>renderToStaticMarkup(h(MemoryRouter,{initialEntries:['/shop-owner/products']},h(AuthContext.Provider,{value},h(Routes,null,h(Route,{element:h(Guard,{allowedRoles:['shop_owner']})},h(Route,{path:'/shop-owner/products',element:h(Page)}))))));
      assert.ok(route(auth).includes('Shop &amp; Products'));for(const role of ['customer','driver','admin'])assert.ok(!route({...auth,user:{...auth.user,platform_role:role}}).includes('Shop &amp; Products'));assert.ok(!route({...auth,isAuthenticated:false}).includes('Shop &amp; Products'));
      const {default:Sidebar}=await server.ssrLoadModule('/src/components/shopOwner/ShopOwnerSidebar.jsx');const sidebar=renderToStaticMarkup(h(MemoryRouter,null,h(Sidebar)));for(const path of ['products','deliveries','notifications','repayments','credit-sales','customers','dashboard'])assert.ok(sidebar.includes('href="/shop-owner/'+path+'"'),path);
      const app=await readFile(new URL('../src/App.jsx',import.meta.url),'utf8');assert.equal(app.split('path="products" element={<ShopOwnerProducts />}').length-1,1);for(const value of ['<DriverDashboard />','<CustomerDashboard />','<RegisterPage />','<LoginPage />'])assert.ok(app.includes(value));
    });
    await t.test('shared Axios uses real GET/POST/PATCH, scoped query, exact decimal strings and abort signal',async()=>{
      const {default:api}=await server.ssrLoadModule('/src/services/api.js'),service=await server.ssrLoadModule('/src/services/shopOwnerCatalogueService.js');const old=api.defaults.adapter,storage=globalThis.sessionStorage,calls=[];globalThis.sessionStorage={getItem:()=> 'fixture'};
      api.defaults.adapter=async config=>{calls.push(config);return {data:{},status:200,statusText:'OK',headers:{},config};};
      try{const signal=new AbortController().signal;await service.getCatalogueBusinesses({signal});await service.getCatalogueSummary(1,{signal});await service.listProducts(1,{page:2,filters:{q:'Rice',category_id:'11',availability_status:'',publication_status:'draft'},signal});await service.getProduct(1,31,{signal});await service.createProduct(1,{name:'Rice',unit_price:'9999999999.99'},{signal});await service.updateProduct(1,31,{publication_status:'published'},{signal});await service.listCategories(1,{page:2,signal});await service.createCategory(1,{name:'New'},{signal});await service.updateCategory(1,11,{is_active:false},{signal});
        assert.deepEqual(calls.map(c=>c.method),['get','get','get','get','post','patch','get','post','patch']);assert.deepEqual(calls[2].params,{business_id:1,page:2,page_size:10,q:'Rice',category_id:'11',publication_status:'draft'});assert.equal(JSON.parse(calls[4].data).unit_price,'9999999999.99');assert.equal(calls[1].url,'/shop-owner/catalogue/summary');for(const call of calls){assert.equal(call.signal,signal);assert.equal(call.headers.Authorization,'Bearer fixture');}
      }finally{api.defaults.adapter=old;if(storage===undefined)delete globalThis.sessionStorage;else globalThis.sessionStorage=storage;}
    });
    workflow.dispose();
  }finally{await server.close();}
});
