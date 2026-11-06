# Day 11 Step 11.3 — My Shops and Credit Account Details

> Final Day 11 audit, security fixes, checkpoint and unresolved linking/browser limitations are recorded in [Step 11.5](day11-final-regression-security-review.md). The results below describe this earlier step.

## Audit and implementation
Steps 11.1 and 11.2 exist in the repository: customer-only dashboard APIs, scoped ledger projections, customer layout/sidebar, dashboard, notification integration, authenticated Axios service and tests. Existing explicit CustomerProfile.user_id links support this feature. Registration creates a User, without automatically linking shop-managed customer profiles. No identity-linking blocker exists for explicitly linked customers; new unlinked users correctly see empty data.

The audit found no dedicated customer account-detail API and no business filter on the account list. This step adds those minimal read-only capabilities and reuses existing summary, shop and transaction APIs. Login, registration, Shop Owner financial rules, notification polling and the palette remain unchanged. No migrations, payment actions, development financial fixtures, automatic links, commits or pushes were introduced.

## Routes and UI
- /customer/shops: My Shops, backend summary totals, paginated linked-shop cards, shop identifiers, linked-account count and outstanding balance. View Details expands an account chooser. Every account has an explicit link; multiple accounts never cause an arbitrary first-account selection. Accounts are paginated independently within each shop.
- /customer/credit/:accountId: account heading, business name/identifier, account identifier/status, authoritative outstanding balance, limit and available credit, paginated account activity and fixed Back to My Shops link.

Both routes are nested in the existing Customer-only ProtectedRoute and CustomerLayout. The sidebar My Shops destination now points to /customer/shops. My Credit and Transactions retain the supported dashboard anchors; Notifications retains its authorized inbox. Header titles follow the current route. Existing desktop/mobile sidebar and shared logo are reused.

Cards retain existing responsive patterns and colors. Names, references and exact monetary strings wrap on small screens. Loading/status text, retry controls, pagination disabled states and expansion ARIA attributes are included. Activities distinguish credit sales, repayment records, reversed records and reversal adjustments; repayment records do not claim bank/card settlement verification.

## API contract
All paths below have prefix /api/v1 and use the shared authenticated Axios client:
- GET /customer/dashboard/summary — existing authoritative aggregate totals.
- GET /customer/shops?page=N&page_size=10 — existing shop list.
- GET /customer/credit-accounts?business_id=ID&page=N&page_size=10 — existing account list extended with an optional positive business_id filter. The business must be explicitly linked to the caller and approved; otherwise safe 404. Linked shops without accounts return an empty list. Unfiltered behavior remains compatible.
- GET /customer/credit-accounts/{credit_account_id} — new positive-ID detail route, returns {currency: "LKR", account: CustomerCreditAccount}. Account fields are credit_account_id, business_id, business_name, account_status, credit_limit, outstanding_balance, advance_balance, available_credit and opened_at.
- GET /customer/transactions?credit_account_id=ID&page=N&page_size=10 — existing authorized account history, newest first. Sales and repayments are ledger records; no separate unsupported record endpoint was invented.

List endpoints retain their existing envelopes and server page-size bounds (1–100). The UI requests 10 records. Successful responses use Cache-Control: no-store. No write route was added.

## Ownership and financial accuracy
The existing verified JWT/active-user dependency and Customer role guard supply user.user_id. Queries require CustomerProfile.user_id to equal that identity, CustomerProfile.business_id to equal the credit account creditor business, and Business.approval_status to be approved. User IDs are never selected from caller input, email or phone. Unknown, foreign, unlinked, pending-business and inconsistent-business detail requests all return the same 404 response. Anonymous users receive 401; other roles receive 403. Every account history request independently rechecks ownership.

