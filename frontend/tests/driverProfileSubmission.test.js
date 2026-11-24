import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createDriverProfileSubmission,driverSubmissionError} from '../src/utils/driverProfileSubmission.js';
import {driverFixtures} from './fixtures/driverDashboardFixtures.js';
const fields={vehicle_type:'van',registration_reference:'TEST-123',driving_licence:new File(['fixture'],'licence.png',{type:'image/png'}),vehicle_ownership_proof:new File(['fixture'],'ownership.pdf',{type:'application/pdf'})};
const pending=()=>({...driverFixtures().profile,approval_status:'pending',eligible_for_jobs:false,eligibility_reason:'approval_pending'});

test('submission distinguishes unavailable private storage and existing applications without exposing raw errors',()=>{
 const failure=(status,detail)=>({response:{status,data:{detail}}});
 assert.match(driverSubmissionError(failure(503,'Driver document submission is not configured')),/not configured on the running server/);
 assert.match(driverSubmissionError(failure(503,'Document submission unavailable')),/Secure document storage or validation/);
 assert.match(driverSubmissionError(failure(409,'PRIVATE')),/already exists or conflicts/);
 for(const status of [400,409,413,415,500,503])assert.ok(!driverSubmissionError(failure(status,'PRIVATE')).includes('PRIVATE'));
});
test('submission trims vehicle fields, strips caller identity and refreshes only after pending confirmation',async()=>{
 let payload,refreshes=0;const flow=createDriverProfileSubmission(async value=>{payload=value;return pending();},7,()=>refreshes++);
 await flow.submit({...fields,vehicle_type:' van ',user_id:99,approval_status:'approved'});
 assert.deepEqual(payload,fields);assert.equal(refreshes,1);assert.equal(flow.getSnapshot().error,'');
});
test('duplicate clicks share one submission while waiting for confirmation',async()=>{
 let calls=0,resolve;const flow=createDriverProfileSubmission(()=>{calls++;return new Promise(done=>resolve=done);},7,()=>{});
 const one=flow.submit(fields),two=flow.submit(fields);assert.equal(calls,1);assert.equal(flow.getSnapshot().saving,true);resolve(pending());await Promise.all([one,two]);
});
for(const status of [401,403,422,429,409,503])test('safe recovery for HTTP '+status,async()=>{
 let calls=0,refreshes=0;const flow=createDriverProfileSubmission(async()=>{calls++;throw {response:{status,data:{detail:'PRIVATE'}}};},7,()=>refreshes++);
 await flow.submit(fields);assert.ok(!flow.getSnapshot().error.includes('PRIVATE'));assert.equal(refreshes,0);
 assert.equal(flow.getSnapshot().uncertain,[409,503].includes(status));if(flow.getSnapshot().uncertain){await flow.submit(fields);assert.equal(calls,1);}
});
test('network or foreign/approved responses remain uncertain and never confirm submission',async()=>{
 for(const operation of [async()=>{throw Error('PRIVATE');},async()=>({...pending(),driver_user_id:99}),async()=>driverFixtures().profile]){
  let refreshes=0;const flow=createDriverProfileSubmission(operation,7,()=>refreshes++);await flow.submit(fields);assert.equal(refreshes,0);assert.equal(flow.getSnapshot().uncertain,true);assert.ok(!flow.getSnapshot().error.includes('PRIVATE'));
 }
});
test('invalid fields never dispatch; disposed sessions ignore late confirmation',async()=>{
 let calls=0,refreshes=0,resolve;const flow=createDriverProfileSubmission(()=>{calls++;return new Promise(done=>resolve=done);},7,()=>refreshes++);
 for(const vehicle_type of ['',' ','x'.repeat(51),'van\nprivate'])await flow.submit({...fields,vehicle_type});assert.equal(calls,0);
 const work=flow.submit(fields);flow.dispose();resolve(pending());await work;assert.equal(refreshes,0);
});
