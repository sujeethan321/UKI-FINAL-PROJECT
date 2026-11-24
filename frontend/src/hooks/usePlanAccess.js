// Purpose: Encapsulate plan access state and lifecycle behavior for reuse by React components.
import useSubscription from './useSubscription';
import useTrialDisplay from './useTrialDisplay';
// Share plan access state and lifecycle behavior between React consumers.
export default function usePlanAccess(businessId,feature) {
  const subscription=useSubscription(businessId);
  const display=useTrialDisplay(subscription.data);
  return {...subscription,locked:Boolean(businessId&&(subscription.loading||subscription.error||display.plan==='FREE'||subscription.data?.entitlements?.[feature]!==true))};
}
