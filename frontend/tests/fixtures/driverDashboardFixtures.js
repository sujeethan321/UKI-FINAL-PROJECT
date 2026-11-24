export const driverFixtures=()=>({
 profile:{driver_user_id:7,full_name:'Driver A',account_status:'active',approval_status:'approved',eligible_for_jobs:true,eligibility_reason:'eligible',vehicle:{vehicle_type:'van',registration_reference:'TEST-123'}},
 summary:{driver_user_id:7,available_jobs_count:3,active_deliveries_count:2,completed_deliveries_count:4},
 deliveries:{driver_user_id:7,total:2,page:1,page_size:5,deliveries:[{delivery_request_id:11,reference:'DR-test-one',business_name:'Assigned shop',pickup_area:'Pickup area',delivery_area:'Delivery area',status:'assigned',assigned_at:'2026-11-06T10:00:00'},{delivery_request_id:12,reference:'DR-test-two',business_name:'Another assigned shop',pickup_area:'Second pickup',delivery_area:'Second destination',status:'in_transit',assigned_at:'2026-11-06T09:00:00'}]},
});
