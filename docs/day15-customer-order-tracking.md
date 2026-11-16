# Day 15 Step 15.3 — Customer order tracking

## Verified dependencies and audit

Verified the working tree on main against Day 14 checkpoint d917e4f. Steps 15.1 and 15.2 are present as uncommitted changes: the order-to-delivery relationship, secured owner create API, Customer-safe summary and owner fulfilment UI exist. Preserved those files and the unrelated .gitignore edit.

Inspected Customer Dashboard, My Orders, sidebar/layout, catalogue and checkout navigation, OrderRecord, DeliveryTimeline, protected routes, Axios session handling, frontend tests, order schemas/services, delivery projection and notification contracts. Customer routes already include orders and orders/:orderId under the customer role guard. No duplicate page, sidebar entry, backend model, tracking system or route is needed. Existing order notifications and owner delivery notifications are unchanged; Customer delivery notification coordination is outside this UI step.

Backend checks confirm order list/details are scoped by authenticated customer_user_id. Delivery summary resolves the owning Order, then its same-business linked DeliveryRequest. Its explicit DTO contains no Driver identity, contacts, areas, assignment notes or financial fields. Step 15.2 owner capabilities and owner tracking remain separate. No backend change is needed for this step.

## Files created or modified in this step

Created:
- frontend/src/components/customer/CustomerOrderTracking.jsx
- frontend/src/utils/customerOrderTracking.js
- frontend/tests/customerOrderTracking.test.js
- frontend/tests/customerOrderTrackingView.test.js
- docs/day15-customer-order-tracking.md

Modified:
- frontend/src/pages/customer/OrderHistory.jsx
- frontend/src/services/orderService.js
- frontend/src/components/delivery/DeliveryTimeline.jsx

The shared timeline only gains an optional missingTimeLabel; existing owner/Driver behavior remains its default. No global CSS, landing content, palette, logo, Customer/Owner/Driver navigation or financial calculations were changed. AI Summary remains deferred: no provider, credentials, SDK or mock AI response was added.

## Customer routes and API integration

UI routes remain /customer/orders and /customer/orders/:orderId. Existing backend-supported status filters and page_size=10 pagination remain in place. Explore Shops and My Shops retain their distinct purposes and navigation.

All calls reuse the existing Axios JWT/session interceptor and configured API base URL:

| Method | Actual API |
| --- | --- |
| GET | /api/v1/customer/orders?page={page}&page_size=10&status={optional} |
| GET | /api/v1/customer/orders/{order_id} |
| GET | /api/v1/customer/orders/{order_id}/delivery |

The new customerOrderDelivery service calls only the Customer endpoint, never owner/Driver delivery endpoints. No arbitrary business or Driver identifier is supplied. No new backend route or migration is introduced.

Actual safe summary shape:

~~~json
{
  "order_id": 123,
  "delivery_requested": true,
  "delivery": {
    "reference": "DLV-example",
    "status": "assigned",
    "created_at": "2026-11-07T08:00:00",
    "updated_at": "2026-11-07T08:10:00",
    "events": [{"status":"assigned","occurred_at":"2026-11-07T08:10:00"}]
  }
}
~~~

Values above illustrate structure only. For an unlinked order, delivery_requested is false and delivery is null. Production rendering uses API values only.

## Order list/details and status presentation

My Orders retains saved shop name, reference, quantities, historical unit/line prices, LKR totals, method/payment/order status and timestamps. Customer list cards now include a compact safe delivery summary for only the current page (at most ten orders). Details include the full tracking section. There is no full-history fetch or invented global count. Empty unfiltered history, filtered-empty results and an empty page have distinct messages.

Customer-friendly explanations cover submitted, approved, rejected, processing, completed and cancelled statuses. Pending Credit explicitly awaits Shop Owner approval; approved/processing Credit does not imply repayment. Cash remains unpaid under the current backend policy. Completed Order is separate from Delivery Completed. Existing Customer cancellation and owner approval/processing/confirmation rules are preserved. Historical prices are never read from the current catalogue.

## Tracking and refresh

Linked delivery states use actual backend values: available, assigned, picked_up, in_transit, delivered and cancelled. Available is labeled Awaiting Driver assignment. The view shows the reference, current state, requested/updated timestamps and existing recorded delivery timeline. Request time comes from persisted created_at, not a fabricated event. Upcoming/history-unavailable stages have no invented timestamps. Defensive handling of absent timestamps displays Timestamp unavailable; malformed timestamp strings, unsupported statuses, duplicate events, inconsistent links or a mismatched order ID fail closed.

