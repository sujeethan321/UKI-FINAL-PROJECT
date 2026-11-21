import {LockKeyhole} from 'lucide-react';
import {Link} from 'react-router-dom';
import usePlanAccess from '../../hooks/usePlanAccess';
import {useAppTranslation} from '../../i18n/useAppTranslation';
export function PlanLockNotice({businessId,continuity=false}) {
  const {tr}=useAppTranslation();
  return <div className="my-4 rounded-xl border border-[#D4E2EE] bg-white p-4 text-sm" role="status"><p className="flex items-center gap-2 font-semibold"><LockKeyhole size={18}/>{tr('Upgrade to Pro')}</p><p className="mt-2 text-[#52698A]">{tr(continuity?'New activity is locked. Existing orders and deliveries remain accessible for resolution.':'This module is locked on the Free plan.')}</p><Link className="mt-3 inline-block font-semibold text-[#087D78]" to={`/shop-owner/subscription?business_id=${businessId}`}>{tr('Subscription & Billing')}</Link></div>;
}
export default function PlanFeatureNotice({businessId,feature,continuity=false}) {
  const {tr}=useAppTranslation();
  const access=usePlanAccess(businessId,feature);
  if(!businessId||access.loading)return null;
  if(access.error)return <p role="alert">{tr('Subscription access is unavailable. Refresh before trying again.')}</p>;
  return access.locked?<PlanLockNotice businessId={businessId} continuity={continuity}/>:null;
}
