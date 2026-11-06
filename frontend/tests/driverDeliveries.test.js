import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createDeliveriesWorkflow,parseDeliveryProgress,parseDeliveryPage} from '../src/utils/driverDeliveries.js';
import {driverFixtures} from './fixtures/driverDashboardFixtures.js';
const fixture=()=>({driver_user_id:7,assignment_id:4,delivery:{delivery_request_id:31,reference:'DR-assigned',business_name:'Real fixture shop',pickup_area:'Pickup district',delivery_area:'Delivery district',status:'assigned',assigned_at:'2026-11-06T10:00:00'},events:[{status:'assigned',occurred_at:'2026-11-06T10:00:00'}],allowed_next_status:'picked_up'});
const error=status=>({response:{status}});
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
function setup(options={}) {
  let data=fixture();const calls=[];
  const api={profile:async()=>driverFixtures().profile,summary:async()=>driverFixtures().summary,
    detail:async()=>structuredClone(data),list:async({page})=>({driver_user_id:7,page,page_size:10,total:1,deliveries:[{...data.delivery,finished_at:null}]}),
    update:async(id,payload)=>{calls.push({id,payload});data={...data,delivery:{...data.delivery,status:payload.status},events:[...data.events,{status:payload.status,occurred_at:'2026-11-06T11:00:00'}],allowed_next_status:{picked_up:'in_transit',in_transit:'delivered'}[payload.status]||null};return structuredClone(data);},...options};
  return {api,calls,workflow:createDeliveriesWorkflow(api,7,{deliveryId:31})};
}
test('delivery parsers scope identity, ids, statuses, page and persisted events',()=>{
  const data=fixture();assert.equal(parseDeliveryProgress(data,7,31).allowed_next_status,'picked_up');
  for(const bad of [{...data,driver_user_id:8},{...data,allowed_next_status:'delivered'},{...data,events:[]},{...data,events:[...data.events,...data.events]}])assert.throws(()=>parseDeliveryProgress(bad,7,31));
  const page={driver_user_id:7,page:1,page_size:10,total:1,deliveries:[{...data.delivery,finished_at:null}]};
  assert.equal(parseDeliveryPage(page,7,1,false).total,1);
  assert.throws(()=>parseDeliveryPage(page,7,1,true));assert.throws(()=>parseDeliveryPage(page,8,1,false));assert.throws(()=>parseDeliveryPage(page,7,2,false));
});
test('pickup, transit and completion use confirmed server state and refresh dashboard counts',async()=>{
  let summaries=0;const {workflow,calls}=setup({summary:async()=>{summaries++;return driverFixtures().summary;}});
  await workflow.start();for(const target of ['picked_up','in_transit','delivered']){await workflow.update();assert.equal(workflow.getSnapshot().detail.data.delivery.status,target);}
  assert.deepEqual(calls.map(c=>c.payload),[{expected_status:'assigned',status:'picked_up'},{expected_status:'picked_up',status:'in_transit'},{expected_status:'in_transit',status:'delivered'}]);assert.equal(summaries,4);await workflow.update();assert.equal(calls.length,3);workflow.dispose();
});
test('duplicate clicks issue a single mutation and do not optimistically change status',async()=>{
  const pending=deferred();let calls=0;const {workflow}=setup({update:()=>{calls++;return pending.promise;}});await workflow.start();
  const first=workflow.update(),second=workflow.update();assert.equal(calls,1);assert.equal(workflow.getSnapshot().busy,true);assert.equal(workflow.getSnapshot().detail.data.delivery.status,'assigned');
  const data=fixture();data.delivery.status='picked_up';data.allowed_next_status='in_transit';data.events.push({status:'picked_up',occurred_at:'2026-11-06T11:00:00'});pending.resolve(data);await Promise.all([first,second]);assert.equal(calls,1);workflow.dispose();
});
for(const status of [409,404,422,503,undefined])test('failed/uncertain update clears actionable state until details refresh: '+status,async()=>{
  let calls=0;const {workflow}=setup({update:async()=>{calls++;throw status?error(status):Error('network');}});await workflow.start();await workflow.update();
  assert.equal(workflow.getSnapshot().uncertain,true);assert.equal(workflow.getSnapshot().detail.data,null);assert.ok(!workflow.getSnapshot().message.includes('updated.'));await workflow.update();assert.equal(calls,1);
  await workflow.refresh();assert.equal(workflow.getSnapshot().uncertain,false);workflow.dispose();
});
for(const status of [401,403])test('auth rejection clears private state: '+status,async()=>{
  const {workflow}=setup({update:async()=>{throw error(status);}});await workflow.start();await workflow.update();assert.ok(workflow.getSnapshot().authError);assert.equal(workflow.getSnapshot().detail.data,null);assert.equal(workflow.getSnapshot().profile.data,null);workflow.dispose();
});
test('pending eligibility allows own reads but never updates',async()=>{
  const profile={...driverFixtures().profile,approval_status:'pending',eligible_for_jobs:false,eligibility_reason:'approval_pending'};
  let calls=0;const {workflow}=setup({profile:async()=>profile,update:async()=>calls++});await workflow.start();await workflow.update();assert.equal(calls,0);assert.ok(workflow.getSnapshot().detail.data);workflow.dispose();
});
test('unmount/session replacement aborts slow requests and ignores late mutation results',async()=>{
  const pending=deferred();let signal;const {workflow}=setup({update:async(id,data,options)=>{signal=options.signal;return pending.promise;}});await workflow.start();const update=workflow.update();workflow.dispose();assert.equal(signal.aborted,true);pending.resolve(fixture());await update;assert.equal(workflow.getSnapshot().detail.data,null);
});
test('list pagination and status filtering reset pages and ignore stale responses',async()=>{
  const calls=[],pending=deferred();let slow=false;
  const api={profile:async()=>driverFixtures().profile,summary:async()=>driverFixtures().summary,list:async(options)=>{calls.push(options);if(slow)return pending.promise;return {driver_user_id:7,page:options.page,page_size:10,total:0,deliveries:[]};}};
  const workflow=createDeliveriesWorkflow(api,7);await workflow.start();await workflow.page(2);await workflow.filter('picked_up');assert.equal(workflow.getSnapshot().page,1);assert.equal(calls.at(-1).status,'picked_up');slow=true;const late=workflow.page(2);workflow.dispose();pending.resolve({driver_user_id:7,page:2,page_size:10,total:0,deliveries:[]});await late;assert.equal(workflow.getSnapshot().list.data,null);
});
