# Day 18 Step 18.1 — Acceptance matrix and manual checklist

Date: 2026-11-07. Branch `main`, base HEAD `d917e4f`. Results describe the
working tree, which includes uncommitted Day 15–18 work, not the base commit alone.
Functional verification is **API/contract-level**; browser UAT remains **BLOCKED**.
Production/pilot launch approval is **not granted**. AI Summary remains deferred,
outside test scope and is not a defect.

Step 18.5 update: the missing first-time Driver application now has an authenticated
submission API and Dashboard form with automated coverage. Earlier BLOCKED rows
remain historical evidence and are not silently promoted to browser PASS. See
[consolidated final matrix](day18-final-uat-readiness.md) for current scope/status.

## Audit and test approach

Existing coverage includes JWT registration/login and guards, business/customer
management, Decimal ledger operations, shopping snapshots/approval, MySQL races,
order/delivery links, notifications and Admin approvals/audits. Frontend tests use
Node's test runner, Vite module loading, server-rendered React and workflow
controllers. There is no established Playwright/Cypress browser suite in the repo.
These tests do not replace a user interacting with a browser.

New `backend/tests/test_day18_uat.py` adds two continuous API journeys (cash and
credit) using actual login-returned JWTs for all four roles and unrelated actors.
It reuses the existing shop/api/db fixtures, real request-session dependencies and
savepoint isolation. No authentication dependency override or approval bypass is
used in the journey. Driver profile creation and account linkage are synthetic
setup; driver approval happens through the actual Admin API. Existing scenarios
already covering registration, repayment, concurrency and failures were reused.

Before collection, `tests/conftest.py` requires `APP_ENV=testing`, both configured
and engine database `lankapex_test_db`, and actual `SELECT DATABASE()` identity.
The underlying fixture verifies identity again, begins an outer transaction,
and rolls it back after request savepoints. Existing concurrency fixtures have
explicit synthetic cleanup. No development/production records are copied or
modified, and no migration or unrestricted database reset is run.

## Synthetic identities and preconditions

| Identity/state | Preparation/evidence |
| --- | --- |
| Administrator | Trusted synthetic `make_user('admin')`; never public registration |
| Approved Shop Owner/business | Existing `shop` fixture with active owner membership |
| Pending/rejected business | Existing Admin/business and catalogue tests set actual approval state |
| Customer / linked credit Customer | Existing API customer plus `profile` active credit account factory |
| Approved Driver | Pending synthetic profile reviewed by real Admin decision endpoint |
| Pending/rejected Driver | Driver fixture plus actual review/rejection cases in Admin/Driver suites |
| Unrelated owner/customer/driver | Separate persisted synthetic users and foreign business fixture |

Synthetic email suffixes and request keys are unique. The new journey generates
an ephemeral password, hashes it and logs in each actor; no report stores tokens
or passwords. These identities are fixture-scoped, not persistent demo accounts.

## Evidence key

All backend references are under `backend/tests/`; frontend references under
`frontend/tests/`. PASS below means the stated **automated API/contract layer**
executed, not browser acceptance. Matrix rows group related cases; they are not
pytest test counts. Final execution totals/log paths are recorded below.

| Ref | Executable evidence |
| --- | --- |
| AUTH | `test_day10_auth_integration.py`, `test_auth_rbac.py`; `authenticationRoles.test.js` |
| BIZ | `test_admin_foundation.py`, `test_catalogue.py` |
| CUST | `test_shop_owner_customer_management.py`, `test_customer_dashboard.py`, `test_customer_history.py` |
| SALE | `test_shop_owner_credit_sales.py`, `test_credit_sales_concurrency.py`; `creditSales.test.js` |
| PAY | `test_shop_owner_repayments.py`, `test_repayments_concurrency.py`; `repayments.test.js` |
| DOC | `test_financial_documents.py`; `customerHistory.test.js`, `customerHistoryView.test.js` |
| CAT | `test_catalogue.py`, `test_customer_catalogue.py`; `shopOwnerCatalogue.test.js`, `customerCatalogue.test.js` |
| ORDER | `test_orders.py`; `shopping.test.js`, `shoppingView.test.js`, `orderFulfilment.test.js` |
| LINK | `test_order_delivery.py`, `test_order_delivery_concurrency.py`; `customerOrderTracking.test.js` |
| DRIVER | `test_driver_dashboard.py`, `test_driver_jobs.py`, `test_driver_jobs_concurrency.py`, `test_driver_deliveries.py` |
| ADMIN | `test_admin_foundation.py`, `test_admin_final_review.py`, `test_admin_final_concurrency.py`; `adminManagement.test.js` |
| NOTE | `test_notifications.py`, `test_delivery_notifications.py`, `test_order_delivery_notifications.py`; `notifications.test.js` |
| HARD | `test_api_hardening.py`, `test_production_config.py`, `test_deployment_readiness.py` |
| UAT | New `test_day18_uat.py::test_login_to_order_approval_delivery_and_customer_reconciliation[cash/credit]` |

