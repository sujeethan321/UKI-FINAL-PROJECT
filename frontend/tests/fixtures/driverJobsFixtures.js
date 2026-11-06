import {driverFixtures} from './driverDashboardFixtures.js';
export const jobFixture=(patch={})=>({delivery_request_id:31,reference:'DR-job-31',business_name:'Requesting shop',pickup_area:'Pickup district',delivery_area:'Destination district',status:'available',created_at:'2026-11-06T10:00:00',...patch});
export const jobPage=(page=1,items=[jobFixture()],total=items.length)=>({driver_user_id:7,page,page_size:10,total,jobs:items});
export const assignmentFixture=()=>({driver_user_id:7,assignment_id:101,delivery:{delivery_request_id:31,reference:'DR-job-31',business_name:'Requesting shop',pickup_area:'Pickup district',delivery_area:'Destination district',status:'assigned',assigned_at:'2026-11-06T10:30:00'}});
export function jobsApi(){let accepted=false;const calls=[];const api={
 calls,profile:async()=>driverFixtures().profile,
 summary:async()=>{calls.push('summary');return {...driverFixtures().summary,available_jobs_count:accepted?0:1,active_deliveries_count:accepted?3:2};},
 jobs:async page=>{calls.push('jobs');return jobPage(page,accepted?[]:[jobFixture()]);},
 detail:async id=>({driver_user_id:7,job:jobFixture({delivery_request_id:id})}),
 accept:async()=>{calls.push('accept');accepted=true;return assignmentFixture();},
 assignment:async()=>assignmentFixture(),
 assigned:async()=>{calls.push('assigned');return {...driverFixtures().deliveries,total:3,deliveries:[assignmentFixture().delivery,...driverFixtures().deliveries.deliveries]};},
 };return api;
}
