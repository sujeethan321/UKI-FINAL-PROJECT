# Day 18 Step 18.2 — Shop Owner and Customer experience review

Date: 2026-11-07. Branch `main`, base HEAD `d917e4f`. Evidence describes the
working tree with uncommitted Day 15–18 dependencies; it does not certify HEAD
alone. No deployment, commit, push, migration, database reset or real-user
provisioning was performed. AI Summary stays deferred and is not a UAT defect.

## A. Repository and prior UAT audit

[Step 18.1 matrix](day18-uat-matrix.md) records 1229 backend passes/one blocked
migration skip, 806 frontend passes, the corrected repayment timing test, and
remaining lint/report/browser gaps. Existing tests already cover registration,
customer management, Decimal sales/repayments/statements, product publication,
cart validation, order price snapshots, credit approval races, delivery links and
notification privacy. Those scenarios were reused rather than recreated.

Reviewed actual registration, Shop Owner dashboard/credit-sale/repayment pages,
Customer cart/checkout/statement pages, registration and money utilities, routes,
services, backend auth/customer schemas and the existing rollback test fixtures.
The dashboard explains business registration/Admin approval and restricts
unapproved businesses. Unsupported dashboard statistics are not invented.

Browser inventory again returned `apps: [], browsers: []`. No installed browser
automation workflow was used; no screenshots, browser E2E or live UI interaction
is claimed. Node/Vite/React static rendering and controller tests provide useful
contract coverage, not viewport/focus/assistive-technology certification.

Before backend collection the existing safety hook verifies APP_ENV testing,
configured and engine database **lankapex_test_db**, and actual SELECT DATABASE().
Selected tests use existing synthetic rollback/savepoint fixtures and scoped
concurrency cleanup. No test may target lankapex_db or a production database.
The separate migration target is not substituted with the test database.

## B–C. Acceptance matrix

Statuses refer to the explicitly stated layer. PASS rows are supported by the
executed selected backend suites/full frontend suite listed below. They do not
imply browser sign-off. Severity is provided only for failures or blocked scope.

