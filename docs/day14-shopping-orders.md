# Day 14 Step 14.4 — Shopping orders

## Audit and transaction design

Verified the main branch and dirty working tree before editing. Steps 14.1–14.3 exist as uncommitted catalogue models, API services, owner product management and Customer browsing. No Order/OrderItem domain existed. Catalogue endpoint/DTO details remain documented in [catalogue backend](day14-catalogue-backend.md) and [customer browsing](day14-customer-catalogue-browsing.md). Actual stored roles are customer, shop_owner, driver and admin. Catalogue products use per-business DECIMAL(12,2), published/draft/archived publication, manual availability, optional active categories and LKR. There is no stock model or business-level credit-purchasing toggle.

Reused JWT role dependencies, approved-owner membership authorization, Business/BusinessMember/User, Product/ProductCategory, CustomerProfile.user_id, CreditAccount, LedgerEntry, the existing record_credit_sale service, balance_position/account_balances, receipt generation, financial statements and in-app Notification infrastructure. There are no separate CreditSale or Repayment models: both are existing ledger entry types. Credit permission follows existing approved-business + active linked credit-account policy. Account selection never uses matching contact information. Multiple eligible linked accounts are deliberately rejected as ambiguous at checkout; the saved account is rechecked at approval.

Unrelated .gitignore edits, prior Day 14 work and a separate LandingPage headline edit are preserved. Nothing was committed or pushed.

## Models and migration

- backend/app/models/order.py: Order and OrderItem.
- backend/alembic/versions/d0e6f9a8b348_shopping_orders.py follows c9d5e8f7a237.
- Orders have a unique reference, authenticated customer user/business, scoped binary request key, canonical request hash, cash/credit method, distinct payment/order statuses, DECIMAL(14,2) subtotal/total, optional saved credit account and unique linked ledger entry, creation/update times.
- Items store product ID, immutable product name, quantity, DECIMAL unit-price and line-total snapshots. Foreign keys restrict deletion; product edits/archive never rewrite history.
- Database checks constrain statuses, financial combinations, positive totals, quantity 1–99 and line arithmetic. Up to 50 distinct products; duplicate products and totals above 999999999999.99 are rejected.
- Migration adds two tables/indexes and expands notification checks without deleting existing records. Downgrade refuses destructive deletion. Test migration applied successfully and Alembic check detected no metadata drift.
- Development lankapex_db remains at b8c4d7e6f126. No development migration/reset was performed.

Manual development migration, after reviewing the two pending migrations, from the project root:

~~~powershell
Set-Location backend
$env:MYSQL_DATABASE = 'lankapex_db'
.\.venv\Scripts\python.exe -m alembic upgrade head
~~~

This applies both catalogue c9d5e8f7a237 and shopping d0e6f9a8b348. It was NOT executed against development during this task.

## Lifecycle and financial behavior

| Method / state | Permitted actor and action | Result |
|---|---|---|
| Credit submitted | Approved active owner: approve | approved / posted; exactly one existing-ledger credit sale |
| Credit submitted | Owner: reject or cancel; Customer: cancel own | rejected or cancelled / pending; no debt |
| Credit approved | Owner: process | processing / posted |
| Cash submitted | Owner: process | processing / unpaid; no credit ledger entry |
| Cash submitted | Owner: reject or cancel; Customer: cancel own | rejected or cancelled / unpaid |
| Either processing | Owner: complete | completed; financial state unchanged |
| Terminal rejected/cancelled/completed | Same successful action replay only | No additional mutation or notification |

Approval replay after processing/completion returns the posted order without a new sale. Arbitrary status PATCH is absent. Posted credit cannot be cancelled or rejected; reversal/refund and reopening workflows are outside scope. Cash completion does not prove receipt of cash. No cash-paid confirmation or invented collection record exists.

Submission locks/current-reads the approved business, active Customer user, products/categories, and eligible account if credit. It calculates authoritative Decimal totals and persists snapshots. Submitted credit does not reserve credit or create debt; approval rechecks the limit. No client prices, totals, customer/account IDs or delivery assignment are accepted.

Approval checks active approved business owner membership, locks current customer then order then account/ledger, verifies persisted CustomerProfile.user_id linkage and same-business saved account, and calls the existing trusted sale service. That service does not commit; it locks the account and applies the unchanged authoritative balance/limit/reversal rules. The order references the sale and LedgerEntry.order_id references the order before one route commit. A manual sale with a colliding internal key is rejected rather than adopted. Failures roll back order, ledger and notifications together. The order lock, unique sale link and deterministic sale key prevent duplicate debt; account locking prevents combined approvals exceeding the limit.

Submission retry keys are scoped to Customer with a canonical hash including shop, method, sorted product IDs and quantities. Same key/body returns the persisted snapshot without recalculating current prices; changed payload conflicts. Current user locking plus the database unique constraint serializes concurrent retries. Unknown server/network results retain the same pending payload/key in the in-memory cart provider.

