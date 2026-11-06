export const deliveryFixture=(changes={})=>({delivery_request_id:31,reference:'DR-shop-31',business_id:1,pickup_area:'Pickup area',delivery_area:'Destination area',status:'available',created_at:'2026-11-06T10:00:00',updated_at:'2026-11-06T10:00:00',...changes});
export const deliveryDetail=(changes={})=>({...deliveryFixture(),assigned_driver:null,events:[],can_cancel:true,...changes});
export const businessFixture=()=>({user_id:7,full_name:'Shop Owner',has_business:true,businesses:[{business_id:1,business_name:'Shop One',approval_status:'approved'},{business_id:2,business_name:'Shop Two',approval_status:'approved'},{business_id:3,business_name:'Pending Shop',approval_status:'pending'}]});
export const summaryFixture=(changes={})=>({business_id:1,total_requests_count:1,available_requests_count:1,in_progress_count:0,completed_count:0,...changes});
export const pageFixture=(changes={})=>({business_id:1,total:1,page:1,page_size:10,deliveries:[deliveryFixture()],...changes});
export function intentFixture(){const pending=new Set();return {read:id=>pending.has(id),mark:id=>pending.add(id),clear:id=>pending.delete(id)};}
export function ownerDeliveryApi(){let record=deliveryDetail();const calls=[];return {calls,
  businesses:async()=>businessFixture(),
  list:async(businessId,{page,status})=>{calls.push(['list',businessId,page,status]);const rows=record.business_id===businessId&&(!status||record.status===status)?[record]:[];return pageFixture({business_id:businessId,page,total:rows.length,deliveries:rows});},
  summary:async businessId=>{calls.push(['summary',businessId]);return summaryFixture({business_id:businessId,total_requests_count:1,available_requests_count:record.status==='available'?1:0});},
  detail:async(businessId,id)=>{calls.push(['detail',businessId,id]);return {...record,business_id:businessId,delivery_request_id:id};},
  create:async(businessId,payload)=>{calls.push(['create',businessId,payload]);record=deliveryDetail({...payload,business_id:businessId});return record;},
  cancel:async(businessId,id)=>{calls.push(['cancel',businessId,id]);record=deliveryDetail({business_id:businessId,delivery_request_id:id,status:'cancelled',can_cancel:false,events:[{status:'cancelled',occurred_at:'2026-11-06T11:00:00'}]});return record;},
};}
