import useSubscription from './useSubscription';
import useTrialDisplay from './useTrialDisplay';
export default function usePlanAccess(businessId,feature) {
  const subscription=useSubscription(businessId);
  const display=useTrialDisplay(subscription.data);
  return {...subscription,locked:Boolean(businessId&&(subscription.loading||subscription.error||display.plan==='FREE'||subscription.data?.entitlements?.[feature]!==true))};
}