## Real backend API

All routes use /api/v1 and Cache-Control: no-store. Customer routes require an active stored Customer JWT; owner routes require an active Shop Owner JWT plus approved business with active owner membership. Admin has no bypass. Unknown/foreign order IDs return 404. Errors exclude SQL diagnostics.

| Method | Path | Request / response |
|---|---|---|
| POST | /customer/orders/quote | Cart -> authoritative current Quote, credit guidance |
| POST | /customer/orders | Cart + payment_method + request_key -> persisted Order (201, including replay) |
| GET | /customer/orders | Own paginated Orders; page/page_size/status |
| GET | /customer/orders/{order_id} | Own Order |
| POST | /customer/orders/{order_id}/decision | Only action cancel for own submitted Order |
| GET | /shop-owner/orders | Required business_id, page/page_size/status -> Orders |
| GET | /shop-owner/orders/{order_id} | Required business_id -> authorized Order |
| POST | /shop-owner/orders/{order_id}/decision | Required business_id; action approve/reject/process/complete/cancel |

Pagination: page 1–1000000, page_size 1–100 (UI uses 10). Responses explicitly project public order fields, not idempotency keys/hashes, account IDs, customer user IDs, contact details or internal notes.

Example request structure (illustrative IDs):

~~~json
{"business_id":1,"items":[{"product_id":2,"quantity":2}],"payment_method":"credit","request_key":"unique-request-key-16-or-more"}
~~~

Cart quote request omits payment_method and request_key. Quote response:

~~~json
{"business_id":1,"business_name":"Shop","currency":"LKR","items":[{"product_id":2,"product_name":"Rice","quantity":2,"unit_price":"125.25","line_total":"250.50"}],"subtotal":"250.50","total":"250.50","credit_available":true,"credit_guidance":"Credit requires Shop Owner approval; no debt is created by submission."}
~~~

Order response structure:

~~~json
{"order_id":1,"reference":"ORD-<server-uuid>","business_id":1,"business_name":"Shop","customer_name":"Customer","payment_method":"credit","payment_status":"pending","status":"submitted","currency":"LKR","subtotal":"250.50","total":"250.50","credit_sale_id":null,"created_at":"2026-11-07T00:00:00","updated_at":"2026-11-07T00:00:00","items":[{"product_id":2,"product_name":"Rice","quantity":2,"unit_price":"125.25","line_total":"250.50"}]}
~~~

Lists wrap orders with page/page_size/total. Money is always serialized as decimal strings. Existing UTC-naive timestamp convention is preserved. Customer display name is exposed only to the same Customer or authorized owner. Approved credit becomes visible in existing financial transactions/receipts/statements using the real ledger entry.

## Frontend and integration

- /customer/cart: single-shop cart; quantity edits/removal/clear; current API prices; checkout navigation.
- /customer/checkout: refreshed server quote, clearly estimated total, cash or eligible credit, disabled duplicate submission, stable retry payload/key, persisted order result and changed-price guidance.
- /customer/orders and /customer/orders/:orderId: own history/detail, pagination/status filter, confirmed submitted-order cancellation.
- /shop-owner/orders and /shop-owner/orders/:orderId?business_id=...: approved business selector, history/detail, confirmed credit approval/rejection and cash processing/completion. /shop-owner/credit-orders redirects to Orders.
- Catalogue cards/details add only available products. Selecting another shop prompts explicit replacement or keeping the current cart.
- Existing customer/owner layouts and LankaPex colors are reused. No global CSS, dashboard redesign, mock production records, stock deduction, tax/fee, online payment or automatic delivery creation.
- Cart and pending payload exist only in memory, scoped to the authenticated user/token. Reload/logout clears the cart; financial information is not persisted in localStorage/sessionStorage. Retry within the session uses the same key; a new deliberate cart is a new order.
- React read requests abort on context changes; stale quotes cannot be used for a changed cart. Role guards and token-keyed providers keep sessions isolated. Server authorization remains authoritative.
- No order notes or rejection reasons are added, since there was no existing supported order schema for them.

Notifications: order_submitted to active owners; order_approved/rejected/processing/completed/cancelled to the active linked Customer. Existing sale notification remains a separate financial event. Writes share the order transaction; replay branches skip new events and recipient/event uniqueness prevents duplicates. Event links route to authorized order details. No external messaging.

Delivery boundary: existing delivery module is untouched. No delivery_request_id is added prematurely; a future explicit authorized workflow can add a business-consistent link. Checkout creates no delivery request.

## Files in Step 14.4