| ID | Role/scenario | Preconditions | Steps | Expected | Actual | Status | Severity | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SC01 | Owner/Customer registration | Synthetic identities | Register/login, duplicate/invalid input, request Admin role | Correct role/next step; safe validation; no public Admin | Existing HTTP and React/controller cases pass | PASS | — | test_day10_auth_integration.py; authenticationRoles.test.js |
| SC02 | Registration password guidance | Render each supported public role | Inspect password label/description with nonempty field | Persistent rule explanation linked to field | Added visible 12–128 character hint and describedby; rendered assertions pass | PASS | — | authenticationRoles.test.js; UX01 |
| SC03 | Owner business onboarding | Pending/rejected/approved synthetic business | Register/review approval, access restricted module | Actual status explained; unapproved access denied | Registration and business approval/state/rollback APIs pass; full browser journey not run | PASS | — | test_day10_auth_integration.py; test_admin_foundation.py -k business; manual checklist below |
| SC04 | Owner dashboard | Synthetic dashboard contracts | Read summary/recent data; inspect approval guidance | Real counts/amounts, scoped data, honest approval guidance | Backend dashboard checks plus source review; full browser view not exercised | PASS | — | test_shop_owner_dashboard.py; creditSalesView.test.js (dashboard navigation only) |
| SC05 | Owner customer management | Own/foreign business and customers | Add/link/search/details/page; duplicate and foreign IDs | Valid scoped relationships only | Selected HTTP cases pass | PASS | — | test_shop_owner_customer_management.py |
| SC06 | Owner credit sale | Active linked account | Submit decimal/invalid/excess; repeat and race | Exactly one sale, exact balance, rollback on failure | Existing financial/controlled concurrency cases pass | PASS | — | test_shop_owner_credit_sales.py; test_credit_sales_concurrency.py; creditSales.test.js |
| SC07 | Owner sale confirmation | Real response-shaped fixture, missing due date | Render confirmation and customer selector | Clear reference/amount/date labels | Question-mark separators replaced; missing date says Not recorded | PASS | — | creditSalesView.test.js; UX02 |
| SC08 | Owner repayment | Posted synthetic debt | Partial/full payment, retry/double-click/race/excess/foreign | One repayment, exact remaining debt/receipt; no unrelated payment mutation | Existing HTTP and controller cases pass | PASS | — | test_shop_owner_repayments.py; test_repayments_concurrency.py; repayments.test.js |
| SC09 | Owner/Customer statements | Linked account/history | Filter period, read/download, empty/foreign records | Correct names/LKR/dates/totals; ownership enforced | Statement/API/React contracts pass | PASS | — | test_financial_documents.py; test_customer_history.py; customerHistoryView.test.js |
| SC10 | Owner product management | Owned catalogue | Create/edit/category/availability/publication; change price after order | Valid current price; historical snapshot unchanged | Catalogue/order cases pass | PASS | — | test_catalogue.py; test_orders.py; shopOwnerCatalogue.test.js |
| SC11 | Customer discovery | Approved/unapproved businesses and draft products | Explore/search/filter/no results; open linked shops | Eligible published catalogue only; discovery distinct from linked credit shops | HTTP/controller/view contracts pass | PASS | — | test_customer_catalogue.py; customerCatalogue.test.js; customerAccounts.test.js |
| SC12 | Customer cart | Published products/one shop | Add/change/remove, empty/invalid/stale product | Valid quantities, server-authoritative quote and totals | Existing workflow/HTTP cases pass | PASS | — | shopping.test.js; shoppingView.test.js; test_orders.py |
| SC13 | Customer/Owner cash checkout | Real login tokens, published 125.25 item | Buy two, retry/process, inspect debt/payment/delivery | Total 250.50; no debt; unpaid; no automatic delivery | Continuous API journey passes | PASS | — | test_day18_uat.py[cash] |
| SC14 | Customer/Owner credit checkout | Authorized credit account | Submit, approve twice/race/reject; read statement | Pending/rejected no debt; approval one sale | Continuous/HTTP/concurrency cases pass | PASS | — | test_day18_uat.py[credit]; test_orders.py; test_order_delivery_concurrency.py |
| SC15 | Owner/Customer order history | Own and unrelated orders | Inspect item snapshots/status/amount/date; invalid transition | Accurate own records; status distinct from payment | Existing HTTP and view/controller cases pass | PASS | — | test_orders.py; orderFulfilment.test.js; shoppingView.test.js |
| SC16 | Customer tracking | Linked/unlinked deliveries | Read each recorded stage/refresh/foreign ID/cancellation | Stored timestamps/status only; no GPS or payment settlement | Selected delivery APIs and frontend tracking cases pass | PASS | — | test_order_delivery.py; customerOrderTracking.test.js |
| SC17 | Owner/Customer notifications | Supported persisted events | Read/retry/foreign read/account-switch/rollback | Correct recipient/link; no duplicate/stale private state | Selected notification/React cases pass | PASS | — | test_notifications.py; test_order_delivery_notifications.py; notifications.test.js |
| SC18 | Both roles error recovery | Auth/network/conflict/invalid responses | Simulate timeout, 401/403/409/422/429/500, stale result | Safe feedback; no duplicate financial dispatch | HTTP/controller error cases pass | PASS | — | test_api_hardening.py; authenticationRoles.test.js; creditSales.test.js; repayments.test.js |
| SC19 | Both roles security | Foreign business/customer/product/order/account | Tamper IDs or role; access statements/tracking | Backend ownership and RBAC deny access | Selected HTTP isolation cases pass | PASS | — | Selected backend suites below |
| SC20 | Mobile and assistive technology | Browser plus isolated backend needed | Run five widths and keyboard/screen reader checks | No overflow, readable money, accessible controls | No browser available; not executed | BLOCKED | MEDIUM | Browser inventory; manual checklist |
| SC21 | Product image upload | Feature not implemented as public upload | Attempt supported product UI flow only | Do not imply upload capability | Catalogue is minimal; no image upload journey executed | NOT RUN | — | Existing product schemas/Day 14 scope |

Backend references are under `backend/tests`; frontend references under
`frontend/tests`. SC03 verifies API steps across existing isolated scenarios, not
a continuous browser onboarding journey. Approval-policy changes were not introduced.

## D. Financial reconciliation

