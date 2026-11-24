export const sections=['businesses','users','orders','deliveries','credit'];
export const metricLabels={
 current_total:'Current businesses',registered_in_period:'Registrations in period',current_pending:'Currently pending',current_approved:'Currently approved',current_rejected:'Currently rejected',current_suspended:'Currently suspended',approved_in_period:'Approval decisions in period',rejected_in_period:'Rejection decisions in period',
 shop_customer_profiles_in_period:'Shop customer profiles in period',shop_owner:'Shop Owners',customer:'Customers',driver:'Delivery Drivers',current_active:'Currently active',created_in_period:'Created in period',submitted:'Submitted',approved:'Approved',rejected:'Rejected',processing:'Processing',completed:'Completed',cancelled:'Cancelled',cash:'Cash orders',credit:'Credit orders',
 product_order_total:'Product order value',non_cancelled_product_total:'Non-cancelled product order value',cancelled_rejected_product_total:'Cancelled / rejected product order value',current_available:'Currently available',current_assigned:'Currently assigned',current_picked_up:'Currently picked up',current_in_transit:'Currently in transit',current_delivered:'Currently delivered',current_cancelled:'Currently cancelled',assigned_in_period:'Assigned in period',completed_in_period:'Completed in period',cancelled_in_period:'Cancelled in period',accounts:'Credit accounts',credit_sales:'Net credit sales',repayments:'Net repayments',current_outstanding:'Current outstanding',current_advances:'Current advances',outstanding:'Current outstanding',advances:'Current advances',orders:'Orders',business_id:'Business ID',business_name:'Business',approval_status:'Approval status'
};
export const sectionLabels={businesses:'Business registrations and approvals',users:'User registrations (platform-wide)',orders:'Orders (created in period; current status)',deliveries:'Delivery activity',credit:'Credit movements and current balances'};
const integer=value=>Number.isSafeInteger(value)&&value>=0;
const date=value=>typeof value==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value)&&Number.isFinite(Date.parse(value+'T00:00:00Z'));
const money=value=>typeof value==='string'&&/^-?\d+\.\d{2}$/.test(value);
const text=value=>typeof value==='string'&&value.length<=1000;
const record=value=>value&&typeof value==='object'&&!Array.isArray(value);
function assert(valid){if(!valid)throw Error('Invalid Admin report');}
export function parseAdminReport(raw){
  assert(record(raw)&&record(raw.report)&&integer(raw.total)&&raw.total<=1000&&integer(raw.offset)&&integer(raw.limit)&&raw.limit>=1&&raw.limit<=100&&Array.isArray(raw.rows)&&raw.rows.length<=raw.limit);
  const r=raw.report;
  assert(date(r.start_date)&&date(r.end_date)&&date(r.database_today)&&r.start_date<=r.end_date&&text(r.generated_at)&&Number.isFinite(Date.parse(r.generated_at)));
  assert((Date.parse(r.end_date)-Date.parse(r.start_date))/86400000<366);
  assert(['mysql_repeatable_read','sqlite_offline_test'].includes(r.snapshot));
  const report={start_date:r.start_date,end_date:r.end_date,database_today:r.database_today,generated_at:r.generated_at,snapshot:r.snapshot};
  assert(r.business_id==null||(integer(r.business_id)&&r.business_id>0));
  assert(r.approval_status==null||['pending','approved','rejected','suspended'].includes(r.approval_status));
  assert(r.order_status==null||['submitted','approved','rejected','processing','completed','cancelled'].includes(r.order_status));
  for(const key of ['business_id','approval_status','order_status'])report[key]=r[key]??null;
  for(const key of ['coverage','reporting_clocks','unavailable']){
    assert(record(r[key]));report[key]={};
    for(const [name,value] of Object.entries(r[key])){assert(text(name)&&(text(value)||integer(value)));report[key][name]=value;}
  }
  assert(Array.isArray(r.limitations)&&r.limitations.length<=20&&r.limitations.every(text));report.limitations=[...r.limitations];
  for(const section of sections){
    const source=r[section];assert(record(source)&&record(source.counts)&&record(source.amounts)&&Array.isArray(source.daily)&&source.daily.length<=366);
    const domain={counts:{},amounts:{},daily:[]};
    for(const [key,value] of Object.entries(source.counts)){assert(Object.hasOwn(metricLabels,key)&&integer(value));domain.counts[key]=value;}
    for(const [key,value] of Object.entries(source.amounts)){assert(Object.hasOwn(metricLabels,key)&&money(value));domain.amounts[key]=value;}
    domain.daily=source.daily.map(day=>{
      assert(record(day)&&date(day.date));
      if(section==='credit'){assert(money(day.credit_sales)&&money(day.repayments));return {date:day.date,credit_sales:day.credit_sales,repayments:day.repayments};}
      assert(integer(day.count));return {date:day.date,count:day.count};
    }); report[section]=domain;
  }
  assert(integer(report.businesses.counts.current_total)&&integer(report.orders.counts.created_in_period)&&money(report.credit.amounts.current_outstanding)&&money(report.credit.amounts.current_advances));
  const seen=new Set();const rows=raw.rows.map(row=>{
    assert(record(row)&&integer(row.business_id)&&row.business_id>0&&!seen.has(row.business_id)&&text(row.business_name)&&text(row.approval_status)&&integer(row.orders));seen.add(row.business_id);
    const clean={business_id:row.business_id,business_name:row.business_name,approval_status:row.approval_status,orders:row.orders};
    for(const key of ['product_order_total','credit_sales','repayments','outstanding','advances']){assert(money(row[key]));clean[key]=row[key];}return clean;
  });
  return {report,rows,total:raw.total,limit:raw.limit,offset:raw.offset};
}
export function reportError(error){
  const status=error?.response?.status;
  return status===401?'Session expired. Please sign in again.':status===403?'Admin Reports access denied.':status===422?'Report exceeds limits or filters are invalid.':status===429?'Too many report requests. Please wait.':'Admin Reports unavailable. Try again.';
}
export function createAdminReports(request,exportRequest,save){
  let controller=null,exportController=null,disposed=false,version=0;
  let state={loading:false,error:'',data:null,selection:null,exporting:false,exportError:''};const listeners=new Set();
  const update=patch=>{if(disposed)return;state={...state,...patch};for(const fn of listeners)fn();};
  const clear=()=>{version++;controller?.abort();exportController?.abort();controller=null;exportController=null;};
  return {
    subscribe:fn=>{listeners.add(fn);return()=>listeners.delete(fn);},getSnapshot:()=>state,
    start(selection={}){disposed=false;return this.load(selection);},
    async load(selection={}){
      if(disposed)return;clear();const active=new AbortController();controller=active;const generation=version;
      update({loading:true,error:'',data:null,selection:null,exporting:false,exportError:''});
      try{
        const data=parseAdminReport(await request(selection,active.signal));
        if(disposed||active.signal.aborted||generation!==version)return;
        for(const key of ['business_id','approval_status','order_status','start_date','end_date']){
          if(selection[key]!==undefined&&selection[key]!==null&&selection[key]!=='')assert(String(data.report[key])===String(selection[key]));
        }
        update({loading:false,data,selection:{...selection,start_date:data.report.start_date,end_date:data.report.end_date}});
      }catch(error){if(!disposed&&!active.signal.aborted&&generation===version)update({loading:false,error:reportError(error),data:null,selection:null});}
    },
    async download(format,language){
      if(disposed||!state.data||state.loading||state.exporting)return;
      const active=new AbortController();exportController=active;const generation=version;const selection={...state.selection};
      update({exporting:true,exportError:''});
      try{
        if(!['csv','pdf'].includes(format)||!['en','ta','si'].includes(language))throw Error('Invalid export');
        const blob=await exportRequest(selection,format,language,active.signal);
        if(disposed||active.signal.aborted||generation!==version)return;
        save(blob,`LankaPex-admin-${selection.start_date}-${selection.end_date}-${language}.${format}`);update({exporting:false});
      }catch(error){if(!disposed&&!active.signal.aborted&&generation===version){
        const denied=[401,403].includes(error?.response?.status);
        update({exporting:false,exportError:reportError(error),...(denied?{data:null,selection:null,error:reportError(error)}:{})});
      }}
    },
    dispose(){clear();state={loading:false,error:'',data:null,selection:null,exporting:false,exportError:''};listeners.clear();disposed=true;}
  };
}
