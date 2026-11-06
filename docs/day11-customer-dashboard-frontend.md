# Day 11 Step 11.2 — Customer Dashboard frontend

> Final Day 11 audit, security fixes, checkpoint and unresolved linking/browser limitations are recorded in [Step 11.5](day11-final-regression-security-review.md). The results below describe this earlier step.

> Step 11.3 now supplies the My Shops route, explicit account chooser and secure account details. See [the Step 11.3 contract and verification](day11-my-shops-credit-details.md). Sidebar/detail limitations below describe the completed Step 11.2 snapshot.


## Verified backend contract
The actual repository contains the Step 11.1 customer router, Pydantic schemas, router registration and 38 customer-specific tests. Its prior verified full backend run passed 683 tests. This step did not change any backend file.

Customer-only authenticated GETs used:
- /api/v1/customer/dashboard/summary
- /api/v1/customer/shops
- /api/v1/customer/credit-accounts
- /api/v1/customer/transactions

The list previews request page=1, page_size=5. The summary's recent_activity contains at most five records, so the Recent Activity card explicitly counts records among the latest five; it does not invent a daily or all-time activity count. Summary shop/account counts and outstanding balance come directly from backend aggregates. Lists preserve backend order. No customer/user ownership ID is supplied by this dashboard to request another customer's records.

The existing notification router permits Customer users and filters on the authenticated recipient. The existing workflow, polling/lifecycle, bell, inbox and read actions are reused, not duplicated. Customer notification items have no guessed Shop Owner financial destination.

## Routes and components
/customer/dashboard now renders CustomerLayout and CustomerDashboard inside the unchanged customer-only ProtectedRoute. The Driver route retains DashboardPlaceholder; Shop Owner/Admin routes and login/registration designs are unchanged. /customer/notifications renders the existing inbox in a customer-specific wrapper.

CustomerLayout provides the shared logo, header, signed-in name, notification bell and logout to unified /login. CustomerSidebar follows the existing desktop sidebar styling, with a native modal dialog for mobile navigation (native focus/escape handling). Sidebar destinations:
- Dashboard: /customer/dashboard
- My Shops: /customer/dashboard#my-shops
- My Credit: /customer/dashboard#my-credit
- Transactions: /customer/dashboard#transactions
- Notifications: /customer/notifications
- Profile and Settings: non-clickable Planned states

Anchors point to actual dashboard sections; the layout scrolls only to the three allowed hash targets. No dead detail routes or empty feature pages were introduced. Account details actions are deferred until secure detail routes exist in Step 11.3.

The page includes a welcome message, outstanding-credit/shop/account/recent-activity cards, My Shops preview, credit-account preview and recent transactions. Each preview states the number of displayed records and backend total. No shopping, payment, delivery, account linking or new credit action is exposed.

## Data and financial handling
customerDashboardService uses the existing Axios instance and JWT interceptor. It performs only the verified customer GETs, carries AbortSignals, and supplies bounded preview parameters. No redundant token handling or identity lookup was added.

The reader validates currency, fields, monetary strings, IDs, counts, dates, pagination, array size, transaction type/status and unique records before rendering. It copies only documented fields, dropping unknown/private response properties. This is contract validation, not a replacement for authoritative backend ownership checks.

The existing formatDocumentMoney helper is reused. Money stays in exact decimal strings, including large aggregates and negative reversal adjustments. The dashboard performs no floating-point balance calculations and never derives outstanding debt from a preview page. Datetimes display the existing database-recorded clock without adding UTC conversion. Transactions retain their recorded/reference/status fields; reversed rows and reversal adjustments are distinguished. Repayment wording does not imply independent bank/card settlement verification.

