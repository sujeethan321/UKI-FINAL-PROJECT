# Day 12 Steps 12.1 and 12.2 - Driver Backend and Dashboard

> Current checkpoint: [Step 12.5 final regression, security review and Git checkpoint](day12-final-regression-security-review.md). The results below are the historical Step 12.1/12.2 snapshot.

> Step 12.3 now exposes secure available-job listing, details and acceptance. See [the current acceptance contract and verification](day12-available-jobs-and-acceptance.md). The deferred-acceptance descriptions below are the completed Step 12.1/12.2 snapshot.

## Result
Step 12.1 is implemented and verified; Step 12.2 now uses its real authenticated read endpoints. Required APIs, backend/frontend tests and the production build pass. Browser-specific responsive verification remains unavailable. No commit or push was made.

## Repository audit
The initial audit found only local branch main, plus the existing origin/main tracking ref. No alternate local implementation was found in models, routers, schemas, services, tests or Alembic revisions. Starting application HEAD was 53b0f53. Driver registration, JWT /auth/me and /access/driver existed; dashboard/profile/vehicle/delivery records did not. LedgerEntry.order_id was only an optional financial reference, not a reusable Order/Delivery model. The original /driver/dashboard used DashboardPlaceholder. No separate approved Driver design file was found; the existing LankaPex layouts and palette are the visual reference.

The unrelated pre-existing .gitignore modifications and the earlier audit document were preserved. No login/registration, Customer financial calculation, Shop Owner dashboard, Admin layout or landing design was changed.

## Backend implementation and models
Location: backend/app/routers/driver.py, backend/app/services/driver_service.py, backend/app/schemas/driver.py and backend/app/models/delivery.py.

- DriverProfile: primary key user_id references the existing User. Explicit approval_status is pending/approved/rejected/suspended, defaults pending. Optional stored vehicle_type and registration_reference must be present together. Review actor/time are stored privately and required for non-pending decisions. A missing profile is reported as not_submitted; GET never creates or approves one.
- DeliveryRequest: unique reference, requesting business FK, creating user FK, pickup/delivery areas, status and created/updated timestamps. It is not an order, charge, fee or earnings record.
- DeliveryAssignment: unique delivery_request_id FK, driver_user_id FK to DriverProfile, assigned_at. The unique request constraint enforces at most one assignment, including historical terminal assignments.

Timestamps in these new services are naive database datetimes representing UTC, serialized as ISO datetimes without an offset. The Driver frontend labels assignment times UTC. Existing Customer/Shop Owner date semantics are unchanged.

## Migration and database safety
New revision: backend/alembic/versions/f6a2b5c4d904_add_driver_delivery_foundation.py, parent e5f1a4b3c803. Upgrade only creates the three new tables, constraints and indexes; it does not backfill records or approve users. Downgrade explicitly refuses destructive removal of assignment/review data.

Before mutating tests, a fresh Python launcher sets MYSQL_DATABASE=lankapex_test_db before imports, checks settings and engine database names and requires SELECT DATABASE() to match. The migration first ran successfully on the verified test database, advancing e5f1a4b3c803 to f6a2b5c4d904. All automated mutations/concurrency fixtures used lankapex_test_db. Real concurrency fixtures commit unique seeds for independent connections and remove only their exact owned IDs afterward; ordinary tests use the existing rollback/savepoint fixture. No database was reset.

The development migration guard initially stopped without modifying anything because lankapex_db was at b2a1c4d6e8f0 rather than e5f1a4b3c803. Schema inspection confirmed payment_reminders, notifications, communication_consents, communication_attempts and all Driver tables were missing. The pending c3/d4/e5 upgrade operations were reviewed: they only create their own missing tables/indexes. After checking the actual database, exact starting revision and absence of all conflicting tables, the reviewed additive chain b2 -> c3 -> d4 -> e5 -> f6 was applied to lankapex_db. No existing records were changed, no tests were run there, and no fake deliveries/drivers/approvals were seeded. Both databases now have the new revision. This also makes the already-supported notification store available to the real development app.

## Actual read APIs
Prefix follows existing registration: /api/v1/driver. All three routes require verified JWT, active User and the Driver role. Responses use Cache-Control: no-store; SQL failures return a generic 503 without database diagnostics. There is no caller-selected driver ID.

### GET /api/v1/driver/profile
Illustrative response shape for an unsubmitted profile (the name/ID are examples, not seeded development records):
~~~json
{
  "driver_user_id": 7,
  "full_name": "Driver display name",
  "account_status": "active",
  "approval_status": "not_submitted",
  "eligible_for_jobs": false,
  "eligibility_reason": "profile_required",
  "vehicle": null
}
~~~
When stored, vehicle is {"vehicle_type":"van","registration_reference":"stored reference"}. Other approval values are pending, approved, rejected and suspended. Eligibility reasons are profile_required, approval_pending, approval_rejected, approval_suspended, vehicle_required and eligible. No private reviewer IDs, approval notes, documents, email or unrelated driver data are exposed.

