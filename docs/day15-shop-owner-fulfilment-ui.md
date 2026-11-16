# Day 15 Step 15.2 — Shop Owner order fulfilment

## Audit and dependencies

Verified main at d917e4f (Day 14 checkpoint), with the uncommitted Step 15.1 bridge and unrelated .gitignore edit preserved. Inspected the existing OrderHistory, ShopOwnerDeliveries, sidebar/layout/header, Axios session interceptor, order/approval/delivery services, timeline, confirmation pattern, business authorization and tests. No duplicate Orders/Deliveries routes or navigation were needed. The corrected landing headline, logo, palette and other dashboards were not edited. AI Summary remains deferred; no provider, key, mock response or AI dependency was added.

The existing Shop Owner Orders page is the owner variant of OrderHistory. It already has authorized business selection, paginated status-filtered history, saved item prices, credit approval/rejection and cash processing confirmations. Delivery Management already accepts business_id and delivery_id query parameters and provides tracking/cancellation. Existing notifications continue linking to authorized delivery views; no new notification contract is required.

## Files

Created:
- frontend/src/components/shopOwner/OrderFulfilment.jsx
- frontend/src/utils/orderFulfilment.js
- frontend/tests/orderFulfilment.test.js
- frontend/tests/orderFulfilmentView.test.js
- docs/day15-shop-owner-fulfilment-ui.md

Modified for this step:
- frontend/src/pages/customer/OrderHistory.jsx (shared existing owner/customer component; fulfilment panel owner-only)
- frontend/src/services/orderService.js
- backend/app/services/order_delivery_service.py
- backend/app/schemas/order_delivery.py
- backend/tests/test_order_delivery.py

Step 15.1 files remain uncommitted. Its additive migration e1f7a0b9c459 remains required; no additional migration is needed for Step 15.2.

## Routes and API contracts

Existing UI routes: /shop-owner/orders and /shop-owner/orders/:orderId?business_id={id}. View Delivery opens /shop-owner/deliveries?business_id={id}&delivery_id={id}. Customer routes, Driver routes and navigation are preserved.

Axios continues using the configured API base URL and existing JWT interceptor. Actual backend endpoints:

| Method | Route |
| --- | --- |
| GET | /api/v1/shop-owner/orders?business_id={id}&page={page}&page_size=10&status={optional} |
| GET | /api/v1/shop-owner/orders/{id}?business_id={id} |
| POST | /api/v1/shop-owner/orders/{id}/decision?business_id={id} |
| GET/POST | /api/v1/shop-owner/orders/{id}/delivery?business_id={id} |

The owner delivery projection now adds can_request_delivery (boolean) and delivery_unavailable_reason (string or null). GET derives these through the same server-side eligibility checks as POST. Existing linked deliveries always disable creation, including cancelled ones. The Customer projection is unchanged. Missing/invalid capability fields fail closed in the frontend parser. No authorization, credit calculation or lifecycle rule changed.

## Fulfilment behavior

The list shows item counts, saved totals, customer display name, method/payment/order states, dates and an owner-only linked delivery summary. Summaries are fetched only for the current page (at most ten), never for the entire history. Status filtering and pagination are backend-driven. Reference search, payment/delivery filters and global order summary cards are omitted because the APIs do not support them; page totals are not presented as global status counts.

Existing actions are retained: submitted Credit → approve/reject/cancel; submitted Cash → process/reject/cancel; approved → process; processing → complete. Each uses the existing confirmation and decision API. Cash remains unpaid; approval posts through the established credit service only. A failed owner decision refreshes current details and retains its error. Completed/rejected/cancelled history is read-only under existing rules.

Request Delivery appears only after a verified backend capability. Pending Credit, unprocessed Cash, invalid/reversed approval and completed orders do not receive that action. Backend POST independently revalidates role, business, order, credit and concurrency requirements.

The inline form follows existing card/form/button conventions. Only required pickup_area and delivery_area fields are sent, trimmed and validated as 1–160 single-line Unicode characters. Both start empty because no supported stored destination exists. There is no invented address, contact, weight, instruction, vehicle, location or fee input. The user explicitly supplies public area names, with private contact/address guidance.

