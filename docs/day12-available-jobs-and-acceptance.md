# Day 12 Step 12.3 - Available Delivery Jobs and Secure Acceptance

> Current checkpoint: [Step 12.5 final regression, security review and Git checkpoint](day12-final-regression-security-review.md). The results below are the Step 12.3 snapshot.

## Audit and scope
Steps 12.1 and 12.2 are implemented in this working tree: DriverProfile, DeliveryRequest, DeliveryAssignment, revision f6a2b5c4d904, Driver read APIs, locked assignment/lifecycle services, real Driver Dashboard, shared layout/sidebar and tests. The role value is driver. Public available-job/detail/accept APIs and their frontend workflow were missing.

The existing assignment service already locks the active Driver User, approved profile and target request, rechecks current assignment/business state and inserts one unique assignment atomically. It is reused, not replaced. No model/migration change is necessary for Step 12.3. Existing unrelated .gitignore edits and uncommitted Steps 12.1/12.2 work are preserved. No commit/push or database reset was performed.

## Backend API contract
All paths below have the actual /api/v1 prefix. Driver JWT and active User are required. Available list/detail and acceptance additionally require approved DriverProfile plus both stored vehicle fields. All successful financial-independent delivery responses use Cache-Control: no-store.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | /driver/jobs?page=1&page_size=10 | Eligible-driver available requests; count plus bounded jobs list |
| GET | /driver/jobs/{job_id} | Eligible-driver pre-acceptance details for a currently available request |
| POST | /driver/jobs/{job_id}/accept | Atomic acceptance, empty JSON body {}, confirmation only after commit |
| GET | /driver/deliveries/{job_id} | Exact authenticated Driver's assigned operational details, including terminal status |
| GET | /driver/profile | Existing profile and eligibility rules |
| GET | /driver/dashboard/summary | Existing authoritative available/active/completed counts |
| GET | /driver/deliveries?page=1&page_size=5 | Existing bounded My Deliveries preview |

Page bounds remain 1-1,000,000; page_size 1-100. Job path IDs must be positive signed BIGINT values. An acceptance body containing driver_id, status or any other extra property is rejected with 422. Caller identity query parameters never override JWT identity.

### Available list/detail examples
These are illustrative response shapes, not production fixtures or created jobs.
~~~json
{
  "driver_user_id": 7,
  "total": 1,
  "page": 1,
  "page_size": 10,
  "jobs": [{
    "delivery_request_id": 31,
    "reference": "DR-server-generated-reference",
    "business_name": "Requesting business display name",
    "pickup_area": "Stored pickup area",
    "delivery_area": "Stored destination area",
    "status": "available",
    "created_at": "2026-11-06T10:00:00"
  }]
}
~~~
Detail returns {driver_user_id, job} with the same documented job fields. Jobs sort by created_at descending then delivery_request_id descending. Availability requires available status, approved business and no assignment record. Assigned, cancelled, delivered, non-approved-business and inconsistent already-assigned requests are excluded. Foreign/unavailable/nonexistent available-detail requests share 404 Available delivery not found.

### Acceptance and own assignment example
~~~json
{
  "driver_user_id": 7,
  "assignment_id": 101,
  "delivery": {
    "delivery_request_id": 31,
    "reference": "DR-server-generated-reference",
    "business_name": "Requesting business display name",
    "pickup_area": "Stored pickup area",
    "delivery_area": "Stored destination area",
    "status": "assigned",
    "assigned_at": "2026-11-06T10:30:00"
  }
}
~~~
POST returns 200 for a newly committed assignment and for an idempotent retry by the same eligible Driver while their assignment remains active. Replays retain the existing assignment_id/assigned_at and do not create another record. Cancelled/delivered requests cannot be accepted again. A second Driver receives safe 409 Delivery is no longer available. Unknown request IDs use 404. No arbitrary status updates, pickup/transit/completion APIs or request-creation UI were added.

