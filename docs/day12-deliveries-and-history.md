# Day 12 Step 12.4 — My Deliveries, progress and history

> Current checkpoint: [Step 12.5 final regression, security review and Git checkpoint](day12-final-regression-security-review.md). The results and stopped-server state below are the Step 12.4 snapshot; the user subsequently requested and received running development servers.

## Audit of Steps 12.1–12.3

Verified the current working tree before implementation. Driver models, the additive foundation migration, JWT Driver router, approval policy, dashboard, Available Jobs, and secure acceptance are present. Acceptance writes one `DeliveryAssignment` for the authenticated eligible Driver and changes the business-owned request to `assigned`. A unique request constraint and current locking reads prevent competing assignments. The existing lifecycle already requires `assigned → picked_up → in_transit → delivered`; terminal states cannot reactivate.

Previously, `/driver/deliveries` was a paginated active preview, assigned details contained only operational areas/reference/shop/status/assignment date, progress transitions were internal service operations, and Delivery History was disabled. No progress event model, public progress endpoint, addresses, customer contacts, per-job vehicle requirements, instructions or settlement model existed. Existing uncommitted changes from earlier steps were preserved. No commits or pushes were made.

## Implemented routes

All frontend pages use the existing Driver layout, JWT session, role guard, typography and LankaPex palette:

- `/driver/deliveries`: My Deliveries, active filters, ten rows per page, deterministic pagination, details/next-action links.
- `/driver/deliveries/:deliveryId`: authorized details, recorded timeline, pickup/transit/completion controls and explicit completion confirmation.
- `/driver/history`: delivered/cancelled filters and pagination, with recorded final dates or “Date not recorded”.

Sidebar links are enabled for My Deliveries and Delivery History. Dashboard and job-acceptance success link to My Deliveries. Existing Dashboard, Available Jobs, Notifications, Profile anchor and role redirects remain supported. Settings remains disabled because no route exists.

The actual FastAPI prefix is `/api/v1`:

| Method | Endpoint | Contract |
| --- | --- | --- |
| GET | `/api/v1/driver/deliveries` | Existing active list, now optional `status=assigned|picked_up|in_transit`; `page` and `page_size` |
| GET | `/api/v1/driver/history` | Own final assignments; optional `status=delivered|cancelled`; `page` and `page_size` |
| GET | `/api/v1/driver/deliveries/{delivery_request_id}` | Existing own-assignment details, extended with recorded `events` and `allowed_next_status` |
| POST | `/api/v1/driver/deliveries/{delivery_request_id}/status` | New guarded transition with `expected_status` and `status`; returns confirmed extended details |
| GET | `/api/v1/driver/profile` | Reused eligibility and stored vehicle information |
| GET | `/api/v1/driver/dashboard/summary` | Reused actual active/completed counts, refreshed after confirmed updates |

IDs are delivery-request IDs, not assignment IDs. List page size is bounded to 1–100, page to 1–1,000,000; the dashboard retains its default five-row preview and the new pages request ten. Lists sort by assignment date descending, then unique assignment ID descending. Out-of-range pages are empty and retain pagination controls. Reads and mutations return `Cache-Control: no-store`.

Illustrative response shape (values shown only to explain the contract, never seeded into development data):

```json
{
  "driver_user_id": 7,
  "total": 1,
  "page": 1,
  "page_size": 10,
  "deliveries": [{
    "delivery_request_id": 31,
    "reference": "DR-example",
    "business_name": "Example shop",
    "pickup_area": "Pickup area",
    "delivery_area": "Destination area",
    "status": "assigned",
    "assigned_at": "2026-11-06T10:00:00",
    "finished_at": null
  }]
}
```

Details return `{driver_user_id, assignment_id, delivery, events, allowed_next_status}`. `delivery` has the same operational fields as above except `finished_at`; `events` is an array of `{status, occurred_at}`. The next status is `picked_up`, `in_transit`, `delivered`, or `null` for terminal/ineligible Drivers. Timestamps follow the existing naive UTC storage convention and are labelled UTC in the UI.

```json
{"expected_status":"assigned","status":"picked_up"}
```

An update must match both the current status and a permitted next transition. Public actions cannot assign, cancel, skip pickup/transit, supply another Driver identity or change approval. Extra body fields are rejected. A duplicate completion returns 409 and never creates another event.

## Persistence and authorization

`DeliveryRequest`, `DeliveryAssignment` and `DriverProfile` are reused. New `DeliveryStatusEvent` stores request ID, authenticated actor ID, status and actual UTC occurrence date. Assignment events use the existing `DeliveryAssignment.assigned_at`. Progress and existing internal cancellation services insert an event in the same transaction as the status change. Events have foreign keys, a status constraint and uniqueness on `(delivery_request_id, status)`.

Migration `a7b3c6d5e015_add_delivery_status_events.py` follows `f6a2b5c4d904`. It only creates the event table; no data backfill, reset, dropped tables, altered credit records, seed deliveries or automatic approvals. Downgrade refuses audit destruction. Applied first to verified `lankapex_test_db`, then to development `lankapex_db` after independently checking the effective database name and exact prior revision. Development schema is ready for the next server start; development servers remain stopped.

JWT signature/expiry, active account and Driver role are enforced by existing dependencies. All assignment reads filter on the authenticated user ID. Other Driver and nonexistent IDs return a generic 404. An active but approval-revoked Driver can still read their own records, while updates require an approved profile and stored vehicle pair. The frontend also suppresses controls when eligibility cannot be confirmed; backend authorization remains authoritative.

