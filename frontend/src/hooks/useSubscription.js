// Purpose: Encapsulate subscription state and lifecycle behavior for reuse by React components.
import { useEffect, useState } from "react";
import { getSubscription } from "../services/subscriptionService";

// Share subscription state and lifecycle behavior between React consumers.
export default function useSubscription(businessId) {
  const [result, setResult] = useState(null);
  const [refresh, setRefresh] = useState(0);
  // Start resource work after rendering and cancel or dispose it during cleanup so obsolete work cannot update this view.
  useEffect(() => {
    if (!businessId) return;
    const controller = new AbortController();
    getSubscription(businessId, controller.signal).then(data => {
      if (!controller.signal.aborted) setResult({ businessId, refresh, data });
    }).catch(() => {
      if (!controller.signal.aborted) setResult({ businessId, refresh, error: true });
    });
    return () => controller.abort();
  }, [businessId, refresh]);
  const current = result && result.businessId === businessId && result.refresh === refresh ? result : null;
  return { data: current?.data, error: current?.error, loading: Boolean(businessId && !current),
    // Retry the unresolved read or operation using the workflow state retained for recovery.
    retry: () => setRefresh(value => value + 1) };
}
