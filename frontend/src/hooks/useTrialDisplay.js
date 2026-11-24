// Purpose: Encapsulate trial display state and lifecycle behavior for reuse by React components.
import { useEffect, useState } from "react";
import { subscriptionDisplay } from "../utils/subscription";

// Share trial display state and lifecycle behavior between React consumers.
export default function useTrialDisplay(data) {
  const [now, setNow] = useState(Date.now);
  // Schedule the component side effect after rendering; the effect body controls when it is refreshed or cleaned up.
  useEffect(() => {
    if (!data?.trial_active) return;
    // Presentation clock only; no automatic API retry, charge or record write.
    const timer = setInterval(() => setNow(Date.now()), 30000);
    return () => clearInterval(timer);
  }, [data?.trial_active]);
  return subscriptionDisplay(data, now);
}