### GET /api/v1/driver/dashboard/summary
~~~json
{
  "driver_user_id": 7,
  "available_jobs_count": 0,
  "active_deliveries_count": 0,
  "completed_deliveries_count": 0
}
~~~
Available jobs means requests with status available, approved requesting business and no assignment, visible only to an eligible Driver. An ineligible Driver has zero jobs currently available to them, not an invented global platform count. Active/completed counts come only from the authenticated Driver's assignments. Active is assigned/picked_up/in_transit; completed is delivered. Cancelled assignments are not counted in either. Own assignments remain readable if profile eligibility is later revoked; mutation privileges do not remain.

### GET /api/v1/driver/deliveries?page=1&page_size=5
~~~json
{
  "driver_user_id": 7,
  "total": 0,
  "page": 1,
  "page_size": 5,
  "deliveries": []
}
~~~
Each actual row has delivery_request_id, reference, business_name, pickup_area, delivery_area, status and assigned_at. The endpoint returns active assignments only, newest assigned_at then assignment_id first. Page bounds are 1-1,000,000; page_size is 1-100. The dashboard requests only the first five and displays the total. It does not fetch an unbounded history or expose unassigned business/customer contact data.

Profile includes status and stored vehicle information, so redundant status/vehicle endpoints were not invented. Existing recipient-scoped /api/v1/notifications reads/actions are reused by the Driver inbox, not reimplemented.

## Approval, ownership and service-layer writes
There was no pre-existing Driver approval policy to reuse; general User account_status remains enforced without alteration. New job eligibility requires an active Driver User, an explicitly approved DriverProfile and both stored vehicle fields. No automatic approval, public self-approval or frontend status override exists.

Internal service helpers (no public mutation routes yet):
- create_profile: checks active Driver identity, validates paired vehicle fields, creates only pending profiles.
- review_profile: requires a stored active Admin actor, locks the actual Driver profile and records an explicit approved/rejected/suspended decision. Driver self-review is denied. This is a privileged service, not a public onboarding/admin screen.
- create_delivery: requires active Shop Owner identity, active membership in the exact requesting business and approved business status. Stores only valid areas and a unique reference.
- accept_delivery: checks/locks User and profile eligibility, locks the exact request row, uses a current locking read of its assignment, and verifies business approval/unassigned availability. Inserts one assignment and changes the request atomically. Same-Driver replay of an active assignment returns its existing assignment. Other-driver races lose with 409. A DB uniqueness constraint is a second protection.
- transition_delivery: checks current eligibility, request lock and exact assignment ownership; foreign/missing assignments use the same safe 404. Validates the current state before updating.
- cancel_business_delivery: verifies the requesting business membership and exact request business, then locks and cancels only before pickup.

Callers must commit the transaction on success or roll back on failure; these helpers never partially commit. Locks/current reads avoid stale MySQL REPEATABLE READ snapshots. A review/suspension update must wait for the protected profile read; revoked/inactive Drivers cannot accept or update deliveries. No acceptance, status-update, delivery-creation or approval HTTP API is exposed in this step. Public job acceptance is deferred to Step 12.3.

## Delivery lifecycle
| From | Permitted next state | Actor through internal service |
| --- | --- | --- |
| available | assigned | Eligible accepting Driver |
| available | cancelled | Authorized requesting business |
| assigned | picked_up | Assigned eligible Driver |
| assigned | cancelled | Assigned eligible Driver or authorized requesting business |
| picked_up | in_transit | Assigned eligible Driver |
| in_transit | delivered | Assigned eligible Driver |
| delivered / cancelled | none | Terminal |

No skipping states, reopening, reassignment or cancellation after pickup is introduced. Terminal assignments are retained. Operations must resolve work for a suspended Driver through a future explicit privileged workflow; the frontend cannot bypass eligibility.

## Frontend integration
- /driver/dashboard renders DriverLayout and DriverDashboard under the unchanged Driver-only ProtectedRoute.
- /driver/notifications uses the existing authorized inbox. One global notification workflow per user/role/token is reused, with its existing polling and session isolation. No Driver-specific delivery notifications were invented.
- DriverSidebar enables Dashboard, My Deliveries (the real dashboard preview anchor), Profile (the real profile anchor) and Notifications. Available Jobs, Delivery History and Settings are visibly Planned, without fake routes or acceptance/update controls.
- Four cards show Available Jobs, Active Deliveries, Completed Deliveries and actual Driver approval status, with general account status separately labeled.
- Greeting uses the authenticated User's display name. Stored profile/vehicle data, no-profile/no-vehicle, actual zero/empty deliveries and supported approval states are shown accurately.
- Assigned delivery preview shows reference, business, pickup/delivery areas, current status and UTC assigned date. No unsupported View Details action, earnings, customer contacts, map, GPS or shopping feature is added.
- Shared BrandLogo, Lucide icons, existing font/palette, 286px sidebar, 90px header and mobile dialog pattern are preserved. DashboardPlaceholder remains available as an unrelated component; only the Driver route stopped using it.

