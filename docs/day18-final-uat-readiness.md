# Day 18 Step 18.5 — Final UAT and pilot readiness assessment

Review date: **2026-11-07 (Asia/Colombo)**. Branch `main`, HEAD `d917e4f`
(`Day 14: complete customer shopping and credit order integration`). This audit
validates the working tree with uncommitted Day 15–18 dependencies, not HEAD alone.
**Overall status: PARTIAL. Live pilot NO-GO. Production NO-GO.**
AI Summary remains excluded, deliberately deferred and is not a defect.

## A–B. Audit and milestone status

| Step | Status | Actual evidence |
| --- | --- | --- |
| 18.1 | PARTIAL | Real-login cash/credit API journeys and existing controller/HTTP regressions pass; browser UAT not run |
| 18.2 | PARTIAL | Owner/Customer API contracts pass; password description and sale confirmation text fixed; browser/assistive-technology acceptance pending |
| 18.3 | PARTIAL | Driver/Admin operational APIs pass; exposed ONB01 application-submission gap; reports/full Activity incomplete |
| 18.4 | PASS for documentation | Five planning documents, proposed 29 accounts/four-week schedule, metrics/support/privacy/financial procedures; no pilot activity occurred |
| 18.5 | PARTIAL | ONB01 remediated at API/controller level; consolidated matrix, regression and readiness review; browser/operational gates still open |

Reviewed actual auth, role/ownership guards, registration/profile/approval,
assignment/status/notification/audit services, frontend routes/services/views,
ledger rules, prior UAT matrices, all five pilot documents and Day 17 operations
guides. Prior user changes and 43 staged Day 15 paths are preserved.
Browser inventory is checked separately below; no written case is execution proof.

## C. Consolidated acceptance matrix

The appendix consolidates source IDs from Steps 18.1–18.3 without replacing
BLOCKED/NOT RUN with PASS. Each source row retains its preconditions, steps,
expected/actual result and evidence. All execution dates below are the recorded
source review date 2026-11-07, not fabricated per-test timestamps. PASS identifies
the API/controller/server-rendered layer; browser evidence is absent. Rows group
scenarios and are not executable test counts. Earlier evidence is explicitly
historical where Step 18.5 has changed implementation.

Added final cases:

| ID | Role/feature | Preconditions | Steps | Expected | Actual | Execution date | Status | Evidence | Defect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| F01 | Driver application | Fresh synthetic real registration/login | POST own vehicle profile; read status; Admin approves; reuse JWT | Pending before review, eligible only after approval | HTTP chain passes; same token observes current persisted approval | 2026-11-07 | PASS | test_day18_driver_onboarding.py | ONB01 |
| F02 | Driver submission security | Driver/foreign roles/inactive account | Inject identity/reviewer/approval, omit fields or fail commit | 401/403/422, no unauthorized write, generic rollback error | Validation/RBAC/rollback tests pass | 2026-11-07 | PASS | test_day18_driver_onboarding.py | ONB01 |
| F03 | Driver submission race | One synthetic active Driver, independent MySQL sessions | Submit two first-time vehicle profiles concurrently | One pending record; one winner/one conflict | 201/409 and one persisted pending profile | 2026-11-07 | PASS | test_competing_first_time_submissions_create_one_pending_profile | ONB01 |
| F04 | Driver form/controller | Pending response and deferred/error requests | Double-click, malformed/foreign/approved response, 401/403/422/429/409/503; dispose | One dispatch in flight, no self-approval/false success/private errors | Controller cases pass; markup labels/help/form visibility pass | 2026-11-07 | PASS | driverProfileSubmission.test.js; driverDashboardView.test.js | ONB01 |
| F05 | Complete browser onboarding | Available browser/isolated backend required | Register → fill Dashboard application → Admin review → jobs | Complete visible usable journey | NOT RUN; no browser available | — | NOT RUN | No screenshots/trace | ONB01 acceptance |
| F06 | Complete all-role browser journey | Fresh actors/business approval and eligible Drivers | Registration through order/credit/delivery/notifications/Customer and Owner tracking | Accurate statuses/ledger in an observed browser flow | NOT RUN; API tests cover portions, not one browser execution | — | NOT RUN | Manual instructions in role UAT docs | Browser gate |

Synthetic training scenarios A–F in Step 18.4 are separately **NOT RUN**; no
attendance, questionnaire responses, pilot orders or participant metrics exist.
The complete all-role registration/business/profile/order journey has not been
observed as one browser session. Do not infer that from stitched API evidence.

## D–H. Role and coordination results

Owner: existing registration, business review/eligibility, authorized Customers,
account relationships, credit sales, partial/full repayments, statements/reminders,
catalogue, order review/approval/fulfilment and delivery request/tracking have
synthetic regression coverage. Confirmation-copy/accessibility fixes remain tested.
Existing lint findings in older Owner pages remain open.

Customer: registration/login, Explore Shops versus linked My Shops, cart validation,
server prices, cash/credit checkout, pending/rejected/approved visibility, own
orders/credit/statement/balance/tracking/notifications and session isolation have
API/controller/view coverage. No user-visible payment collection is invented.

Driver: new **POST /api/v1/driver/profile** accepts only vehicle_type and
registration_reference for the authenticated active Driver. Fields are trimmed,
single-line, 1–50 characters; unknown fields are forbidden. The existing locked
create_profile service creates only pending and rejects replacement. GET remains
read-only. Admin review remains the existing API/policy. No self-approval, profile
edit/reapplication policy, verification claim or schema migration was added.

