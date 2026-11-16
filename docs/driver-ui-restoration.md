# Delivery Driver approved UI restoration

## Pre-edit audit — 2026-11-08

Opened and inspected all six reference PNGs under `design-references/driver/`.
Inspected Driver layout/sidebar, dashboard, jobs, deliveries/history/detail,
profile submission, notifications, API services, state workflows, response
parsers and FastAPI Driver schemas. No AGENTS.md was found.

| Page | Existing mismatch | Functional boundary |
| --- | --- | --- |
| Shared shell | Flat active navigation, muted labels, page-title header, no profile footer/search/menu. | No backend Online/offline presence: eligibility must not be labelled Online. |
| Dashboard | Four summary cards, profile/active list first; no embedded available-jobs acceptance or next-assignment panel. | Counts are all-time/current, not today-only. No earnings, fees, distances or scheduled pickup. |
| My Deliveries | Stacked records, select filter, separate detail route; reference uses rows/tabs/selected detail. | Keep active/history endpoints separate; assigned -> picked_up -> in_transit -> delivered, backend next-action and final confirmation. Area names are not precise navigation destinations. |
| My Earnings | Missing. | No earnings/payout/accounting API. Never derive paid/withdrawable balances from completion. |
| My Vehicle | Missing; stored vehicle fields only visible in dashboard. | Type/registration are stored. No photo, make/model/year/fuel/load, documents, expiry or document verification/edit API. Preserve first profile submission and Admin approval. |
| Notifications | Generic shared inbox lacks grouped reference hierarchy/icons. | Existing recipient-scoped types/read/page behavior; no payout/document/earnings notifications. |
| My Profile | Dashboard anchor only; no dedicated page. | Own Driver profile + /auth/me supply basic identity/account/approval state. No NIC, residential address, DOB/photo/member-since/identity verification/edit/password API. |
| Available Orders / Settings | Jobs workflow exists; Settings disabled. No separate screenshots supplied. | Restyle jobs using existing actions. Settings can show supported navigation/logout and honest unavailable preferences. |

Other role layouts, financial formulas, API methods, database models, migrations
and authentication must remain unchanged. Reference people/photos/IDs/amounts are
illustrative and must not be hardcoded into application data.

## Restored sections and remaining reference differences

| Page | Completed | Remaining differences / unavailable capability |
| --- | --- | --- |
| Shared shell | Driver-only Inter typography, navy sidebar with white/teal transparent logo, white labels/icons, gradient active state, authenticated initials/name footer, wide working search, bell/count and profile menu, light background/cards/tables. | No Online/offline API: header explicitly says Presence unavailable. No invented green Online badge. Initials replace an unstored portrait. Header searches the current assigned-delivery page through existing local filtering, not a new global endpoint. Legacy history navigation remains. |
| Dashboard | Three reference-style summary cards, actual completed/active counts, explicit earnings unavailable, existing eligibility/application, embedded Available Orders list with real acceptance, Next Assigned Delivery preview, retained profile/active records below. | Counts are all-time/current, not today's totals. No fees/earnings/distances/appointment times. Next-assignment panel explicitly describes a request from the latest preview, not a scheduled or prioritized next job. Personalized Welcome remains under the Dashboard title. |
| My Deliveries | Assigned-delivery table, actual-status tabs, current-page search/sort, selected details using existing detail workflow, recorded timeline and original update/completion confirmation controls. Direct detail URLs retained. | Active/history remain separate and clearly labelled; completed/cancelled route uses existing history filter. No fee, order-ID mapping, distance, precise destination/navigation or receipts API. Area names are not treated as confirmed navigation coordinates. |
| My Earnings | New protected page with Total Earnings/Available Balance/Pending Earnings cards, period/overview/history/payout sections matching reference hierarchy. | All amounts/trends/exports/payouts explicitly unavailable. Disabled period controls do not pretend to fetch reports. Completion is never treated as paid or withdrawable earnings. |
| My Vehicle | New protected page with actual registration/type, vehicle-image placeholder, attribute grid, four document panels and Driver approval/eligibility section. Existing first profile submission reused. | No make/model/year/fuel/color/capacity/photo/document/expiry API. Document statuses are unavailable; Driver approval is not document verification. No fake edit/upload/renew action. |
| Notifications | Driver-only grouped Recent Notifications, actual unread count/read controls, supported delivery/application event filters, colored icons and safe contextual links. | Existing exact event types replace unsupported aggregate categories. Earnings tab is explicitly unavailable; no payout/document notifications fabricated. Existing server Previous/Next pagination retained instead of fake Load More. |
| My Profile | New protected page with actual own Driver ID/name/account/approval, authenticated email, personal-information and verification/security sections. First application form retained where appropriate. | No NIC, residential address, DOB/location/photo/member-since fields, independent verification or edit/password API. No national identity value or invented Verified badge. |
| Available Orders / Settings | Existing Jobs workflow gains shared styling and optional embedded presentation. New guarded Settings page uses same card hierarchy with working profile/vehicle/inbox/logout links. | No invented preference, presence, password, two-factor or session management controls. No separate reference was supplied for these two pages. |

The screenshot's illustrative shops, personal identities, fees, dates and payouts
were not copied into application data. Missing backend values are labelled
unavailable, not zero. Existing API projections and rules govern all displayed
operational values.

## Functional and security preservation

- No FastAPI routes, API service methods, database models, migrations, ledger
  formulas or credit data changed. No database operation, reset, upgrade,
  deployment, commit, push or AI Summary work occurred.
