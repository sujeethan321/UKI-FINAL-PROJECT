export const NOTIFICATION_TYPES = [
  ["credit_sale_recorded", "Credit sale recorded", "ledger_entry"],
  ["repayment_recorded", "Repayment recorded", "ledger_entry"],
  ["payment_reminder_recorded", "Payment reminder recorded", "payment_reminder"],
  ["business_approved", "Business approved", "business_approval_audit"],
  ["business_rejected", "Business rejected", "business_approval_audit"],
];
export const validNotificationId = value => Number.isSafeInteger(value) && value > 0;
export const validCount = value => Number.isSafeInteger(value) && value >= 0;
const validDate = value => typeof value === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && !Number.isNaN(Date.parse(value));
export function validNotification(row) {
  const type = NOTIFICATION_TYPES.find(([value]) => value === row?.notification_type);
  return !!type && validNotificationId(row.notification_id) && (row.business_id === null || validNotificationId(row.business_id)) &&
    typeof row.title === "string" && !!row.title.trim() && row.title.length <= 120 &&
    typeof row.message === "string" && row.message.length <= 300 &&
    row.related_entity_type === type[2] && validNotificationId(row.related_entity_id) &&
    typeof row.is_read === "boolean" && validDate(row.created_at) &&
    (row.is_read ? validDate(row.read_at) : row.read_at === null);
}
export function validNotificationPage(data, filters) {
  return data?.page === filters.page && data.page_size === filters.page_size && validCount(data.total) &&
    Array.isArray(data.notifications) && data.notifications.length <= filters.page_size &&
    data.notifications.every(row => validNotification(row) &&
      (filters.is_read === undefined || row.is_read === filters.is_read) &&
      (!filters.notification_type || row.notification_type === filters.notification_type)) &&
    new Set(data.notifications.map(row => row.notification_id)).size === data.notifications.length;
}
export function notificationError(error, mutation = false) {
  const status = error?.response?.status;
  if (status === 401) return "Login required. Please sign in again.";
  if (status === 403) return "Notification access is forbidden. Please check your account access.";
  if (status === 404) return "Notification not found or no longer available. Refresh and try again.";
  if (status === 422) return "Unable to use these notification filters. Check your selection and retry.";
  if (status === 429) return "Too many notification requests. Please wait before retrying.";
  return mutation ? "The read update could not be confirmed. Refresh or retry safely." :
    status >= 500 ? "The notification service is unavailable. Please retry." : "Unable to load notifications. Check your connection and retry.";
}
export function notificationInboxPath(role) {
  return role === "shop_owner" ? "/shop-owner/notifications" : role === "admin" ? "/admin/notifications" : null;
}

// Ignore URLs/text/metadata completely. Only existing role-appropriate routes.
// Minimal events cannot safely resolve a financial customer: never guess an ID.
export function notificationDestination(row, role) {
  if (!validNotification(row) || !validNotificationId(row.business_id)) return null;
  if (role === "shop_owner") {
    if (["business_approved", "business_rejected"].includes(row.notification_type)) return { to: "/shop-owner/dashboard", label: "View my businesses" };
  }
  if (role === "admin" && ["business_approved", "business_rejected"].includes(row.notification_type)) return { to: "/admin/businesses", label: "View businesses" };
  return null;
}
export function notificationTime(value, now = Date.now()) {
  const ms = Date.parse(value);
  if (Number.isNaN(ms)) return { relative: "Time unavailable", full: "Time unavailable" };
  const seconds = Math.max(0, Math.floor((now - ms) / 1000));
  const relative = seconds < 60 ? "Just now" : seconds < 3600 ? Math.floor(seconds / 60) + "m ago" : seconds < 86400 ? Math.floor(seconds / 3600) + "h ago" : Math.floor(seconds / 86400) + "d ago";
  return { relative, full: new Date(ms).toLocaleString("en-LK", { timeZone: "Asia/Colombo", dateStyle: "medium", timeStyle: "short" }) + " (Asia/Colombo)" };
}
