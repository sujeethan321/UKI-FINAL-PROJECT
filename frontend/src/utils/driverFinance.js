export const financeLabels={pending:'Pending earning',collection_declared:'Collection declared',directly_settled:'Directly settled',
 exception_review:'Exception review',disputed:'Disputed',reversed:'Refund/reversal pending',refund_pending:'Refund/reversal pending',refund_confirmed:'Refund confirmed',no_fee_due:'No fee due'};
const amount=value=>typeof value==='string'&&/^\d{1,20}\.\d{2}$/.test(value);
export function parseEarnings(data,driverId){
 if(data?.driver_user_id!==driverId||data.currency!=='LKR'||!Number.isSafeInteger(data.total)||data.total<0||
 !Number.isSafeInteger(data.page)||data.page<1||!Number.isSafeInteger(data.page_size)||data.page_size<1||data.page_size>50||
 !Array.isArray(data.earnings)||data.earnings.length>Math.min(data.page_size,data.total)||!data.summary||data.summary.platform_payout_supported!==false||
 !['pending','declared','directly_settled','review','total_earned','available','platform_paid'].every(k=>amount(data.summary[k]))||
 data.summary.available!=='0.00'||data.summary.platform_paid!=='0.00'||!Array.isArray(data.daily)||data.daily.length>30)throw Error('Unverified finance response');
 const seen=new Set();
 for(const row of data.earnings){
  if(row.driver_user_id!==driverId||typeof row.earning_id!=='string'||seen.has(row.earning_id)||!Object.hasOwn(financeLabels,row.status)||
   !amount(row.amount)||row.platform_payout_supported!==false||typeof row.collection_verified!=='boolean'||typeof row.directly_settled!=='boolean'||
   !Array.isArray(row.collections)||!Array.isArray(row.settlement_events)||!row.created_at)throw Error('Unverified earning');
  if(row.directly_settled!==(row.status==='directly_settled')||(row.directly_settled&&!row.collection_verified)||
    (row.status==='collection_declared'&&row.collection_verified))throw Error('Unverified settlement status');
  seen.add(row.earning_id);
  const stamp=value=>typeof value==='string'&&/^\d{4}-\d{2}-\d{2}T/.test(value)&&Number.isFinite(Date.parse(value));
  if(!stamp(row.created_at)||row.collections.some(e=>!['declared','exception'].includes(e.kind)||typeof e.collection_id!=='string'||!amount(e.amount)||!stamp(e.created_at))||
    row.settlement_events.some(e=>!['direct_settled','disputed','reversed','refund_confirmed'].includes(e.kind)||typeof e.event_id!=='string'||!amount(e.amount)||!stamp(e.created_at)))throw Error('Unverified financial event');
 }
 if(data.daily.some(r=>!/^\d{4}-\d{2}-\d{2}$/.test(r.date)||!amount(r.earned)))throw Error('Unverified trend');
 return data;
}
