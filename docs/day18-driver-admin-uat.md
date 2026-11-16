# Day 18 Step 18.3 — Driver and Administrator experience UAT

Date: 2026-11-07. Branch `main`, HEAD `d917e4f`; tested working tree includes
uncommitted Day 15–18 work. No deployment, cloud/production connection, commit,
push, migration, database creation/reset or real-user provisioning occurred.
AI Summary remains deferred, outside scope and is not a defect.

Step 18.5 update: ONB01's missing submission API/form has been remediated with
automated coverage. This document preserves historical Step 18.3 outcomes.
Browser onboarding remains NOT RUN; see [final review](day18-final-uat-readiness.md).

## A. Repository audit

Reviewed [Step 18.1](day18-uat-matrix.md),
[Step 18.2](day18-shop-customer-uat.md) and
[Day 17 blockers](day17-production-readiness.md), actual Driver/Admin pages,
routes, auth guards, Axios modules, approval/assignment/status/audit services,
registration schemas/service, notification contracts and isolated fixtures.
Prior password-help/confirmation-copy fixes and repayment-test stabilization
remain preserved. Existing 43 staged paths were not staged, unstaged or committed.

The repo already has extensive Driver/Admin API, concurrency, frontend-controller
and React server-render tests. They were reused. No established browser suite was
executed: inventory returned `apps: [], browsers: []`. Browser journeys below are
**NOT RUN**; viewport/focus/assistive-technology execution is unavailable.

Actual test identity was verified by settings/engine and SELECT DATABASE() as
**lankapex_test_db** before the selected backend run. Session-start guards reject
other environments/databases. Existing synthetic rollback/savepoint fixtures and
scoped concurrency cleanup were reused. No development/production data is copied
and the synthetic test DB is not used for migration-chain verification.

## B–D. Acceptance matrix

PASS means the described API/contract scenario actually executed. Browser
acceptance, external monitoring, identity verification and unsupported features
are not inferred. Evidence paths below are relative to `backend/tests` or
`frontend/tests`. Severity is impact of an unresolved finding, not of a passing guard.