Authoritative existing Decimal ledger rules are unchanged. Selected suites verify
credit/repayment precision, account relationships/limits, receipts/statements,
idempotent retries, concurrent duplicate prevention and rollback after failures.
The continuous cash/credit journeys assert total **250.50**, no debt before
approval, exactly one approved CreditSale and Customer balance **250.50** versus
**0.00** for cash. Delivery and Admin reads preserve exact row/financial snapshots.
Credit moves from `pending` to `posted` on approval; posted is not repayment.
Cash remains unpaid. Product edits do not rewrite OrderItem price snapshots.
No development/production balances or posted historical transactions were changed.

## E. Mobile, accessibility and localization

UX01 fixes a markup-verifiable accessibility gap: password instructions now persist
after typing and are connected with aria-describedby. Existing labels, errors
and status regions were reviewed through source/static rendering. This does not
prove screen-reader announcement or focus behavior in a live browser.

LKR formatters retain string/BigInt-based two-decimal output and grouping without
floating-point ledger changes. Dates on the reviewed sale page use en-LK browser
locale formatting; timezone policy/browser variation still needs manual review.
Customer statements disclose recorded-clock date semantics. Customer-management
phone validation supports local `07…` and `+947…` normalization; public registration
currently imposes a 20-character bound, not a Sri Lankan-only format. This
inconsistency is documented as a localization follow-up, not silently tightened.
Preferred-language values en/ta/si do not establish translated UI coverage. No
Tamil/Sinhala translation, language switch or new Nayam terminology was added.

Manual browser procedure for SC03/SC20 (all **BLOCKED**, not passed):

1. Attach an available browser to a verified isolated synthetic backend; never use
   development/production financial data to bypass this limitation.
2. At **375, 768, 1024, 1366 and 1536 px**, repeat registration/onboarding,
   customer search, sale, partial/full repayment, statement, product edit, cart,
   cash/credit checkout, order details and delivery tracking. Inspect navigation,
   tables/cards, amount wrapping, intentional table scrolling, touch targets and
   visible confirmation/retry buttons. Record actual dimensions and screenshots.
3. Use Tab/Shift-Tab/Enter/Escape to inspect field labels, visible focus, logical
   order and dialog focus entry/trap/return. Verify errors/loading/success with
   assistive technology; measure contrast rather than inferring it from colors.
4. Exercise invalid amount, duplicate registration, expired session, timeout and
   conflicting order state. Verify safe feedback and one financial result after
   retry; check statements and Customer balance. Inspect pending/rejected approval
   communication without treating a submitted business as approved.
5. Record operator/time/browser/version, scenario ID, expected/actual, status,
   severity and redacted local evidence. Keep each viewport/browser result NOT RUN
   until executed; absence of a browser is not a visual PASS.

## F. Security

No permission or API implementation changed. Selected backend suites exercise
actual JWT identities, active-account checks, approved business/account scope,
customer/order/product/delivery ownership and private notification/statement
access. Frontend tests retain safe timeout/authorization handling and session
isolation. No external messaging integration was added.

## G–H. Execution evidence

New assertions were run before fixes and reproduced the missing password
description and unclear sale confirmation: 38 passed, six failures including
parent aggregate failures (four failing leaf scenarios). After fixes, the same
targeted registration/credit-sale view run passed **44 tests, zero failures** in
5.20 seconds. No test rules or financial assertions were weakened.

Final execution results:

- Selected backend: **603 passed, 0 failed, 0 skipped**, 170.70 seconds; one
  existing pytest cache-path warning. Migration execution was not selected and
  remains **BLOCKED**, not passed.
- Full frontend: **806 passed, 0 failed, 0 skipped**, 75.27 seconds.
- Additional Shop Owner dashboard backend run: **68 passed**, 0 failed/skipped,
  4.75 seconds. Additional business-approval selection: **15 passed**, 56
  deselected, 0 failed/skipped, 3.41 seconds. Each emitted the same existing
  pytest cache-path warning. Across these three backend runs: **686 passes**.
- Full lint: **FAIL — 8 existing errors, 1 warning**. No configured typecheck.
- Vite production build: **PASS**, 3.52 seconds; existing >500 kB chunk warning.
- Known-secret scan: zero findings across 445 current files/assets and 635
  historical text blobs, scoped to two known local labels; this does not rule out
  unknown secrets. Changed tracked whitespace check passed.

