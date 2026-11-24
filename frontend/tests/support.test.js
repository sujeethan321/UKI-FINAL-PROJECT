import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createSupportReader,supportError,validateCase,supportLabels} from '../src/utils/support.js';
import {notificationDestination,validNotification} from '../src/utils/notification.js';

export function supportFixture(){
 const row={reference:'SUP-'+'a'.repeat(32),category:'account',subject:'Fictional support',description:'Fictional description only',status:'open',priority:'normal',version:1,created_at:'2026-11-23T10:00:00',updated_at:'2026-11-23T10:00:00',business_id:null,business_shared:false,resolution:null};
 return {case:row,references:[],messages:{total:0,offset:0,limit:100,items:[]},events:{total:1,offset:0,limit:100,items:[{action:'created',new_value:'open',created_at:row.created_at}]}};
}
const list=()=>({total:1,limit:20,offset:0,cases:[supportFixture().case],financial_links:'unavailable'});
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};

test('case payload validation rejects unknown lifecycle and missing identity',()=>{
 assert.equal(validateCase(supportFixture().case).status,'open');for(const row of [{...supportFixture().case,reference:'other'},{...supportFixture().case,status:'paid'},{...supportFixture().case,version:0}])assert.throws(()=>validateCase(row));
});
test('disabled schema state never fabricates zero cases and ignores private error details',async()=>{
 const reader=createSupportReader({list:async()=>{throw {response:{status:503,data:{detail:{code:'SUPPORT_DISABLED',password:'private'}}}};}});
 await reader.start();assert.equal(reader.getSnapshot().list,null);assert.equal(reader.getSnapshot().error,'Support is not enabled on this server.');reader.dispose();
});
test('old identity, cancelled reads and strict-mode restarts cannot publish stale data',async()=>{
 const first=deferred(),second=deferred();let calls=0;const reader=createSupportReader({list:()=>++calls===1?first.promise:second.promise});const work=reader.start();reader.dispose();const newer=reader.start();first.resolve({...list(),total:999});await work;assert.equal(reader.getSnapshot().list,null);second.resolve(list());await newer;assert.equal(reader.getSnapshot().list.total,1);reader.dispose();assert.equal(reader.getSnapshot().detail,null);
});
test('uncertain mutation retains exactly the same idempotency payload for explicit retry',async()=>{
 const calls=[];let fail=true;const reader=createSupportReader({list:async()=>list(),create:async payload=>{calls.push(payload);if(fail)throw Error('network');return supportFixture();}});
 await reader.start();await reader.send({kind:'create',payload:{category:'account',subject:'Fictional support',description:'Fictional description only'}});assert.ok(reader.getSnapshot().pending);
 await reader.send({kind:'create',payload:{subject:'must not submit'}});assert.equal(calls.length,1);fail=false;await reader.retry();assert.deepEqual(calls[0],calls[1]);assert.equal(reader.getSnapshot().pending,null);assert.ok(reader.getSnapshot().notice.includes('Financial records were not changed'));reader.dispose();
});
for(const status of [401,403])test('authorization '+status+' clears all sensitive case data',async()=>{
 const api={list:async()=>list(),detail:async()=>supportFixture()};const reader=createSupportReader(api);await reader.start();await reader.open(supportFixture().case.reference);assert.ok(reader.getSnapshot().detail);
 api.list=async()=>{throw {response:{status}};};await reader.load();assert.equal(reader.getSnapshot().list,null);assert.equal(reader.getSnapshot().detail,null);reader.dispose();
});
test('stale version conflict is not automatically retried',async()=>{
 let calls=0;const reader=createSupportReader({list:async()=>list(),action:async()=>{calls++;throw {response:{status:409}};}});await reader.start();await reader.send({kind:'action',reference:supportFixture().case.reference,payload:{action:'reopen',expected_version:1,reason:'Fictional reason'}});assert.equal(calls,1);assert.equal(reader.getSnapshot().pending,null);assert.match(reader.getSnapshot().error,/Refresh/);reader.dispose();
});
test('late mutation completion cannot update a logged-out session',async()=>{
 const pending=deferred();const reader=createSupportReader({list:async()=>list(),create:()=>pending.promise});await reader.start();const work=reader.send({kind:'create',payload:{}});reader.dispose();pending.resolve(supportFixture());await work;assert.equal(reader.getSnapshot().detail,null);assert.equal(reader.getSnapshot().pending,null);
});
test('business-less support notifications use role-safe routes and ignore supplied URLs',()=>{
 const row={notification_id:1,business_id:null,notification_type:'support_resolved',title:'Support case resolved',message:'Generic only',related_entity_type:'support_case',related_entity_id:1,is_read:false,created_at:'2026-11-23T10:00:00Z',read_at:null,url:'/admin/users'};
 assert.ok(validNotification(row));for(const [role,root] of [['customer','customer'],['driver','driver'],['shop_owner','shop-owner'],['admin','admin']])assert.equal(notificationDestination(row,role).to,`/${root}/support`);
});
test('three-language support resources and protected four-role routes exist',async()=>{
 for(const language of ['en','ta','si']){const data=JSON.parse(await readFile(new URL(`../src/i18n/locales/application.${language}.json`,import.meta.url),'utf8'));for(const label of [...Object.values(supportLabels),'My Support Tickets','Support & Disputes','Support is not enabled on this server.'])assert.ok(data[label],label);}
 const source=await readFile(new URL('../src/App.jsx',import.meta.url),'utf8');for(const page of ['CustomerSupport','ShopOwnerSupport','DriverSupport','AdminSupport'])assert.ok(source.includes(`element={<${page} />}`));
 assert.ok(!supportError({response:{status:500,data:{detail:'private'}}}).includes('private'));
});