| ID | Role / feature | Preconditions | Steps | Expected outcome | Actual outcome | Status | Severity | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DA01 | Driver registration/account | Unique synthetic identity | Register, duplicate/invalid request, login, identity read | Secure password; correct role/status; no Admin escalation | Existing registration/JWT cases pass | PASS | — | test_day10_auth_integration.py; authenticationRoles.test.js |
| DA02 | Driver complete onboarding | Newly registered Driver without fixture profile | Submit profile/vehicle then request Admin review | Supported application submission leading to review | No public submission workflow exists; account stays not_submitted | BLOCKED | HIGH | ONB01; new test_day18_driver_onboarding.py |
| DA03 | Driver/Admin missing application guard | Fresh real registration/login | Read profile/jobs; Admin attempts approval | Missing application cannot gain job access/approval | Profile_required, no vehicle; jobs 403; Admin decision 409 | PASS | — | test_day18_driver_onboarding.py |
| DA04 | Driver approval eligibility | Stored pending/rejected/approved/suspended profile | Read jobs/update; change approval and reuse JWT | Backend persisted status authoritative; vehicle required | Eligibility and current-session cases pass | PASS | — | test_driver_dashboard.py; test_driver_jobs.py; test_day18_uat.py |
| DA05 | Driver dashboard | Synthetic assigned/terminal deliveries | Read counts/profile/preview; render loading/empty/error | Actual own counts only; no earnings/GPS/ratings | API/React contracts pass | PASS | — | test_driver_dashboard.py; driverDashboard.test.js; driverDashboardView.test.js |
| DA06 | Driver available jobs | Approved businesses/unassigned requests | List/filter/page/read details/refresh; foreign/private fields | Only available eligible records; minimal area information | Listing/scope/contract cases pass | PASS | — | test_driver_jobs.py; driverJobs.test.js; driverJobsView.test.js |
| DA07 | Driver vehicle matching | Job-specific vehicle requirement needed | Compare request requirement to stored vehicle | Enforce actual compatibility rules if present | Only profile vehicle completeness exists; requests store no compatibility requirement | NOT RUN | — | driver_service eligibility/create_delivery; no feature invented |
| DA08 | Driver acceptance | Available job; two eligible drivers | Accept/retry/race; read lists/assignment | One assignment; losing driver conflict; own My Deliveries | Atomic MySQL and frontend dispatch cases pass | PASS | — | test_driver_jobs_concurrency.py; test_driver_concurrency.py; driverJobs.test.js |
| DA09 | Driver lifecycle/history | Assigned own delivery | Pickup/transit/delivered; duplicate/skip/out-of-order updates | Valid transitions/events/timestamps; terminal immutability | HTTP/persisted-event and concurrent update cases pass | PASS | — | test_driver_deliveries.py; test_driver_deliveries_concurrency.py; driverDeliveries.test.js |
| DA10 | Driver cancellation | Available/assigned request with existing cancellation rules | Owner cancels where allowed; attempt unsupported driver cancellation | Only existing authorized lifecycle; notification privacy | Cancellation/boundary cases pass; no new public bypass | PASS | — | test_delivery_final_review.py; test_order_delivery_notifications.py |
| DA11 | Owner/Driver/Customer coordination | Linked cash/credit order | Request delivery, accept, progress, refresh tracking | Correct business/order/driver; matching recorded state | Continuous real-login and integration cases pass | PASS | — | test_day18_uat.py; test_shop_driver_integration.py; test_order_delivery.py |
| DA12 | Driver notifications | Approval/rejection/assignment/cancellation events | Inspect recipient/link/read-unread; retry/rollback | No duplicates, cross-account reads or false committed messages | Notification/approval cases pass | PASS | — | test_notifications.py; test_delivery_notifications.py; test_order_delivery_notifications.py; notifications.test.js |
| DA13 | Driver new-job broadcast | Available-job event broadcast needed | Inspect supported event catalogue | Do not claim unsupported push notices | No general available-job broadcast certified; use explicit job refresh | NOT RUN | — | Existing event/service scope |
| DA14 | Admin login/dashboard | Active Admin and other roles | Login/read overview/guard; load failed/empty data | Database-backed counts; Admin-only; honest unavailable state | API and React/controller contracts pass | PASS | — | test_admin_foundation.py; adminDashboard.test.js; adminDashboardView.test.js |
| DA15 | Admin Owner/Customer management | Managed users/foreign roles | Search/filter/page/details/associations; inspect DTOs | Safe supported identity fields; no generic ledger editing | Scope/DTO/role cases pass | PASS | — | test_admin_foundation.py; test_admin_final_review.py; adminManagementView.test.js |
| DA16 | Admin Driver review | Pending profile with stored vehicle | Approve/reject, repeat/race, missing target/fields/non-Admin | One valid transition, audit and notification; no automatic verification | Approval/rejection/concurrency cases pass | PASS | — | test_admin_concurrency.py; test_admin_final_concurrency.py; adminManagement.test.js |
| DA17 | Admin business review | Pending business/active owner | Approve/reject/retry/race; unauthorized decision | Supported pending-only policy; atomic audit/notification | Business conflict and state cases pass | PASS | — | test_admin_foundation.py; test_admin_concurrency.py; test_admin_final_concurrency.py |
| DA18 | Admin suspension/reactivation | Managed non-Admin users | Change status; try active-job/order/last-owner conflict | Auth sessions denied next request; records/assignments preserved | Account safeguards/concurrency cases pass | PASS | — | test_admin_foundation.py; test_admin_final_concurrency.py |
| DA19 | Admin self/last-Admin protection | Target an Administrator | Use generic account status endpoint | No normal API can disable Admins | All Admin targets are excluded from managed_user; self/last Admin denied | PASS | — | test_admin_foundation.py; no Admin-to-Admin suspension UI invented |
| DA20 | Admin audit API/recent dashboard | Recorded synthetic Admin/business decisions | Read actor/target/action/time/states; filter/page; try edit/delete/non-Admin | Actual immutable audit history; safe access | API fields/bounds and recent dashboard contracts pass | PASS | — | test_admin_foundation.py; test_admin_final_review.py; adminDashboard.test.js |
| DA21 | Admin full Activity UI | Dedicated complete activity experience needed | Open full audit list/detail workflow | Complete supported audit experience | Recent dashboard preview/API exist; full Activity UI incomplete | BLOCKED | MEDIUM | Previous Day 16/17 findings; not replaced by a fake report |
| DA22 | Admin platform reports/CSV | Reports/date-filter/timezone/export workflow needed | Open report/filter/export/empty/error state | Actual SQL-backed reports, no revenue mislabeling/private balances | Platform Reports remains Coming soon; workflow/API not implemented | BLOCKED | MEDIUM | AdminDashboard.jsx, App.jsx; no report UAT pass claimed |
| DA23 | All role/ownership isolation | Unrelated users/businesses/drivers | Tamper IDs and roles; attempt self-approval/generic finance write | Backend denies unauthorized access | JWT/RBAC/ownership tests pass | PASS | — | test_auth_rbac.py; test_driver_security_review.py; test_admin_final_review.py |
| DA24 | Driver/Admin errors/conflicts | Deferred/failed requests, stale statuses | Timeout/401/403/409/422/429/500, failed pagination/audit refresh | Safe feedback, no false success; preserve uncertainty | Existing workflow/API error cases pass; reporting failures unsupported | PASS | — | driverJobs.test.js; driverDeliveries.test.js; adminManagement.test.js; test_api_hardening.py |
| DA25 | Driver/Admin financial isolation | Posted ledger/order snapshots | Approve/read/manage, accept, pickup, deliver, inspect audit | No credit/repayment/payment-status changes from delivery/Admin operations | Exact persisted snapshot checks pass | PASS | — | test_driver_deliveries.py; test_admin_final_review.py; test_day18_uat.py |