## Automated acceptance matrix

Precondition for every automated row: isolated test database and synthetic actors.
Severity is impact if the expected result fails; `—` means no failure recorded.

| ID | Role / feature | Additional preconditions | Steps | Expected result | Actual result | Status | Severity | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A01 | All / registration | Public supported role | Register owner/customer/driver, login and read identity | Correct persisted role; no public Admin registration/escalation | Enforced by HTTP tests | PASS | — | AUTH |
| A02 | All / invalid session | Invalid credentials/expired/forged JWT | Login or read protected route | Safe denial; no sensitive errors | Denied as specified | PASS | — | AUTH |
| A03 | All / redirects/logout | Frontend auth controller | Restore session, select role path, logout | Correct role routes; cleared session | Controller/React tests pass; browser not tested | PASS | — | AUTH |
| A04 | Owner/Admin / onboarding | Pending business with active owner | Admin approves/rejects; attempt restricted operations | Only eligible approved business proceeds | API review/state guards pass | PASS | — | BIZ |
| A05 | Owner / customer management | Authorized business | Add/link/look up/search customer, request foreign IDs | Valid relationships only; scoped results | API ownership/search cases pass | PASS | — | CUST |
| A06 | Owner / credit sale | Active linked credit account | Submit exact Decimal, retry, exceed limit | One posted sale; exact balance; invalid input denied | Ledger/idempotency cases pass | PASS | — | SALE |
| A07 | Owner / repayment | Posted debt | Submit partial/full repayment, repeat key | Exact balance reduction; one receipt; account stays open | Payment/statement cases pass | PASS | — | PAY, DOC |
| A08 | Owner / invalid repayment | Existing debt/account | Submit zero/invalid/excess/foreign payment | Existing policy rejects; no partial write | Validation/rollback cases pass | PASS | — | PAY |
| A09 | Customer / credit view | Linked and foreign accounts | Read dashboard/history/statements after repayment | Own records only; matching totals | API/contract checks pass | PASS | — | CUST, DOC |
| A10 | Owner/Customer / products | Owner and published/draft products | Create/edit/category/filter/archive | Exact prices; correct visibility and ownership | Catalogue cases pass | PASS | — | CAT |
| A11 | Customer / cart | Published items | Add/change/remove, empty cart, stale price/product | Valid quantities; server authoritative totals | Workflow/HTTP cases pass | PASS | — | ORDER, CAT |
| A12 | Customer/Owner / cash order | Published 125.25 item | Checkout two, retry, process | Total 250.50; no debt, no payment/delivery auto-confirmation | Continuous login journey passes | PASS | — | UAT cash, ORDER |
| A13 | Customer/Owner / credit order | Linked credit account | Submit, approve twice, process | Pending creates no debt; approval exactly one 250.50 sale | Continuous login journey passes | PASS | — | UAT credit, ORDER |
| A14 | Owner / rejected credit | Submitted credit order | Reject/cancel then approve | No debt; invalid progression denied | API cases pass | PASS | — | ORDER |
| A15 | Owner / fulfilment | Eligible/noneligible order | Process/complete; try invalid transitions | Existing states only; approval prerequisite enforced | Lifecycle cases pass | PASS | — | ORDER, LINK |
| A16 | Owner/Customer / delivery link | Eligible processed order | Request delivery twice, read tracking | One linked request in correct business | Continuous journey and linking cases pass | PASS | — | UAT, LINK |
| A17 | Driver/Admin / eligibility | Pending/rejected/approved profiles | Read/accept jobs before/after decision | Pending/rejected denied; persisted approval respected | Pre-login tokens observe approval; rejection cases pass | PASS | — | UAT, DRIVER, ADMIN |
| A18 | Driver / duplicate and race | Available job, two approved drivers | Accept twice/simultaneously | One assignment/winner; safe retry/conflict | Sequential UAT plus controlled MySQL race tests pass | PASS | — | UAT, DRIVER, LINK |
| A19 | Driver / progression | Assigned own delivery | Try skip; pickup, transit, delivered | Skip denied; real events/timestamps/history | Continuous UAT and timeline cases pass | PASS | — | UAT, DRIVER |
| A20 | Customer/Owner / tracking | Linked delivery | Read after each Driver transition | Matching persisted progress; no invented GPS | API tracking matches every step | PASS | — | UAT, LINK |
| A21 | Admin / management | Admin and non-Admin actors | List/manage approvals/accounts; inspect audit | Admin-only authorized actions; safe DTOs | Management/role/audit cases pass | PASS | — | ADMIN |
| A22 | All / notifications | Persisted events | Inspect recipients/read state/foreign IDs | Correct links, privacy, no duplicates | One delivered notice; foreign read denied; rollback cases pass | PASS | — | UAT, NOTE |
| A23 | All / financial reconciliation | Posted order and ledger | Compare snapshots before/after delivery/Admin reads | No changed ledger/order financial snapshots | Exact Decimal/row snapshots unchanged | PASS | — | UAT, ADMIN, ORDER, PAY |
| A24 | All / security | Other users/roles/businesses | Tamper record IDs/role payloads | Ownership/RBAC authoritative; no escalation | Boundary cases pass | PASS | — | AUTH, CUST, DRIVER, ADMIN |
| A25 | All / network recovery | Deferred/error frontend requests | Timeout/unavailable/duplicate/stale response | Safe feedback; no false success or stale overwrite | Controller/React error contracts pass | PASS | — | Frontend full suite |
| A26 | All / API limits/errors | Bounded local config | Hit quotas, invalid body/page/search | 429/Retry-After and safe bounded failures | Hardening cases pass | PASS | — | HARD |
| A27 | Admin / platform reports | Report workflow required | Open reports/date filter/export | Functional actual reports | Reports/full Activity remain incomplete | BLOCKED | MEDIUM | Day 17 audit; no report journey executed |

