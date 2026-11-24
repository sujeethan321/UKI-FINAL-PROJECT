export function adminReportFixture(){
  return {total:1,limit:20,offset:0,rows:[{business_id:10,business_name:'Fictional Shop',approval_status:'approved',orders:1,product_order_total:'100.00',credit_sales:'100.00',repayments:'25.00',outstanding:'75.00',advances:'10.00'}],report:{
    generated_at:'2026-11-23T10:00:00Z',database_today:'2026-11-23',start_date:'2026-11-01',end_date:'2026-11-03',business_id:null,approval_status:null,order_status:null,snapshot:'mysql_repeatable_read',
    reporting_clocks:{registrations_approvals_credit:'database_wall_clock',orders_deliveries:'UTC'},coverage:{status:'complete_within_bounds',businesses:1},limitations:['Current balances and statuses are not historical period-end positions.'],
    unavailable:{driver_finance:'not_enabled',platform_revenue:'no_verified_revenue_dataset',cash_collected:'order_state_does_not_verify_collection'},
    businesses:{counts:{current_total:1,registered_in_period:1,current_approved:1},amounts:{},daily:[{date:'2026-11-01',count:1}]},
    users:{counts:{registered_in_period:1,customer:1},amounts:{},daily:[]},orders:{counts:{created_in_period:1,cash:1},amounts:{product_order_total:'100.00'},daily:[]},
    deliveries:{counts:{created_in_period:0,completed_in_period:0},amounts:{},daily:[]},credit:{counts:{accounts:2},amounts:{credit_sales:'100.00',repayments:'25.00',current_outstanding:'75.00',current_advances:'10.00'},daily:[{date:'2026-11-01',credit_sales:'100.00',repayments:'-25.00'}]}
  }};
}