The own-assignment GET uses {driver_user_id, assignment_id, delivery}, scoped by DeliveryAssignment.driver_user_id from JWT. It permits assigned, picked_up, in_transit, delivered and cancelled status on that Driver's existing record. Foreign/unknown records share 404 Assigned delivery not found. Existing profile eligibility can be revoked while own records remain readable to an active authenticated Driver; acceptance permissions do not remain.

## Concurrency and rollback
The HTTP handler invokes the existing locked service, builds and validates the authorized response, and commits before returning success. Any HTTP rejection rolls back. Integrity conflicts roll back with safe 409; database failures roll back with safe 503 confirmation guidance and no raw diagnostic.

MySQL REPEATABLE READ requires care after waiting on the delivery lock. The assignment service already uses a current locking read to see the winner's assignment. The acceptance response now also uses an explicitly current locking read; an ordinary detail SELECT could otherwise retain an earlier snapshot and miss a concurrent same-Driver assignment. This response query is used only inside the acceptance transaction; ordinary GET details do not add mutation locks.

The request row lock serializes competing acceptance/status operations. The unique delivery_request_id constraint is an additional invariant. The original requesting business, creator/reference, assignment time and existing lifecycle are preserved. No server-side progress transition implementation changed in this step; public progress/status API/UI remains deferred to Step 12.4.

A lost connection during commit can leave the client uncertain even if the server committed. No failure response is used as proof of non-assignment. Retrying this same job is safe through the documented same-Driver policy; the scoped assignment GET can independently confirm the current record.

## Vehicle eligibility, fees and privacy
Supported checks are active Driver User, explicitly approved DriverProfile and stored nonempty vehicle_type/registration_reference. The existing request model has no required vehicle type, capacity, vehicle-specific approval, fee, earnings, distance or estimated-time field. Therefore no per-job vehicle/capacity matching or price is claimed or invented. No new category/unit/fee migration was added. Those fields are not in the API contract and are not rendered from untrusted extra payload properties.

Pre-acceptance output contains only business display name, reference, pickup/destination areas, availability and creation time. It does not query/expose customer credit data, full customer addresses, phone numbers, private instructions, staff fields or profile review notes. Operational details are also scoped to the assigned Driver. Customer, Shop Owner and Admin identities cannot use these ordinary Driver endpoints or impersonate a Driver.

## Frontend route and details
/driver/jobs renders Available Delivery Jobs within the existing DriverLayout and Driver-only ProtectedRoute. DriverSidebar now enables its real Available Jobs link; the Dashboard links to it. Other role navigation/designs are unchanged. My Deliveries remains the existing /driver/dashboard#active-deliveries destination, refreshed on dashboard remount.

The page provides actual available count, actual active-delivery count, paginated cards, business/reference/areas/creation time, View Details and Accept Job. Details are a labeled inline section fetched from the authorized detail endpoint, with close/retry controls. No unsupported fee/vehicle requirement/map/distance/earnings field is displayed. Layout, palette, logo, typography, focus patterns and responsive wrapping follow the existing Driver design.

Profile eligibility is fetched first. Pending/rejected/suspended/missing-profile/vehicle-incomplete Drivers see their actual profile reason and do not dispatch available-job requests or see acceptance controls. Backend checks remain mandatory even if client eligibility was loaded before a later suspension.

## Frontend acceptance workflow
- A synchronous controller lock prevents duplicate submissions, independently of disabled buttons.
- No optimistic assignment or success message is published. The response must match current driver_user_id, requested job, assignment ID, actual fields and active status.
- Confirmed success clears stale details and refreshes the available page, Driver summary and bounded My Deliveries preview through authenticated GETs. The confirmation links to the real My Deliveries destination; navigating there mounts fresh Dashboard readers.
- 404/409/422 acceptance rejection shows safe unavailable/rejected feedback and refreshes availability/counts without claiming success.
- Timeout/network/503/malformed acceptance response keeps an uncertain same-job state, blocks acceptance of other jobs and page changes, and offers Retry this job acceptance or Check my assignment.
- A scoped assignment check can confirm active or terminal owned records. A 404 check stays uncertain because the original POST might still be processing; it is not treated as proof that acceptance failed.
- 401/403 clears every job/detail/confirmation resource and uses centralized auth handling. Partial read failures retain other successful sections and offer safe retry.
- Page/detail replacement, refresh, disposal and session changes abort requests and invalidate late generations. State is keyed by authenticated User/session and held only in memory. No duplicate token store, ledger/financial cache, production mock or polling workflow was introduced.