The Dashboard form appears only for not_submitted, uses accessible labels/help,
blocks duplicate clicks, verifies the returned identity/pending/vehicle state,
refreshes after confirmation and requires profile refresh after uncertain/conflict
results. Backend tests cover new registration → login → submission → pending job
denial → Admin approval → eligibility using the same JWT. Driver operational,
ownership, history and supported transition tests remain in regression.

Admin: management/search/filter/pagination/DTOs, Driver/business approve/reject,
safe account restrictions, immutable audit API and recent activity are covered.
All Admin targets are excluded from generic suspension, which protects self/last
Admin without inventing an Admin-management policy. Full reports/CSV/date filters
and complete Activity investigation UI remain incomplete/BLOCKED. No fake report
metrics, collected-revenue label or generic financial editing was added.

Cross-role evidence: real-login cash/credit journeys pass from catalogue checkout,
Owner processing/linking, Admin Driver review, Driver acceptance/progression to
Customer tracking and notification privacy. Existing independent MySQL races cover
orders/credit approval, request linking, assignment and approve/reject decisions.
Setup-provisioned business/account/profile records must not be described as
completed public onboarding. Browser end-to-end acceptance remains NOT RUN.

## I–J. Financial integrity, authorization and privacy

Existing Decimal rules and posted history are unchanged. Effective entries exclude
reversed originals. Reconciliation tests check sales, repayments, outstanding,
statements, order-sale links, exact approved credit posting once, no pending/
rejected/cash debt, idempotency and transactional rollback. Cash/credit journey
totals 250.50 reconcile to Customer outstanding 0.00/250.50 respectively. Delivery
and Admin actions preserve row/financial snapshots and do not create repayments,
pay cash or settle credit. New profile submission has no financial mutation path.

Backend identity/active-account/role/ownership remains authoritative. Tests cover
cross-business credit, cross-customer order/statement, cross-driver delivery,
Admin-only review/audit, role injection, no public Admin registration and safe
notification/export handling where supported. New submission body cannot select
another user, approval status, reviewer or platform role. Parameterized SQLAlchemy
queries and generic database errors are retained. Unknown credentials and untested
live infrastructure are not certified by local tests.

Pilot privacy procedures are documented, not legally certified or operationally
executed. Consent, staff/support coverage and real participant data collection
remain unapproved. No production connection or live financial record was used.

## K. Mobile and accessibility

All requested widths **375/768/1024/1366/1536 px** and real keyboard/dialog focus,
screen-reader, contrast and touch-target checks remain **NOT RUN**. Browser
availability prevents execution; static responsive CSS/markup is not visual proof.
New profile labels/required lengths/help and first-time-only rendering are tested.
Prior persistent password help/aria-describedby and clearer sale confirmations
remain verified at markup level. No redesign or palette change was made.

## L. Pilot documentation review

The five Step 18.4 documents cover objectives/scope; proposed 5 Owners, 20 Customers,
3 Drivers, 1 Admin (**29 proposed**, none recruited); relative four-week schedule;
all role guides; synthetic A–F training; coded optional questionnaire; blank task,
feedback/incident/reconciliation registers; escalation and independent review;
metric numerators/denominators/sources/frequency/owners/proposed thresholds;
financial stop/reconcile/resume; privacy/retention/withdrawal review and exit rules.
Targets are not results. No session, event, support account, message or invitation
was created. Updated Driver guide/training/gates to match the new submission flow;
historical reports retain their original blocked evidence with a supersession note.

## M. Tests and build

**Final full backend: 1245 passed, 0 failed, 1 skipped**, 172.89 seconds.
The skip is isolated migration execution, still **BLOCKED**, not passed. Two
warnings are the deliberately short wrong HMAC key in the tampered-token test and
the existing pytest cache-path creation conflict; neither was suppressed.
Final lock-fix targeted backend: **35 passed**, including five independent
same-Driver insert races, 6.13 seconds. No schema/model/migration change was needed.

Earlier targeted backend: 82 passed, then 31 passed before the expanded race run.
Targeted frontend: **20 passed**; controller validation recheck: **10 passed**.
Scoped lint for new/modified Driver application code passed.

Final frontend recheck: **817 passed, 0 failed/skipped**, 48.99 seconds. Full lint
retains **8 inherited errors and 1 warning**; new scoped lint passes. Production
build passed in **3.79 seconds** with the existing >500 kB chunk warning, using
process-only `https://api.example.invalid/api/v1`. These artifacts are not a
production endpoint configuration. No configured typecheck exists. The corrected
landing headline **Management** remains present. Browser: **zero executed**, NOT RUN.

Intermediate failures are retained: initial full backend had **1239 passed,
1 failed, 1 skipped**, because an old test expected all profile POSTs to be 405.
The intentional new route now rejects approval injection with 422; both old
no-self-approval tests were updated to assert this boundary, not removed.
Initial frontend authoring had a test-variable ReferenceError, corrected before
the passing focused/full runs. A control-character-regex lint issue in new code
was replaced with equivalent character-code checks and scoped lint rerun.

A second full run had **1240 passed, 1 failed, 1 skipped**: the new insert-race
case exposed an existing create_profile shared-lock deadlock. Fixed creation to
take an exclusive User lock before the missing-profile probe; other actor-lock
callers retain their policy. The race is repeated with five independent synthetic
seeds and still requires one 201/one 409, never a database error. This is a real
concurrency correction, not a relaxed test expectation. Final verification is
the passing 1245-test run above.