Business/Driver approval notification cases are covered in ADMIN; reminders and
read/unread privacy in NOTE. Do not infer email/SMS/WhatsApp delivery. Driver
cancellation uses existing permissions; assigned cancellation is not a public
self-service bypass. Credit `posted` means a ledger entry was created, not that
the customer has repaid. Cash stays `unpaid`; delivery is never payment settlement.

## Manual browser acceptance checklist — execution blocked

The current browser inventory returned `apps: [], browsers: []`. No screenshots,
browser traces, viewport run or keyboard/screen-reader session was produced.
Every manual row below is **BLOCKED**; no automated PASS above promotes these rows.
Use an available browser attached to an isolated synthetic backend before running.
Do not point the UI to development or production data to bypass setup limitations.

| ID | Roles/feature | Preconditions | Steps | Expected result | Actual result | Status | Severity if failed | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| M01 | All / desktop 1536 px | Browser + synthetic backend | Open each role dashboard; navigate forms/tables/dialogs | Readable amounts; no overflow/hidden actions | Browser unavailable | BLOCKED | MEDIUM | Browser inventory |
| M02 | All / laptop 1366 px | Same | Repeat M01 with checkout/statements/tracking/approvals | No clipped content or inaccessible controls | Not executed | BLOCKED | MEDIUM | None |
| M03 | All / tablet 1024 px | Same | Repeat navigation and core transactions | Cards/tables wrap/scroll intentionally | Not executed | BLOCKED | MEDIUM | None |
| M04 | All / tablet 768 px | Same | Open/close nav, filters and confirmation dialogs | Actions/amounts remain visible | Not executed | BLOCKED | MEDIUM | None |
| M05 | All / mobile 375 px | Same | Complete cart, review statement and delivery timeline | No page overflow; usable touch targets | Not executed | BLOCKED | MEDIUM | None |
| M06 | All / accessibility | Keyboard + assistive technology | Tab/Shift-Tab/Enter/Escape through each form/dialog | Labels, logical focus/trapping/return, visible focus | Not executed | BLOCKED | MEDIUM | None |
| M07 | All / status/errors | Synthetic error/slow responses | Submit invalid inputs; delay/deny request; empty/search miss | Error/loading announcements; useful recovery | Only automated contract coverage | BLOCKED | MEDIUM | A25 does not verify screen readers |
| M08 | Owner/Admin / confirmation | Synthetic records only | Review target and confirm allowed action | Clear identity/amount/action; no double processing | Not executed | BLOCKED | HIGH | None |
| M09 | All / contrast | All supported states | Inspect text/buttons/focus/disabled/error status | Adequate contrast; text beyond color | No contrast measurement | BLOCKED | MEDIUM | None |
| M10 | Four roles / complete journey | Fresh synthetic actors | Login, order, approve, assign, deliver, review Customer tracking | Visible browser flow matches API evidence | API flow only executed | BLOCKED | HIGH | UAT is not browser E2E |

