import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter,Route,Routes} from 'react-router-dom';
import {createServer} from 'vite';
import {readFile} from 'node:fs/promises';
import {businessFixture,deliveryFixture,deliveryDetail,summaryFixture} from './fixtures/shopOwnerDeliveryFixtures.js';
const section=data=>({data,loading:false,error:''});
const ready=()=>({businesses:businessFixture().businesses,businessId:1,contextLoading:false,contextError:'',authError:'',page:1,status:'',
 list:section({total:1,deliveries:[deliveryFixture()]}),summary:section(summaryFixture()),detail:{...section(null),id:null},
 form:{pickup_area:'',delivery_area:''},busy:false,confirmCancel:false,uncertain:false,reviewed:false,storageError:'',message:'',error:''});
const actions={start(){},refresh(){},selectBusiness(){},create(){},cancel(){},edit(){},details(){},closeDetails(){},filter(){},page(){},confirmCancel(){},reviewUncertain(){},acknowledge(){}};
test('Shop Owner delivery page, guards, navigation and real Axios contracts',async t=>{
 const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
 try{
 const {ShopOwnerDeliveriesView:View,default:Page}=await server.ssrLoadModule('/src/pages/shopOwner/ShopOwnerDeliveries.jsx');
 const render=(state=ready())=>renderToStaticMarkup(h(MemoryRouter,null,h(View,{state,actions})));
 await t.test('real scoped requests, authoritative summary, form and supported filters render',()=>{
  const html=render();for(const value of ['Delivery Management','Create delivery requests and track your shop','Total Requests','Available Requests','In Progress','Completed','New Delivery Request','DR-shop-31','Pickup area','Destination area','View Details','Filter by status','name="pickup_area"','name="delivery_area"','Page 1'])assert.ok(html.includes(value),value);
  for(const value of ['name="business_id"','name="weight"','name="order_id"','name="required_vehicle_type"','LKR'])assert.ok(!html.includes(value),value);
 });
 await t.test('loading, empty, summary unavailable and errors do not fabricate rows/counts',()=>{
  const state=ready();state.list={data:null,loading:true,error:''};state.summary={data:null,loading:true,error:''};let html=render(state);assert.ok(html.includes('Loading delivery requests'));assert.ok(!html.includes('No delivery requests'));assert.ok(html.includes('—'));
  state.list=section({total:0,deliveries:[]});assert.ok(render(state).includes('No delivery requests match this filter'));
  state.list={data:null,loading:false,error:'Network unavailable'};state.summary={data:null,loading:false,error:'offline'};html=render(state);assert.ok(html.includes('Network unavailable'));assert.ok(html.includes('Summary unavailable'));
 });
 await t.test('pending, missing business and expired session protect operations and private content',()=>{
  const state=ready();state.businessId=3;let html=render(state);assert.ok(html.includes('Business approval is required'));assert.ok(!html.includes('New Delivery Request'));
  state.businesses=[];state.businessId=null;assert.ok(render(state).includes('No business is linked'));
  state.authError='Your session has expired.';html=render(state);assert.ok(html.includes('expired'));assert.ok(!html.includes('DR-shop-31'));
 });
 await t.test('details show recorded Driver and progress without private metadata',()=>{
  const state=ready();state.detail={id:31,...section(deliveryDetail({status:'assigned',can_cancel:false,assigned_driver:{full_name:'Driver A',assigned_at:deliveryFixture().created_at,email:'SECRET-EMAIL'},events:[{status:'assigned',occurred_at:deliveryFixture().created_at}],credit_limit:'SECRET-LEDGER'}))};
  const html=render(state);for(const value of ['Delivery Request Details','Driver A','Recorded delivery progress','2026-11-06 10:00:00 UTC'])assert.ok(html.includes(value),value);assert.ok(!html.includes('SECRET'));assert.ok(!html.includes('>Cancel Request<'));
 });
 await t.test('tracking separates recorded, current, future and missing stages',()=>{
  const state=ready();state.detail={id:31,...section(deliveryDetail({status:'picked_up',can_cancel:false,events:[{status:'picked_up',occurred_at:deliveryFixture().created_at}]}))};
  const html=render(state);assert.ok(html.includes('aria-current="step"'));assert.ok(html.includes('Current \u00b7 recorded'));assert.ok(html.includes('Upcoming'));assert.ok(html.includes('History unavailable'));
  state.detail.data.status='cancelled';state.detail.data.events=[{status:'cancelled',occurred_at:deliveryFixture().created_at}];
  assert.ok(render(state).includes('Not recorded \u00b7 cancelled'));
 });
 await t.test('available cancellation requires explicit confirmation and saving disables controls',()=>{
  const state=ready();state.detail={id:31,...section(deliveryDetail())};assert.ok(render(state).includes('>Cancel Request<'));assert.ok(!render(state).includes('Confirm Cancellation'));
  state.confirmCancel=true;const html=render(state);assert.ok(html.includes('Cancel this unassigned delivery request?'));assert.ok(html.includes('Confirm Cancellation'));assert.ok(html.includes('Keep Request'));
  state.busy=true;assert.ok(render(state).includes('disabled'));assert.ok(render(state).includes('Saving delivery...'));
 });
 await t.test('unconfirmed creation blocks resubmission until review and explicit acknowledgement',()=>{
  const state=ready();state.uncertain=true;const html=render(state);assert.ok(html.includes('Do not submit it again'));assert.ok(html.includes('Refresh requests for review'));assert.ok(html.includes('I reviewed requests; start a new request'));assert.ok(html.includes('disabled'));
 });
 await t.test('Shop Owner-only actual route and ready sidebar preserve existing modules',async()=>{
  const {AuthContext}=await server.ssrLoadModule('/src/context/AuthContext.jsx'),{default:Guard}=await server.ssrLoadModule('/src/routes/ProtectedRoute.jsx');
  const auth={isAuthenticated:true,loading:false,token:'fixture',user:{user_id:7,platform_role:'shop_owner',account_status:'active'}};
  const route=value=>renderToStaticMarkup(h(MemoryRouter,{initialEntries:['/shop-owner/deliveries']},h(AuthContext.Provider,{value},h(Routes,null,h(Route,{element:h(Guard,{allowedRoles:['shop_owner']})},h(Route,{path:'/shop-owner/deliveries',element:h(Page)}))))));
  assert.ok(route(auth).includes('Delivery Management'));for(const role of ['customer','driver','admin'])assert.ok(!route({...auth,user:{...auth.user,platform_role:role}}).includes('Delivery Management'));assert.ok(!route({...auth,isAuthenticated:false}).includes('Delivery Management'));
  const {default:Sidebar}=await server.ssrLoadModule('/src/components/shopOwner/ShopOwnerSidebar.jsx');const html=renderToStaticMarkup(h(MemoryRouter,null,h(Sidebar)));for(const path of ['dashboard','customers','credit-sales','repayments','notifications','deliveries'])assert.ok(html.includes('href="/shop-owner/'+path+'"'),path);
  const app=await readFile(new URL('../src/App.jsx',import.meta.url),'utf8');assert.ok(app.includes('path="deliveries" element={<ShopOwnerDeliveries />}'));for(const value of ['<DriverDashboard />','<CustomerDashboard />','<ShopOwnerCreditSales />','<RegisterPage />','<LoginPage />'])assert.ok(app.includes(value));
 });
 await t.test('shared JWT Axios uses query-selected business, bounded pages, actual methods and cancellation',async()=>{
  const {default:api}=await server.ssrLoadModule('/src/services/api.js'),service=await server.ssrLoadModule('/src/services/shopOwnerDeliveryService.js');const old=api.defaults.adapter,storage=globalThis.localStorage,calls=[];globalThis.localStorage={getItem:()=> 'fixture'};api.defaults.adapter=async config=>{calls.push(config);return {data:{},status:200,statusText:'OK',headers:{},config};};
  try{const signal=new AbortController().signal;await service.getDeliveryBusinesses({signal});await service.listShopDeliveries(1,{page:2,status:'assigned',signal});await service.getShopDeliverySummary(1,{signal});await service.getShopDelivery(1,31,{signal});await service.createShopDelivery(1,{pickup_area:'Pickup',delivery_area:'Destination'},{signal});await service.cancelShopDelivery(1,31,{signal});
   assert.deepEqual(calls.map(c=>c.url),['/shop-owner/business-context','/shop-owner/deliveries','/shop-owner/deliveries/summary','/shop-owner/deliveries/31','/shop-owner/deliveries','/shop-owner/deliveries/31/cancel']);assert.deepEqual(calls[1].params,{business_id:1,page:2,page_size:10,status:'assigned'});assert.equal(calls[5].data,'{}');assert.equal(calls[4].data,'{"pickup_area":"Pickup","delivery_area":"Destination"}');for(const call of calls){assert.equal(call.signal,signal);assert.equal(call.headers.Authorization,'Bearer fixture');}
  }finally{api.defaults.adapter=old;if(storage===undefined)delete globalThis.localStorage;else globalThis.localStorage=storage;}
 });
 }finally{await server.close();}
});