Logs: `.server-logs/day18-5-targeted-backend.log`,
`day18-5-backend-target-final.log`, `day18-5-backend.log` (initial),
`day18-5-backend-final.log`, `day18-5-targeted-frontend-final.log`,
`day18-5-frontend.log` (initial), `day18-5-frontend-final.log`,
`day18-5-lint-final.log`, `day18-5-build-final.log`, `day18-5-scoped-lint.log`.
Final lock-fix evidence: `day18-5-racefix-target.log`,
`day18-5-backend-verified.log`.
Tests require APP_ENV testing, exact lankapex_test_db, actual identity guard and
fresh ignored basetemp directories. Concurrency setup/cleanup checks identity and
uses only exact seeded IDs. No migration is invoked by this test run.

## N. Database and recovery

**Isolated migration-chain execution BLOCKED**, not passed. Previous MySQL denial
for creating lankapex_migration_verify_20261107 has no new resolution evidence.
An authorized local DBA must create the separate empty schema/grant the intended
account, then actual identity/access/emptiness must be verified before a separately
authorized guarded chain run. No elevated retry, administrator-password request,
test-DB substitution, real-data upgrade/downgrade or reset.

| Recovery requirement | Status |
| --- | --- |
| Procedure/retention/secure credential handling | DOCUMENTED in Day 17 operations |
| Real backup created/verified in this work | NOT VERIFIED / not performed |
| Isolated restore and integrity check | NOT VERIFIED |
| Reconciliation after restore / recovery timing | NOT VERIFIED |
| Recovery staffing/operational rehearsal | NOT VERIFIED |

Passing test-schema metadata/offline SQL does not certify migration execution or
restore. No backup was generated/uploaded and no production database was accessed.

## O. Separate readiness decisions

| Area | Decision | Reason |
| --- | --- | --- |
| Code quality | PARTIAL | New scoped lint passes; inherited full lint fails |
| Functional UAT | PARTIAL | Automated contracts pass; browser/complete reports unverified |
| Financial integrity | PASS within synthetic tested scope | Exact ledger/statement/idempotency/rollback cases; not live reconciliation |
| Security/privacy | PARTIAL | Local guards/tests pass; operational/privacy/advisory/security gates unverified |
| Pilot documentation | PASS for preparation | Complete reviewed draft; targets/people/approval not actual outcomes |
| Database migration | BLOCKED | Separate target permission/execution prerequisite unresolved |
| Backup/restore | BLOCKED for launch sign-off | Procedures documented; execution/reconciliation not verified |
| Controlled live pilot | **NO-GO** | Mandatory migration/recovery/security/browser/operations gates remain |
| Production deployment | **NO-GO** | UAT/build is not deployment approval |

## P. Git review and checkpoint

Branch main, HEAD d917e4f with the message at the top; working tree remains dirty.
43 inherited staged paths are Day 15 work, not an isolated Day 18 checkpoint.
Day 18 depends on unstaged/untracked Day 16/17 code, so staging only Day 18 would
not reproduce the tested application at this HEAD. Prior unrelated .gitignore,
%SystemDrive%/ and .vite/ state is preserved. No add -A, reset, amend or history
rewrite was used. Build output, node_modules, logs, dotenv and dumps remain ignored.

**Completion commit withheld:** required full lint still fails and a coherent
Day-18-only commit cannot be made without including earlier uncommitted dependency
work. The inherited index is not committed accidentally. No new commit/hash/message,
push or empty commit is claimed. A later checkpoint needs reviewed dependency
boundaries and passing required checks; it still does not authorize launch.

Final Git working-tree review: 152 status entries; 43 inherited staged paths.
Known-secret scan found zero matches across 456 current files/assets and 646
reachable historical text blobs against two known local labels. A separate actual
index scan found zero known-secret matches in all 43 staged paths. This scoped
scan does not certify absence of unknown credentials. Ignore checks confirm local
dotenv, dist and verification logs are excluded; staged path review contains no
dump, node_modules or build artifact. `pip check` passed. Tracked diff whitespace,
new Python syntax and 131 internal links across nine Day 18 documents passed.

Step 18.5 implementation/review files (prior edits in shared files preserved):

- Backend: app/schemas/driver.py, app/routers/driver.py,
  app/services/driver_service.py; tests/test_day18_driver_onboarding.py,
  tests/test_admin_foundation.py, tests/test_driver_dashboard.py.
- Frontend: src/components/driver/DriverProfileForm.jsx (new),
  src/utils/driverProfileSubmission.js (new), src/pages/driver/DriverDashboard.jsx,
  src/services/driverDashboardService.js, tests/driverProfileSubmission.test.js (new),
  tests/driverDashboardView.test.js.
- Documentation: this final report; day18-uat-matrix.md, day18-driver-admin-uat.md,
  day18-onboarding-guide.md, day18-pilot-plan.md, day18-training-scenarios.md,
  day18-pilot-go-no-go.md. Historical outcomes remain identified as historical.

## Q. Consolidated defects and actions

| ID | Role/feature | Severity | Reproduction / current impact | Status and verification |
| --- | --- | --- | --- | --- |
| ONB01 | Driver application | HIGH originally | Fresh register/login lacked submission path; now Dashboard vehicle form posts pending-only | FIXED at API/controller/markup level with registration/approval chain, injection/rollback/race tests; browser acceptance still NOT RUN |
| ONB02 | Driver concurrent profile creation | HIGH | Competing missing-profile inserts could deadlock under shared User locks | Exclusive User lock for creation; five-seed strict race regression and final full suite verify correction |
| UX01 | Registration help | LOW | Password placeholder alone disappeared while typing | FIXED in 18.2; persistent accessible description regression retained |
| UX02 | Owner confirmation | LOW | Question-mark separators/missing due date | FIXED in 18.2; clear separators/Not recorded regression retained |
| T02 | Repayment test | MEDIUM test reliability | Async fingerprint occasionally exceeded fixed 15ms sleep | FIXED in 18.1; dispatch-signal wait and timeout retain duplicate assertions |
| ADM01/D02 | Admin reports | MEDIUM | Reports/date filter/CSV workflow absent | OPEN/BLOCKED; implement or explicitly exclude scope, no fabricated result |
| ADM02 | Admin full Activity | MEDIUM | Recent preview/API not complete investigation UI | OPEN/BLOCKED; no false full-UI coverage |
| LINT01/D01 | Owner/test validation | MEDIUM | Existing lint errors/warning | OPEN; focused cleanup with tests remains required |
| L01 | Phone policy | LOW follow-up | Registration length bound differs from Customer local-phone normalization | OPEN for policy review; no silent validation change |

