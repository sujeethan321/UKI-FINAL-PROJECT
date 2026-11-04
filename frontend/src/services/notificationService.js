import api from "./api";

// JWTs and recipient ownership remain with the existing API client/backend.
export async function getNotifications(filters = {}, options = {}) {
  const params = {};
  for (const key of ["page", "page_size", "unread_only", "is_read", "notification_type"]) {
    if (filters[key] !== undefined) params[key] = filters[key];
  }
  return (await api.get("/notifications", { params, signal: options.signal })).data;
}
export async function getNotificationUnreadCount(options = {}) {
  return (await api.get("/notifications/unread-count", { signal: options.signal })).data;
}
export async function markNotificationRead(notificationId, options = {}) {
  if (!Number.isSafeInteger(notificationId) || notificationId <= 0) throw new Error("Invalid notification identifier");
  return (await api.patch("/notifications/" + notificationId + "/read", undefined, { signal: options.signal })).data;
}
export async function markAllNotificationsRead(options = {}) {
  return (await api.patch("/notifications/read-all", undefined, { signal: options.signal })).data;
}
