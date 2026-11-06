import { useEffect, useState, useSyncExternalStore } from "react";
import { createCustomerRead } from "../utils/customerAccounts";

export function useCustomerRead(api, parse, onDenied) {
  // Callers key the mounted resource by session and all request parameters.
  const [reader] = useState(() => createCustomerRead(api, parse, onDenied));
  const state = useSyncExternalStore(reader.subscribe, reader.getSnapshot, reader.getSnapshot);
  useEffect(() => { reader.load(); return () => reader.dispose(); }, [reader]);
  return [state, reader];
}