No newly demonstrated critical financial/security corruption remains from executed
tests. This is not proof of defect absence in unexecuted browser/live environments.
Do not close operational gates based on passing ONB01 automation alone.

## R. Recommended Day 19

Recommend **release-gate closure and isolated staging rehearsal preparation**:
verify browser onboarding/all five widths/accessibility; fix inherited lint;
complete or agree explicit Admin scope; obtain DBA prerequisite and guarded
migration evidence; authorize isolated recovery/reconciliation rehearsal; verify
runtime/advisories/shared throttling/actual ingress and monitoring; assign support,
privacy review and compatible rollback artifacts. Then reassess live pilot GO/NO-GO
and reviewed Git checkpoints. Do not start Day 19, deploy, recruit or process live
financial data as part of this review.

## Consolidated source-case appendix

<!-- Matrix rows are consolidated below with source references. -->

Source-case totals: PASS: **65**, FAIL: **0**, BLOCKED: **15**, NOT RUN: **18**; **98 source/training rows**. With F01–F06 above: **104 unique scenario rows**, PASS **69**, FAIL **0**, BLOCKED **15**, NOT RUN **20**. These are scenario groups, not test-run counts.

| ID | Role/feature | Preconditions | Steps | Expected | Actual | Execution date | Status | Source/evidence | Defect |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A01 | All / registration | Public supported role | Register owner/customer/driver, login and read identity | Correct persisted role; no public Admin registration/escalation | Enforced by HTTP tests | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); AUTH | — |
| A02 | All / invalid session | Invalid credentials/expired/forged JWT | Login or read protected route | Safe denial; no sensitive errors | Denied as specified | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); AUTH | — |
| A03 | All / redirects/logout | Frontend auth controller | Restore session, select role path, logout | Correct role routes; cleared session | Controller/React tests pass; browser not tested | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); AUTH | — |
| A04 | Owner/Admin / onboarding | Pending business with active owner | Admin approves/rejects; attempt restricted operations | Only eligible approved business proceeds | API review/state guards pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); BIZ | — |
| A05 | Owner / customer management | Authorized business | Add/link/look up/search customer, request foreign IDs | Valid relationships only; scoped results | API ownership/search cases pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); CUST | — |
| A06 | Owner / credit sale | Active linked credit account | Submit exact Decimal, retry, exceed limit | One posted sale; exact balance; invalid input denied | Ledger/idempotency cases pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); SALE | — |
| A07 | Owner / repayment | Posted debt | Submit partial/full repayment, repeat key | Exact balance reduction; one receipt; account stays open | Payment/statement cases pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); PAY, DOC | — |
| A08 | Owner / invalid repayment | Existing debt/account | Submit zero/invalid/excess/foreign payment | Existing policy rejects; no partial write | Validation/rollback cases pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); PAY | — |
| A09 | Customer / credit view | Linked and foreign accounts | Read dashboard/history/statements after repayment | Own records only; matching totals | API/contract checks pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); CUST, DOC | — |
| A10 | Owner/Customer / products | Owner and published/draft products | Create/edit/category/filter/archive | Exact prices; correct visibility and ownership | Catalogue cases pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); CAT | — |
| A11 | Customer / cart | Published items | Add/change/remove, empty cart, stale price/product | Valid quantities; server authoritative totals | Workflow/HTTP cases pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); ORDER, CAT | — |
| A12 | Customer/Owner / cash order | Published 125.25 item | Checkout two, retry, process | Total 250.50; no debt, no payment/delivery auto-confirmation | Continuous login journey passes | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); UAT cash, ORDER | — |
| A13 | Customer/Owner / credit order | Linked credit account | Submit, approve twice, process | Pending creates no debt; approval exactly one 250.50 sale | Continuous login journey passes | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); UAT credit, ORDER | — |
| A14 | Owner / rejected credit | Submitted credit order | Reject/cancel then approve | No debt; invalid progression denied | API cases pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); ORDER | — |
| A15 | Owner / fulfilment | Eligible/noneligible order | Process/complete; try invalid transitions | Existing states only; approval prerequisite enforced | Lifecycle cases pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); ORDER, LINK | — |
| A16 | Owner/Customer / delivery link | Eligible processed order | Request delivery twice, read tracking | One linked request in correct business | Continuous journey and linking cases pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); UAT, LINK | — |
| A17 | Driver/Admin / eligibility | Pending/rejected/approved profiles | Read/accept jobs before/after decision | Pending/rejected denied; persisted approval respected | Pre-login tokens observe approval; rejection cases pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); UAT, DRIVER, ADMIN | — |
| A18 | Driver / duplicate and race | Available job, two approved drivers | Accept twice/simultaneously | One assignment/winner; safe retry/conflict | Sequential UAT plus controlled MySQL race tests pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); UAT, DRIVER, LINK | — |
| A19 | Driver / progression | Assigned own delivery | Try skip; pickup, transit, delivered | Skip denied; real events/timestamps/history | Continuous UAT and timeline cases pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); UAT, DRIVER | — |
| A20 | Customer/Owner / tracking | Linked delivery | Read after each Driver transition | Matching persisted progress; no invented GPS | API tracking matches every step | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); UAT, LINK | — |
| A21 | Admin / management | Admin and non-Admin actors | List/manage approvals/accounts; inspect audit | Admin-only authorized actions; safe DTOs | Management/role/audit cases pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); ADMIN | — |
| A22 | All / notifications | Persisted events | Inspect recipients/read state/foreign IDs | Correct links, privacy, no duplicates | One delivered notice; foreign read denied; rollback cases pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); UAT, NOTE | — |
| A23 | All / financial reconciliation | Posted order and ledger | Compare snapshots before/after delivery/Admin reads | No changed ledger/order financial snapshots | Exact Decimal/row snapshots unchanged | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); UAT, ADMIN, ORDER, PAY | — |
| A24 | All / security | Other users/roles/businesses | Tamper record IDs/role payloads | Ownership/RBAC authoritative; no escalation | Boundary cases pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); AUTH, CUST, DRIVER, ADMIN | — |
| A25 | All / network recovery | Deferred/error frontend requests | Timeout/unavailable/duplicate/stale response | Safe feedback; no false success or stale overwrite | Controller/React error contracts pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); Frontend full suite | — |
| A26 | All / API limits/errors | Bounded local config | Hit quotas, invalid body/page/search | 429/Retry-After and safe bounded failures | Hardening cases pass | 2026-11-07 | PASS | [day18-uat-matrix.md](day18-uat-matrix.md); HARD | — |
| A27 | Admin / platform reports | Report workflow required | Open reports/date filter/export | Functional actual reports | Reports/full Activity remain incomplete | — | BLOCKED | [day18-uat-matrix.md](day18-uat-matrix.md); Day 17 audit; no report journey executed | ADM01/ADM02 |
| M01 | All / desktop 1536 px | Browser + synthetic backend | Open each role dashboard; navigate forms/tables/dialogs | Readable amounts; no overflow/hidden actions | Browser unavailable | — | BLOCKED | [day18-uat-matrix.md](day18-uat-matrix.md); Browser inventory | Browser gate |
| M02 | All / laptop 1366 px | Same | Repeat M01 with checkout/statements/tracking/approvals | No clipped content or inaccessible controls | Not executed | — | BLOCKED | [day18-uat-matrix.md](day18-uat-matrix.md); None | Browser gate |
| M03 | All / tablet 1024 px | Same | Repeat navigation and core transactions | Cards/tables wrap/scroll intentionally | Not executed | — | BLOCKED | [day18-uat-matrix.md](day18-uat-matrix.md); None | Browser gate |
| M04 | All / tablet 768 px | Same | Open/close nav, filters and confirmation dialogs | Actions/amounts remain visible | Not executed | — | BLOCKED | [day18-uat-matrix.md](day18-uat-matrix.md); None | Browser gate |
| M05 | All / mobile 375 px | Same | Complete cart, review statement and delivery timeline | No page overflow; usable touch targets | Not executed | — | BLOCKED | [day18-uat-matrix.md](day18-uat-matrix.md); None | Browser gate |
| M06 | All / accessibility | Keyboard + assistive technology | Tab/Shift-Tab/Enter/Escape through each form/dialog | Labels, logical focus/trapping/return, visible focus | Not executed | — | BLOCKED | [day18-uat-matrix.md](day18-uat-matrix.md); None | Browser gate |
| M07 | All / status/errors | Synthetic error/slow responses | Submit invalid inputs; delay/deny request; empty/search miss | Error/loading announcements; useful recovery | Only automated contract coverage | — | BLOCKED | [day18-uat-matrix.md](day18-uat-matrix.md); A25 does not verify screen readers | Browser gate |
| M08 | Owner/Admin / confirmation | Synthetic records only | Review target and confirm allowed action | Clear identity/amount/action; no double processing | Not executed | — | BLOCKED | [day18-uat-matrix.md](day18-uat-matrix.md); None | Browser gate |
| M09 | All / contrast | All supported states | Inspect text/buttons/focus/disabled/error status | Adequate contrast; text beyond color | No contrast measurement | — | BLOCKED | [day18-uat-matrix.md](day18-uat-matrix.md); None | Browser gate |
| M10 | Four roles / complete journey | Fresh synthetic actors | Login, order, approve, assign, deliver, review Customer tracking | Visible browser flow matches API evidence | API flow only executed | — | BLOCKED | [day18-uat-matrix.md](day18-uat-matrix.md); UAT is not browser E2E | Browser gate |
| SC01 | Owner/Customer registration | Synthetic identities | Register/login, duplicate/invalid input, request Admin role | Correct role/next step; safe validation; no public Admin | Existing HTTP and React/controller cases pass | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); test_day10_auth_integration.py; authenticationRoles.test.js | — |
| SC02 | Registration password guidance | Render each supported public role | Inspect password label/description with nonempty field | Persistent rule explanation linked to field | Added visible 12–128 character hint and describedby; rendered assertions pass | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); authenticationRoles.test.js; UX01 | — |
| SC03 | Owner business onboarding | Pending/rejected/approved synthetic business | Register/review approval, access restricted module | Actual status explained; unapproved access denied | Registration and business approval/state/rollback APIs pass; full browser journey not run | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); test_day10_auth_integration.py; test_admin_foundation.py -k business; manual checklist below | — |
| SC04 | Owner dashboard | Synthetic dashboard contracts | Read summary/recent data; inspect approval guidance | Real counts/amounts, scoped data, honest approval guidance | Backend dashboard checks plus source review; full browser view not exercised | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); test_shop_owner_dashboard.py; creditSalesView.test.js (dashboard navigation only) | — |
| SC05 | Owner customer management | Own/foreign business and customers | Add/link/search/details/page; duplicate and foreign IDs | Valid scoped relationships only | Selected HTTP cases pass | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); test_shop_owner_customer_management.py | — |
| SC06 | Owner credit sale | Active linked account | Submit decimal/invalid/excess; repeat and race | Exactly one sale, exact balance, rollback on failure | Existing financial/controlled concurrency cases pass | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); test_shop_owner_credit_sales.py; test_credit_sales_concurrency.py; creditSales.test.js | — |
| SC07 | Owner sale confirmation | Real response-shaped fixture, missing due date | Render confirmation and customer selector | Clear reference/amount/date labels | Question-mark separators replaced; missing date says Not recorded | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); creditSalesView.test.js; UX02 | — |
| SC08 | Owner repayment | Posted synthetic debt | Partial/full payment, retry/double-click/race/excess/foreign | One repayment, exact remaining debt/receipt; no unrelated payment mutation | Existing HTTP and controller cases pass | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); test_shop_owner_repayments.py; test_repayments_concurrency.py; repayments.test.js | — |
| SC09 | Owner/Customer statements | Linked account/history | Filter period, read/download, empty/foreign records | Correct names/LKR/dates/totals; ownership enforced | Statement/API/React contracts pass | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); test_financial_documents.py; test_customer_history.py; customerHistoryView.test.js | — |
| SC10 | Owner product management | Owned catalogue | Create/edit/category/availability/publication; change price after order | Valid current price; historical snapshot unchanged | Catalogue/order cases pass | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); test_catalogue.py; test_orders.py; shopOwnerCatalogue.test.js | — |
| SC11 | Customer discovery | Approved/unapproved businesses and draft products | Explore/search/filter/no results; open linked shops | Eligible published catalogue only; discovery distinct from linked credit shops | HTTP/controller/view contracts pass | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); test_customer_catalogue.py; customerCatalogue.test.js; customerAccounts.test.js | — |
| SC12 | Customer cart | Published products/one shop | Add/change/remove, empty/invalid/stale product | Valid quantities, server-authoritative quote and totals | Existing workflow/HTTP cases pass | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); shopping.test.js; shoppingView.test.js; test_orders.py | — |
| SC13 | Customer/Owner cash checkout | Real login tokens, published 125.25 item | Buy two, retry/process, inspect debt/payment/delivery | Total 250.50; no debt; unpaid; no automatic delivery | Continuous API journey passes | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); test_day18_uat.py[cash] | — |
| SC14 | Customer/Owner credit checkout | Authorized credit account | Submit, approve twice/race/reject; read statement | Pending/rejected no debt; approval one sale | Continuous/HTTP/concurrency cases pass | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); test_day18_uat.py[credit]; test_orders.py; test_order_delivery_concurrency.py | — |
| SC15 | Owner/Customer order history | Own and unrelated orders | Inspect item snapshots/status/amount/date; invalid transition | Accurate own records; status distinct from payment | Existing HTTP and view/controller cases pass | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); test_orders.py; orderFulfilment.test.js; shoppingView.test.js | — |
| SC16 | Customer tracking | Linked/unlinked deliveries | Read each recorded stage/refresh/foreign ID/cancellation | Stored timestamps/status only; no GPS or payment settlement | Selected delivery APIs and frontend tracking cases pass | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); test_order_delivery.py; customerOrderTracking.test.js | — |
| SC17 | Owner/Customer notifications | Supported persisted events | Read/retry/foreign read/account-switch/rollback | Correct recipient/link; no duplicate/stale private state | Selected notification/React cases pass | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); test_notifications.py; test_order_delivery_notifications.py; notifications.test.js | — |
| SC18 | Both roles error recovery | Auth/network/conflict/invalid responses | Simulate timeout, 401/403/409/422/429/500, stale result | Safe feedback; no duplicate financial dispatch | HTTP/controller error cases pass | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); test_api_hardening.py; authenticationRoles.test.js; creditSales.test.js; repayments.test.js | — |
| SC19 | Both roles security | Foreign business/customer/product/order/account | Tamper IDs or role; access statements/tracking | Backend ownership and RBAC deny access | Selected HTTP isolation cases pass | 2026-11-07 | PASS | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); Selected backend suites below | — |
| SC20 | Mobile and assistive technology | Browser plus isolated backend needed | Run five widths and keyboard/screen reader checks | No overflow, readable money, accessible controls | No browser available; not executed | — | BLOCKED | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); Browser inventory; manual checklist | Browser gate |
| SC21 | Product image upload | Feature not implemented as public upload | Attempt supported product UI flow only | Do not imply upload capability | Catalogue is minimal; no image upload journey executed | — | NOT RUN | [day18-shop-customer-uat.md](day18-shop-customer-uat.md); Existing product schemas/Day 14 scope | — |
| DA01 | Driver registration/account | Unique synthetic identity | Register, duplicate/invalid request, login, identity read | Secure password; correct role/status; no Admin escalation | Existing registration/JWT cases pass | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_day10_auth_integration.py; authenticationRoles.test.js | — |
| DA02 | Driver complete onboarding | Newly registered Driver without fixture profile | Submit profile/vehicle then request Admin review | Supported application submission leading to review | No public submission workflow exists; account stays not_submitted (historical 18.3 result; implementation fixed in 18.5, browser still NOT RUN) | — | BLOCKED | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); ONB01; new test_day18_driver_onboarding.py | ONB01 |
| DA03 | Driver/Admin missing application guard | Fresh real registration/login | Read profile/jobs; Admin attempts approval | Missing application cannot gain job access/approval | Profile_required, no vehicle; jobs 403; Admin decision 409 (before submission; now followed by F01–F03) | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_day18_driver_onboarding.py | — |
| DA04 | Driver approval eligibility | Stored pending/rejected/approved/suspended profile | Read jobs/update; change approval and reuse JWT | Backend persisted status authoritative; vehicle required | Eligibility and current-session cases pass | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_driver_dashboard.py; test_driver_jobs.py; test_day18_uat.py | — |
| DA05 | Driver dashboard | Synthetic assigned/terminal deliveries | Read counts/profile/preview; render loading/empty/error | Actual own counts only; no earnings/GPS/ratings | API/React contracts pass | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_driver_dashboard.py; driverDashboard.test.js; driverDashboardView.test.js | — |
| DA06 | Driver available jobs | Approved businesses/unassigned requests | List/filter/page/read details/refresh; foreign/private fields | Only available eligible records; minimal area information | Listing/scope/contract cases pass | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_driver_jobs.py; driverJobs.test.js; driverJobsView.test.js | — |
| DA07 | Driver vehicle matching | Job-specific vehicle requirement needed | Compare request requirement to stored vehicle | Enforce actual compatibility rules if present | Only profile vehicle completeness exists; requests store no compatibility requirement | — | NOT RUN | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); driver_service eligibility/create_delivery; no feature invented | — |
| DA08 | Driver acceptance | Available job; two eligible drivers | Accept/retry/race; read lists/assignment | One assignment; losing driver conflict; own My Deliveries | Atomic MySQL and frontend dispatch cases pass | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_driver_jobs_concurrency.py; test_driver_concurrency.py; driverJobs.test.js | — |
| DA09 | Driver lifecycle/history | Assigned own delivery | Pickup/transit/delivered; duplicate/skip/out-of-order updates | Valid transitions/events/timestamps; terminal immutability | HTTP/persisted-event and concurrent update cases pass | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_driver_deliveries.py; test_driver_deliveries_concurrency.py; driverDeliveries.test.js | — |
| DA10 | Driver cancellation | Available/assigned request with existing cancellation rules | Owner cancels where allowed; attempt unsupported driver cancellation | Only existing authorized lifecycle; notification privacy | Cancellation/boundary cases pass; no new public bypass | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_delivery_final_review.py; test_order_delivery_notifications.py | — |
| DA11 | Owner/Driver/Customer coordination | Linked cash/credit order | Request delivery, accept, progress, refresh tracking | Correct business/order/driver; matching recorded state | Continuous real-login and integration cases pass | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_day18_uat.py; test_shop_driver_integration.py; test_order_delivery.py | — |
| DA12 | Driver notifications | Approval/rejection/assignment/cancellation events | Inspect recipient/link/read-unread; retry/rollback | No duplicates, cross-account reads or false committed messages | Notification/approval cases pass | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_notifications.py; test_delivery_notifications.py; test_order_delivery_notifications.py; notifications.test.js | — |
| DA13 | Driver new-job broadcast | Available-job event broadcast needed | Inspect supported event catalogue | Do not claim unsupported push notices | No general available-job broadcast certified; use explicit job refresh | — | NOT RUN | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); Existing event/service scope | — |
| DA14 | Admin login/dashboard | Active Admin and other roles | Login/read overview/guard; load failed/empty data | Database-backed counts; Admin-only; honest unavailable state | API and React/controller contracts pass | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_admin_foundation.py; adminDashboard.test.js; adminDashboardView.test.js | — |
| DA15 | Admin Owner/Customer management | Managed users/foreign roles | Search/filter/page/details/associations; inspect DTOs | Safe supported identity fields; no generic ledger editing | Scope/DTO/role cases pass | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_admin_foundation.py; test_admin_final_review.py; adminManagementView.test.js | — |
| DA16 | Admin Driver review | Pending profile with stored vehicle | Approve/reject, repeat/race, missing target/fields/non-Admin | One valid transition, audit and notification; no automatic verification | Approval/rejection/concurrency cases pass | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_admin_concurrency.py; test_admin_final_concurrency.py; adminManagement.test.js | — |
| DA17 | Admin business review | Pending business/active owner | Approve/reject/retry/race; unauthorized decision | Supported pending-only policy; atomic audit/notification | Business conflict and state cases pass | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_admin_foundation.py; test_admin_concurrency.py; test_admin_final_concurrency.py | — |
| DA18 | Admin suspension/reactivation | Managed non-Admin users | Change status; try active-job/order/last-owner conflict | Auth sessions denied next request; records/assignments preserved | Account safeguards/concurrency cases pass | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_admin_foundation.py; test_admin_final_concurrency.py | — |
| DA19 | Admin self/last-Admin protection | Target an Administrator | Use generic account status endpoint | No normal API can disable Admins | All Admin targets are excluded from managed_user; self/last Admin denied | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_admin_foundation.py; no Admin-to-Admin suspension UI invented | — |
| DA20 | Admin audit API/recent dashboard | Recorded synthetic Admin/business decisions | Read actor/target/action/time/states; filter/page; try edit/delete/non-Admin | Actual immutable audit history; safe access | API fields/bounds and recent dashboard contracts pass | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_admin_foundation.py; test_admin_final_review.py; adminDashboard.test.js | — |
| DA21 | Admin full Activity UI | Dedicated complete activity experience needed | Open full audit list/detail workflow | Complete supported audit experience | Recent dashboard preview/API exist; full Activity UI incomplete | — | BLOCKED | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); Previous Day 16/17 findings; not replaced by a fake report | ADM01/ADM02 |
| DA22 | Admin platform reports/CSV | Reports/date-filter/timezone/export workflow needed | Open report/filter/export/empty/error state | Actual SQL-backed reports, no revenue mislabeling/private balances | Platform Reports remains Coming soon; workflow/API not implemented | — | BLOCKED | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); AdminDashboard.jsx, App.jsx; no report UAT pass claimed | ADM01/ADM02 |
| DA23 | All role/ownership isolation | Unrelated users/businesses/drivers | Tamper IDs and roles; attempt self-approval/generic finance write | Backend denies unauthorized access | JWT/RBAC/ownership tests pass | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_auth_rbac.py; test_driver_security_review.py; test_admin_final_review.py | — |
| DA24 | Driver/Admin errors/conflicts | Deferred/failed requests, stale statuses | Timeout/401/403/409/422/429/500, failed pagination/audit refresh | Safe feedback, no false success; preserve uncertainty | Existing workflow/API error cases pass; reporting failures unsupported | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); driverJobs.test.js; driverDeliveries.test.js; adminManagement.test.js; test_api_hardening.py | — |
| DA25 | Driver/Admin financial isolation | Posted ledger/order snapshots | Approve/read/manage, accept, pickup, deliver, inspect audit | No credit/repayment/payment-status changes from delivery/Admin operations | Exact persisted snapshot checks pass | 2026-11-07 | PASS | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); test_driver_deliveries.py; test_admin_final_review.py; test_day18_uat.py | — |
| B01 | Driver/Admin; fresh Driver registration | Driver/Admin; fresh Driver registration | Register/login, submit profile/vehicle, Admin review, reopen Driver jobs | Complete onboarding with pending review and explicit approval | NOT RUN; DA02 also BLOCKED by missing submission flow | — | NOT RUN | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); No screenshots | Browser gate |
| B02 | Owner/approved Driver/Customer; fixture profile | Owner/approved Driver/Customer; fixture profile | Create eligible linked delivery, review details, accept, pickup/transit/deliver, refresh both tracking views | Matching persisted states; clear delivered confirmation, no payment claim | NOT RUN | — | NOT RUN | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); API evidence DA11 is not browser evidence | Browser gate |
| B03 | Admin/Owner; pending business | Admin/Owner; pending business | Review/confirm approve or reject, reopen Owner eligibility | Accurate status, one audit/notification, no self-approval | NOT RUN | — | NOT RUN | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); No browser trace | Browser gate |
| B04 | Admin | Admin | Dashboard → users → Drivers/business approvals → reports → activity | Safe metrics/controls, no fake report or audit data | NOT RUN; full reports/Activity also blocked | — | NOT RUN | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); DA21/DA22 | Browser gate |
| B05 | Rejected/suspended Driver | Rejected/suspended Driver | Login where allowed; inspect dashboard/jobs/update actions | Accurate reason; backend denial and no false eligible UI | NOT RUN | — | NOT RUN | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); No browser trace | Browser gate |
| B06 | Both roles, each 375/768/1024/1366/1536 px | Both roles, each 375/768/1024/1366/1536 px | Repeat dashboard, jobs/details/accept/status/notifications and management/filter/dialog flows | No page overflow/clipped controls; readable areas/amounts; usable navigation/touch targets | NOT RUN at all five widths | — | NOT RUN | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); No viewport screenshots | Browser gate |
| B07 | Both roles; keyboard/screen reader | Both roles; keyboard/screen reader | Tab/Shift-Tab/Enter/Escape through filters, confirmations and notification menus | Visible focus, dialog entry/trap/return, labels and status/error announcements | NOT RUN | — | NOT RUN | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); No accessibility session | Browser gate |
| B08 | Both roles; slow/denied/conflicting synthetic requests | Both roles; slow/denied/conflicting synthetic requests | Timeout, expired JWT, duplicate clicks, stale decision, page/audit failure | Safe error/retry, uncertain result preserved, no duplicate write | NOT RUN | — | NOT RUN | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); API/controller coverage DA24 only | Browser gate |
| B09 | Both roles; contrast tooling | Both roles; contrast tooling | Measure normal/disabled/focus/error/approval-status colors and targets | Readable contrast and reachable controls | NOT RUN | — | NOT RUN | [day18-driver-admin-uat.md](day18-driver-admin-uat.md); No measurement | Browser gate |
| TR-A | Training / CreditSale | Approved synthetic demo environment; see scenario preconditions | Run scenario A | See exact synthetic outcomes in training guide | No session delivered | — | NOT RUN | [Training guide](day18-training-scenarios.md) | — |
| TR-B | Training / Partial/full repayment | Approved synthetic demo environment; see scenario preconditions | Run scenario B | See exact synthetic outcomes in training guide | No session delivered | — | NOT RUN | [Training guide](day18-training-scenarios.md) | — |
| TR-C | Training / Cash order | Approved synthetic demo environment; see scenario preconditions | Run scenario C | See exact synthetic outcomes in training guide | No session delivered | — | NOT RUN | [Training guide](day18-training-scenarios.md) | — |
| TR-D | Training / Credit order approval | Approved synthetic demo environment; see scenario preconditions | Run scenario D | See exact synthetic outcomes in training guide | No session delivered | — | NOT RUN | [Training guide](day18-training-scenarios.md) | — |
| TR-E | Training / Delivery coordination | Approved synthetic demo environment; see scenario preconditions | Run scenario E | See exact synthetic outcomes in training guide | No session delivered | — | NOT RUN | [Training guide](day18-training-scenarios.md) | — |
| TR-F | Training / Admin approvals | Approved synthetic demo environment; see scenario preconditions | Run scenario F | See exact synthetic outcomes in training guide | No session delivered | — | NOT RUN | [Training guide](day18-training-scenarios.md) | — |