Backend selection includes:
`test_day18_uat`, `test_day10_auth_integration`, `test_shop_owner_customer_management`,
`test_shop_owner_credit_sales`, `test_credit_sales_concurrency`,
`test_shop_owner_repayments`, `test_repayments_concurrency`,
`test_financial_documents`, `test_catalogue`, `test_customer_catalogue`,
`test_orders`, `test_order_delivery`, `test_order_delivery_concurrency`,
`test_order_delivery_notifications`, `test_customer_dashboard`,
`test_customer_history`, `test_notifications`, `test_api_hardening`.
Additional focused runs: `test_shop_owner_dashboard.py` and
`test_admin_foundation.py -k business`.
No backend application changes justify another unrelated full-suite run.

Commands: `node --test tests/authenticationRoles.test.js tests/creditSalesView.test.js`,
`npm.cmd test`, `npm.cmd run lint`, `npm.cmd run build`; selected pytest run with
APP_ENV testing/MYSQL_DATABASE lankapex_test_db and a fresh ignored basetemp.
Vite uses process-only `https://api.example.invalid/api/v1`, not a deployment URL.
No dotenv file was edited and these build artifacts are not production configured.
Logs: `.server-logs/day18-2-before.log`, `day18-2-targeted.log`,
`day18-2-frontend.log`, `day18-2-backend.log`, `day18-2-lint.log`,
`day18-2-build.log`. No screenshots/browser traces exist for this step.
Additional backend logs: `day18-2-dashboard.log`, `day18-2-onboarding.log`.

## I. Defects and remaining findings

| ID | Role/severity | Reproduce; expected versus actual | Root cause | Fix / regression |
| --- | --- | --- | --- | --- |
| UX01 | Registration / LOW | Type password; requirements should remain available; previously placeholder-only, no describedby | Missing persistent accessible description | Added helper text and aria-describedby; all three existing public-role render cases assert the relationship |
| UX02 | Owner / LOW | Render confirmed sale with null due date; expected clear fields, previously literal question marks | Placeholder separators and fallback | Clear separators and Not recorded date fallback; confirmation regression checks exact copy |
| D01 | Owner/build / MEDIUM | Run full lint; expected clean, existing effect updates/unused imports/dependency findings | Existing code debt from earlier milestones | Open; no unrelated refactor or suppression |
| L01 | Registration / LOW follow-up | Compare registration phone bound to customer-management normalization | Different existing validation scope | Documented for policy review; no new phone restriction |

No new critical/high application defect is claimed from this review. Unexecuted
mobile/accessibility checks cannot establish absence of defects.

## J. Files changed

- `frontend/src/pages/auth/RegistrationForm.jsx`: persistent accessible password hint.
- `frontend/src/pages/shopOwner/ShopOwnerCreditSales.jsx`: confirmation/selector
  separators and missing-date explanation.
- `frontend/tests/authenticationRoles.test.js`: helper-description regression.
- `frontend/tests/creditSalesView.test.js`: clear confirmation regression.
- `docs/day18-shop-customer-uat.md`: this matrix, findings and manual procedure.

Prior staged/shared changes, including the Step 18.1 repayment timing fix, are
preserved. No branding/colors, transaction formula, endpoint or account policy
changed. No staging/commit/push was performed.

## K–L. Readiness and next step

Shop Owner API/contract UAT and Customer API/contract UAT **PASS within the stated
executed scope**; full user-experience sign-off remains **BLOCKED** by browser
availability. Overall Day 18 UAT is incomplete; production remains **NO-GO**.
[Day 17 blockers](day17-production-readiness.md) persist: isolated migration-chain
execution **BLOCKED** after MySQL permission denial, restore/reconciliation
unverified, shared/edge throttling and hosting/monitoring/runtime/advisory/rollback
evidence unresolved. Do not retry database creation with elevated privileges,
request DBA passwords, use the synthetic test DB as a migration substitute or
mark migration execution passed.

Suggested pilot improvements: complete the manual browser checklist, resolve lint,
agree date/timezone and phone-format policy, and verify recovery/operational
prerequisites before pilot sign-off. AI Summary stays deferred.
Step **18.3 Driver and Administrator Experience Testing** may proceed with safe
isolated API/contract review; browser and production sign-off remain withheld.
Do not start that milestone or deploy as part of this report.
