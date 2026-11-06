import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseDriverResponse,createDriverDashboardReader,driverReadError,formatAssignedTime} from '../src/utils/driverDashboard.js';
import {driverFixtures} from './fixtures/driverDashboardFixtures.js';
const apis=data=>Object.fromEntries(Object.keys(data).map(key=>[key,async()=>data[key]]));
test('verified Driver response fields are projected and foreign identity is rejected',()=>{
 const f=driverFixtures();f.profile.private_note='hidden';f.profile.vehicle.internal_document='hidden';
 assert.equal(parseDriverResponse('profile',f.profile,7).private_note,undefined);assert.equal(parseDriverResponse('profile',f.profile,7).vehicle.internal_document,undefined);
 for(const section of Object.keys(f))assert.throws(()=>parseDriverResponse(section,f[section],8));
});
test('counts require complete nonnegative integer fields including explicit zero',()=>{
 const f=driverFixtures();f.summary.available_jobs_count=0;assert.equal(parseDriverResponse('summary',f.summary,7).available_jobs_count,0);
 for(const patch of [{available_jobs_count:undefined},{active_deliveries_count:-1},{completed_deliveries_count:1.5}])assert.throws(()=>parseDriverResponse('summary',{...f.summary,...patch},7));
});
test('profile eligibility and nullable vehicle match the actual approval contract',()=>{
 const p=driverFixtures().profile;
 for(const status of ['pending','rejected','suspended'])assert.equal(parseDriverResponse('profile',{...p,approval_status:status,eligible_for_jobs:false,eligibility_reason:'approval_'+status},7).approval_status,status);
 assert.equal(parseDriverResponse('profile',{...p,approval_status:'not_submitted',eligible_for_jobs:false,eligibility_reason:'profile_required',vehicle:null},7).vehicle,null);
 assert.throws(()=>parseDriverResponse('profile',{...p,approval_status:'pending'},7));
 assert.throws(()=>parseDriverResponse('profile',{...p,vehicle:{}},7));
});
test('delivery preview rejects unbounded, duplicate, malformed or unsupported status records',()=>{
 const d=driverFixtures().deliveries;
 for(const patch of [{page:2},{page_size:100},{total:1},{deliveries:[d.deliveries[0],d.deliveries[0]]},{deliveries:[{...d.deliveries[0],status:'available'}]},{deliveries:[{...d.deliveries[0],assigned_at:'bad'}]}])assert.throws(()=>parseDriverResponse('deliveries',{...d,...patch},7));
 assert.equal(formatAssignedTime('2026-11-06T10:00:00'),'2026-11-06 10:00:00 UTC');
});
test('three dashboard resources load actual data and disposal clears it',async()=>{
 const reader=createDriverDashboardReader(apis(driverFixtures()),7);await reader.start();assert.equal(reader.getSnapshot().summary.data.completed_deliveries_count,4);reader.dispose();assert.equal(reader.getSnapshot().profile.data,null);
});
test('explicit zero/empty/no-profile responses never fabricate missing values',async()=>{
 const f=driverFixtures();f.profile={...f.profile,approval_status:'not_submitted',eligible_for_jobs:false,eligibility_reason:'profile_required',vehicle:null};f.summary={driver_user_id:7,available_jobs_count:0,active_deliveries_count:0,completed_deliveries_count:0};f.deliveries={...f.deliveries,total:0,deliveries:[]};
 const reader=createDriverDashboardReader(apis(f),7);await reader.start();assert.equal(reader.getSnapshot().summary.data.available_jobs_count,0);assert.deepEqual(reader.getSnapshot().deliveries.data.deliveries,[]);
});
test('partial failure preserves successful sections and section retry recovers',async()=>{
 const f=driverFixtures(),api=apis(f);let fail=true;api.summary=async()=>{if(fail)throw {response:{status:503,data:{detail:'private'}}};return f.summary;};
 const reader=createDriverDashboardReader(api,7);await reader.start();assert.equal(reader.getSnapshot().summary.data,null);assert.ok(reader.getSnapshot().profile.data);assert.ok(!reader.getSnapshot().summary.error.includes('private'));fail=false;await reader.load('summary');assert.equal(reader.getSnapshot().summary.data.active_deliveries_count,2);
});
test('missing response fields remain unavailable instead of becoming zero',async()=>{
 const f=driverFixtures();delete f.summary.active_deliveries_count;const reader=createDriverDashboardReader(apis(f),7);await reader.start();assert.equal(reader.getSnapshot().summary.data,null);assert.match(reader.getSnapshot().summary.error,/could not be verified/);
});
for(const status of [401,403])test('authorization loss '+status+' clears every section and suppresses late delivery data',async()=>{
 const f=driverFixtures();let rejectSummary,resolveDeliveries;const reader=createDriverDashboardReader({profile:async()=>f.profile,summary:()=>new Promise((resolve,reject)=>rejectSummary=reject),deliveries:()=>new Promise(resolve=>resolveDeliveries=resolve)},7);
 const pending=reader.start();await Promise.resolve();rejectSummary({response:{status}});await Promise.resolve();await Promise.resolve();resolveDeliveries(f.deliveries);await pending;assert.ok(reader.getSnapshot().authError);for(const section of ['profile','summary','deliveries'])assert.equal(reader.getSnapshot()[section].data,null);
});
test('superseded requests and former driver sessions cannot populate current state',async()=>{
 const f=driverFixtures(),pending=[];const api=Object.fromEntries(Object.keys(f).map(section=>[section,({signal})=>new Promise(resolve=>pending.push({section,signal,resolve}))]));
 const reader=createDriverDashboardReader(api,7),old=reader.start(),current=reader.start();assert.ok(pending.slice(0,3).every(p=>p.signal.aborted));
 for(const p of pending.slice(3))p.resolve(f[p.section]);await current;for(const p of pending.slice(0,3))p.resolve({...f[p.section],driver_user_id:8});await old;assert.equal(reader.getSnapshot().profile.data.driver_user_id,7);
 const former=createDriverDashboardReader(api,7),work=former.start();former.dispose();for(const p of pending.slice(6))p.resolve(f[p.section]);await work;assert.equal(former.getSnapshot().profile.data,null);
 const next=createDriverDashboardReader(apis(f),8);await next.start();assert.equal(next.getSnapshot().profile.data,null);
});
test('timeout, forbidden and network errors never disclose raw backend text',()=>{
 assert.match(driverReadError({response:{status:401}}),/expired/);assert.match(driverReadError({code:'ECONNABORTED'}),/too long/);assert.ok(!driverReadError({response:{status:503,data:{detail:'secret'}}}).includes('secret'));
});
