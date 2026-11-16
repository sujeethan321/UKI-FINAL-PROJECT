# Day 15 Step 15.4 — Order/delivery coordination and in-app notifications

## Audit and verified dependencies

Steps 15.1–15.3 exist in the working tree: nullable same-business Order.delivery_request_id, secure create/replay service, owner fulfilment UI and Customer-safe tracking. Existing owner/Customer/Driver order/delivery views, protected routes, notification model/service/router, bell/inbox, lifecycle polling and tests were inspected. Main remains at Day 14 checkpoint d917e4f with prior uncommitted work and unrelated .gitignore edits preserved.

Actual Order states: submitted, approved, rejected, processing, completed, cancelled. Delivery states: available, assigned, picked_up, in_transit, delivered, cancelled. There is no ready state. Existing order notifications already cover all six order states; submitted targets active business owners and later transitions target the order Customer. Existing delivery notifications covered owners for assignment/pickup/transit/delivered, but omitted linked Customers, assignment confirmation for Drivers, request creation and cancellation. Existing read APIs are recipient-scoped and deduplicate by recipient_user_id/event_key. The notification bell polls unread count every 60 seconds while visible, with bounded backoff/focus refresh; inboxes and tracking also have manual refresh.

## Implemented event-to-recipient matrix

All recipients are resolved from persisted Order, DeliveryAssignment, User and active owner membership records. No client recipient field or public notification-create endpoint exists.

| Existing/new event | Customer | Shop Owner | Driver | Destination |
| --- | --- | --- | --- | --- |
| order_submitted | No self-alert | Active authorized business owners | None | Owner Order Details |
| order_approved | Active owning Customer | None | None | Customer Order Details |
| order_rejected | Active owning Customer (Cash or Credit) | None | None | Customer Order Details |
| order_processing | Active owning Customer | None | None | Customer Order Details |
| order_completed / order_cancelled | Existing owning-Customer policy | None | None | Customer Order Details |
| delivery_requested | Active owning Customer, linked orders only | Creator gets existing creation confirmation; no extra self-alert | No broadcast | Customer Order Details |
| delivery_assigned | Active owning Customer if linked | Active business owners | Active assigned Driver confirmation | Customer Order Details / Owner Delivery Management / Driver My Delivery |
| delivery_picked_up / delivery_in_transit / delivery_delivered | Active owning Customer if linked | Active business owners | No self-alert for own progress | Customer Order Details / Owner Delivery Management |
| delivery_cancelled | Active owning Customer if linked | Active business owners except the persisted cancellation actor | Assigned active Driver if an existing internal assigned-cancellation workflow is used | Same role-specific destinations |

Public owner cancellation remains restricted to available/unassigned requests. This step adds no assigned-job cancellation API or Driver permission. Existing internal cancellation authorization/lifecycle is unchanged. Ordinary unlinked delivery requests retain owner alerts and assignment confirmation without inferring any Customer. Delivery requested is emitted only by the successful order-link creation branch, not ordinary available-job publication. Drivers discover jobs using existing APIs; no per-job broadcast is added.

## Persistence, idempotency and transaction boundaries

Reuses the existing Notification table, unread/read state, event_key and MySQL no-op upsert. Adds only delivery_requested and delivery_cancelled event types and widens existing type/entity check constraints. No redundant fields, model, queue or API is introduced.

Customer delivery notifications carry related_entity_type=order and the owning Order ID. Owner/Driver delivery alerts retain delivery_request and its ID. This avoids exposing an operational request ID or adding a lookup endpoint/metadata field to Customer alerts. Stable deduplication remains delivery_event_type:delivery_request_id even when the visible destination is an Order. Existing order event keys remain unchanged.

New-event hooks run after the actual flushed relationship/assignment/history event, within the same transaction and caller-owned commit. Replays do not resolve new recipients. The database unique key arbitrates concurrent callers and preserves original ID, timestamp and read status. If the transaction fails, the event/link and alerts roll back together. No external network calls, toast or irreversible side effects occur inside the transaction.