Summary and per-shop totals come from the existing full-history SQL/Decimal projections, distinct linked businesses and one position per account. Reversals remove the same-account original entry under existing ledger definitions. Each account's nonnegative outstanding debt is summed once; an advance on one account does not offset another account's debt. Detail/list mapping shares the existing balance_position helper. Available credit is supplied by the backend, never inferred from activity pages. Money remains exact decimal strings in the browser and uses the existing LKR formatter; there are no floating-point financial calculations.

## State handling
Explicit states cover no shops, linked shop without accounts, closed/suspended accounts, zero balances, empty activity, invalid route IDs, unauthorized/missing records, expired sessions, unavailable service and malformed responses. Missing or foreign records show a generic unavailable message and safe back link. Detail history loads only after authorized detail succeeds. 401/403 errors clear visible financial content for the page; the existing global session-expiry flow remains active.

Readers keep data only in memory, abort pending requests on disposal/replacement, reject stale generations and drop undocumented fields. Resource components are keyed by user/session and route/page parameters. Response validators check page metadata, exact monetary strings, unique IDs and requested business/account identity. These checks complement backend authorization; they do not replace it.

## Files in this step
Added:
- frontend/src/pages/customer/MyShops.jsx
- frontend/src/pages/customer/CreditAccountDetails.jsx
- frontend/src/components/customer/CustomerData.jsx
- frontend/src/hooks/useCustomerRead.js
- frontend/src/utils/customerAccounts.js
- frontend/tests/customerAccounts.test.js
- frontend/tests/customerAccountViews.test.js
- docs/day11-my-shops-credit-details.md

Extended existing Step 11.1/11.2 files:
- backend/app/routers/customer.py
- backend/app/schemas/customer_dashboard.py
- backend/app/services/customer_dashboard_service.py
- backend/tests/test_customer_dashboard.py
- frontend/src/services/customerDashboardService.js
- frontend/src/App.jsx
- frontend/src/layouts/CustomerLayout.jsx
- frontend/src/components/customer/CustomerSidebar.jsx
- frontend/tests/customerDashboardView.test.js
- docs/day11-customer-dashboard-frontend.md (link to the updated contract)

The pre-existing .gitignore changes and other uncommitted Day 11 work are preserved.

## Verification
- Targeted frontend controller/view/dashboard tests: 28 passed, no failures or skips.
- Final full frontend regression: node --test --test-concurrency=1 — 408 passed, no failures or skips. Includes existing login, registration, dashboard and notification tests.
- Customer backend targeted tests: 50 passed. Connection preflight checked both configured SQLAlchemy database and SELECT DATABASE() as lankapex_test_db before pytest. Development database tests were not run.
- Final isolated full backend regression: 695 passed, no failures or skips, exit 0 (329.93 seconds), using the same verified test-database launcher. One existing JWT-test HMAC-key-length warning remains. An initial accidental overlapping launch produced three fixture-setup errors; both runs ended before this clean isolated rerun, which passed.
- npm run build: passed, 2,174 modules transformed. Existing JavaScript chunk-size warning remains.
- ESLint on the changed customer source files and new tests: passed. git diff --check: passed.
- Frontend tests cover distinct account links, backend summary totals independent of pagination, exact large/zero values, activity semantics, invalid/foreign IDs, role guards, API parameters/JWT/cancellation, response projection, network retry and stale/disposed requests. Backend tests extend ownership, role, business isolation, read-only method behavior, duplicate aggregation, exact Decimal balances and existing reversal rules.

## Browser limitation and readiness
No browser or native app surface was connected. Server-rendered React, protected-route/API contracts and responsive class assertions were tested; interactive clicks, mobile screenshots, actual overflow measurements and live authenticated browser navigation were not verified. The existing large production bundle warning remains. Previously documented unrelated full-project lint findings are outside this step; targeted lint is used for changed customer files.

The read-only feature is implemented for Step 11.4. Before release, perform an authenticated desktop/mobile browser walkthrough with explicitly linked authorized fixtures. A secure customer-linking workflow remains a separate feature; no automatic linking is appropriate here.
