// Purpose: Keep notification change data handling and workflow helpers separate from React rendering so callers use consistent rules.
// Local invalidation only: no payload, persistent cache, toast or push claim.
export const NOTIFICATION_CHANGE_EVENT='lankapex:notification-change';
// Notify other application consumers that notification data should be refreshed.
export function notificationChanged(data) {
 if(typeof window!=='undefined')window.dispatchEvent(new Event(NOTIFICATION_CHANGE_EVENT));
 return data;
}
