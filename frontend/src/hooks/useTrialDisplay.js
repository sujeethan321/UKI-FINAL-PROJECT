import { useEffect, useState } from "react";
import { subscriptionDisplay } from "../utils/subscription";

export default function useTrialDisplay(data) {
  const [now, setNow] = useState(Date.now);
  useEffect(() => {
    if (!data?.trial_active) return;
    // Presentation clock only; no automatic API retry, charge or record write.
    const timer = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(timer);
  }, [data?.trial_active]);
  return subscriptionDisplay(data, now);
}
