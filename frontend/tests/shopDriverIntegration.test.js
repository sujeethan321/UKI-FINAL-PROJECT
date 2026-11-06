import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createShopDeliveryWorkflow} from '../src/utils/shopOwnerDeliveries.js';
import {createDriverJobsWorkflow} from '../src/utils/driverJobs.js';
import {createDeliveriesWorkflow} from '../src/utils/driverDeliveries.js';
import {createDriverDashboardReader} from '../src/utils/driverDashboard.js';
import {businessFixture,intentFixture} from './fixtures/shopOwnerDeliveryFixtures.js';
import {driverFixtures} from './fixtures/driverDashboardFixtures.js';

test('actual role workflows share one schema-matched request through creation, acceptance and completion',async()=>{
 const driverId=17;let record=null,assignment=null;const events=[],stamp='2026-11-06T10:00:00';
 const ownerDetail=()=>({...record,assigned_driver:assignment?{full_name:'Driver A',assigned_at:stamp}:null,events:structuredClone(events),can_cancel:record.status==='available'});
 const operational=()=>Object.fromEntries(['delivery_request_id','reference','pickup_area','delivery_area','status'].map(key=>[key,record[key]]).concat([['business_name','Shop One'],['assigned_at',stamp]]));
 const ownAssignment=()=>({driver_user_id:driverId,assignment_id:1,delivery:operational()});
 const progress=()=>({...ownAssignment(),events:structuredClone(events),allowed_next_status:{assigned:'picked_up',picked_up:'in_transit',in_transit:'delivered'}[record.status]||null});
 const counts=()=>({driver_user_id:driverId,available_jobs_count:record?.status==='available'?1:0,active_deliveries_count:assignment&&record.status!=='delivered'?1:0,completed_deliveries_count:record?.status==='delivered'?1:0});
 const driverList=size=>({driver_user_id:driverId,page:1,page_size:size,total:assignment&&record.status!=='delivered'?1:0,deliveries:assignment&&record.status!=='delivered'?[{...operational(),finished_at:null}]:[]});
 const profile=async()=>({...driverFixtures().profile,driver_user_id:driverId});
 const owner=createShopDeliveryWorkflow({businesses:async()=>businessFixture(),
  list:async(businessId,{page,status})=>({business_id:businessId,page,page_size:10,total:record&&(!status||record.status===status)?1:0,deliveries:record&&(!status||record.status===status)?[structuredClone(record)]:[]}),
  summary:async()=>({business_id:1,total_requests_count:record?1:0,available_requests_count:counts().available_jobs_count,in_progress_count:counts().active_deliveries_count,completed_count:counts().completed_deliveries_count}),
  detail:async()=>ownerDetail(),create:async(businessId,payload)=>{record={...payload,business_id:businessId,delivery_request_id:31,reference:'DR-shared',status:'available',created_at:stamp,updated_at:stamp};return ownerDetail();},
  cancel:async()=>{throw {response:{status:409}};},
 },7,intentFixture());
 const jobs=createDriverJobsWorkflow({profile,summary:async()=>counts(),assigned:async()=>driverList(5),
  jobs:async page=>({driver_user_id:driverId,page,page_size:10,total:record?.status==='available'?1:0,jobs:record?.status==='available'?[{...Object.fromEntries(Object.entries(operational()).filter(([key])=>key!=='assigned_at')),created_at:stamp}]:[]}),
  accept:async()=>{record.status='assigned';assignment=1;events.push({status:'assigned',occurred_at:stamp});return ownAssignment();},
 },driverId);
 await owner.start();owner.edit('pickup_area','Pickup');owner.edit('delivery_area','Destination');await owner.create();await jobs.start();assert.equal(jobs.getSnapshot().jobs.data.total,1);
 await jobs.accept(31);assert.equal(jobs.getSnapshot().acceptance.phase,'confirmed');assert.equal(jobs.getSnapshot().jobs.data.total,0);assert.equal(jobs.getSnapshot().assigned.data.total,1);
 await owner.refresh();assert.equal(owner.getSnapshot().detail.data.assigned_driver.full_name,'Driver A');assert.equal(owner.getSnapshot().detail.data.can_cancel,false);
 const driver=createDeliveriesWorkflow({profile,summary:async()=>counts(),detail:async()=>progress(),update:async(id,payload)=>{
  assert.equal(id,31);assert.equal(payload.expected_status,record.status);record.status=payload.status;events.push({status:payload.status,occurred_at:stamp});return progress();
 }},driverId,{deliveryId:31});await driver.start();
 for(const status of ['picked_up','in_transit','delivered']){await driver.update();await owner.refresh();assert.equal(owner.getSnapshot().detail.data.status,status);assert.deepEqual(owner.getSnapshot().detail.data.events,driver.getSnapshot().detail.data.events);}
 assert.equal(owner.getSnapshot().summary.data.completed_count,1);assert.equal(driver.getSnapshot().summary.data.active_deliveries_count,0);
 const dashboard=createDriverDashboardReader({profile,summary:async()=>counts(),deliveries:async()=>driverList(5)},driverId);await dashboard.start();assert.equal(dashboard.getSnapshot().summary.data.completed_deliveries_count,1);
 const freshOwner=createShopDeliveryWorkflow({businesses:async()=>businessFixture(),list:async()=>({business_id:1,page:1,page_size:10,total:1,deliveries:[record]}),summary:async()=>owner.getSnapshot().summary.data,detail:async()=>ownerDetail()},7,intentFixture());
 await freshOwner.start();await freshOwner.details(31);assert.equal(freshOwner.getSnapshot().detail.data.status,'delivered');
 owner.dispose();freshOwner.dispose();jobs.dispose();driver.dispose();dashboard.dispose();
});