No earnings, ratings, GPS, ETA, vehicle matching engine, public self-approval,
reporting subsystem or SMS/WhatsApp/email integration was added.

## E–F. Security and financial isolation

Current JWT identity, active User and role/ownership checks remain authoritative.
Ineligible profiles may retain authorized assignment read access, but may not
accept/progress jobs. Account suspension is separate from Driver approval state.
Stored profile fields do not prove identity verification. Admin account management
excludes all Admin targets; it does not implement arbitrary Admin suspension.

Controlled MySQL tests exercise competing Driver acceptance, duplicate/stale
status updates, approval-versus-rejection races and serialized suspension/accept.
Approval/audit/notification commit failures roll back together. Generic Admin DTOs
exclude financial histories and direct balance editing. Audit API returns actor,
target, state transition and time; the recent UI preview deliberately omits actor
contact/reason fields. It is not certified as a full audit investigation UI.

Financial checks compare actual CreditAccount/LedgerEntry and order/item snapshots
before/after operations using existing Decimal rules. Acceptance/pickup/delivery
create no repayment or credit sale. Delivered does not pay cash or settle credit.
Admin management/audit reads do not alter posted financial records. The continuous
cash/credit journeys retain Customer balances 0.00/250.50 respectively and cash
unpaid versus credit posted (posted is not repayment). No formula changed.

## G. Mobile, accessibility and browser checklist

Source/static review found existing explicit labels, status/error regions,
focus-visible styles, min-h-11 controls, wrapping cards and native Admin confirmation
dialogs. Driver Delivered uses an inline confirmation group. These are implementation
observations, not measured contrast/focus/viewport passes. No new markup defect
was sufficiently demonstrated to justify an application change.