## Files
Backend modified: app/routers/driver.py, app/schemas/driver.py and app/services/driver_service.py.
Backend tests added: backend/tests/test_driver_jobs.py and backend/tests/test_driver_jobs_concurrency.py.
Frontend added: src/services/driverJobsService.js, src/utils/driverJobs.js, src/pages/driver/AvailableJobs.jsx; tests/driverJobs.test.js, tests/driverJobsView.test.js and tests/fixtures/driverJobsFixtures.js.
Frontend modified: App.jsx, DriverSidebar.jsx, DriverLayout.jsx, DriverDashboard.jsx and driverDashboardView.test.js for the functional navigation/route expectation.
Documentation: this report; earlier Step 12.1/12.2 report links here as the superseding acceptance contract.

## Test database and results
Every backend test process sets MYSQL_DATABASE=lankapex_test_db before importing app configuration, verifies configured/engine names and actual SELECT DATABASE(), and keeps existing guards/fixtures. No automated mutations were run on lankapex_db. Real HTTP concurrency tests use independent MySQL request sessions and fixture-owned rows; they wait for both requests at the real request row lock before releasing it. No schema changes or development fake records were needed for this step.

- Targeted backend (new jobs/HTTP races plus existing Driver security/lifecycle races): 47 passed, 0 failed/skipped.
- Full backend: 772 passed, 0 failed/skipped, 297.39 seconds. Existing short-key tampered-token test warning remains.
- Targeted frontend (jobs workflow/views and existing Driver Dashboard): 35 passed, 0 failed/skipped.
- Full frontend via npm run test -- --test-concurrency=1: 474 passed, 0 failed/skipped, 78.28 seconds.
- npm run build: passed, 2,185 modules transformed; existing large JavaScript bundle warning remains.
- Targeted changed Driver source/test ESLint: passed. Full npm run lint still reports 8 pre-existing errors and 1 warning in unchanged ShopOwnerCustomers.jsx, ShopOwnerDashboard.jsx and repayments.test.js.
- Backend AST syntax check: 55 application files passed. git diff --check passed; index remains empty.
- The local backend still served the prior route snapshot despite its reload watcher. Its exact project process tree was verified and restarted. Fresh live OpenAPI lists the new GET list/detail, POST accept and assigned-detail paths; anonymous job/assigned-detail GETs return 401. The Available Jobs Vite SPA shell returns 200. No development job was created or accepted for this smoke check.

Coverage includes available/empty/order/page behavior; cancelled/completed/assigned/unapproved-business exclusion; approved/pending/rejected/suspended/vehicle-incomplete/inactive identity; JWT/role/expiry; safe details/field projection; request-ID/body validation; JWT identity overriding caller hints; correct assignment/status; duplicate same-Driver acceptance; second-Driver conflict; commit-failure rollback; concurrent different-Driver and same-Driver public HTTP acceptance; confirmation/refresh/duplicate click behavior; uncertain retries/checks; stale/foreign responses and preserved existing workflows.

## Browser limits and readiness
No browser/native surface was connected. React server-rendered views, guards, workflow/service contracts and responsive classes are tested. Interactive desktop/mobile flows and actual layout measurements at 1536, 1366, 1024, 768 and 375 pixels were not performed and are not claimed.

Step 12.3 is implemented with secure assignment, passing targeted/full tests and a passing production build. No per-job vehicle matching or fees are supported by the existing model. Profile provisioning/review and business delivery creation remain internal privileged services from Step 12.1, not public self-approval/request-creation features. No production deliveries or approvals were fabricated to populate the screen.

Ready for Step 12.4 planning around the existing lifecycle, subject to the documented browser verification limit. No public pickup/transit/completion flow, GPS, maps, earnings, order/shopping or payment feature was added. No commit or push.