Record viewport dimensions, browser/version, test ID, operator/time, actual result
and local redacted screenshot reference when these are eventually executed.
No persistent test identities are provisioned by this report; use a guarded
synthetic fixture workflow and ensure cleanup remains test-scoped.

## Defects and limitations

| ID | Severity | Role | Reproduction / expected vs actual | Root cause | Fix status / regression |
| --- | --- | --- | --- | --- | --- |
| D01 | MEDIUM | Owner/build | `npm run lint`; expected clean, actual 8 errors/1 warning | Existing effect-state updates, unused imports and hook dependency | Open; Day 17 findings reproduced; no rule suppression |
| D02 | MEDIUM | Admin | Required reports/full Activity; expected complete workflow, actual incomplete implementation | Missing report functionality | Open; A27 BLOCKED; no fake report data |
| T01 | Test expectation | UAT authoring | Initial credit journey expected unpaid; actual pending before approval, posted afterward | New test incorrectly reused cash status | Corrected test to documented service policy; targeted 2/2 pass |
| T02 | MEDIUM test reliability | Owner repayment | Full frontend run: duplicate-submission test expected one dispatch after 15 ms; got zero while async fingerprinting still pending | Wall-clock sleep races asynchronous crypto under concurrent host load | Fixed test to await a dispatch signal with 10-second timeout; same one-operation/edit-blocking assertions retained; focused 51/51 pass |

No confirmed new application defect is claimed from T01/T02. No design, colors,
business rules or production configuration changed in this step. No claim of
absence of all defects follows from passing API tests or unexecuted browser UAT.

## Execution and evidence

Commands run from backend with process-only `APP_ENV=testing` and
`MYSQL_DATABASE=lankapex_test_db`; session-start identity checks execute before tests.

- Targeted new journey: **2 passed**, 22.88 seconds; one existing pytest cache-path
  warning. Initial authoring run: one cash pass, one credit expectation failure;
  corrected without changing the application.
- Full backend regression: **1229 passed, 0 failed, 1 skipped**, 459.56 seconds.
  This includes both new acceptance cases plus the existing role, finance,
  concurrency, notification and safety suites. The skipped isolated migration
  execution remains **BLOCKED**, not passed. Two warnings: deliberately short
  wrong HMAC key in the tampered-token test and an existing pytest cache-path
  conflict. Neither warning was suppressed.
- Initial frontend full run: **805 passed, 1 failed**, 99.65 seconds; T02 above.
  Focused repayment run after the test fix: **51 passed**, 0 failed/skipped,
  0.80 seconds. Final full rerun is recorded separately; the failure is not hidden.
- Final frontend full rerun: **806 passed, 0 failed, 0 skipped**, 87.00 seconds.
- Lint: **FAIL**, existing 8 errors and 1 warning; no configured typecheck.
- Vite production build: **PASS**, 6.25 seconds, existing large-chunk warning.
  Post-fix build recheck also **PASS**, 5.62 seconds, logged in
  `.server-logs/day18-1-build-final.log`.
- Local dependency consistency: `pip check` PASS. Known-secret scan: zero
  findings across 444 current files/assets and 632 historical text blobs against
  two known local labels. Scoped matching does not rule out unknown credentials.
- Logs: `.server-logs/day18-1-targeted.log`,
  `day18-1-targeted-final.log`, `day18-1-backend.log`, `day18-1-frontend.log`,
  `day18-1-lint.log`, `day18-1-build.log`. Logs are ignored local artifacts.
  Post-fix frontend logs: `day18-1-repayments.log`, `day18-1-frontend-final.log`.
- Backend uses a fresh `--basetemp=../.server-logs/day18-1-full-tmp`.
- Build uses process-only `VITE_API_URL=https://api.example.invalid/api/v1`;
  this nonresolving verification URL is not a deployment destination.
