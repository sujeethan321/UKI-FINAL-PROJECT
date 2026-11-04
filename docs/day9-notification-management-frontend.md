# Day 9 Step 9.5 — Notification Management Frontend

Date: 2026-11-04 (Asia/Colombo).

## Outcome

Notification frontend implementation is complete. Required frontend tests and production Vite build pass. The existing Shop Owner Notifications route now includes a personal notification inbox alongside its unchanged payment-reminder workflow. Shop Owner and Admin headers use a shared real-count bell and accessible recent-notification dropdown. The ready Admin layout also has a personal inbox route. No backend code, environment files or database schema were changed for this step.

## Existing files inspected and structures reused

Inspected frontend App routes, ProtectedRoute, AuthContext/useAuth, ShopOwnerLayout, ShopOwnerHeader, ShopOwnerSidebar, AdminLayout, AdminSidebar, DashboardPlaceholder, BusinessOnboarding, shopOwnerBusinessService, existing Axios client, ShopOwnerNotifications and reminder tests, package.json, index.css and eslint.config.js. Read the actual Step 9.4 notification router and Pydantic schemas, and inspected the Git working tree before editing. No additional AGENTS.md instructions were found in the inspected paths.

The app had no notification bell, notification fetching hook or generic inbox component. Its existing Notifications page contained Step 9.3 reminder creation/history. Customer and Driver routes still use placeholder dashboards. The project uses the existing Node test runner, Vite SSR transformation and React server rendering for frontend tests; no new dependency was introduced.

Reused existing Axios JWT/session-expiry interceptors, authenticated user context, protected routes, React Router links, Lucide icons, card/field/button/alert styles, navy #10243E, teal #12B8A6, background #F5F8FC and existing typography. Header titles can truncate on narrow screens and the compact mobile account controls leave room for the bell; desktop layout is retained. No font substitution or generic dashboard redesign was introduced.

## Backend contracts used

Existing Axios baseURL supplies /api/v1. The new service uses these relative paths:

- GET /notifications with page, page_size, unread_only, is_read and notification_type where applicable.
- GET /notifications/unread-count, response { unread_count: nonnegative integer }.
- PATCH /notifications/{notification_id}/read with no body; returns the full NotificationResponse with is_read=true and read_at.
- PATCH /notifications/read-all with no body; response { updated_count: nonnegative integer }.

The list response is { page, page_size, total, notifications }. Notification records preserve notification_id, business_id, notification_type, title, message, related_entity_type, related_entity_id, is_read, created_at and read_at. The service returns backend response data without discarding extra response fields. Runtime validation rejects malformed IDs, counts, type/entity combinations, timestamps and page/filter mismatches before displaying them.

Allowed event types are exactly credit_sale_recorded, repayment_recorded, payment_reminder_recorded, business_approved and business_rejected. The UI uses page_size=20 for history and page_size=5 for the dropdown. Newest-first ordering is supplied by the backend. All/Unread/Read maps to omitted is_read, is_read=false and is_read=true respectively. Changing a filter resets page to 1; subsequent pages retain the active filters.

The service whitelists supported query keys and never forwards recipient_user_id/user_id or constructs Authorization headers. The existing interceptor supplies the current JWT. Individual mutation IDs must be positive safe integers; the backend remains authoritative for ownership.

## Shared session state and role coverage

NotificationProvider is inside AuthProvider and scopes its NotificationSession by authenticated user, role and token. It creates one shared workflow for a ready Shop Owner or Admin session. Old sessions unmount on logout/user/role/token changes, immediately replace their displayed scope and cancel all requests and timers. Notification records and counts are never persisted to browser storage or logged.

Shop Owner: bell in the existing header and inbox inside the existing /shop-owner/notifications page. Its reminder form, English/Tamil preview, safe reminder request store and business-specific reminder history remain intact. The inbox is personal across businesses and deliberately independent of the reminder form's business selection.

Admin: bell in the existing Admin header, a Notifications sidebar item and /admin/notifications showing only the signed-in administrator's inbox. It has no global-recipient filter or private-inbox bypass.

Customer and Driver: service and components remain reusable, but UI integration is deferred because these roles have placeholder dashboards. No replacement/fake dashboard or background notification polling was added to their placeholders.

## Bell and dropdown

The bell starts with an unknown count, fetches the real count, hides the badge at zero and shows 99+ above 99. Loading hides any badge until the current count is confirmed; failures show an unavailable state rather than a fabricated zero. Screen-reader labels include the exact count or explain loading/unavailability.

Opening the nonmodal dropdown loads at most five recent notifications and never marks them read. It displays title, compact message, accurate Read/Unread state, relative creation time, a full Asia/Colombo timestamp in accessible text/title, an explicit Mark as Read control, and a role-appropriate View All Notifications link. It provides loading, empty, failure and retry states.

The dropdown focuses its first control when opened, closes on Escape with focus restored to the bell, closes on outside pointer interaction, and removes its event listeners when closed/unmounted. Native buttons/links support keyboard Tab navigation. The mobile panel is fixed to the viewport edge; desktop anchoring, bounded width/height, vertical scrolling, message wrapping and clamping prevent long content from expanding the header or page.

## Read actions and stale-response protection

Only explicit Mark as Read or Mark All as Read actions call PATCH. Opening, viewing or following a destination link does not mark anything automatically. A synchronous shared mutation lock controls duplicate single clicks and simultaneous single/all actions. Controls stay disabled during the action and reconciliation.