Writes revalidate current account/profile under shared locks, then lock the delivery and assignment in the existing order. MySQL current reads refresh previously loaded entities after waiting on locks. The locked status must match `expected_status`, and the lifecycle must allow the requested status. Event insertion, response validation and commit are one transaction; HTTP/database failures roll back. Integrity conflicts return 409; other SQL errors return a sanitized 503. Business cancellation retains its existing ownership and lifecycle checks and records a cancellation event.

Frontend mutations are single-flight, wait for validated server confirmation, and refresh delivery details and dashboard counts. Completion asks for confirmation. A timeout, malformed response or conflict clears actionable detail and requests a refresh instead of claiming success. Expected-state checks protect retries against stale state. Abort controllers, request versions and session-specific component keys prevent previous requests/accounts from repopulating a later view.

## Files changed for Step 12.4

New:

- `backend/alembic/versions/a7b3c6d5e015_add_delivery_status_events.py`
- `backend/tests/test_driver_deliveries.py`
- `backend/tests/test_driver_deliveries_concurrency.py`
- `frontend/src/services/driverDeliveriesService.js`
- `frontend/src/utils/driverDeliveries.js`
- `frontend/src/pages/driver/DriverDeliveries.jsx`
- `frontend/tests/driverDeliveries.test.js`
- `frontend/tests/driverDeliveriesView.test.js`
- This report.

Updated:

- `backend/app/models/delivery.py`, `backend/app/models/__init__.py`
- `backend/app/schemas/driver.py`, `backend/app/services/driver_service.py`, `backend/app/routers/driver.py`
- `backend/tests/test_driver_dashboard.py`, `backend/tests/test_driver_jobs.py`, `backend/tests/test_driver_concurrency.py` (evolved endpoint expectations and exact-fixture audit-event cleanup)
- `frontend/src/App.jsx`, `frontend/src/layouts/DriverLayout.jsx`, `frontend/src/components/driver/DriverSidebar.jsx`
- `frontend/src/pages/driver/DriverDashboard.jsx`, `frontend/src/pages/driver/AvailableJobs.jsx`
- `frontend/tests/driverDashboardView.test.js`, `frontend/tests/driverJobsView.test.js` (new navigation expectations)

## Validation

Test database safety: configuration, SQLAlchemy engine database and `SELECT DATABASE()` all verified as exactly `lankapex_test_db` before migrations/tests. Existing pytest session guard performs this check before collection. Rollback fixtures isolate HTTP tests; concurrency tests use separately committed unique fixtures and exact-ID cleanup only on the verified test database.

- Final new delivery-management backend tests: **20 passed, 0 failed, 0 skipped**. Includes real HTTP ownership/lifecycle/history, pagination, eligibility/JWT, atomic rollback, unchanged stored credit/ledger rows, and independent MySQL pickup/completion races. The initial broader Driver run passed 63 tests and found one obsolete assertion that the now-supported status route should be absent; that assertion was updated and passes in the full suite.
- Final combined Driver backend regression (all six Driver test modules): **67 passed, 0 failed, 0 skipped**, 11.54 seconds.
- Full backend: **789 passed, 0 failed, 0 skipped**, 539.78 seconds. One existing warning comes from the deliberately short key in the JWT tampering test. Three additional cases were added after full-suite collection (expired/inactive sessions, missing vehicle, concurrent completion) and are included in the final 20-test targeted run.
- New frontend workflow/view tests: **21 passed, 0 failed, 0 skipped**.
- Full frontend: **495 passed, 0 failed, 0 skipped**.
- After the final sidebar active-state refinement, Dashboard/Available Jobs view and navigation tests were rerun: **19 passed, 0 failed, 0 skipped**; production build and changed-source lint passed again.
- `npm run build`: passed, 2,188 modules; existing large-bundle warning remains.
- ESLint on all changed frontend source files: passed. Full-project lint: **8 existing errors and 1 warning** in `ShopOwnerCustomers.jsx`, `ShopOwnerDashboard.jsx` and `tests/repayments.test.js`; unrelated files were preserved. No typecheck script is configured.
- Headless Chrome using the production build: My Deliveries, Delivery Details and empty History checked at **1536, 1366, 1024, 768 and 375 pixels**; all 15 checks passed with no document horizontal overflow. Screenshots captured and desktop/mobile output inspected.
- Browser interaction: pickup, transit, completion prompt, cancel prompt without mutation, confirmed completion, refreshed active/completed counts and populated history all passed. Exactly three mutation requests occurred.
- Browser checks were repeated successfully against the final production build. An intermediate rerun caught a QA-runner race reading a newly navigated document before its body existed; the local runner now waits for the body, and all final checks pass.
- `git diff --check`: passed. Final listener check confirmed ports 5173, 8000, 5187 and 9237 are closed.

Browser verification uses isolated browser-only API fixtures; it is not a claim that a real customer delivery was driven through the UI against MySQL. Backend HTTP tests independently exercise real JWTs, ownership, MySQL transactions, actual events and concurrent requests. No production mocks are imported by the application. Temporary browser/static-server processes were closed; the user's development servers remain stopped.

Local QA artifacts are ignored under `.server-logs/day12-deliveries-browser/`, including 15 screenshots and `results.json`; the local runner is `.server-logs/day12-deliveries-browser.mjs`.

## Limitations and Step 12.5 readiness

Older pickup/transit/final event dates cannot be recovered. No historical events are inferred from status or `updated_at`; legacy terminal rows display no recorded completion/cancellation date. Assignment date remains available from the existing assignment record.

The current model stores areas rather than precise addresses or contacts. The UI explicitly states those fields, operational instructions and per-job vehicle requirements are not stored. It does not expose customer credit information, invent earnings, change balances, introduce GPS/payments/ordering, or auto-approve Drivers.

Step 12.5 can use the real delivery-management workflow and additive event history. No backend dependency remains blocked for this scope. Outstanding project-wide issues are the existing unrelated lint failures and bundle-size warning.