Delivery writers acquire a current shared read of the linked Order before locking the DeliveryRequest. This matches bridge replay/creation/summary order and prevents introducing a Delivery→Order lock inversion. Notification resolution uses current locking reads for the Order link and recipient status rather than a potentially stale JWT-authentication snapshot. Direct notification calls still validate an actual assignment/event/current lifecycle state.

For future external messaging, use an outbox row written in this same transaction, with a separately retried worker and delivery idempotency. No external messaging/outbox worker is implemented here.

## API, UI, navigation and refresh

Existing APIs remain:
- GET /api/v1/notifications (bounded pagination, read/type filters)
- GET /api/v1/notifications/unread-count
- PATCH /api/v1/notifications/{notification_id}/read
- PATCH /api/v1/notifications/read-all

Recipient identity is JWT-derived. A foreign/nonexistent notification yields the same 404 on mark-read. Generic historical alerts remain owned by their original recipient; current resource routes independently recheck Customer ownership/business membership/Driver assignment before showing details.

Reuses all existing notification pages, bells and inboxes. New types appear in the current filter list. Destinations are constructed only from validated internal IDs, ignoring arbitrary URLs/metadata:
- Customer: /customer/orders/{order_id}
- Owner order: /shop-owner/orders/{order_id}?business_id={business_id}
- Owner delivery: /shop-owner/deliveries?business_id={business_id}&delivery_id={delivery_id}
- Driver: /driver/deliveries/{delivery_id}

Customer and Driver never receive a link to owner tracking. Missing/inaccessible resources are handled by existing protected details views, without bypassing authorization. Text includes no names, contacts, addresses, amounts or ledger balances. Delivered is described as marked by the Driver, not independent proof of receipt/payment.

Successful order create/decision, order-delivery create, ordinary delivery mutations and Driver accept/status responses emit a local payload-free invalidation event. The existing session-scoped provider invalidates pre-event reads and refreshes count and any open feed when visible; a change arriving during a mark-read mutation is refreshed after that mutation completes. Failed API calls and reads emit no success event. Mark-read confirmation also verifies the related entity type so a response cannot switch an Order link into a delivery link. Listener cleanup occurs on unmount/logout. This introduces no global state framework, stored records, automatic navigation or duplicate toasts. Existing generation/version/abort safeguards and mutation locks remain authoritative. It is not push or instantaneous cross-account synchronization: other sessions see updates on manual navigation/refresh, focus return, or the existing unread-count poll. Tracking pages retain their existing manual refresh behavior.

## Files changed for this step

Backend:
- app/models/notification.py
- app/schemas/notification.py
- app/services/notification_service.py
- app/services/driver_service.py
- app/services/shop_owner_delivery_service.py
- app/services/order_delivery_service.py
- alembic/versions/f2a8b1c0d560_order_delivery_notifications.py (created)
- tests/test_delivery_final_review.py
- tests/test_driver_jobs_concurrency.py
- tests/test_driver_security_review.py
- tests/test_delivery_notifications.py
- tests/test_order_delivery_concurrency.py
- tests/test_order_delivery_notifications.py (created)

Frontend:
- src/utils/notification.js
- src/utils/notificationWorkflow.js
- src/utils/notificationChange.js (created)
- src/services/orderService.js
- src/services/driverJobsService.js
- src/services/driverDeliveriesService.js
- src/services/shopOwnerDeliveryService.js
- tests/orderDeliveryNotifications.test.js (created)
- tests/deliveryTracking.test.js

Report: docs/day15-order-delivery-notifications.md (created).

Existing AI deferral, colors, layout, logo, landing headline, financial functions and previous work are preserved. No new dependencies, GPS, gateway, WhatsApp/SMS, AI service or automatic assignment is introduced. No files are staged/committed/pushed.

## Migration and rollout

Revision f2a8b1c0d560 follows e1f7a0b9c459. It replaces only the two notification check constraints with wider compatible definitions; no history is deleted or rewritten. Downgrade deliberately refuses to discard incompatible notification history. Settings, engine URL and SELECT DATABASE() were verified as lankapex_test_db before applying it or running mutating tests. Alembic check passed with no metadata drift. lankapex_db was not migrated or reset.

