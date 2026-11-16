import { useAppTranslation } from "../../i18n/useAppTranslation.js";
import { Link } from "react-router-dom";
import { CreditCard, Wallet, Package, ArrowRight } from "lucide-react";

const actions = [
  {label:"New Credit Sale", path:"credit-sales", icon:CreditCard},
  {label:"Record Repayment", path:"repayments", icon:Wallet},
  {label:"Manage Products", path:"products", icon:Package},
];
export default function QuickActions({businessId}) {
  const { tr } = useAppTranslation();
  return <section aria-labelledby="quick-actions-title" className="rounded-xl border border-[#E1EAF4] bg-white p-5">
    <h2 id="quick-actions-title" className="text-xl font-bold">{tr("Quick Actions")}</h2>
    <div className="mt-4 grid gap-3 md:grid-cols-3">{actions.map(({label,path,icon:Icon},index)=><Link key={path} to={'/shop-owner/'+path} state={{businessId}} className={'flex min-h-14 items-center gap-3 rounded-lg border border-[#12B8A6] px-4 py-3 text-sm font-semibold '+(index===0?'bg-gradient-to-r from-[#12B8A6] to-[#009BA7] text-white':'text-[#10243E] hover:bg-[#E7F9F6]')}><Icon size={23} aria-hidden="true"/><span className="flex-1">{tr(label)}</span><ArrowRight size={19} aria-hidden="true"/></Link>)}</div>
  </section>;
}
