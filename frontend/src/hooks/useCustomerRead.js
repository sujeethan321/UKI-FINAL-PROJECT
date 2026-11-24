// Purpose: Encapsulate customer read state and lifecycle behavior for reuse by React components.
import { useEffect, useState, useSyncExternalStore } from "react";
import { createCustomerRead } from "../utils/customerAccounts";

// Subscribe React to a customer resource reader and dispose its work when the mounted resource changes.
export function useCustomerRead(api, parse, onDenied) {
  // Callers key the mounted resource by session and all request parameters.
  const [reader] = useState(() => createCustomerRead(api, parse, onDenied));
  const state = useSyncExternalStore(reader.subscribe, reader.getSnapshot, reader.getSnapshot);
  // Start resource work after rendering and cancel or dispose it during cleanup so obsolete work cannot update this view.
  useEffect(() => { reader.load(); return () => reader.dispose(); }, [reader]);
  return [state, reader];
}
