import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter,Routes,Route} from 'react-router-dom';
import {createServer} from 'vite';
import {parseDriverResponse} from '../src/utils/driverDashboard.js';
import {driverFixtures} from './fixtures/driverDashboardFixtures.js';
const actions={start(){},load(){}};
const ready=()=>({authError:'',...Object.fromEntries(Object.entries(driverFixtures()).map(([key,data])=>[key,{data:parseDriverResponse(key,data,7),loading:false,error:''}]))});
test('Driver Dashboard JSX, protected routes, layout, navigation and verified Axios contracts',async t=>{
 const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
 try{
 const {DriverDashboardView,default:Dashboard}=await server.ssrLoadModule('/src/pages/driver/DriverDashboard.jsx');
 const {default:Layout}=await server.ssrLoadModule('/src/layouts/DriverLayout.jsx');const {default:Sidebar}=await server.ssrLoadModule('/src/components/driver/DriverSidebar.jsx');
 const {AuthContext}=await server.ssrLoadModule('/src/context/AuthContext.jsx');const {default:Guard}=await server.ssrLoadModule('/src/routes/ProtectedRoute.jsx');
 const render=(state=ready())=>renderToStaticMarkup(h(MemoryRouter,null,h(DriverDashboardView,{state,actions,displayName:'Driver A'})));
 await t.test('actual backend profile, vehicle, counts and assigned records render',()=>{
 const html=render();for(const value of ['Driver Dashboard','Manage your deliveries in one place.','Welcome, Driver A!','Available Jobs','Active Deliveries','Completed Deliveries','DR-test-one','Pickup area','Delivery area','In transit','2026-11-06 10:00:00 UTC','Showing 2 of 2'])assert.ok(html.includes(value),value);
 assert.ok(!html.includes('Driver approval:'));assert.ok(!html.includes('TEST-123'));
 assert.ok(!html.includes('LKR'));assert.ok(html.includes('Earnings accounting is not available.'));assert.ok(!html.includes('View Details'));assert.ok(!html.includes('Accept Job'));
 });
 await t.test('real zero, no vehicle and no delivery states remain distinct from unavailability',()=>{
 const state=ready();state.summary.data={driver_user_id:7,available_jobs_count:0,active_deliveries_count:0,completed_deliveries_count:0};state.profile.data={...state.profile.data,approval_status:'not_submitted',eligible_for_jobs:false,eligibility_reason:'profile_required',vehicle:null};state.deliveries.data={total:0,deliveries:[]};
 const html=render(state);for(const value of ['>0</p>','No active deliveries yet.','Submit Driver application'])assert.ok(html.includes(value),value);
 const loading=ready();for(const key of ['profile','summary','deliveries'])loading[key]={data:null,loading:true,error:''};const wait=render(loading);assert.ok(wait.includes('role="status"'));assert.ok(!wait.includes('No active deliveries yet.'));assert.ok(!wait.includes('>0</p>'));
 });
 await t.test('pending, rejected and suspended approvals have accurate restrictions without private notes',()=>{
 for(const status of ['pending','rejected','suspended']){
 const state=ready();state.profile.data={...state.profile.data,approval_status:status,eligible_for_jobs:false,eligibility_reason:'approval_'+status};const html=render(state);assert.ok(!html.includes('Driver approval:'));assert.ok(!html.includes('internal approval notes'));
 }
 });
 await t.test('partial failures preserve successful sections and auth failures hide all driver records',()=>{
 const state=ready();state.summary={data:null,loading:false,error:'Driver information is unavailable.'};const html=render(state);assert.ok(html.includes('Retry delivery summary'));assert.ok(html.includes('DR-test-one'));assert.ok(!html.includes('TEST-123'));
 for(const message of ['Your session has expired. Please sign in again.','Driver access is unavailable.']){state.authError=message;const blocked=render(state);assert.ok(blocked.includes(message));assert.ok(!blocked.includes('DR-test-one'));assert.ok(!blocked.includes('TEST-123'));}
 });
 await t.test('sidebar enables supported Driver routes including truthful account pages',()=>{
 const html=renderToStaticMarkup(h(MemoryRouter,null,h(Sidebar)));for(const path of ['/driver/dashboard','/driver/deliveries','/driver/profile','/driver/notifications'])assert.ok(html.includes('href="'+path+'"'),path);
 assert.ok(html.includes('href="/driver/jobs"'));assert.ok(html.includes('href="/driver/history"'));
 for(const path of ['/driver/settings','/driver/earnings','/driver/vehicle'])assert.ok(html.includes('href="'+path+'"'));
 assert.ok(!html.includes('Planned'));assert.ok(html.includes('<dialog'));assert.ok(html.includes('Driver menu'));assert.ok(html.includes('LankaPex'));
 });
 await t.test('real Driver route renders through layout/guard; other roles and inactive identities are denied',()=>{
 const auth={isAuthenticated:true,loading:false,token:'fixture',user:{user_id:7,full_name:'Driver A',platform_role:'driver',account_status:'active'},logout(){}};
 const route=value=>renderToStaticMarkup(h(MemoryRouter,{initialEntries:['/driver/dashboard']},h(AuthContext.Provider,{value},h(Routes,null,h(Route,{element:h(Guard,{allowedRoles:['driver']})},h(Route,{element:h(Layout)},h(Route,{path:'/driver/dashboard',element:h(Dashboard)})))))));
 assert.ok(route(auth).includes('Manage your deliveries in one place.'));
 for(const role of ['customer','shop_owner','admin'])assert.ok(!route({...auth,user:{...auth.user,platform_role:role}}).includes('Manage your deliveries in one place.'));
 assert.ok(!route({...auth,isAuthenticated:false}).includes('Manage your deliveries in one place.'));
 assert.ok(!route({...auth,user:{...auth.user,account_status:'suspended'}}).includes('Manage your deliveries in one place.'));
 });
 await t.test('first-time profile form explains pending review with accessible required fields',()=>{
 const fixtures=driverFixtures();
 const state={authError:'',...Object.fromEntries(Object.entries(fixtures).map(([key,data])=>[key,{data,loading:false,error:''}]))};
 state.profile.data={...fixtures.profile,approval_status:'not_submitted',eligible_for_jobs:false,eligibility_reason:'profile_required',vehicle:null};
 const html=renderToStaticMarkup(h(MemoryRouter,null,h(DriverDashboardView,{state,actions:{start(){},load(){}},displayName:'Driver'})));
 for(const text of ['Submit for review','pending application','Vehicle type','Registration reference','maxLength="50"','aria-describedby="driver-application-help"'])assert.ok(html.includes(text),text);
 state.profile.data=fixtures.profile;assert.ok(!renderToStaticMarkup(h(MemoryRouter,null,h(DriverDashboardView,{state,actions:{start(){},load(){}}}))).includes('Submit for review'));
 });
 await t.test('Driver service uses shared JWT, GET-only read contracts and bounded preview cancellation',async()=>{
 const {default:api}=await server.ssrLoadModule('/src/services/api.js'),service=await server.ssrLoadModule('/src/services/driverDashboardService.js');const previous=api.defaults.adapter,storage=globalThis.sessionStorage,calls=[];globalThis.sessionStorage={getItem:()=> 'fixture'};
 api.defaults.adapter=async config=>{calls.push(config);return {data:{},status:200,statusText:'OK',headers:{},config};};
 try{const signal=new AbortController().signal;for(const method of ['getDriverProfile','getDriverSummary','getDriverDeliveries'])await service[method]({signal});assert.deepEqual(calls.map(c=>c.url),['/driver/profile','/driver/dashboard/summary','/driver/deliveries']);for(const call of calls){assert.equal(call.method,'get');assert.equal(call.signal,signal);assert.equal(call.headers.Authorization,'Bearer fixture');}assert.deepEqual(calls[2].params,{page:1,page_size:5});
 }finally{api.defaults.adapter=previous;if(storage===undefined)delete globalThis.sessionStorage;else globalThis.sessionStorage=storage;}
 });
 await t.test('App replaces only the Driver placeholder; responsive patterns and session resource keys are present',async()=>{
 const app=await readFile(new URL('../src/App.jsx',import.meta.url),'utf8');for(const value of ['path="/driver/dashboard" element={<DriverDashboard />}','path="/driver/notifications" element={<DriverNotifications />}','allowedRoles={["driver"]}','<CustomerDashboard />','<ShopOwnerDashboard />','<LoginPage />','<RegisterPage />'])assert.ok(app.includes(value),value);
 const source=await readFile(new URL('../src/pages/driver/DriverDashboard.jsx',import.meta.url),'utf8');for(const value of ['sm:grid-cols-2','md:grid-cols-3','overflow-wrap:anywhere',"key={user.user_id+':'+token}"])assert.ok(source.includes(value),value);
 assert.ok(!source.includes('sessionStorage'));assert.ok(!source.includes('setInterval'));
 });
 }finally{await server.close();}
});
