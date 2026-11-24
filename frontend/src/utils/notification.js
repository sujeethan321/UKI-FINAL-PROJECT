// Purpose: Keep notification data handling and workflow helpers separate from React rendering so callers use consistent rules.
export const NOTIFICATION_TYPES = [
  ["support_created", "Support case created", "support_case"],
  ["support_replied", "Support reply", "support_case"],
  ["support_awaiting_user", "Support information requested", "support_case"],
  ["support_resolved", "Support case resolved", "support_case"],
  ["support_reopened", "Support case reopened", "support_case"],
  ["driver_approved", "Driver application approved", "admin_audit"],
  ["driver_rejected", "Driver application rejected", "admin_audit"],
  ["order_submitted", "Order submitted", "order"],
  ["order_approved", "Order approved", "order"],
  ["order_rejected", "Order rejected", "order"],
  ["order_processing", "Order processing", "order"],
  ["order_completed", "Order completed", "order"],
  ["order_cancelled", "Order cancelled", "order"],
  ["delivery_requested", "Delivery requested", "delivery_request"],
  ["delivery_cancelled", "Delivery cancelled", "delivery_request"],
  ["delivery_assigned", "Delivery assigned", "delivery_request"],
  ["delivery_picked_up", "Delivery picked up", "delivery_request"],
  ["delivery_in_transit", "Delivery in transit", "delivery_request"],
  ["delivery_delivered", "Delivery marked as delivered", "delivery_request"],
  ["credit_sale_recorded", "Credit sale recorded", "ledger_entry"],
  ["repayment_recorded", "Repayment recorded", "ledger_entry"],
  ["payment_reminder_recorded", "Payment reminder recorded", "payment_reminder"],
  ["business_approved", "Business approved", "business_approval_audit"],
  ["business_rejected", "Business rejected", "business_approval_audit"],
];
// Check the notification identifier before allowing a read-state request.
export const validNotificationId = value => Number.isSafeInteger(value) && value > 0;
// Reject invalid totals so list counts cannot silently display malformed API values.
export const validCount = value => Number.isSafeInteger(value) && value >= 0;
// Check the date representation before using it in notification display or filtering.
const validDate = value => typeof value === "string" && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && !Number.isNaN(Date.parse(value));
// Check the notification fields before the inbox renders the record.
export function validNotification(row) {
  const type = NOTIFICATION_TYPES.find(([value]) => value === row?.notification_type);
  return !!type && validNotificationId(row.notification_id) && (row.business_id === null || validNotificationId(row.business_id)) &&
    typeof row.title === "string" && !!row.title.trim() && row.title.length <= 120 &&
    typeof row.message === "string" && row.message.length <= 300 &&
    (row.related_entity_type === type[2] || (type[2] === 'delivery_request' && row.related_entity_type === 'order')) && validNotificationId(row.related_entity_id) &&
    typeof row.is_read === "boolean" && validDate(row.created_at) &&
    (row.is_read ? validDate(row.read_at) : row.read_at === null);
}
// Check pagination and notification rows before publishing inbox state.
export function validNotificationPage(data, filters) {
  return data?.page === filters.page && data.page_size === filters.page_size && validCount(data.total) &&
    Array.isArray(data.notifications) && data.notifications.length <= filters.page_size &&
    data.notifications.every(row => validNotification(row) &&
      (filters.is_read === undefined || row.is_read === filters.is_read) &&
      (!filters.notification_type || row.notification_type === filters.notification_type)) &&
    new Set(data.notifications.map(row => row.notification_id)).size === data.notifications.length;
}
// Translate notification outcomes into display text for the interface.
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
// Resolve the inbox route for the active role using the supported role destinations.
export function notificationInboxPath(role) {
  return role === "shop_owner" ? "/shop-owner/notifications" : role === "admin" ? "/admin/notifications" : role === "customer" ? "/customer/notifications" : role === "driver" ? "/driver/notifications" : null;
}

// Ignore URLs/text/metadata completely. Only existing role-appropriate routes.
// Minimal events cannot safely resolve a financial customer: never guess an ID.
export function notificationDestination(row, role) {
  if (!validNotification(row)) return null;
  if (row.related_entity_type === "support_case") { const root={admin:"admin",shop_owner:"shop-owner",customer:"customer",driver:"driver"}[role]; return root ? {to:`/${root}/support`,label:"View support cases"} : null; }
  if (role === "driver" && row.related_entity_type === "admin_audit" && ["driver_approved","driver_rejected"].includes(row.notification_type)) return {to:"/driver/dashboard",label:"View Driver application"};
  if (!validNotificationId(row.business_id)) return null;
  if (row.related_entity_type === "order") {
    if(role === "customer") return {to: `/customer/orders/${row.related_entity_id}`, label: "View order"};
    if(role === "shop_owner") return {to: `/shop-owner/orders/${row.related_entity_id}?business_id=${row.business_id}`, label: "View order"};
  }
  if (role === "driver" && row.related_entity_type === "delivery_request") return {to: `/driver/deliveries/${row.related_entity_id}`, label: "View my delivery"};
  if (role === "shop_owner") {
    if (row.related_entity_type === "delivery_request") return { to: `/shop-owner/deliveries?business_id=${row.business_id}&delivery_id=${row.related_entity_id}`, label: "View delivery tracking" };
    if (["business_approved", "business_rejected"].includes(row.notification_type)) return { to: "/shop-owner/dashboard", label: "View my businesses" };
  }
  if (role === "admin" && ["business_approved", "business_rejected"].includes(row.notification_type)) return { to: "/admin/businesses", label: "View businesses" };
  return null;
}
// Format notification timestamps for inbox display.
export function notificationTime(value, now = Date.now()) {
  const ms = Date.parse(value);
  if (Number.isNaN(ms)) return { relative: "Time unavailable", full: "Time unavailable" };
  const seconds = Math.max(0, Math.floor((now - ms) / 1000));
  const relative = seconds < 60 ? "Just now" : seconds < 3600 ? Math.floor(seconds / 60) + "m ago" : seconds < 86400 ? Math.floor(seconds / 3600) + "h ago" : Math.floor(seconds / 86400) + "d ago";
  return { relative, full: new Date(ms).toLocaleString("en-LK", { timeZone: "Asia/Colombo", dateStyle: "medium", timeStyle: "short" }) + " (Asia/Colombo)" };
}
