import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createElement as h} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {MemoryRouter,Routes,Route} from 'react-router-dom';
import {createServer} from 'vite';
import {readFile} from 'node:fs/promises';
import {driverFixtures} from './fixtures/driverDashboardFixtures.js';
import {jobFixture,assignmentFixture} from './fixtures/driverJobsFixtures.js';
const section=data=>({data,loading:false,error:''});
const ready=()=>({authError:'',page:1,profile:section(driverFixtures().profile),summary:section(driverFixtures().summary),jobs:section({total:1,items:[jobFixture()]}),assigned:section(null),detail:{...section(null),jobId:null},acceptance:{phase:'idle',jobId:null,error:'',confirmed:null}});
const actions={refresh(){},details(){},accept(){},page(){},closeDetails(){},retryJobs(){},checkAssignment(){}};
test('Available Jobs React view, routes and real authenticated API contracts',async t=>{
 const server=await createServer({logLevel:'silent',appType:'custom',server:{middlewareMode:true,hmr:false}});
 try{
 const {default:Page,AvailableJobsView,JobInformation}=await server.ssrLoadModule('/src/pages/driver/AvailableJobs.jsx');
 const {AuthContext}=await server.ssrLoadModule('/src/context/AuthContext.jsx'),{default:Guard}=await server.ssrLoadModule('/src/routes/ProtectedRoute.jsx');
 const render=(state=ready())=>renderToStaticMarkup(h(MemoryRouter,null,h(AvailableJobsView,{state,actions})));
 await t.test('authorized jobs render actual areas, business, reference, count and controls',()=>{
 const html=render();for(const value of ['Available Delivery Jobs','DR-job-31','Requesting shop','Pickup district','Destination district','View Details','Accept Job','Page 1','1 jobs'])assert.ok(html.includes(value),value);
 assert.ok(!html.includes('LKR'));assert.ok(!html.includes('Earnings'));
 });
 await t.test('details expose supported fields without inventing requirements or fees',()=>{
 const state=ready();state.detail={...section(jobFixture()),jobId:31};const html=render(state);assert.ok(html.includes('Delivery Job Details'));assert.ok(html.includes('Close details'));assert.ok(html.includes('2026-11-06 10:00:00 UTC'));
 const unsupported=renderToStaticMarkup(h(JobInformation,{job:{...jobFixture(),phone:'PRIVATE',vehicle_requirement:'UNSUPPORTED',fee:'999.00'}}));for(const value of ['PRIVATE','UNSUPPORTED','999.00'])assert.ok(!unsupported.includes(value));
 });
 await t.test('loading, empty and unavailable jobs remain distinct',()=>{
 const state=ready();state.jobs={data:null,loading:true,error:''};assert.ok(render(state).includes('Loading available jobs...'));assert.ok(!render(state).includes('No available delivery jobs'));
 state.jobs=section({total:0,items:[]});assert.ok(render(state).includes('No available delivery jobs right now.'));
 state.jobs={data:null,loading:false,error:'Service unavailable'};assert.ok(render(state).includes('Retry available jobs'));
 });
 await t.test('pending and suspended profiles have no acceptance controls',()=>{
 for(const status of ['pending','suspended']){const state=ready();state.profile.data={...state.profile.data,approval_status:status,eligible_for_jobs:false,eligibility_reason:'approval_'+status};const html=render(state);assert.ok(!html.includes('Accept Job'));assert.ok(html.includes(status==='pending'?'pending review':'eligibility is suspended'));}
 });
 await t.test('submission, conflict and unconfirmed retries never claim success',()=>{
 for(const phase of ['submitting','uncertain','conflict']){const state=ready();state.acceptance={phase,jobId:31,error:phase==='submitting'?'':'Assignment not confirmed',confirmed:null};const html=render(state);assert.ok(!html.includes('Assignment confirmed'));if(phase==='submitting'){assert.ok(html.includes('Confirming this job assignment'));assert.ok(html.includes('disabled'));}if(phase==='uncertain'){assert.ok(html.includes('Retry this job acceptance'));assert.ok(html.includes('Check my assignment'));}}
 });
 await t.test('confirmed assignment links to existing My Deliveries; access loss hides all job details',()=>{
 const state=ready();state.acceptance={phase:'confirmed',jobId:31,error:'',confirmed:assignmentFixture()};const html=render(state);assert.ok(html.includes('Assignment confirmed'));assert.ok(html.includes('href="/driver/deliveries"'));
 state.authError='Your session has expired.';const denied=render(state);assert.ok(denied.includes('expired'));assert.ok(!denied.includes('DR-job-31'));
 });
 await t.test('route is Driver-only and ordinary other roles cannot render it',()=>{
 const auth={isAuthenticated:true,loading:false,token:'fixture',user:{user_id:7,platform_role:'driver',account_status:'active'}};
 const route=value=>renderToStaticMarkup(h(MemoryRouter,{initialEntries:['/driver/jobs']},h(AuthContext.Provider,{value},h(Routes,null,h(Route,{element:h(Guard,{allowedRoles:['driver']})},h(Route,{path:'/driver/jobs',element:h(Page)}))))));
 assert.ok(route(auth).includes('Available Delivery Jobs'));for(const role of ['customer','shop_owner','admin'])assert.ok(!route({...auth,user:{...auth.user,platform_role:role}}).includes('Available Delivery Jobs'));assert.ok(!route({...auth,isAuthenticated:false}).includes('Available Delivery Jobs'));
 });
 await t.test('shared Axios sends bounded reads, empty acceptance body, JWT and cancellation',async()=>{
 const {default:api}=await server.ssrLoadModule('/src/services/api.js'),service=await server.ssrLoadModule('/src/services/driverJobsService.js');const previous=api.defaults.adapter,storage=globalThis.sessionStorage,calls=[];globalThis.sessionStorage={getItem:()=> 'fixture'};api.defaults.adapter=async config=>{calls.push(config);return {data:{},status:200,statusText:'OK',headers:{},config};};
 try{const signal=new AbortController().signal;await service.getAvailableJobs(2,{signal});await service.getAvailableJob(31,{signal});await service.acceptDriverJob(31,{signal});await service.getAssignedDelivery(31,{signal});assert.deepEqual(calls.map(c=>c.url),['/driver/jobs','/driver/jobs/31','/driver/jobs/31/accept','/driver/deliveries/31']);assert.deepEqual(calls[0].params,{page:2,page_size:10});assert.equal(calls[2].method,'post');assert.equal(calls[2].data,'{}');for(const call of calls){assert.equal(call.headers.Authorization,'Bearer fixture');assert.equal(call.signal,signal);}
 }finally{api.defaults.adapter=previous;if(storage===undefined)delete globalThis.sessionStorage;else globalThis.sessionStorage=storage;}
 });
 await t.test('functional route/navigation and mobile wrapping use existing patterns',async()=>{
 const app=await readFile(new URL('../src/App.jsx',import.meta.url),'utf8');assert.ok(app.includes('path="/driver/jobs" element={<AvailableJobs />}'));
 const sidebar=await readFile(new URL('../src/components/driver/DriverSidebar.jsx',import.meta.url),'utf8');assert.ok(sidebar.includes('to="/driver/jobs"'));
 const source=await readFile(new URL('../src/pages/driver/AvailableJobs.jsx',import.meta.url),'utf8');for(const value of ['xl:grid-cols-2','min-w-0','overflow-wrap:anywhere','focus-visible:outline','flex-wrap'])assert.ok(source.includes(value));
 });
 }finally{await server.close();}
});
