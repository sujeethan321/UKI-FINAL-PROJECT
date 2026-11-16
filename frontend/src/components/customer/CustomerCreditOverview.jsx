import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { Wallet, CalendarClock, AlertTriangle } from 'lucide-react';
import { formatCustomerMoney } from '../../utils/customerDashboard';

export default function CustomerCreditOverview({summary,loading=false}) {
  const { tr } = useAppTranslation();
  const cards=[
    ['Total Outstanding Credit',summary?formatCustomerMoney(summary.total_outstanding_balance):'—',Wallet,'bg-[#EAF6FF] text-[#079AC9]',summary?tr("Across {{count}} linked shops", { count: summary.linked_shop_count }):'Summary unavailable'],
    ['Due Soon','—',CalendarClock,'bg-[#FFF5DF] text-[#C78513]','Due-date totals unavailable'],
    ['Overdue Amount','—',AlertTriangle,'bg-[#FFF0F1] text-[#DC4545]','Overdue totals unavailable'],
  ];
  return <div className="grid min-w-0 gap-4 md:grid-cols-3">{cards.map(([title,value,Icon,tone,note])=><article key={title} className="flex min-w-0 items-center gap-4 rounded-xl border border-[#DFEDF7] bg-white p-5"><span className={'shrink-0 rounded-xl p-4 '+tone}><Icon size={28} aria-hidden="true"/></span><div className="min-w-0"><h3 className="text-sm font-medium">{tr(title)}</h3><p className="mt-2 break-words text-2xl font-bold [overflow-wrap:anywhere]">{value}</p><p className="mt-2 text-xs text-[#52698A]">{loading?tr("Loading..."):tr(note)}</p></div></article>)}</div>;
}
