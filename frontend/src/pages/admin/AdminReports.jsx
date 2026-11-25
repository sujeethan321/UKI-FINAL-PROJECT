// Purpose: Render the admin reports screen and connect its user interactions to shared application state and services.
import {useEffect,useState,useSyncExternalStore} from 'react';
import {RefreshCw,Download} from 'lucide-react';
import {useAuth} from '../../context/useAuth';
import {useAppTranslation} from '../../i18n/useAppTranslation';
import {getAdminReport,getAdminReportExport} from '../../services/adminReportsService';
import {createAdminReports,sections,sectionLabels,metricLabels} from '../../utils/adminReports';
import {saveReportCSV} from '../../utils/reportCSVExport';
import {money} from '../../utils/shopping';

const card='min-w-0 rounded-2xl border border-[#D4E2EE] bg-white p-5 shadow-sm sm:p-6';
const button='inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-[#D4E2EE] bg-white px-4 py-2 text-sm font-semibold text-[#10243E] hover:border-[#12B8A6] disabled:opacity-50';
const input='min-h-11 w-full rounded-lg border border-[#D4E2EE] bg-white px-3 text-sm text-[#10243E]';
const initial={start_date:'',end_date:'',business_id:'',approval_status:'',order_status:'',sort:'business_id',direction:'asc'};
// Build report query parameters from the applied business and date selection.
function parameters(filters,offset=0){return {...Object.fromEntries(Object.entries(filters).filter(([,value])=>value!=='')),limit:20,offset};}
// Format the validated report amount for display in LKR.
function currency(value){return (value.startsWith('-')?'− ':'')+money(value.replace(/^-/,''));}