Created:
- backend/app/models/order.py
- backend/app/schemas/order.py
- backend/app/services/order_service.py
- backend/app/routers/orders.py
- backend/alembic/versions/d0e6f9a8b348_shopping_orders.py
- backend/tests/test_orders.py
- backend/tests/test_orders_concurrency.py
- backend/scripts/order_browser_fixture.py
- frontend/src/utils/shopping.js
- frontend/src/context/ShoppingContext.js
- frontend/src/context/ShoppingProvider.jsx
- frontend/src/services/orderService.js
- frontend/src/components/customer/AddToCart.jsx
- frontend/src/pages/customer/ShoppingCart.jsx
- frontend/src/pages/customer/OrderHistory.jsx
- frontend/tests/shopping.test.js
- frontend/tests/shoppingView.test.js
- frontend/scripts/verifyShoppingOrders.mjs
- docs/day14-shopping-orders.md

Modified integrations:
- backend/app/main.py; backend/app/models/__init__.py
- backend/app/models/notification.py; backend/app/schemas/notification.py; backend/app/services/notification_service.py
- frontend/src/App.jsx
- frontend/src/components/customer/CustomerSidebar.jsx; frontend/src/components/shopOwner/ShopOwnerSidebar.jsx
- frontend/src/layouts/CustomerLayout.jsx; frontend/src/layouts/ShopOwnerLayout.jsx
- frontend/src/pages/customer/CustomerCatalogue.jsx; frontend/src/utils/notification.js

## Validation and remaining work

- Effective test settings, engine database and SELECT DATABASE() all verified as lankapex_test_db before mutation. Fixture cleanup rechecks exact nonce-owned identities and touches only those fixture rows. No automated mutating tests use lankapex_db.
- Targeted order backend: 37 passed, 0 failed/skipped. Includes real independent-connection forced lock races, submission retries, account limits/linkage, snapshot history, notification deduplication, manual-sale reference conflict, expired JWT and failure after ledger posting with complete rollback.
- Full backend final run: 963 passed, 0 failed/skipped in 119.93 seconds (initial run: 960 passed before the final three security-edge tests). Existing short-HMAC test warning remains.
- New frontend unit/React tests: 21 passed, 0 failed/skipped.
- Full frontend: 609 total; 607 passed, 2 failed, 0 skipped. One landing headline assertion plus its parent suite fail because a separate working-tree edit changes Management to Ma2xnagement. This task did not edit LandingPage or weaken its tests. All shopping and prior financial/catalogue tests passed.
- Vite production build passed (756.40 kB JS, 204.90 kB gzip); existing large-chunk advisory remains.
- All Step 14.4 application files, tests and browser script pass configured ESLint. Full lint retains existing 8 errors/1 warning in ShopOwnerCustomers, ShopOwnerDashboard and repayments.test.js. No separate typecheck is configured.
- Browser test against actual lankapex_test_db passed the Customer-to-owner credit/cash lifecycle. 50 responsive + 50 accessibility checks at 1536/1366/1024/768/375; no horizontal overflow, overlapping actions, unlabeled form fields or unnamed buttons; keyboard focus checked. Cash completed/unpaid with no sale; credit completed with exactly one LKR 250.50 sale. Mobile checkout and desktop owner screenshots visually inspected.
- The final browser run also deliberately lost the first successful submission response. Retry reused the same key and returned the same persisted order; the final database still contained exactly two intended orders and one credit sale. Browser verification used the supported host runtime.
- Evidence (ignored): .server-logs/day14-orders-browser/results.json, screenshots, backend/frontend/lint logs. Browser fixture tokens are removed during cleanup. Temporary QA listeners are stopped after verification.

Step 14.5 can proceed with the implemented order workflow. Remaining release checks: resolve the unrelated landing headline/test mismatch and existing full-repository lint failures; deliberately apply pending migrations to development before using these APIs there. Refunds, posted-order cancellation, cash receipt confirmation, persistent carts and order-to-delivery linking remain outside this step's supported policy.


## Step 14.5 final verification

See [final regression and financial-security review](day14-final-regression-security-review.md) for the current checkpoint. This document retains the historical Step 14.4 counts above; the final review supersedes its earlier landing-test failure after the user requested restoring Management. The review verifies catalogue management, Customer browsing, cash/credit orders, atomic approval, linked account limits, notifications and delivery isolation. It adds final MySQL integration checks, fixes pending checkout payment selection and mobile header overlap, preserves the existing LankaPex design, and records actual full-suite/build/browser results and the scoped local Git checkpoint.

Final verified totals: 969 backend tests and 610 frontend tests passed (zero failures/skips); production build passed; 170 responsive plus 170 basic accessibility checks passed after mobile fixes; all 33 Day 14 frontend files pass scoped lint. Existing full-repository lint remains eight errors/one warning. Day 14 is complete for the verified module scope and has a local main-branch checkpoint named Day 14: complete customer shopping and credit order integration; see the final report and git log for its containing hash. The development database was not migrated. Known memory-cart, offline-cash and posted-cancellation boundaries remain documented above.
