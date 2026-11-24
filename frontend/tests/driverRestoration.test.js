import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter,Route,Routes} from 'react-router-dom';
import {createServer} from 'vite';
import {driverFixtures} from './fixtures/driverDashboardFixtures.js';
import {parseDriverResponse} from '../src/utils/driverDashboard.js';

test('restored Driver pages retain approval, ownership and unsupported-finance boundaries',async t=>{
  const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
  try{
    const load=path=>server.ssrLoadModule('/src/'+path);
    const render=(View,props)=>renderToStaticMarkup(h(MemoryRouter,null,h(View,props)));
    const fixtures=driverFixtures(),profile=parseDriverResponse('profile',fixtures.profile,7);
    await t.test('all Driver destinations remain reachable without the removed identity footer',async()=>{
      const {default:View}=await load('components/driver/DriverSidebar.jsx');
      const html=render(View,{user:{full_name:'Synthetic Driver'}});
      for(const path of ['dashboard','deliveries','history','earnings','vehicle','notifications','profile','settings'])assert.ok(html.includes('href="/driver/'+path+'"'),path);
      assert.doesNotMatch(html,/Synthetic Driver|Tharindu Perera|Planned/);
    });
    await t.test('dashboard uses existing counts without fake today, fee, presence or earnings data',async()=>{
      const {DriverDashboardView:View}=await load('pages/driver/DriverDashboard.jsx');
      const state={authError:'',...Object.fromEntries(Object.entries(fixtures).map(([key,data])=>[key,{data:parseDriverResponse(key,data,7),loading:false,error:''}]))};
      const html=render(View,{state,actions:{},displayName:'Synthetic Driver'});
      assert.equal((html.match(/<article/g)||[]).length,3);assert.match(html,/Available Orders/);assert.ok(html.includes('href="/driver/jobs"'));assert.match(html,/Next Assigned Delivery/);assert.match(html,/Earnings accounting is not available/);assert.doesNotMatch(html,/LKR \d|>Online<|Scheduled pickup:/);
    });
    await t.test('earnings cards and controls cannot masquerade as settled or withdrawable money',async()=>{
      const {DriverEarningsView:View}=await load('pages/driver/DriverEarnings.jsx');
      const html=render(View,{});for(const label of ['Total Earnings','Available Balance','Pending Earnings','Earnings Overview','Earnings History','Payout Information'])assert.ok(html.includes(label),label);
      assert.match(html,/disabled/);assert.match(html,/Unavailable/);assert.doesNotMatch(html,/LKR \d|>Paid<|Ready for withdrawal/);
    });
    await t.test('vehicle uses stored type/reference without unsupported verification or expiry badges',async()=>{
      const {DriverVehicleView:View}=await load('pages/driver/DriverVehicle.jsx');
      const html=render(View,{profile:{...profile,document_verified:true,vehicle:{...profile.vehicle,nic:'PRIVATE-NIC'}}});
      assert.match(html,/TEST-123/);assert.match(html,/Vehicle Documents/);assert.match(html,/Approved/);assert.doesNotMatch(html,/>Verified<|>Expired<|PRIVATE-NIC|Honda|WP PBT/);
      const first=render(View,{profile:{...profile,approval_status:'not_submitted',vehicle_registration_status:'not_registered',eligible_for_jobs:false,eligibility_reason:'profile_required',vehicle:null}});assert.match(first,/Register Vehicle/);assert.match(first,/pending application/);assert.doesNotMatch(first,/self.approv/i);
    });
    await t.test('profile shows own authenticated fields without national identity or false verification',async()=>{
      const {DriverProfileView:View}=await load('pages/driver/DriverProfile.jsx');
      const html=render(View,{profile,user:{email:'synthetic@example.invalid',nic:'PRIVATE-NIC',identity_verified:true}});
      assert.match(html,/synthetic@example.invalid/);assert.match(html,/Driver approval/);assert.doesNotMatch(html,/PRIVATE-NIC|>Identity Verified<|>Verified<|Tharindu Perera/);
    });
    await t.test('Driver inbox preserves recipient routing/read controls and conceals stale records',async()=>{
      const {DriverInboxView:View}=await load('components/driver/DriverInbox.jsx');
      const state={count:1,typeFilter:'',readFilter:'all',page:1,pageSize:20,list:{total:1,notifications:[{notification_id:1,notification_type:'delivery_assigned',title:'Synthetic assignment',message:'Recorded assignment.',created_at:'2026-11-08T10:00:00Z',is_read:false,read_at:null,related_entity_type:'delivery_request',related_entity_id:31,business_id:2}]}};
      let html=render(View,{state,actions:{}});assert.match(html,/Synthetic assignment/);assert.match(html,/href="\/driver\/deliveries\/31"/);assert.match(html,/Mark All as Read/);assert.match(html,/Earnings unavailable/);
      html=render(View,{state:{...state,authError:'Session expired'},actions:{}});assert.match(html,/Session expired/);assert.doesNotMatch(html,/Synthetic assignment|1 Unread/);
    });
    await t.test('new protected pages are unavailable to other roles',async()=>{
      const {AuthContext}=await load('context/AuthContext.jsx'),{default:Guard}=await load('routes/ProtectedRoute.jsx'),{default:View}=await load('pages/driver/DriverEarnings.jsx');
      const route=role=>renderToStaticMarkup(h(MemoryRouter,{initialEntries:['/driver/earnings']},h(AuthContext.Provider,{value:{isAuthenticated:true,loading:false,user:{platform_role:role,account_status:'active'}}},h(Routes,null,h(Route,{element:h(Guard,{allowedRoles:['driver']})},h(Route,{path:'/driver/earnings',element:h(View)}))))));
      assert.match(route('driver'),/Payout Information/);for(const role of ['customer','shop_owner','admin'])assert.doesNotMatch(route(role),/Payout Information/);
    });
    await t.test('Settings provides existing navigation/logout without fake availability toggles',async()=>{
      const {DriverSettingsView:View}=await load('pages/driver/DriverSettings.jsx');const html=render(View,{});
      assert.match(html,/Sign Out/);assert.match(html,/href="\/driver\/vehicle"/);assert.match(html,/not supported/);assert.doesNotMatch(html,/type="checkbox"|Save Preferences/);
    });
  }finally{await server.close();}
});
