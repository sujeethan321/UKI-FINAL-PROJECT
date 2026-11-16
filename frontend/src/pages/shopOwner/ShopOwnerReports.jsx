import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import { BarChart3, Download } from 'lucide-react';
import OverviewCards from '../../components/shopOwner/OverviewCards';
import { getShopOwnerDashboardSummary } from '../../services/shopOwnerDashboardService';

export function ShopOwnerReportsView({businesses=[], businessId, onBusiness, summary, loading, error}) {
  return <div className="space-y-5"><div className="flex flex-wrap items-start justify-between gap-4"><div className="owner-page-heading"><h2>Business Reports</h2><p>Understand your shop's credit activity and outstanding balances.</p></div><button type="button" disabled title="Period report export is not available" className="inline-flex items-center gap-2 rounded-lg border border-[#DAE5F3] bg-white px-4 py-3 text-sm text-[#64748B]"><Download size={18}/>Export Report unavailable</button></div>
    <label className="block text-sm font-semibold">Business<select className="mt-2 block max-w-full rounded-lg border border-[#DAE5F3] bg-white px-3 py-2" value={businessId || ''} onChange={e=>onBusiness(Number(e.target.value))}><option value="">Select an approved business</option>{businesses.map(b=><option key={b.business_id} value={b.business_id} disabled={b.approval_status!=='approved'}>{b.business_name}</option>)}</select></label>
    <section className="rounded-xl border border-[#E1EAF4] bg-white p-5"><h3 className="mb-2 text-xl font-bold">Financial Overview</h3><p className="mb-5 text-sm text-[#52698A]">Current dashboard figures. Date-range reporting is not available.</p>{loading&&<p role="status">Loading financial overview...</p>}{error&&<p role="alert" className="mb-4 text-sm text-[#DC4545]">{error}</p>}<OverviewCards summary={summary}/></section>
    <div className="grid gap-4 lg:grid-cols-2">{['Credit Sales Trend','Repayment Trend'].map(title=><section key={title} className="rounded-xl border border-[#E1EAF4] bg-white p-5"><h3 className="text-xl font-bold">{title}</h3><div className="owner-unavailable mt-4 flex min-h-48 flex-col items-center justify-center gap-4 text-center"><BarChart3 size={35} aria-hidden="true"/><p>Period totals are not available from the current reporting service.</p></div></section>)}</div>
    <section className="rounded-xl border border-[#E1EAF4] bg-white p-5"><h3 className="text-xl font-bold">Outstanding Credit Aging</h3><div className="owner-unavailable mt-4">Aging buckets are not available. View individual customer ledgers for recorded balances.</div></section>
  </div>;
}
export default function ShopOwnerReports() {
  const {businesses=[]}=useOutletContext() || {};
  const [selected,setSelected]=useState(null);
  const business=businesses.find(b=>b.business_id===selected) || businesses.find(b=>b.approval_status==='approved');
  const businessId=business?.business_id;
  const [result,setResult]=useState({id:null,data:null,error:''});
  useEffect(()=>{
    if(!businessId || business.approval_status!=='approved')return;
    let active=true;
    getShopOwnerDashboardSummary(businessId).then(data=>{if(active)setResult({id:businessId,data,error:''});}).catch(()=>{if(active)setResult({id:businessId,data:null,error:'Financial overview is unavailable. Refresh the page to retry.'});});
    return()=>{active=false;};
  },[businessId,business?.approval_status]);
  const current=result.id===businessId;
  return <ShopOwnerReportsView businesses={businesses} businessId={businessId} onBusiness={setSelected} summary={current?result.data:null} loading={!!businessId&&!current} error={current?result.error:''}/>;
}