Manual Refresh delivery re-reads the safe summary; Refresh orders refreshes the actual order and remounts/refetches its delivery section. Navigation also reads current state. No polling, real-time claim, WebSocket, location, map or GPS infrastructure is added.

Reuses useCustomerRead/createCustomerRead: abort controllers and increasing request versions reject stale responses, even if the transport ignores abort. Unmount invalidates pending reads. The existing page key includes authenticated user ID, token, path and query, so account/order changes create isolated readers. A new explicit active-role guard also prevents mounting the shared page for the wrong/inactive session.

Loading and failed refreshes clear stale tracking data. 401/403 invokes parent denial handling, clearing order data/actions; the Axios interceptor handles expired JWTs. 404/422 displays an unavailable-to-your-account message. Network/backend/malformed-response errors show tracking unavailable without treating an error as an unlinked delivery. There are keyboard-accessible refresh controls and standard status/alert semantics.

## Privacy and financial independence

The parser allowlists order_id, delivery_requested and delivery reference/status/times/events, stripping any unexpected operational/private fields before React state. It verifies the expected order ID. Backend ownership is authoritative; parsing is defense in depth, not a substitute for authorization. No private order or delivery data is added to persistent browser storage.

Driver identity/contact/vehicle, pickup/drop-off areas, other Customers, internal notes and shop finances are excluded. Customer UI does not navigate to owner/Driver delivery pages. Tracking uses GET only and cannot accept a job, request a delivery, update status or create any financial record. Delivered does not mean Paid; credit approval does not mean repaid. No balances or saved totals are altered.

## Verification

- Targeted new frontend checks: 29 passed, 0 failed/skipped.
- Full frontend suite: 662 passed, 0 failed/skipped in 50.91 seconds, run with node --test --test-concurrency=1. Includes existing Customer Shopping/credit views, Shop Owner fulfilment/deliveries, Driver workflows and authentication regressions.
- Existing backend order-delivery integration/concurrency suite: 48 passed, 0 failed/skipped in 11.58 seconds. Verified settings.MYSQL_DATABASE, engine URL and SELECT DATABASE() all equal lankapex_test_db before running. Includes Customer ownership/role isolation, safe response fields, no-write summaries and financial isolation. No backend code changed, so the full backend suite was not rerun for this UI-only step.
- ESLint for all seven changed/new frontend source/test files: passed.
- Full repository ESLint: failed with the same 8 pre-existing errors and 1 warning in unchanged ShopOwnerCustomers.jsx, ShopOwnerDashboard.jsx and repayments.test.js. No findings in this step's changed files. No separate typecheck script is configured.
- npm run build: passed with Vite 8.3.5, 2,211 modules, 2.40 seconds. JavaScript 771.12 kB / 209.09 kB gzip; CSS 63.53 kB / 13.08 kB gzip. Existing >500 kB chunk-size warning remains.
- git diff --check: passed. No database migrations/resets or development database writes were performed.

Browser inventory was checked and returned no available apps or browsers. Both in-app browser and Chrome had also reported unavailable during Step 15.2. Live safe-data workflow and viewport checks at 1536/1366/1024/768/375 pixels remain unverified. No browser fixture or production mock records were created. The UI reuses existing responsive cards/wrapping controls and a one-column mobile/two-column larger-screen timestamp layout; source/render checks do not establish actual overflow behavior at those widths.

## Remaining issues and Step 15.4 readiness

The Step 15.1 additive migration must still be applied manually to the intended development database before using order-delivery features there; this step does not migrate/reset lankapex_db. See day15-order-delivery-backend.md for the reviewed command. No new migration is required.

The Customer UI integration is ready for Step 15.4 coordination/notifications work, subject to deployment of the earlier backend migration and live-browser verification. Updates are manually refreshed, not instantaneous. This step does not add Customer delivery notification recipients or change existing notification permissions. One retained delivery per Order and no replacement after cancellation remain the backend MVP policy. No files were staged, committed or pushed.


## Consolidated Day 15 checkpoint

Step 15.5 reviews the complete Day 15 implementation and creates the requested local checkpoint. See [final verification and progress report](day15-final-regression-security-review.md) for fresh consolidated results, deployment limitations and Git checkpoint details. Earlier per-step test counts above are historical results.