- No separate typecheck is configured. No browser server was started for UAT.

Reproduce the new API acceptance checks from `backend` (PowerShell):

```powershell
$env:APP_ENV = 'testing'
$env:MYSQL_DATABASE = 'lankapex_test_db'
.\.venv\Scripts\python.exe -m pytest tests/test_day18_uat.py -q --basetemp=../.server-logs/day18-uat-fresh-run
```

Use a fresh ignored basetemp path containing no valuable files. The guards must
pass; never change the target to bypass a failure. Run `npm.cmd test` from
`frontend` for existing frontend contracts. A browser runner and persistent
isolated backend are not created by these commands.

## Readiness decisions and next step

| Area | Decision |
| --- | --- |
| Automated functional/API UAT | PASS for executed A01–A26 API/contract groups; browser sign-off withheld |
| Browser/responsive/accessibility UAT | BLOCKED by unavailable browser |
| Migration-chain execution | BLOCKED; prior MySQL CREATE permission failure unresolved |
| Backup/restore | NOT RUN; procedure documented, rehearsal unverified |
| Live deployment/pilot launch | NO-GO; UAT evidence is not deployment approval |

Preserve [Day 17 release blockers](day17-production-readiness.md): DBA must create
and grant access to the separate empty migration target before guarded chain
execution; no elevated retry/password request or test-database substitution.
Recovery rehearsal, distributed/edge throttling, actual hosting/TLS/ingress,
active monitoring, advisory/Linux-runtime validation and rollback evidence remain
unverified. Do not deploy, migrate, reset databases, provision real users, commit
or push. AI Summary stays deferred.

Day 18 Step 18.2 can proceed with Shop Owner/Customer test planning and existing
isolated API/contract testing. Full experience sign-off needs a browser and a
verified isolated backend; focus on M01–M09, payment confirmations, statements,
stale/error recovery and minimal fixes for reproduced defects. No pilot launch
or additional milestone implementation is started by this document.

## A–N acceptance report

| Report item | Outcome / evidence |
| --- | --- |
| A. Repository audit | Existing API/contract suites reused; branch main/base d917e4f, dirty dependent work preserved; no browser framework/session available |
| B. UAT coverage | A01–A26 automated scenario groups; A27 and M01–M10 blocked; group totals are not executable test counts |
| C. Shop Owner | Synthetic customer/credit/repayment/product/order/fulfilment APIs and existing frontend contracts covered |
| D. Customer | Cash/credit checkout, linked accounts, exact balances/history and tracking covered at API/contract level |
| E. Driver | Approval restriction, acceptance/conflict, private assignment and supported status progression covered |
| F. Administrator | Approval/management/authorization/audit covered; reports/full Activity incomplete |
| G. Cross-role workflow | Two new real-login cash/credit journeys pass from checkout through Admin driver approval and delivery to Customer tracking |
| H. Financial integrity | Credit posts once, cash posts no debt; exact 250.50/0.00 Customer balances; delivery/Admin reads preserve snapshots; repayment reconciliation covered by existing suites |
| I. Security | Actual login JWTs, role/ownership denials, notification privacy; existing race/rollback/authorization cases retained |
| J. Usability | Browser/viewport/keyboard/assistive-technology checks BLOCKED; no visual acceptance claimed |
| K. Defects | T01 test-policy mismatch corrected; T02 flaky timing test fixed; D01 lint and D02 reports remain open |
| L. Tests/build | Actual targeted/full results above; lint failed and build passed; no test suppression |
| M. Blockers | Isolated migration permission/execution, recovery, production throttling/hosting/monitoring and browser sign-off unresolved |
| N. Next step | Step 18.2 may continue isolated testing/planning; full experience and pilot sign-off withheld |

Only this matrix, `backend/tests/test_day18_uat.py` and
`frontend/tests/repayments.test.js` were created/edited for Step 18.1. Existing 43
staged paths remain staged; nothing was staged, committed, pushed or deployed.

Step 18.3 follow-up: [Driver/Admin UAT](day18-driver-admin-uat.md) identified
ONB01: newly registered Drivers have no public profile/vehicle submission journey.
Registration/authentication passes above do not imply completed onboarding.
Fixture-created profile approval/operational tests remain valid, but full new-Driver
onboarding is **BLOCKED**; no automatic approval or eligibility bypass was added.