- The existing Driver role guard wraps all four new routes. Profile resources
  use the existing JWT client and `parseDriverResponse('profile', data, userId)`
  to validate the authenticated identity, approval/eligibility consistency and
  field allowlist. Aborted/stale session responses are ignored and not persisted.
- `/api/v1/driver/profile` is reused for profile/vehicle reads; the existing
  first-time POST form still creates only a pending application. There is no
  profile replacement, public approval or fabricated document review.
- Dashboard embedded acceptance reuses `createDriverJobsWorkflow`, the same
  `/driver/jobs/{id}/accept` call, idempotent/uncertain-result handling and profile
  eligibility checks. Confirmed acceptance/check callbacks refresh the outer
  Dashboard through its existing reader.
- Selected delivery detail reuses `createDeliveriesWorkflow` and the existing
  `/driver/deliveries/{id}/status` payload (`expected_status`, `status`). Server
  `allowed_next_status` and eligibility still control actions; delivered still
  requires the existing confirmation. Confirmed changes refresh the parent list.
  No new transitions or ownership assumptions were introduced.
- Search/sort is explicitly current-page presentation. No unsupported API query
  parameters or cross-driver identifiers are sent. All original jobs, deliveries,
  history and direct detail routes remain available.
- Notifications reuse the current recipient-scoped workflow, existing item
  destination validation and list/count/read endpoints. The Driver inbox hides
  previous records/counts on authorization failure. Other role inboxes/layouts
  were not edited.

## Exact files changed in this task

Modified:

- `frontend/src/App.jsx`: guarded Driver earnings/vehicle/profile/settings routes.
- `frontend/src/layouts/DriverLayout.jsx`.
- `frontend/src/components/driver/DriverSidebar.jsx`.
- `frontend/src/pages/driver/DriverDashboard.jsx`, `AvailableJobs.jsx`,
  `DriverDeliveries.jsx`, `DriverNotifications.jsx`.
- `frontend/tests/driverDashboardView.test.js`: intentional three-card/new-route
  assertions, retaining real-field, auth, approval and service checks.

Created:

- `frontend/src/layouts/driver.css` (scoped to Driver shell/content).
- `frontend/src/hooks/useDriverProfile.js`.
- `frontend/src/components/driver/DriverAccountResource.jsx`, `DriverInbox.jsx`.
- `frontend/src/pages/driver/DriverEarnings.jsx`, `DriverVehicle.jsx`,
  `DriverProfile.jsx`, `DriverSettings.jsx`.
- `frontend/tests/driverRestoration.test.js`.
- `docs/driver-ui-restoration.md` (this report and pre-edit audit).

No dependency changes were needed; locally bundled Inter from the existing
frontend dependency is reused. Existing unrelated workspace changes were retained.

## Actual verification

- **Full frontend suite: 845 passed, zero failed/skipped**, 61.53s, using
  `npm test` (`node --test`). Includes existing Driver dashboard/profile
  submission/jobs/deliveries/controller/service tests and all Customer, Shop Owner,
  Admin and notification frontend tests.
- New restoration tests verify real identity/navigation, three truthful summary
  cards, no fake earnings/payout amounts, stored vehicle projection, pending-only
  onboarding, absence of unsupported verification/NIC exposure, recipient links,
  stale-data concealment, Driver role guard and honest Settings controls.
- Existing acceptance/status controller tests exercise duplicate requests,
  uncertainty, malformed/foreign responses, ineligible accounts, request payloads
  and server-permitted transitions. Automated adapters/SSR do not prove a live
  MySQL transaction or manual browser action in this task.
- **Vite build: PASS**, final run 3.99s. Used process-only
  `VITE_API_URL=https://api.example.invalid/api/v1` for production configuration
  validation; no env file changed or real deployment endpoint certified.
  Existing large-bundle (>500 kB) warning remains.
- **Scoped ESLint: PASS** for Driver layout/components/pages, new profile hook
  and App routes.
- Full `npm run lint`: **FAIL**, the same **7 pre-existing errors and 1 warning**
  outside Driver changes: synchronous effect state updates in ShopOwnerCustomers
  (3) and ShopOwnerDashboard (1), unused repayment test imports (3), and the
  existing Dashboard effect dependency warning.
- `git diff --check`: no whitespace errors in this task's frontend paths;
  existing Git line-ending notices only.
- During implementation, build caught an unmatched JSX conditional in the
  embedded Jobs totals; corrected before final checks. Initial focused tests
  found three obsolete Dashboard layout/navigation assertions; updated to the
  intended design. First full run also caught an incomplete synthetic notification
  fixture (missing required `read_at:null`) and an obsolete application-form
  label assertion in the new tests; corrected the fixtures/assertions, preserving
  existing destination validation. Final full result above passes.

Ignored local evidence: `.server-logs/driver-ui-full-tests-final.log`,
`driver-ui-build-final.log`, `driver-ui-lint.log`, `driver-ui-scoped-lint.log`.

## Browser and API/database limits

All six reference PNGs were inspected. Computer-use inventory again returned
`apps: []`, `browsers: []`. Restored-page screenshots, desktop/tablet/mobile
interaction, focus navigation and pixel comparison are therefore **NOT RUN**.
Responsive CSS and actual rendered React markup were checked automatically;
these are not represented as browser visual verification.

No backend code changed or database-changing tests were needed. Previously passing
Day12 backend results were not rerun or relabelled as fresh executions here.
Authentication, concurrency and approval implementation is preserved; live
backend readiness was not independently certified. Earlier development schema /
isolated migration-verification blockers remain outside this UI task, unchanged
and not reverified. Earnings/payout/document/presence capability gaps require
separate supported backend implementation, not fabricated UI or automatic schema
changes.
