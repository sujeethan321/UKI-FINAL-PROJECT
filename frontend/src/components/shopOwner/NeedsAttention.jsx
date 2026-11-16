import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { Link } from 'react-router-dom';
import { ClipboardList, Users, Truck, ArrowRight } from 'lucide-react';

export default function NeedsAttention({summary, businessId}) {
  const { tr } = useAppTranslation();
  const rows = [
    {label:'Pending Credit Requests', value:summary?.pending_credit_requests, path:'orders', icon:ClipboardList, tone:'text-[#C78513] bg-[#FFF6E5]'},
    {label:'Credit Customers', value:summary?.credit_customers, path:'customers', icon:Users, tone:'text-[#12B8A6] bg-[#E7F9F6]'},
    {label:'Active Deliveries', value:summary?.active_deliveries, path:'deliveries', icon:Truck, tone:'text-[#1676D2] bg-[#EAF6FF]'},
  ];
  return <section className="rounded-xl border border-[#E1EAF4] bg-white p-5"><h2 className="text-xl font-bold">{tr("Needs Attention")}</h2><div className="mt-4 space-y-3">{rows.map(({label,value,path,icon:Icon,tone})=><Link key={path} to={'/shop-owner/'+path} state={{businessId}} className="flex min-h-20 items-center gap-3 rounded-xl border border-[#E1EAF4] p-3 hover:bg-[#F5F8FC]"><span className={'rounded-xl p-3 '+tone}><Icon size={24} aria-hidden="true"/></span><div className="min-w-0 flex-1"><p className="text-sm font-semibold"><span className="mr-2 text-xl">{value ?? '—'}</span>{tr(label)}</p>{value == null && <p className="mt-1 text-xs text-[#64748B]">{tr("Count unavailable")}</p>}</div><ArrowRight className="shrink-0 text-[#12B8A6]" size={18} aria-hidden="true"/></Link>)}</div></section>;
}