Every browser case below is **NOT RUN** because no browser is available. Overall
browser sign-off is BLOCKED. Use only a verified isolated backend and synthetic
actors; fixture-created profiles must be identified explicitly in evidence.

| ID | Preconditions / role | Steps | Expected | Actual / status | Evidence |
| --- | --- | --- | --- | --- | --- |
| B01 | Driver/Admin; fresh Driver registration | Register/login, submit profile/vehicle, Admin review, reopen Driver jobs | Complete onboarding with pending review and explicit approval | NOT RUN; DA02 also BLOCKED by missing submission flow | No screenshots |
| B02 | Owner/approved Driver/Customer; fixture profile | Create eligible linked delivery, review details, accept, pickup/transit/deliver, refresh both tracking views | Matching persisted states; clear delivered confirmation, no payment claim | NOT RUN | API evidence DA11 is not browser evidence |
| B03 | Admin/Owner; pending business | Review/confirm approve or reject, reopen Owner eligibility | Accurate status, one audit/notification, no self-approval | NOT RUN | No browser trace |
| B04 | Admin | Dashboard → users → Drivers/business approvals → reports → activity | Safe metrics/controls, no fake report or audit data | NOT RUN; full reports/Activity also blocked | DA21/DA22 |
| B05 | Rejected/suspended Driver | Login where allowed; inspect dashboard/jobs/update actions | Accurate reason; backend denial and no false eligible UI | NOT RUN | No browser trace |
| B06 | Both roles, each 375/768/1024/1366/1536 px | Repeat dashboard, jobs/details/accept/status/notifications and management/filter/dialog flows | No page overflow/clipped controls; readable areas/amounts; usable navigation/touch targets | NOT RUN at all five widths | No viewport screenshots |
| B07 | Both roles; keyboard/screen reader | Tab/Shift-Tab/Enter/Escape through filters, confirmations and notification menus | Visible focus, dialog entry/trap/return, labels and status/error announcements | NOT RUN | No accessibility session |
| B08 | Both roles; slow/denied/conflicting synthetic requests | Timeout, expired JWT, duplicate clicks, stale decision, page/audit failure | Safe error/retry, uncertain result preserved, no duplicate write | NOT RUN | API/controller coverage DA24 only |
| B09 | Both roles; contrast tooling | Measure normal/disabled/focus/error/approval-status colors and targets | Readable contrast and reachable controls | NOT RUN | No measurement |

Record operator/time, browser/version, exact width, case ID, expected/actual,
severity, and redacted local screenshot/trace references when executed. Do not
alter branding/colors merely to satisfy an unmeasured assumption.

## H–I. Tests and build

- Backend selected regression: **347 passed, 0 failed, 0 skipped**, 111.24 seconds.
- New onboarding safety contract: **1 passed**, 0 failed/skipped, 3.54 seconds.
  Both runs emitted the existing pytest cache-path creation warning; not suppressed.
- Focused Driver/Admin/notification frontend: **236 passed**, 0 failed/skipped,
  15.17 seconds. Full frontend: **806 passed**, 0 failed/skipped, 57.42 seconds.
- Full lint: **FAIL — 8 existing errors, 1 warning** in the earlier Owner/test
  files; no configured typecheck. No suppression or business-rule change.
- Vite production build: **PASS**, 3.12 seconds; existing large-chunk warning.
  Process-only `https://api.example.invalid/api/v1` was used; not a deployment
  endpoint or production-ready bundle configuration. No dotenv changes.
- Browser tests: **0 executed**, not passed. Report/date-filter/CSV execution:
  **BLOCKED**, not part of a passing test count.
- New test syntax and documentation whitespace checks passed. Known-secret scan:
  zero findings in 447 current files/assets and 639 historical text blobs against
  two known local labels; this limited scan does not certify absence of unknown
  credentials. Existing 43 staged paths remain unchanged in count.

