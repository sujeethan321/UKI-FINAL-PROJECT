// Purpose: Wrap notification API calls so components use a shared request interface instead of building HTTP requests themselves.
import api from "./api";

// JWTs and recipient ownership remain with the existing API client/backend.
export async function getNotifications(filters = {}, options = {}) {
  const params = {};
  for (const key of ["page", "page_size", "unread_only", "is_read", "notification_type"]) {
    if (filters[key] !== undefined) params[key] = filters[key];
  }
  return (await api.get("/notifications", { params, signal: options.signal })).data;
}
// Call GET /notifications/unread-count through the shared client so authentication and API configuration are applied consistently.
export async function getNotificationUnreadCount(options = {}) {
  return (await api.get("/notifications/unread-count", { signal: options.signal })).data;
}
// Send the notification read-state request through the shared HTTP client.
export async function markNotificationRead(notificationId, options = {}) {
  if (!Number.isSafeInteger(notificationId) || notificationId <= 0) throw new Error("Invalid notification identifier");
  return (await api.patch("/notifications/" + notificationId + "/read", undefined, { signal: options.signal })).data;
}
// Call PATCH /notifications/read-all through the shared client so authentication and API configuration are applied consistently.
export async function markAllNotificationsRead(options = {}) {
  return (await api.patch("/notifications/read-all", undefined, { signal: options.signal })).data;
}