An in-flight latch blocks duplicate submissions and edits; pending order decisions also block the delivery form. Success requires a valid persisted POST response scoped to the exact order/business and matching areas. Then the actual order and linked delivery are re-read. No optimistic delivery is fabricated. Equivalent retries use Step 15.1's locked permanent link; conflicts refresh state. Unknown network outcomes retain and freeze the submitted areas, offer explicit same-input retry, and refresh to discover a real link. Nothing retries automatically or stores delivery text in browser storage.

Requests are scoped to mounted session/order/business. Abort signals and monotonically increasing read versions reject late responses. Unmount invalidates mutation results. 401/403/404 clear delivery data and controls; the existing Axios interceptor handles expired sessions. Error messages distinguish validation, authorization, conflicts and uncertain outcomes.

Linked details show reference, independent delivery status, public areas, permitted Driver display name/assignment time, persisted created/updated times and the existing DeliveryTimeline component. Refresh delivery or Refresh orders retrieves assignment and progress updates. There is no new polling, assignment or cancellation service. View Delivery uses the existing management page for tracking/cancellation. Cancelled requests remain linked and cannot be silently replaced.

## Financial isolation

Delivery creation and progress do not change totals, price snapshots, payment/approval state, balances or ledger records. No sale, repayment, cash collection or settlement is added by this UI. Order completion remains an explicit existing owner decision; delivered never means paid or automatically completed. Backend tests snapshot financial records around bridge operations and Driver progress. The read-only eligibility projection invokes validation only and performs no DML.

## Verification

- Targeted frontend: 32 passed, 0 failed/skipped (23 new fulfilment checks plus existing shopping view regression).
- Full frontend: 633 passed, 0 failed/skipped, 93.04 seconds. Includes Shop Owner Deliveries, Customer Shopping, Driver module, auth and financial view contracts.
- Full backend on verified lankapex_test_db: 1,017 passed, 0 failed/skipped, 187.04 seconds. One existing short test-key warning in test_jwt.test_tampered_token_rejected.
- Final targeted backend: 48 passed, 0 failed/skipped, 13.94 seconds. Includes concurrent delivery creation and read-only eligibility for invalid/reversed credit approvals.
- Changed-file ESLint: passed (all six changed/new frontend source/test files).
- Full ESLint: failed with the existing 8 errors and 1 warning in unchanged ShopOwnerCustomers.jsx (three effect state errors), ShopOwnerDashboard.jsx (unused Store, effect state error, dependency warning), and repayments.test.js (three unused imports). No new lint findings in this step.
- Vite production build: passed, Vite 8.3.5, 2,209 modules; JavaScript 765.98 kB / 208.20 kB gzip, CSS 63.53 kB / 13.08 kB gzip. Existing large-chunk warning remains; build also emitted plugin timing diagnostics.
- No separate typecheck script is configured. git diff --check passed.
- Backend tests reuse the test-database session guard; no development database writes, migrations or resets were performed.

Browser verification was attempted with the computer-use skill's preferred browser tools. Both the in-app browser and Chrome reported unavailable; no test browser fixture was created. Live workflow and viewport checks at 1536/1366/1024/768/375 pixels therefore remain unverified. The implementation reuses responsive min-width-zero cards, wrapping actions/text and single-column mobile/two-column larger-screen forms, but that is not a substitute for live viewport verification.

## Rollout, blockers and Step 15.3

No development database migration/reset was run. The effective settings, engine and actual database were verified as lankapex_test_db before automated mutations. Deploy the updated backend and apply the reviewed Step 15.1 migration manually to the intended development database before using the new UI there (see day15-order-delivery-backend.md). A backend lacking the new eligibility fields displays a safe unavailable/error state.

Ready for Step 15.3 backend integration: the existing Customer-safe summary endpoint is available; Customer delivery tracking UI was deliberately not built here. Known scope limits remain one retained request per order (no replacement/split delivery), public areas only, manual progress refresh and unsupported search/payment/delivery filters/global order counts. No files were staged, committed or pushed.


## Consolidated Day 15 checkpoint

Step 15.5 reviews the complete Day 15 implementation and creates the requested local checkpoint. See [final verification and progress report](day15-final-regression-security-review.md) for fresh consolidated results, deployment limitations and Git checkpoint details. Earlier per-step test counts above are historical results.
