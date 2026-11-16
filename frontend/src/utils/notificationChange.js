// Local invalidation only: no payload, persistent cache, toast or push claim.
export const NOTIFICATION_CHANGE_EVENT='lankapex:notification-change';
export function notificationChanged(data) {
 if(typeof window!=='undefined')window.dispatchEvent(new Event(NOTIFICATION_CHANGE_EVENT));
 return data;
}
