import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createShopDeliveryWorkflow,parseShopDelivery,parseShopDeliveryList,parseShopDeliverySummary,validateDeliveryAreas,deliveryIntentStore} from '../src/utils/shopOwnerDeliveries.js';
import {ownerDeliveryApi,intentFixture,deliveryDetail,deliveryFixture,businessFixture,pageFixture,summaryFixture} from './fixtures/shopOwnerDeliveryFixtures.js';
const setup=(api=ownerDeliveryApi(),store=intentFixture())=>({api,store,workflow:createShopDeliveryWorkflow(api,7,store)});
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
const fill=workflow=>{workflow.edit('pickup_area',' Pickup area ');workflow.edit('delivery_area','Destination area');};
test('strict scoped parsers strip private data and reject wrong identity, filters, pagination or counts',()=>{
 const parsed=parseShopDelivery({...deliveryDetail(),phone:'SECRET',credit_limit:999},1,31);assert.equal(parsed.phone,undefined);
 for(const data of [deliveryDetail({business_id:2}),deliveryDetail({can_cancel:false}),deliveryDetail({status:'assigned'}),deliveryDetail({events:[{status:'invented',occurred_at:'bad'}]})])assert.throws(()=>parseShopDelivery(data,1,31));
 assert.throws(()=>parseShopDelivery(deliveryDetail(),1,99));assert.throws(()=>parseShopDeliveryList(pageFixture(),2,1,''));assert.throws(()=>parseShopDeliveryList(pageFixture(),1,2,''));assert.throws(()=>parseShopDeliveryList(pageFixture(),1,1,'cancelled'));
 assert.throws(()=>parseShopDeliverySummary(summaryFixture({total_requests_count:0}),1));
});
test('validation sends only two supported fields with trimmed single-line Unicode areas',()=>{
 assert.deepEqual(validateDeliveryAreas({pickup_area:' <shop> ',delivery_area:' யாழ்ப்பாணம் ',business_id:99}).payload,{pickup_area:'<shop>',delivery_area:'யாழ்ப்பாணம்'});
 for(const value of ['', ' ', 'a'.repeat(161),'a\nb','a\x00b'])assert.ok(validateDeliveryAreas({pickup_area:value,delivery_area:'Area'}).error);
});
test('trusted business context selects approved ownership; pending/no business cannot create',async()=>{
 const {api,workflow}=setup();await workflow.start();assert.equal(workflow.getSnapshot().businessId,1);await workflow.selectBusiness(999);assert.equal(workflow.getSnapshot().businessId,1);
 await workflow.selectBusiness(3);fill(workflow);await workflow.create();assert.ok(!api.calls.some(c=>c[0]==='create'));assert.equal(workflow.getSnapshot().list.data,null);workflow.dispose();
 const other=setup({...ownerDeliveryApi(),businesses:async()=>({...businessFixture(),businesses:[]})});await other.workflow.start();assert.equal(other.workflow.getSnapshot().businessId,null);other.workflow.dispose();
});
test('confirmed creation waits for backend, clears form/marker and refreshes summary and list',async()=>{
 const {api,store,workflow}=setup();await workflow.start();fill(workflow);await workflow.create();const state=workflow.getSnapshot();
 assert.equal(state.message,'Delivery request created.');assert.deepEqual(state.form,{pickup_area:'',delivery_area:''});assert.equal(store.read(1),false);
 assert.deepEqual(api.calls.find(c=>c[0]==='create'),['create',1,{pickup_area:'Pickup area',delivery_area:'Destination area'}]);assert.equal(api.calls.filter(c=>c[0]==='summary').length,2);workflow.dispose();
});
test('duplicate creation shares one mutation and blocks edits/business changes while pending',async()=>{
 const api=ownerDeliveryApi(),gate=deferred();let sent=0;api.create=async()=>{sent++;return gate.promise;};const {workflow,store}=setup(api);await workflow.start();fill(workflow);const a=workflow.create(),b=workflow.create();
 assert.equal(sent,1);assert.equal(store.read(1),true);assert.equal(workflow.getSnapshot().message,'');workflow.edit('pickup_area','Changed');await workflow.selectBusiness(2);assert.equal(workflow.getSnapshot().businessId,1);gate.resolve(deliveryDetail());await Promise.all([a,b]);assert.equal(sent,1);workflow.dispose();
});
for(const status of [422,409,404])test('definitive creation rejection preserves form without success: '+status,async()=>{
 const {workflow,store}=setup({...ownerDeliveryApi(),create:async()=>{throw {response:{status}};}});await workflow.start();fill(workflow);await workflow.create();assert.equal(store.read(1),false);assert.ok(workflow.getSnapshot().error);assert.equal(workflow.getSnapshot().message,'');assert.ok(workflow.getSnapshot().form.pickup_area);workflow.dispose();
});
test('network uncertainty survives remount, never retries automatically, and requires list review',async()=>{
 const store=intentFixture(),api=ownerDeliveryApi();let sent=0;api.create=async()=>{sent++;throw Error('network');};let workflow=setup(api,store).workflow;await workflow.start();fill(workflow);await workflow.create();assert.equal(store.read(1),true);await workflow.create();assert.equal(sent,1);workflow.dispose();
 workflow=setup(api,store).workflow;await workflow.start();assert.equal(workflow.getSnapshot().uncertain,true);workflow.acknowledge();assert.equal(workflow.getSnapshot().uncertain,true);await workflow.reviewUncertain();workflow.acknowledge();assert.equal(workflow.getSnapshot().uncertain,false);assert.equal(store.read(1),false);assert.equal(sent,1);workflow.dispose();
});
test('malformed or foreign creation response remains uncertain',async()=>{
 const {workflow}=setup({...ownerDeliveryApi(),create:async()=>deliveryDetail({business_id:2})});await workflow.start();fill(workflow);await workflow.create();assert.equal(workflow.getSnapshot().uncertain,true);assert.equal(workflow.getSnapshot().message,'');workflow.dispose();
});
test('cancellation requires confirmation, calls once and refreshes actual final state',async()=>{
 const {workflow,api}=setup();await workflow.start();await workflow.details(31);await workflow.cancel();assert.ok(!api.calls.some(c=>c[0]==='cancel'));
 workflow.confirmCancel(true);await workflow.cancel();assert.equal(workflow.getSnapshot().detail.data.status,'cancelled');assert.equal(workflow.getSnapshot().message,'Delivery request cancelled.');assert.equal(api.calls.filter(c=>c[0]==='cancel').length,1);workflow.dispose();
});
test('concurrent acceptance conflict reloads assigned Driver and removes cancellation',async()=>{
 const api=ownerDeliveryApi();let assigned=false;api.cancel=async()=>{assigned=true;throw {response:{status:409}};};api.detail=async()=>assigned?deliveryDetail({status:'assigned',can_cancel:false,assigned_driver:{full_name:'Assigned Driver',assigned_at:deliveryFixture().created_at},events:[{status:'assigned',occurred_at:deliveryFixture().created_at}]}):deliveryDetail();
 const {workflow}=setup(api);await workflow.start();await workflow.details(31);workflow.confirmCancel(true);await workflow.cancel();assert.equal(workflow.getSnapshot().detail.data.status,'assigned');assert.equal(workflow.getSnapshot().detail.data.can_cancel,false);assert.ok(workflow.getSnapshot().error.includes('accepted'));assert.equal(workflow.getSnapshot().message,'');workflow.dispose();
});
test('uncertain cancellation and duplicate clicks use one request then refresh recorded state',async()=>{
 const api=ownerDeliveryApi(),gate=deferred();let sent=0,cancelled=false;
 api.cancel=async()=>{sent++;await gate.promise;cancelled=true;throw Error('response lost');};
 api.detail=async()=>cancelled?deliveryDetail({status:'cancelled',can_cancel:false,events:[{status:'cancelled',occurred_at:'2026-11-06T11:00:00'}]}):deliveryDetail();
 const {workflow}=setup(api);await workflow.start();await workflow.details(31);workflow.confirmCancel(true);const a=workflow.cancel(),b=workflow.cancel();assert.equal(sent,1);gate.resolve();await Promise.all([a,b]);assert.equal(workflow.getSnapshot().detail.data.status,'cancelled');assert.equal(workflow.getSnapshot().message,'');assert.ok(workflow.getSnapshot().error.includes('could not be confirmed'));workflow.dispose();
});
test('a delayed old-business response cannot replace the newly selected business',async()=>{
 const api=ownerDeliveryApi(),gate=deferred();const original=api.list;let slow=false;
 api.list=async(businessId,options)=>slow&&businessId===1?gate.promise:original(businessId,options);
 const {workflow}=setup(api);await workflow.start();slow=true;const refresh=workflow.refresh();await workflow.selectBusiness(2);
 gate.resolve(pageFixture());await refresh;assert.equal(workflow.getSnapshot().businessId,2);assert.equal(workflow.getSnapshot().list.data.total,0);assert.equal(workflow.getSnapshot().detail.data,null);workflow.dispose();
});
test('summary uses server-wide totals independently of one paginated response',async()=>{
 const api=ownerDeliveryApi();api.summary=async()=>summaryFixture({total_requests_count:500,available_requests_count:100,in_progress_count:200,completed_count:150});
 const {workflow}=setup(api);await workflow.start();assert.equal(workflow.getSnapshot().list.data.deliveries.length,1);assert.equal(workflow.getSnapshot().summary.data.total_requests_count,500);assert.equal(workflow.getSnapshot().summary.data.in_progress_count,200);workflow.dispose();
});
test('filter/page changes reset pagination and ignore superseded responses',async()=>{
 const api=ownerDeliveryApi(),requests=[];const {workflow}=setup(api);await workflow.start();api.list=(businessId,options)=>new Promise(resolve=>requests.push({businessId,...options,resolve}));const a=workflow.page(2),b=workflow.filter('cancelled');assert.equal(requests[0].signal.aborted,true);requests[1].resolve(pageFixture({deliveries:[],total:0}));await b;requests[0].resolve(pageFixture({page:2}));await a;assert.equal(workflow.getSnapshot().page,1);assert.equal(workflow.getSnapshot().status,'cancelled');assert.deepEqual(workflow.getSnapshot().list.data.deliveries,[]);workflow.dispose();
});
test('late business/private responses and unmounted creation cannot repopulate a later session',async()=>{
 const gate=deferred(),api=ownerDeliveryApi();api.create=()=>gate.promise;const {workflow,store}=setup(api);await workflow.start();fill(workflow);const mutation=workflow.create();workflow.dispose();gate.resolve(deliveryDetail());await mutation;assert.equal(workflow.getSnapshot().detail.data,null);assert.equal(store.read(1),true);
});
for(const status of [401,403])test('authorization failure clears business data: '+status,async()=>{
 const api=ownerDeliveryApi();const {workflow}=setup(api);await workflow.start();api.detail=async()=>{throw {response:{status}};};await workflow.details(31);assert.ok(workflow.getSnapshot().authError);assert.equal(workflow.getSnapshot().list.data,null);assert.deepEqual(workflow.getSnapshot().businesses,[]);workflow.dispose();
});
test('storage failure sends no create; tab marker contains no delivery text',async()=>{
 let calls=0;const {workflow}=setup({...ownerDeliveryApi(),create:async()=>calls++},{read:()=>false,mark:()=>{throw Error('disabled');}});await workflow.start();fill(workflow);await workflow.create();assert.equal(calls,0);assert.ok(workflow.getSnapshot().storageError);workflow.dispose();
 const old=globalThis.sessionStorage,data=new Map();globalThis.sessionStorage={getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,value),removeItem:key=>data.delete(key)};
 try{const store=deliveryIntentStore(7);store.mark(1);assert.deepEqual([...data],[['lankapex_delivery_attempt:7:1','unconfirmed']]);assert.equal(store.read(1),true);assert.equal(deliveryIntentStore(8).read(1),false);store.clear(1);assert.equal(data.size,0);}finally{if(old===undefined)delete globalThis.sessionStorage;else globalThis.sessionStorage=old;}
});