After reviewing/backing up the intended development database, the manual command from backend is:

~~~powershell
$env:MYSQL_DATABASE = "lankapex_db"
.\.venv\Scripts\python.exe -m alembic upgrade head
~~~

This also applies pending earlier revisions. Deploy the updated backend/schema and frontend together; new delivery events require the widened checks.

## Verification and financial/privacy findings

- Final targeted backend suite: 78 passed, 0 failed/skipped in 21.10 seconds, including the updated recipient and financial-review tests.
- Full backend: 1,031 passed, 0 failed/skipped in 166.32 seconds on lankapex_test_db. One existing InsecureKeyLengthWarning comes from test_jwt.test_tampered_token_rejected (short test-only key). Includes authentication, reminders, notifications/read ownership, order approval/checkout, credit/repayment/statements and delivery regressions.
- Final targeted frontend notification/timeline suite: 54 passed, 0 failed/skipped.
- Full frontend: 679 passed, 0 failed/skipped in 78.92 seconds (node --test --test-concurrency=1), including Customer tracking, owner fulfilment, Driver, notification and financial UI regressions.
- Changed-file ESLint: passed for all nine frontend source/test files changed in this step. Full ESLint retains 8 pre-existing errors and 1 warning in unchanged ShopOwnerCustomers.jsx, ShopOwnerDashboard.jsx and repayments.test.js. No separate typecheck script is configured.
- npm run build: passed with Vite 8.3.5, 2,212 modules in 3.49 seconds. JavaScript 771.93 kB / 209.37 kB gzip; CSS 63.53 kB / 13.08 kB gzip. Existing >500 kB chunk warning remains.
- Alembic check passed with no metadata drift. git diff --check passed.

Development runs initially exposed a recipient-projection implementation error and legacy owner-only notification assertions; both were corrected. Updated tests now assert the precise owner/Customer/assigned-Driver policy and exclude losing/foreign Drivers, rather than weakening authorization expectations. The final results above supersede those development failures.

Tests cover the real Customer→Owner→Driver→Customer flow, exact recipients/destination IDs, new and existing order events, idempotent retries/read preservation, active role/membership restrictions, foreign-user mark-read denial, financial snapshots, failed creation/cancellation/transition commits, genuine MySQL simultaneous creates/accept-versus-cancel/two-Driver races and concurrent notification upserts. A stale-snapshot case verifies Customer resolution after the link was committed by another transaction. Frontend tests exercise existing JSX, role links, filters/read controls, event cleanup and actual Axios success/failure hooks; existing tests cover unread polling, account switching, expired JWT, stale responses, empty/loading/error states and mark-read confirmation.

No notification action posts sales/repayments, changes limits/balances/order totals/payment state, or records cash receipt. Delivery cancellation does not reverse the existing sale. Existing trusted approval/financial services retain exclusive control of ledger changes.

Browser/viewport and safe three-role journey verification remain limited by the unavailable browser environment; no live browser success is claimed. No production fixture records were created. No layouts or colors were changed, but 1536/1366/1024/768/375 viewport behavior is not live-verified.

## Step 15.5 readiness and remaining boundaries

The integration is intended for final verification after the reviewed migrations are applied to the target development environment. No external messaging, instant push, order-ready status, split fulfilment or automatic settlement is supported. The retained-link cancellation policy from Step 15.1 remains unchanged. Ready for Step 15.5 final integration verification after the reviewed development migration. Remaining limitations are unavailable live browser/viewport verification, the existing full-lint baseline, the existing bundle-size warning and manual rather than instant cross-session refresh. No required event, recipient, rollback, concurrency, privacy or financial-isolation test remains failing.


## Consolidated Day 15 checkpoint

Step 15.5 reviews the complete Day 15 implementation and creates the requested local checkpoint. See [final verification and progress report](day15-final-regression-security-review.md) for fresh consolidated results, deployment limitations and Git checkpoint details. Earlier per-step test counts above are historical results.
