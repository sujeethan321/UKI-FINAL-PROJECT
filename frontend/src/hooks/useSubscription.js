import { useEffect, useState } from "react";
import { getSubscription } from "../services/subscriptionService";

export default function useSubscription(businessId) {
  const [result, setResult] = useState(null);
  const [refresh, setRefresh] = useState(0);
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
    retry: () => setRefresh(value => value + 1) };
}