// Render the admin reports view interface and connect its controls to the state and callbacks defined here.
export function AdminReportsView({state,actions}){
  const {tr,statusLabel}=useAppTranslation();const [filters,setFilters]=useState(initial);const [language,setLanguage]=useState('en');
  const data=state.data,r=data?.report;
  // Apply the user change to the current form or filter state.
  const change=(key,value)=>setFilters(previous=>({...previous,[key]:value}));
  return <div className="space-y-6 pb-6 text-[#10243E]">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><h2 className="text-2xl font-bold">{tr('Platform Reports')}</h2><p className="mt-2 text-sm text-[#64748B]">{tr('Read-only platform activity and credit reporting.')}</p></div><button className={button} disabled={state.loading} onClick={()=>actions.load(state.selection||parameters(filters))}><RefreshCw size={17}/>{tr('Refresh')}</button></div>
    <form className={card+' grid gap-4 sm:grid-cols-2 xl:grid-cols-4'} onSubmit={event=>{event.preventDefault();actions.load(parameters(filters));}}>
      {['start_date','end_date','business_id'].map(key=><label key={key} className="text-sm font-semibold">{tr({start_date:'Start date',end_date:'End date',business_id:'Business ID'}[key])}<input className={input+' mt-2'} type={key==='business_id'?'number':'date'} min={key==='business_id'?1:undefined} max={key==='business_id'?'9007199254740991':undefined} value={filters[key]} onChange={event=>change(key,event.target.value)}/></label>)}
      {[['approval_status','Business approval status',['pending','approved','rejected','suspended']],['order_status','Order status',['submitted','approved','rejected','processing','completed','cancelled']],['sort','Sort by',['business_id','orders','outstanding']],['direction','Sort direction',['asc','desc']]].map(([key,label,values])=><label key={key} className="text-sm font-semibold">{tr(label)}<select className={input+' mt-2'} value={filters[key]} onChange={event=>change(key,event.target.value)}>{key.endsWith('status')&&<option value="">{tr('All')}</option>}{values.map(value=><option key={value} value={value}>{value==='asc'?tr('Ascending'):value==='desc'?tr('Descending'):metricLabels[value]?tr(metricLabels[value]):statusLabel(value)}</option>)}</select></label>)}
      <button className={button+' self-end'} disabled={state.loading}>{tr('Apply filters')}</button>
      <p className="text-xs text-[#64748B] sm:col-span-2 xl:col-span-4">{tr('Default 30 days. Maximum 366 inclusive days. Current balances are independent of the selected period.')}</p>
    </form>
    {state.loading&&<p role="status">{tr('Loading Admin Reports…')}</p>}
    {state.error&&<p className={card} role="alert">{tr(state.error)}</p>}
    {r&&<>
      <section className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4" aria-label={tr('Report overview')}>
        {[['Businesses',String(r.businesses.counts.current_total)],['Orders',String(r.orders.counts.created_in_period)],['Current outstanding',money(r.credit.amounts.current_outstanding)],['Current advances',money(r.credit.amounts.current_advances)]].map(([label,value])=><article key={label} className={card}><h3 className="text-sm font-semibold">{tr(label)}</h3><p className="mt-4 break-words text-2xl font-bold">{value}</p></article>)}
      </section>
      <section className={card}><p>{tr('Applied period')}: {r.start_date} — {r.end_date}</p><p className="mt-2 text-sm">{tr('Generated at UTC')}: {r.generated_at}</p><p className="mt-2 text-sm">{tr('Database reporting day')}: {r.database_today}</p><p className="mt-2 text-sm">{tr('Registrations, approvals and credit use database wall clock. Orders and deliveries use UTC. No historical timestamp conversion.')}</p><p className="mt-2 text-sm">{tr('Coverage')}: {r.coverage.status} | {r.snapshot}</p>
        <div className="mt-4 flex flex-wrap gap-3"><select aria-label={tr('Export language')} className={input+' w-auto'} value={language} onChange={event=>setLanguage(event.target.value)}><option value="en">English</option><option value="ta">தமிழ்</option><option value="si">සිංහල</option></select>{['csv','pdf'].map(format=><button key={format} className={button} disabled={state.exporting||state.loading} onClick={()=>actions.download(format,language)}><Download size={16}/>{tr(format==='csv'?'Export CSV':'Export PDF')}</button>)}</div>
        {state.exporting&&<p role="status">{tr('Preparing export…')}</p>}{state.exportError&&<p role="alert">{tr(state.exportError)}</p>}
      </section>
      {sections.map(section=><section key={section} className={card}><h3 className="text-xl font-bold">{tr(sectionLabels[section])}</h3><dl className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">{Object.entries(r[section].counts).map(([key,value])=><div key={key}><dt className="text-sm text-[#64748B]">{tr(metricLabels[key])}</dt><dd className="mt-1 font-semibold">{value}</dd></div>)}{Object.entries(r[section].amounts).map(([key,value])=><div key={key}><dt className="text-sm text-[#64748B]">{tr(metricLabels[key])}</dt><dd className="mt-1 font-semibold">{currency(value)}</dd></div>)}</dl>
        {r[section].daily.length>0&&<details className="mt-4"><summary className="cursor-pointer text-sm font-semibold">{tr('Daily trends')}</summary><div className="mt-3 max-h-80 overflow-auto"><table className="w-full text-left text-sm"><thead><tr><th>{tr('Date')}</th>{section==='credit'?<><th>{tr('Net credit sales')}</th><th>{tr('Net repayments')}</th></>:<th>{tr('Count')}</th>}</tr></thead><tbody>{r[section].daily.map(day=><tr key={day.date} className="border-b border-[#D4E2EE]"><td className="py-2">{day.date}</td>{section==='credit'?<><td>{day.credit_sales}</td><td>{day.repayments}</td></>:<td>{day.count}</td>}</tr>)}</tbody></table></div></details>}
      </section>)}
      <section className={card}><h3 className="text-xl font-bold">{tr('Business comparisons')}</h3>{!data.rows.length?<p className="mt-4">{tr('No matching businesses.')}</p>:<div className="mt-4 overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr>{['business_name','approval_status','orders','product_order_total','credit_sales','repayments','outstanding','advances'].map(key=><th key={key} className="p-2">{tr(metricLabels[key])}</th>)}</tr></thead><tbody>{data.rows.map(row=><tr key={row.business_id} className="border-b border-[#D4E2EE]">{['business_name','approval_status','orders','product_order_total','credit_sales','repayments','outstanding','advances'].map(key=><td key={key} className="p-2">{key==='approval_status'?statusLabel(row[key]):row[key]}</td>)}</tr>)}</tbody></table></div>}<nav aria-label={tr('Business report pagination')} className="mt-4 flex flex-wrap items-center gap-3"><button className={button} disabled={state.loading||data.offset===0} onClick={()=>actions.load({...state.selection,offset:Math.max(0,data.offset-data.limit)})}>{tr('Previous')}</button><span>{data.rows.length?data.offset+1:0}–{data.offset+data.rows.length} / {data.total}</span><button className={button} disabled={state.loading||data.offset+data.limit>=data.total} onClick={()=>actions.load({...state.selection,offset:data.offset+data.limit})}>{tr('Next')}</button></nav><p className="mt-3 text-xs">{tr('Exports include all filtered business rows within the export limit.')}</p></section>
      <section className={card}><h3 className="text-xl font-bold">{tr('Unavailable metrics')}</h3>{Object.entries(r.unavailable).map(([key,reason])=><p key={key} className="mt-2 text-sm">{tr({driver_finance:'Driver Finance',platform_revenue:'Platform revenue',cash_collected:'Cash collected'}[key]||key)}: {tr('Unavailable')} ({tr(reason)})</p>)}<ul className="mt-4 list-disc space-y-2 pl-5 text-xs text-[#64748B]">{r.limitations.map(value=><li key={value}>{tr(value)}</li>)}</ul></section>
    </>}
  </div>;
}
// Render the session interface and connect its controls to the state and callbacks defined here.
function Session(){
  const [reader]=useState(()=>createAdminReports(getAdminReport,getAdminReportExport,saveReportCSV));
  const state=useSyncExternalStore(reader.subscribe,reader.getSnapshot,reader.getSnapshot);
  // Start resource work after rendering and cancel or dispose it during cleanup so obsolete work cannot update this view.
  useEffect(()=>{reader.start({limit:20,offset:0});return()=>reader.dispose();},[reader]);
  return <AdminReportsView state={state} actions={reader}/>;
}
// Render the admin reports interface and connect its controls to the state and callbacks defined here.
export default function AdminReports(){
  const {user,token,isAuthenticated}=useAuth();
  if(!isAuthenticated||user?.platform_role!=='admin'||user?.account_status!=='active')return null;
  return <Session key={user.user_id+':'+token}/>;
}
