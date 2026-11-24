// Purpose: Define the shared notification context used by notification consumers.
import { createContext, useContext } from "react";
export const NotificationContext = createContext(null);
// Share notifications state and lifecycle behavior between React consumers.
export function useNotifications() { return useContext(NotificationContext); }
