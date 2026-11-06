import {test} from 'node:test';
import assert from 'node:assert/strict';
import {parseAvailableJobs,parseAvailableJob,parseAssignment,createDriverJobsWorkflow} from '../src/utils/driverJobs.js';
import {jobFixture,jobPage,assignmentFixture,jobsApi} from './fixtures/driverJobsFixtures.js';
import {driverFixtures} from './fixtures/driverDashboardFixtures.js';
test('job pages and details reject foreign identity, wrong page, duplicate or private fields',()=>{
 const row={...jobFixture(),phone:'private',fee:'999.00',vehicle_requirement:'unsupported'};
 const parsed=parseAvailableJobs(jobPage(2,[row],12),7,2);assert.equal(parsed.total,12);assert.equal(parsed.items[0].phone,undefined);assert.equal(parsed.items[0].fee,undefined);
 assert.throws(()=>parseAvailableJobs(jobPage(),8,1));assert.throws(()=>parseAvailableJobs(jobPage(),7,2));assert.throws(()=>parseAvailableJobs(jobPage(1,[row,row]),7,1));
 assert.throws(()=>parseAvailableJob({driver_user_id:7,job:row},7,99));assert.equal(parseAvailableJob({driver_user_id:7,job:row},7,31).reference,'DR-job-31');
});
test('assignment requires exact authenticated identity, requested job and confirmed status',()=>{
 assert.equal(parseAssignment(assignmentFixture(),7,31).assignment_id,101);
 assert.throws(()=>parseAssignment(assignmentFixture(),8,31));assert.throws(()=>parseAssignment(assignmentFixture(),7,32));
 const cancelled=assignmentFixture();cancelled.delivery.status='cancelled';assert.throws(()=>parseAssignment(cancelled,7,31));assert.equal(parseAssignment(cancelled,7,31,true).delivery.status,'cancelled');
});
test('loading and successful acceptance use server confirmation and refresh dashboard/My Deliveries',async()=>{
 const api=jobsApi(),reader=createDriverJobsWorkflow(api,7);await reader.start();assert.equal(reader.getSnapshot().jobs.data.total,1);await reader.accept(31);
 assert.equal(reader.getSnapshot().acceptance.phase,'confirmed');assert.equal(reader.getSnapshot().jobs.data.total,0);assert.equal(reader.getSnapshot().summary.data.active_deliveries_count,3);assert.equal(reader.getSnapshot().assigned.data.total,3);assert.ok(api.calls.includes('assigned'));assert.equal(reader.getSnapshot().detail.data,null);
});
test('duplicate clicks submit once while waiting for backend confirmation',async()=>{
 const api=jobsApi();let resolve,count=0;api.accept=()=>{count++;return new Promise(r=>resolve=r);};const reader=createDriverJobsWorkflow(api,7);await reader.start();const one=reader.accept(31),two=reader.accept(31);
 assert.equal(count,1);assert.equal(reader.getSnapshot().acceptance.phase,'submitting');assert.equal(reader.getSnapshot().acceptance.confirmed,null);resolve(assignmentFixture());await Promise.all([one,two]);assert.equal(count,1);
});
test('409 conflict refreshes jobs without claiming assignment',async()=>{
 const api=jobsApi();let conflict=false;api.accept=async()=>{conflict=true;throw {response:{status:409,data:{detail:'secret'}}};};api.jobs=async page=>jobPage(page,conflict?[]:[jobFixture()]);const reader=createDriverJobsWorkflow(api,7);await reader.start();await reader.accept(31);
 assert.equal(reader.getSnapshot().acceptance.phase,'conflict');assert.equal(reader.getSnapshot().acceptance.confirmed,null);assert.equal(reader.getSnapshot().jobs.data.total,0);assert.ok(!reader.getSnapshot().acceptance.error.includes('secret'));
});
test('uncertain network response blocks other jobs and retries the same job safely',async()=>{
 const api=jobsApi();let attempts=0;api.accept=async()=>{if(++attempts===1)throw Error('private network failure');return assignmentFixture();};const reader=createDriverJobsWorkflow(api,7);await reader.start();await reader.accept(31);
 assert.equal(reader.getSnapshot().acceptance.phase,'uncertain');await reader.accept(32);assert.equal(attempts,1);const page=reader.getSnapshot().page;await reader.page(2);assert.equal(reader.getSnapshot().page,page);await reader.accept(31);assert.equal(attempts,2);assert.equal(reader.getSnapshot().acceptance.phase,'confirmed');
});
test('an assignment check 404 remains uncertain because the first request may still commit',async()=>{
 const api=jobsApi();api.accept=async()=>{throw {response:{status:503}};};api.assignment=async()=>{throw {response:{status:404}};};const reader=createDriverJobsWorkflow(api,7);await reader.start();await reader.accept(31);await reader.checkAssignment();assert.equal(reader.getSnapshot().acceptance.phase,'uncertain');assert.match(reader.getSnapshot().acceptance.error,/may still be processing/);
 api.assignment=async()=>assignmentFixture();await reader.checkAssignment();assert.equal(reader.getSnapshot().acceptance.phase,'confirmed');
});
test('malformed acceptance cannot become a success notification',async()=>{
 const api=jobsApi();api.accept=async()=>({...assignmentFixture(),driver_user_id:8});const reader=createDriverJobsWorkflow(api,7);await reader.start();await reader.accept(31);assert.equal(reader.getSnapshot().acceptance.phase,'uncertain');assert.equal(reader.getSnapshot().acceptance.confirmed,null);
});
for(const status of ['pending','rejected','suspended'])test(status+' driver does not fetch or accept available jobs',async()=>{
 const api=jobsApi();let jobCalls=0,acceptCalls=0;api.profile=async()=>({...driverFixtures().profile,approval_status:status,eligible_for_jobs:false,eligibility_reason:'approval_'+status});api.jobs=async()=>{jobCalls++;return jobPage();};api.accept=async()=>{acceptCalls++;};const reader=createDriverJobsWorkflow(api,7);await reader.start();await reader.accept(31);assert.equal(jobCalls,0);assert.equal(acceptCalls,0);assert.equal(reader.getSnapshot().jobs.data,null);
});
for(const status of [401,403])test('acceptance '+status+' clears data and uses safe access feedback',async()=>{
 const api=jobsApi();api.accept=async()=>{throw {response:{status,data:{detail:'private'}}};};const reader=createDriverJobsWorkflow(api,7);await reader.start();await reader.accept(31);assert.ok(reader.getSnapshot().authError);assert.equal(reader.getSnapshot().jobs.data,null);assert.equal(reader.getSnapshot().acceptance.confirmed,null);
});
test('partial summary failure keeps authorized jobs and permits section recovery',async()=>{
 const api=jobsApi();api.summary=async()=>{throw Error('offline');};const reader=createDriverJobsWorkflow(api,7);await reader.start();assert.equal(reader.getSnapshot().jobs.data.total,1);assert.equal(reader.getSnapshot().summary.data,null);assert.ok(reader.getSnapshot().summary.error);
});
test('page and detail replacement ignore superseded responses',async()=>{
 const api=jobsApi(),requests=[];const reader=createDriverJobsWorkflow(api,7);await reader.start();api.jobs=(page,{signal})=>new Promise(resolve=>requests.push({page,signal,resolve}));const a=reader.page(2),b=reader.page(3);assert.equal(requests[0].signal.aborted,true);requests[1].resolve(jobPage(3,[],30));await b;requests[0].resolve(jobPage(2,[jobFixture()],30));await a;assert.equal(reader.getSnapshot().page,3);assert.deepEqual(reader.getSnapshot().jobs.data.items,[]);
});
test('disposing while acceptance is in flight suppresses late confirmation and refreshes',async()=>{
 const api=jobsApi();let resolve;api.accept=()=>new Promise(r=>resolve=r);const reader=createDriverJobsWorkflow(api,7);await reader.start();const pending=reader.accept(31);reader.dispose();resolve(assignmentFixture());await pending;assert.equal(reader.getSnapshot().acceptance.confirmed,null);assert.ok(!api.calls.includes('assigned'));
});