The dedicated Driver service uses shared Axios JWT/session handling and AbortSignals. Profile/summary/delivery envelopes must match the current authenticated user ID. Row types, supported status, count integers, bounds, dates and uniqueness are validated; undocumented/private properties are dropped. Data stays in component/controller memory. User/session keys, aborts and generation checks prevent previous-driver or superseded responses from repopulating state. Any 401/403 clears all Driver sections. Loading/unavailable/malformed data displays dashes and retry, not fabricated zero. One section's network failure preserves other successful sections.

General User account suspension/pending restrictions still block authentication/protected routes as before. DriverProfile pending/rejected/suspended is distinct from general User status and can be shown to an active authenticated Driver with no acceptance controls. No claimed approval exists when profile is absent.

## Files
Backend added:
- backend/app/models/delivery.py
- backend/app/schemas/driver.py
- backend/app/services/driver_service.py
- backend/app/routers/driver.py
- backend/alembic/versions/f6a2b5c4d904_add_driver_delivery_foundation.py
- backend/tests/test_driver_dashboard.py
- backend/tests/test_driver_concurrency.py

Backend extended: backend/app/models/__init__.py and backend/app/main.py.

Frontend added:
- frontend/src/layouts/DriverLayout.jsx
- frontend/src/components/driver/DriverSidebar.jsx
- frontend/src/pages/driver/DriverDashboard.jsx
- frontend/src/pages/driver/DriverNotifications.jsx
- frontend/src/services/driverDashboardService.js
- frontend/src/utils/driverDashboard.js
- frontend/tests/driverDashboard.test.js
- frontend/tests/driverDashboardView.test.js
- frontend/tests/fixtures/driverDashboardFixtures.js

Frontend extended: App.jsx, NotificationProvider.jsx, notification.js and existing customer/notification view tests to assert the now-real Driver routes/provider support. Existing role guards/redirects, auth flows and other dashboard designs were not changed. Documentation includes this report and a resolution note on the earlier missing-foundation audit.

## Verification
- Verified-test-DB targeted driver API/service tests: 19 passed.
- Verified-test-DB combined driver/security/real MySQL concurrency tests: 22 passed, 0 failed/skipped.
- Full backend regression: 747 passed, 0 failed/skipped, 156.89 seconds. One existing tampered-token short HMAC-key warning remains.
- Targeted Driver frontend, existing Customer and notification views: 47 passed, 0 failed/skipped.
- Full frontend via npm run test -- --test-concurrency=1: 448 passed, 0 failed/skipped, 65.91 seconds. Includes existing auth, Customer, Shop Owner and notification workflows.
- Targeted ESLint on new/changed Driver/integration/test files: passed. npm run lint still reports the pre-existing 8 errors/1 warning in unchanged ShopOwnerCustomers.jsx, ShopOwnerDashboard.jsx and repayments.test.js.
- npm run build: passed, 2,182 modules transformed. The existing large JavaScript chunk warning remains.
- AST syntax check: 55 backend application files passed. git diff --check passed.
- The old local Uvicorn process initially served the prior route list. Its project path, port listener and process tree were verified before restarting only that backend tree. Fresh live OpenAPI now lists exactly the three new Driver GET paths; anonymous requests to each return 401. /driver/dashboard returns the Vite SPA shell successfully.

Tests include required JWT claims/expiry, incorrect roles, inactive Users, profile review/vehicle/eligibility, no public mutations/self-approval, real counts, business filtering, A/B scope, preview pagination, ownership and lifecycle, no GET mutation SQL, sanitized failures, real independent-transaction races, frontend partial failure, stale generations, driver switching, loading/zero/empty distinctions and real navigation. No development fixtures or production mock data were used.

## Limitations and Step 12.3 readiness
No browser/native surface was connected, so screenshots/interactive checks at 1536, 1366, 1024, 768 and 375 px, actual horizontal overflow, focus traversal and mobile dialog behavior were not performed. Responsive markup/classes and protected React rendering are tested; that is not claimed as visual browser verification.

Profile provisioning/review and delivery creation currently exist only as privileged/internal service functions. New Driver Users legitimately see not_submitted/no vehicle/zero available jobs until authorized records are provided. No public onboarding, admin review screen or development seed was fabricated to make the dashboard look populated.

Ready for Step 12.3 to expose a properly authorized acceptance API/UI around the tested locked service and define its explicit contract. Delivery creation/admin onboarding UI, full delivery history/detail pages, status-update UI, reassignment, notification events and operations for suspended assignments are separate future work. No backend dependency blocks the implemented read-only Driver Dashboard.