## States and security
- Loading: accessible status text and reduced-motion-aware spinner, with unavailable summary values shown as a dash.
- Explicit zero: LKR 0.00 and numeric zero only when supplied by a validated backend response.
- Unlinked user: safe empty-shop explanation, empty accounts/history, no invented records or automatic linking.
- Shop with no credit account: explicit no-account message.
- Partial failures: independent error/retry controls preserve other successful sections.
- Unexpected/malformed response: rejected, never displayed as a real balance.
- 401/403: all financial sections clear, outstanding requests abort and late responses are ignored. Existing Axios session expiration still handles logout globally.
- Slow/unavailable service: timeout/network/service messages with retry; raw exception details are never displayed.

Data exists only in component/controller memory, not localStorage/sessionStorage or another persistent ledger cache. The dashboard session is keyed by authenticated user ID and current session; disposal aborts requests, clears stored data and invalidates old generations. Resource retries also reject superseded responses. Native customer route guards and backend authorization remain authoritative. Shared notification sessions retain their existing user/role/session isolation.

## Visual design
The supplied logo and existing navy, teal, green, amber, red, background and neutral styles are reused. No existing colors or other dashboard designs changed. Cards use existing border/rounded/shadow conventions. Error text uses navy with a red border for contrast. Summary grids use one/two/four columns across existing responsive breakpoints, previews wrap into cards and transactions use a stacked mobile layout instead of a wide overflowing table. Long names/references/amounts wrap. Buttons have visible focus styles and meaningful labels.

No browser was connected. Visual checks at 1536, 1366, 1024, 768 and 375 pixels, actual overflow measurements and mobile dialog interaction were NOT performed. Responsive classes and native dialog semantics were inspected and checked in rendered markup; no visual-success claim is made.

## Files created
- frontend/src/services/customerDashboardService.js
- frontend/src/utils/customerDashboard.js
- frontend/src/components/customer/CustomerSidebar.jsx
- frontend/src/layouts/CustomerLayout.jsx
- frontend/src/pages/customer/CustomerDashboard.jsx
- frontend/src/pages/customer/CustomerNotifications.jsx
- frontend/tests/customerDashboard.test.js
- frontend/tests/customerDashboardView.test.js
- frontend/tests/fixtures/customerDashboardFixtures.js
- docs/day11-customer-dashboard-frontend.md

Modified:
- frontend/src/App.jsx: customer layout/dashboard/notification routes only
- frontend/src/context/NotificationProvider.jsx: enable the existing workflow for Customer, retaining inactive Driver placeholder behavior
- frontend/src/utils/notification.js: add the real customer inbox route
- frontend/tests/notificationsView.test.js: extend the provider expectation for newly supported Customer access

Pre-existing Step 11.1 backend files and the user's .gitignore changes remain untouched. No commit or push.

## Verification
- Targeted customer/controller/view and existing notification tests: 41 passed, 0 failed/skipped.
- Full frontend suite: node --test --test-concurrency=1 — 391 passed, 0 failed/skipped.
- Production build: final npm run build passed (2,169 transformed modules). The existing large-JavaScript-chunk warning remains.
- ESLint on new/modified source files and new tests/fixtures passed. Final post-contrast component test run: 11 passed, 0 failed/skipped. git diff --check passed. Full-project lint was not rerun; the previously documented unrelated baseline lint findings are unchanged.
- Live frontend /customer/dashboard: HTTP 200; live customer summary endpoint without a token: HTTP 401 (route registered and protected). Local frontend and backend preview servers were started because neither was running. No development accounts were created, linked or used for financial testing.
- Browser check: unavailable, as detailed above.
- Backend tests were not rerun for this frontend-only step; no backend integration correction was required.

## Step 11.3 readiness and limitations
Ready to build My Shops and Credit Account Details around the verified contracts. There is no blocker to the implemented read-only dashboard. New users without explicit authorized links will see empty data by design; a secure linking workflow remains outside this step. Dedicated full list/detail pages and pagination controls are future Step 11.3 work. The backend currently has no dedicated credit-account-details endpoint; Step 11.3 must use the existing scoped contracts or add an explicitly authorized, tested customer-only detail route if needed. Current previews intentionally show only the first five records. Production JSX uses no mock data; schema-consistent fixtures are isolated under frontend/tests.