No optimistic mutation is performed. Before writing, in-flight count/list/recent reads are aborted and invalidated. On confirmed success, affected read states update and new server reads reconcile the authoritative unread count, recent list and current filtered page. No arithmetic decrement is used, so counts cannot become negative. An empty out-of-range filtered page returns to a valid page after reconciliation. History is never deleted.

On mutation failure or an unconfirmed response, previous read states remain and a sanitized message offers refresh/retry. The unread count becomes unknown until it is reconfirmed. Read actions are backend-idempotent, making retries safe. Request generations and AbortControllers prevent stale reads or writes from overwriting a newer selection/session. Lifecycle generations also protect React effect cleanup/restart and late responses from APIs that ignore cancellation.

401/403 clear all notification lists/counts, close the dropdown, abort requests and suspend polling. The existing Axios 401 interceptor also expires the session. 404, 422, 429, 5xx and connection errors have sanitized feedback; raw backend details and stack traces are not rendered.

## Polling strategy and cleanup

A single shared workflow uses self-scheduling timeouts, normally one unread-count request every 60 seconds after the previous request finishes. There is no setInterval, unlimited history polling or overlapping periodic count request. Failures back off to 120, 240 and at most 300 seconds; successful reads restore the normal interval.

Polling pauses while the document is hidden. Returning to a visible tab or window focus refreshes the count and currently active page/dropdown; duplicate focus/visibility events are throttled for five seconds. Hidden-start sessions wait until visible. Logout, authentication loss, session replacement and provider unmount cancel timers and requests. Open inbox registration works regardless of parent/child effect order. Tests use injected deterministic fake timers and fake event targets.

## Safe navigation

Destinations come only from an allowlist of validated event types and implemented role-specific routes. User-supplied URLs, notification text and metadata are ignored. Business approval/rejection notifications can open the Shop Owner's business overview (/shop-owner/dashboard) or the Admin business overview (/admin/businesses).

Credit-sale, repayment and payment-reminder records display details without an event destination link: their minimal payload cannot safely resolve an authorized customer or active approved-business selection. Customer/Driver destinations are also deferred with their dashboards. No related_entity_id is guessed to be a customer ID, and no inbox item grants financial/business access. Destination APIs continue to enforce their own authorization.

## Verification

- npm test: **250 passed, 0 failed, 0 skipped, 0 cancelled**, exit 0. Final run: 22.65 seconds.
- Includes **46 new notification checks**: 31 workflow/lifecycle/security checks and 15 component/contract checks, plus all 204 existing tests. Existing reminder, credit-sale, repayment and financial-document tests still pass.
- Coverage includes real count/loading/zero/99+, dropdown open/close/empty/retry states, explicit read actions, failed writes, duplicate clicks, read/type filters, pagination, stale-response protection, authoritative count reconciliation, fake-timer backoff, tab events, cleanup, user switching, authorization loss, escaped long content, safe destinations and existing role/reminder/layout imports/rendering.
- API calls use controlled promises or mocked Axios adapters. No test creates real notifications, reminders or financial records, and no automated frontend test accesses lankapex_db.
- npm run build: **passed**, Vite 8.3.5, 2152 modules transformed. Final JavaScript bundle: 530.51 kB minified / 154.97 kB gzip. Vite reports its non-failing warning for a chunk above 500 kB; the project already exceeded this threshold before this step.
- ESLint on all new and modified frontend source/test files: **passed**.
- Existing App and role layouts compile through Vite; actual React server rendering and pure lifecycle/action tests pass. No missing import/route or duplicate component definition was found in these checks.
- Browser smoke test: **unavailable**. Browser inventory returned no connected browsers; creating an in-app browser returned Browser is not available: iab. Interactive DOM behavior, authenticated navigation and visual review were not browser-verified; SSR/action tests are not a substitute for that check.
- Backend tests: not run for this frontend-only step. No backend changes or new migrations were needed.

## Remaining issues and deferred integrations

Interactive browser smoke testing remains to be done with a connected browser. Customer/Driver UI and unresolved financial-event destinations remain deferred as described above. The existing non-failing Vite bundle-size warning remains.

Step 9.4's additive notification migration still needs applying to the deliberately selected development database before live notification endpoints/event hooks can work there; this frontend task did not apply development migrations or change backend/.env. Notification backend failures are surfaced through the UI with retry controls.

No SMS, WhatsApp, email, push/browser-permission requests, WebSockets, new workflows, financial calculations, commits or pushes were introduced.

## Files created

- frontend/src/services/notificationService.js
- frontend/src/utils/notification.js
- frontend/src/utils/notificationWorkflow.js
- frontend/src/utils/notificationPopover.js
- frontend/src/context/NotificationContext.js
- frontend/src/context/NotificationProvider.jsx
- frontend/src/components/notifications/NotificationBell.jsx
- frontend/src/components/notifications/NotificationInbox.jsx
- frontend/src/components/notifications/NotificationItem.jsx
- frontend/src/pages/admin/AdminNotifications.jsx
- frontend/tests/notifications.test.js
- frontend/tests/notificationsView.test.js
- docs/day9-notification-management-frontend.md

## Files modified

- frontend/src/App.jsx: notification provider and protected Admin notification route.
- frontend/src/components/shopOwner/ShopOwnerHeader.jsx: shared bell and compact header fit.
- frontend/src/pages/shopOwner/ShopOwnerNotifications.jsx: personal inbox alongside existing reminder controls.
- frontend/src/layouts/AdminLayout.jsx: shared bell, Notifications title and compact title fit.
- frontend/src/components/admin/AdminSidebar.jsx: link to personal Admin inbox.

All pre-existing working-tree edits from earlier steps were preserved.
