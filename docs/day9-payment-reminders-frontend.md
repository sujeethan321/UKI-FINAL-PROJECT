# Day 9 Step 9.3 — Payment Reminder Frontend Integration

Implemented on 2026-11-04. Required frontend tests and production build pass. Interactive browser verification remains unavailable in this environment.

## Existing code reused

- Shared ShopOwnerLayout, header, sidebar, protected routes and AuthContext remain in place.
- Existing authenticated Axios client supplies JWTs, timeout handling and session expiry behavior.
- Existing business-context service supplies approved owned businesses; there is no separate global active-business store in the current frontend. The page follows the payment pages' local selection pattern and accepts Customer Details navigation state only after checking trusted business/customer responses.
- Existing customer list/details services supply authorized contact information and effective outstanding balances.
- Existing repayment fingerprint and secure random identifier helpers are reused. Reminder session storage follows the existing opaque hash/key pattern with its own per-user namespace.
- Existing payment-page cards, fields, alerts, tables and typography are preserved, with navy #10243E and teal #12B8A6. Notifications previously had only a disabled navigation item, with no implemented page or reminder modal.

## Files created

- frontend/src/pages/shopOwner/ShopOwnerNotifications.jsx
- frontend/src/pages/shopOwner/reminderWorkflow.js
- frontend/src/services/shopOwnerReminderService.js
- frontend/src/utils/reminder.js
- frontend/tests/reminders.test.js
- frontend/tests/remindersView.test.js
- docs/day9-payment-reminders-frontend.md

## Files changed

- frontend/src/App.jsx: protected Notifications route.
- frontend/src/components/shopOwner/ShopOwnerSidebar.jsx: enable existing Notifications item.
- frontend/src/pages/shopOwner/ShopOwnerCustomers.jsx: Prepare Reminder navigation action carrying business/customer selection.

Pre-existing working-tree backend and .gitignore changes were preserved. No backend changes, migrations, ledger writes, commits or pushes were performed by this integration.

## Backend contracts

POST /shop-owner/payment-reminders?business_id=<id>

Body: customer_id (integer), channel (internal/copy/whatsapp/sms), language (en/ta), note (trimmed string or null, at most 1000 characters), idempotency_key (string). No amount is sent. The backend calculates the effective outstanding snapshot and final message. A new record returns 201; an identical replay returns 200 with replayed=true.

GET /shop-owner/payment-reminders?business_id=<id>

Supported filters used: customer_id, status=recorded, ordering=newest/oldest, page, page_size. Response: business_id, page, page_size, total, reminders. Each record supplies reminder_id, business_id, customer_id, credit_account_id, outstanding_amount, currency=LKR, message, channel, language, note, status=recorded, created_at, delivery_allowed=false and replayed. History has no customer-name field or idempotency-key lookup. Names are resolved from the authorized business customer list with a customer-ID fallback.

Existing reads: GET /shop-owner/business-context, GET /shop-owner/customers?business_id=<id>, GET /shop-owner/customers/<customer_id>?business_id=<id>. Details provide customer, credit_account and effective outstanding_balance, excluding reversed ledger effects as calculated by the backend.

## Creation, preview and history

Only approved businesses load financial data. Missing credit accounts, zero outstanding, inactive accounts, unavailable details, and invalid fields block new reminder creation. Missing phone details are labeled Unavailable and restrict intended channels to Internal. No mock amounts, due dates or overdue classifications are introduced.

English/Tamil draft previews use the selected customer's name, shop name and exact decimal LKR balance. They are explicitly labeled unsaved. After confirmation, the exact server message and snapshot replace the draft. Notes remain internal and are not appended to the message. Only recorded is displayed as a record status; saving never claims delivery.

History supports customer/status filters, ordering and pagination, with expandable exact server messages. Timestamps explicitly use Asia/Colombo. Aborts and request generations prevent stale business, customer and history responses from replacing current data. Customer switches clear previous customer notes and previews.

## Idempotency and cooldown

A cryptographically generated operation key and SHA-256 request fingerprint are saved before dispatch. Only opaque identifiers are persisted in per-user session storage, without customer, contact, note or financial content. Concurrent clicks are locked synchronously. Confirmed forms cannot submit again until a new operation is explicitly started or the intent changes.

Timeouts, network failures, 5xx errors and malformed success responses retain the original pending key. Different operations remain blocked while pending. Users must re-enter the identical original business, customer, channel, language and normalized note to reconcile through same-key POST replay, including after reload. Replays remain available after a balance falls to zero. Prior uncertainty is retained even if a later retry receives an authorization or validation error. There is deliberately no force-reset control for unresolved operations.

History can be reviewed but cannot safely prove which request completed because the API omits keys. No automatic matching by amount/customer/time is attempted. A confirmed replay safely resolves the operation and clears its key. Definite first-attempt 4xx rejection retains the key for identical retries but allows a changed intended operation.

Cooldown 409 responses show a specific restriction. The backend provides no allowed retry timestamp, so the UI states that explicitly. No alternate-key workaround or automatic key rotation is performed after cooldown or uncertain results.

## Error handling

401 requests sign-in; 403 explains forbidden access/business approval; 404 explains missing customer/account/reminder; 409 maps known cooldown/account/contact/idempotency conflicts; 422 requests corrected inputs. Reads show sanitized server/connection errors. Mutation 5xx and network failures explain that the result is uncertain. Raw API details, traces and secrets are not rendered. Existing page alert styles are used.

## Verification

- npm test: 204 passed, 0 failed, 0 skipped, 0 cancelled. Includes 45 new reminder checks under the existing Node test runner, controlled API promises, Vite SSR transformation, actual React server rendering and mocked Axios adapters. No requests create real reminders in a development or test database.
- npm run build: passed with Vite 8.3.5; 2142 modules transformed.
- Targeted ESLint on all new reminder source/test files: passed.
- Route and component smoke checks: Notifications, Sidebar and App imports/rendering passed through Vite in the test suite.
- Browser smoke test: unavailable. Browser inventory returned no browsers and opening an in-app browser returned Browser is not available: iab. No interactive authenticated session or visual browser review was possible.
- Backend tests: not run; backend code was not changed. No automated tests touched lankapex_db or lankapex_test_db.

## Remaining limitations

- Vite reports a non-failing JavaScript chunk-size warning: 511.82 kB minified (149.31 kB gzip), above its 500 kB threshold.
- Interactive browser smoke testing remains to be done in a connected authenticated browser.
- Backend history has no request-key lookup, customer-name snapshot or cooldown retry timestamp. These are handled with same-key replay, current authorized customer names/ID fallback, and an honest restriction message respectively.
- External delivery and communication permission remain unavailable by design. No SMS, WhatsApp or email is sent.