Selected backend files: test_day18_uat, test_day10_auth_integration, test_auth_rbac,
test_driver_dashboard, test_driver_jobs, test_driver_jobs_concurrency,
test_driver_deliveries, test_driver_deliveries_concurrency, test_driver_concurrency,
test_driver_security_review, test_admin_foundation, test_admin_concurrency,
test_admin_final_concurrency, test_admin_final_review, test_order_delivery,
test_order_delivery_concurrency, test_order_delivery_notifications,
test_shop_driver_integration, test_shop_owner_delivery_summary,
test_delivery_notifications, test_delivery_final_review, test_notifications,
test_notifications_concurrency and test_api_hardening (all .py).

Logs: `.server-logs/day18-3-backend.log`, `day18-3-onboarding.log`,
`day18-3-targeted.log`, `day18-3-frontend.log`, `day18-3-lint.log`,
`day18-3-build.log`. Backend uses process-only APP_ENV testing and exact test
database with fresh ignored basetemp directories. No unrelated full backend
rerun is needed for a test/documentation-only change.

## J. Defect register

| ID | Severity/role | Reproduction, expected vs actual | Root cause | Fix / verification |
| --- | --- | --- | --- | --- |
| ONB01 | HIGH / Driver | Register/login new Driver; expected a supported route to submit profile/vehicle for review; actual not_submitted, jobs 403 and Admin approval 409 | Registration creates User only; create_profile exists only as internal service/fixture use; no public profile-submission route/UI | OPEN, complete onboarding BLOCKED; new executable contract verifies secure denial, not a completed journey |
| ADM01 | MEDIUM / Admin | Navigate Platform Reports/date filters/CSV; expected implemented workflow, actual Coming soon | Missing report functionality | OPEN/BLOCKED; no invented aggregates or exports |
| ADM02 | MEDIUM / Admin | Open full audit investigation UI; expected list/detail experience, actual recent preview/API only | Full Activity UI incomplete | OPEN/BLOCKED; API coverage does not substitute for UI |
| LINT01 | MEDIUM / validation | npm run lint expected clean; actual 8 errors/1 warning | Existing effect-state/unused-import/dependency findings | OPEN; unchanged by this step |

ONB01 needs a deliberate authenticated submission/vehicle-management workflow with
validation, ownership, pending-only review and tests; it is not safely fixed by
auto-creating approved profiles, relaxing eligibility or injecting production data.
This UAT step does not introduce that new workflow. No new application code was
modified, no approval policy weakened and no ledger mutation surface added.

## K. Files created/modified

- `backend/tests/test_day18_driver_onboarding.py`: real registration/login and
  missing-application eligibility/review safety contract.
- `docs/day18-driver-admin-uat.md`: this A–M matrix and findings.
- `docs/day18-uat-matrix.md`: link the new onboarding blocker to the overall UAT.

## L–M. Readiness, blockers and next step

**Driver operational API UAT:** PASS for existing fixture-provisioned eligible
profiles; complete new-Driver onboarding **BLOCKED**. **Administrator supported
API/contract UAT:** PASS; complete reporting/Activity experience **BLOCKED**.
**Overall Day 18 UAT:** incomplete/BLOCKED for user-experience sign-off.
**Production/pilot launch:** **NO-GO**. These are separate decisions.

Preserve all Day 17 blockers: isolated migration-chain execution **BLOCKED** after
MySQL permission denial; no new resolution evidence, no elevated retry or DBA
password request. Restore/reconciliation, production shared/edge throttling,
actual hosting/TLS/proxy/runtime/advisory checks, monitoring and compatible rollback
artifacts remain unverified. No test-database substitution or destructive migration.

Step **18.4 Pilot Launch Planning** may proceed as planning with explicit entry
gates: resolve ONB01 or agree a reviewed limited onboarding process, complete or
explicitly limit Admin reports/Activity scope, execute all browser/manual checks,
resolve lint and satisfy database/recovery/security/operations prerequisites.
Do not start pilot operation or deploy as part of this testing report.
