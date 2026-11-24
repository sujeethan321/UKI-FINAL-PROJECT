import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter,Routes,Route} from 'react-router-dom';
import {createServer} from 'vite';
import {driverFixtures} from './fixtures/driverDashboardFixtures.js';
const section=data=>({data,loading:false,error:''});
const row={delivery_request_id:31,reference:'DR-real',business_name:'Fixture shop',pickup_area:'Pickup area A',delivery_area:'Delivery area B',status:'assigned',assigned_at:'2026-11-06T10:00:00',finished_at:null};
const ready=()=>({authError:'',page:1,status:'',profile:section(driverFixtures().profile),summary:section(driverFixtures().summary),list:section({total:1,deliveries:[row]}),detail:section({delivery:row,events:[{status:'assigned',occurred_at:row.assigned_at}],allowed_next_status:'picked_up'}),busy:false,uncertain:false,message:''});
const actions={refresh(){},filter(){},page(){},update(){}};
test('My Deliveries real React views, Driver guard and Axios contracts',async t=>{
  const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
  try{
    const {DriverDeliveriesView:View,default:Page}=await server.ssrLoadModule('/src/pages/driver/DriverDeliveries.jsx');
    const render=(state=ready(),props={})=>renderToStaticMarkup(h(MemoryRouter,null,h(View,{state,actions,...props})));
    await t.test('responsive list, filters, pagination and actual next action links',()=>{
      const html=render();for(const value of ['My Deliveries','DR-real','Fixture shop','Pickup area A','Delivery area B','Assigned','Confirm Pickup','Filter by status','Previous','Next','/driver/deliveries/31'])assert.ok(html.includes(value),value);
    });
    await t.test('details render persisted timeline, assigned driver and only stored operational fields',()=>{
      const state=ready();state.detail.data.delivery={...row,phone:'PRIVATE-PHONE',address:'PRIVATE-ADDRESS',credit_limit:'SECRET-CREDIT'};
      const html=render(state,{detail:true});for(const value of ['Delivery Details','Recorded delivery progress','2026-11-06 10:00:00 UTC','Assigned Driver','Confirm Pickup'])assert.ok(html.includes(value),value);
      for(const value of ['PRIVATE-PHONE','PRIVATE-ADDRESS','SECRET-CREDIT','LKR'])assert.ok(!html.includes(value));
    });
    await t.test('transit and completion controls follow server-permitted next action',()=>{
      const state=ready();for(const [status,next,label] of [['picked_up','in_transit','Start Delivery'],['in_transit','delivered','Mark Delivered']]){state.detail.data={...state.detail.data,delivery:{...row,status},allowed_next_status:next};assert.ok(render(state,{detail:true}).includes(label));}
      state.busy=true;assert.ok(render(state,{detail:true}).includes('Updating delivery...'));assert.ok(render(state,{detail:true}).includes('disabled'));
      for(const status of ['delivered','cancelled']){state.detail.data={...state.detail.data,delivery:{...row,status},allowed_next_status:null};const html=render(state,{detail:true});assert.ok(html.includes('No further status updates'));assert.ok(!html.includes('Mark Delivered'));}
    });
    await t.test('pending approval, expired session and uncertain result hide actions/data appropriately',()=>{
      const state=ready();state.profile.data={...state.profile.data,eligible_for_jobs:false,eligibility_reason:'approval_pending'};assert.ok(!render(state,{detail:true}).includes('>Confirm Pickup<'));
      state.authError='Your session has expired.';const html=render(state,{detail:true});assert.ok(html.includes('expired'));assert.ok(!html.includes('DR-real'));
      state.authError='';state.detail=section(null);state.uncertain=true;state.message='Update could not be confirmed.';assert.ok(render(state,{detail:true}).includes('Refresh details to check'));
    });
    await t.test('empty, loading, backend unavailable and history dates are truthful',()=>{
      const state=ready();state.list=section({total:0,deliveries:[]});assert.ok(render(state).includes('No assigned deliveries'));assert.ok(render(state,{history:true}).includes('No completed or cancelled'));
      state.list={data:null,loading:true,error:''};assert.ok(render(state).includes('Loading deliveries...'));assert.ok(!render(state).includes('No assigned deliveries'));
      state.list={data:null,loading:false,error:'Network unavailable'};assert.ok(render(state).includes('Network unavailable'));
      state.list=section({total:1,deliveries:[{...row,status:'delivered'}]});const html=render(state,{history:true});assert.ok(html.includes('Delivery History'));assert.ok(html.includes('Date not recorded'));
    });
    await t.test('all new pages require the existing Driver role and valid delivery identifier',async()=>{
      const {AuthContext}=await server.ssrLoadModule('/src/context/AuthContext.jsx'),{default:Guard}=await server.ssrLoadModule('/src/routes/ProtectedRoute.jsx');
      const auth={isAuthenticated:true,loading:false,token:'fixture',user:{user_id:7,platform_role:'driver',account_status:'active'}};
      const renderRoute=(value,path,detail=false)=>renderToStaticMarkup(h(MemoryRouter,{initialEntries:[path]},h(AuthContext.Provider,{value},h(Routes,null,h(Route,{element:h(Guard,{allowedRoles:['driver']})},h(Route,{path:detail?'/driver/deliveries/:deliveryId':'/driver/deliveries',element:h(Page,{detail})}))))));
      assert.ok(renderRoute(auth,'/driver/deliveries').includes('My Deliveries'));assert.ok(renderRoute(auth,'/driver/deliveries/bad',true).includes('Invalid delivery ID'));
      for(const role of ['customer','shop_owner','admin'])assert.ok(!renderRoute({...auth,user:{...auth.user,platform_role:role}},'/driver/deliveries').includes('My Deliveries'));
    });
    await t.test('shared JWT service uses actual endpoints, filters and explicit expected status',async()=>{
      const {default:api}=await server.ssrLoadModule('/src/services/api.js'),service=await server.ssrLoadModule('/src/services/driverDeliveriesService.js');const old=api.defaults.adapter,storage=globalThis.localStorage,calls=[];globalThis.localStorage={getItem:()=> 'fixture'};api.defaults.adapter=async config=>{calls.push(config);return {data:{},status:200,statusText:'OK',headers:{},config};};
      try{const signal=new AbortController().signal;await service.listDriverDeliveries({page:2,status:'picked_up',signal});await service.listDriverDeliveries({history:true,status:'delivered',signal});await service.readDriverDelivery(31,{signal});await service.updateDriverDelivery(31,{expected_status:'assigned',status:'picked_up'},{signal});assert.deepEqual(calls.map(c=>c.url),['/driver/deliveries','/driver/history','/driver/deliveries/31','/driver/deliveries/31/status']);assert.deepEqual(calls[0].params,{page:2,page_size:10,status:'picked_up'});assert.equal(calls[3].data,'{"expected_status":"assigned","status":"picked_up"}');for(const call of calls){assert.equal(call.signal,signal);assert.equal(call.headers.Authorization,'Bearer fixture');}
      }finally{api.defaults.adapter=old;if(storage===undefined)delete globalThis.localStorage;else globalThis.localStorage=storage;}
    });
  }finally{await server.close();}
});
