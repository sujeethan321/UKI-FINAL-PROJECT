import { useEffect, useState, useSyncExternalStore } from "react";
import { useAuth } from "./useAuth";
import { NotificationContext } from "./NotificationContext";
import { getNotifications, getNotificationUnreadCount, markNotificationRead, markAllNotificationsRead } from "../services/notificationService";
import { bindNotificationLifecycle, createNotificationWorkflow } from "../utils/notificationWorkflow";

const api = { list: getNotifications, count: getNotificationUnreadCount, markOne: markNotificationRead, markAll: markAllNotificationsRead };
function NotificationSession({ children, role }) {
  const [workflow] = useState(() => createNotificationWorkflow({ api }));
  const state = useSyncExternalStore(workflow.subscribe, workflow.getSnapshot, workflow.getSnapshot);
  useEffect(() => bindNotificationLifecycle(workflow, window, document), [workflow]);
  return <NotificationContext.Provider value={{ state, actions: workflow, role }}>{children}</NotificationContext.Provider>;
}
export default function NotificationProvider({ children }) {
  const { user, token, isAuthenticated } = useAuth();
  // One recipient-scoped workflow for every implemented role layout.
  if (!isAuthenticated || !user || !["shop_owner", "customer", "driver", "admin"].includes(user.platform_role)) return children;
  return <NotificationSession key={user.user_id + ":" + user.platform_role + ":" + token} role={user.platform_role}>{children}</NotificationSession>;
}
