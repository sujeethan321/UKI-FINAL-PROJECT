import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { Wallet, CalendarClock, AlertTriangle } from 'lucide-react';
import { formatCustomerMoney } from '../../utils/customerDashboard';

export default function CustomerCreditOverview({summary,loading=false}) {
  const { tr } = useAppTranslation();
  const dueValue=key=>!loading&&summary?.due_totals_status==='complete'&&typeof summary[key]==='string'&&/^\d+\.\d{2}$/.test(summary[key])
    ? `Rs. ${summary[key].replace(/\B(?=(\d{3})+(?!\d))/g,',')}`:tr('Unavailable');
  const cards=[
    ['Total Outstanding Credit',summary?formatCustomerMoney(summary.total_outstanding_balance):'—',Wallet,'bg-[#EAF6FF] text-[#079AC9]',summary?tr("Across {{count}} linked shops", { count: summary.linked_shop_count }):'Summary unavailable'],
    ['Due Soon',dueValue('due_soon_amount'),CalendarClock,'bg-[#FFF5DF] text-[#C78513]',summary?.due_totals_status==='complete'?'FIFO unpaid credit; due today through the next 7 days.':'Due-date totals unavailable'],
    ['Overdue Amount',dueValue('overdue_amount'),AlertTriangle,'bg-[#FFF0F1] text-[#DC4545]',summary?.due_totals_status==='complete'?'FIFO unpaid credit; past its saved due date.':'Overdue totals unavailable'],
  ];
  return <div className="grid min-w-0 gap-4 md:grid-cols-3">{cards.map(([title,value,Icon,tone,note])=><article key={title} className="flex min-w-0 items-center gap-4 rounded-xl border border-[#DFEDF7] bg-white p-5"><span className={'shrink-0 rounded-xl p-4 '+tone}><Icon size={28} aria-hidden="true"/></span><div className="min-w-0"><h3 className="text-sm font-medium">{tr(title)}</h3><p className="mt-2 break-words text-2xl font-bold [overflow-wrap:anywhere]">{value}</p><p className="mt-2 text-xs text-[#52698A]">{loading?tr("Loading..."):tr(note)}</p></div></article>)}</div>;
}
