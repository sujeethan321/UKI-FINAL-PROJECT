# Day 13 Shop Owner Delivery Management test execution

Executed 2026-11-08 (Asia/Colombo). **64 backend tests and 65 frontend tests
passed, zero failed or skipped.** No application defect was reproduced and no
application/UI code was changed. Three targeted regressions were added to close
coverage gaps. Automated API/controller/view verification passed; manual browser
verification was **NOT RUN**.

## Environment and safety

Before any test writes, a separate connection asserted all of:
`APP_ENV=testing`, `MYSQL_DATABASE=lankapex_test_db`, engine database
`lankapex_test_db`, a local engine host, and actual `SELECT DATABASE()` equal to
`lankapex_test_db`. Actual test Alembic revision: `03b9c2d1e671`.
`backend/tests/conftest.py` repeats configured/connected database checks before
each pytest session. Existing rollback fixtures and independent-transaction
concurrency fixtures with exact synthetic-row cleanup were reused.

JWT and stored-role authorization remain enabled. Ordinary HTTP tests substitute
the database session with an isolated transaction, not the authenticated identity.
Concurrency tests use independent real MySQL transactions and the actual HTTP
app without dependency overrides. Synthetic JWTs reference synthetic stored
users; interactive login/browser authentication was not exercised by this run.

No development database writes, resets, migrations, balance repair, deployment,
push or AI Summary work occurred. A synthetic financial snapshot test verified
delivery create/cancel leaves its credit account, ledger, reminder and existing
notification rows unchanged. Existing unrelated workspace changes were preserved.

## D13-T01 — Create delivery request: PASS

**Expected:** an active Shop Owner with an approved business and active owner
membership can submit supported details. Persisted requests belong to that
business and creator, initially available/unassigned. Invalid or privileged
inputs must be rejected and SQL failures must not leave partial writes.

**Actual:** authenticated POST returned **201**, `Cache-Control: no-store`,
trimmed pickup/destination areas, unique reference, correct business/creator,
`status=available`, no assigned driver and no progress events. Follow-up detail
GET returned **200** with the same data. Boundary-length and Unicode area values
were preserved. Empty/missing/oversized/control-character/wrong-type inputs,
invalid identifiers and unsupported identity/status/order/vehicle/idempotency
fields returned **422** without unintended inserts. Unapproved businesses
returned **403**. Simulated commit failure returned sanitized **503** with rollback.

The inspected actual form is
`frontend/src/pages/shopOwner/ShopOwnerDeliveries.jsx`: required `pickup_area`
and `delivery_area`, max length 160, area-only guidance, submission/loading
guards. `frontend/src/services/shopOwnerDeliveryService.js` sends these fields
with a query-selected business through the shared JWT Axios client. Frontend
tests verified form/controller behavior and the actual service contract; this
does not claim manual form submission in a browser.

**Failure root cause:** none reproduced.

## D13-T02 — View and track delivery requests: PASS

**Expected:** owners see only their selected business's requests, stable
pagination/filter totals and accurate persisted progress after driver acceptance
and valid updates. Empty/missing records must be handled accurately.

**Actual:** list/detail/summary GET returned **200**. Empty/out-of-range pages
returned empty collections, deterministic timestamp/ID ordering and page/status
filters passed, and summary totals were independent of pagination. Initial
requests were available. Driver acceptance through
`POST /api/v1/driver/jobs/{id}/accept` returned **200**, removed the job from the
available Driver list, and exposed assigned status, operational Driver name and
assignment time to the owner without email/phone/reviewer/registration/financial
fields. The new HTTP regression advanced
`assigned -> picked_up -> in_transit -> delivered`, receiving **200** at each
step. After expiring ORM state, owner detail and filtered-list GETs returned
the persisted current status and ordered events; the persisted request agreed.
This is database/API reload verification, not a browser reload claim.

Missing valid IDs returned **404**; malformed/out-of-bounds IDs and unsupported
status values returned **422**. Unsupported PUT/PATCH editing returned **405**.
Read operations emitted no DML; simulated read failures returned sanitized
**503**. Driver timeline notification/rollback assertions also passed.

**Failure root cause:** none reproduced.

## D13-T03 — Duplicate prevention and authorization: PASS under existing rules

**Expected:** backend role and object authorization isolate separate owners and
businesses. Existing duplicate/cancellation/acceptance policies must survive
retries and concurrent requests without inconsistent assignment or events.

**Actual:** two synthetic owners, each with an approved business and their own
request, could list their own data (**200**). In both directions, foreign
business selection and foreign request IDs were denied (**404**), including
read/cancel and create against an unowned business. Foreign-detail responses
matched nonexistent-detail responses for the same selected business. Both
requests remained available after denied modifications. Inactive/staff/foreign
memberships were denied (**404**). Customer/Driver/Admin roles received **403**
on Shop Owner-only endpoints; missing/invalid/expired JWT received **401**;
suspended accounts **403**. Summary role/business isolation also passed.

Only available, unassigned requests may be cancelled. Assigned, picked-up,
in-transit and delivered cancellation attempts returned **409**. Cancellation
retry returned the original **200** result without changing its event/timestamp.
Invalid Driver transitions remain guarded by the existing Driver implementation;
concurrent status/security regressions were included to preserve it.

Concurrent acceptance versus cancellation was executed three times: exactly one
**200** and one **409**, with either one assignment or one cancellation event,
never both. Concurrent cancellation retries returned **200/200** with identical
results and one event. Competing drivers produced **200/409**; same-driver
acceptance retries returned **200/200** with one assignment.

**Duplicate-create limitation:** the current POST has no server idempotency key
or content deduplication contract. The new regression confirms two identical
valid POSTs return **201/201** with distinct IDs/references and two requests;
an `idempotency_key` body field is unsupported (**422**). Frontend tests confirm
duplicate clicks share one mutation, and uncertain creation blocks automatic
resubmission until list review and explicit acknowledgement. Passing this case
does **not** certify backend duplicate-create suppression or concurrent-create
deduplication; concurrency tests exercised acceptance/status/cancellation.
No change was made to this existing business rule. If server-side exactly-once
creation is required, that remains an additional product requirement.

**Failure root cause:** none reproduced against the current contract; no
cross-business disclosure or unauthorized state change was confirmed.

## Implementation inspected

- `backend/app/routers/shop_owner_deliveries.py`: authenticated stored Shop Owner
  role; business ID selection, bounded pagination, typed status filters,
  sanitized read/write failures and transactional rollback.
- `backend/app/services/shop_owner_delivery_service.py`: approved requesting
  business and active owner membership, business-scoped request lookup,
  minimal Driver projection, stable pages, summary and locked cancellation.
- `backend/app/services/driver_service.py`: existing request creation, eligible
  acceptance and lifecycle locking used by Shop Owner operations.
- `backend/app/schemas/shop_owner_delivery.py`: only area fields on creation,
  extra fields forbidden; six actual statuses and minimal projections.
- `backend/app/models/delivery.py`: business/creator foreign keys, unique request
  reference, unique request assignment and unique per-status event.
- Frontend: `ShopOwnerDeliveries.jsx`, `shopOwnerDeliveryService.js`,
  `utils/shopOwnerDeliveries.js`, shared timeline/service contract tests.

Actual Shop Owner routes, prefixed `/api/v1/shop-owner/deliveries`:

| Method | Suffix | Selection/body |
| --- | --- | --- |
| POST | empty | business_id query; pickup_area, delivery_area body |
| GET | empty | business_id; optional page, page_size, status |
| GET | /summary | business_id |
| GET | /{request_id} | business_id |
| POST | /{request_id}/cancel | business_id; empty object body |

## Automated execution

Ran sequentially from `backend` with explicit testing variables:
`.venv/Scripts/python.exe -m pytest <selection> -v`, using a separate
`--basetemp=../.server-logs/day13-T0N-tmp` for each group.
Groups overlap case requirements: the creation test file also covers substantial
T02/T03 behavior; counts below describe execution groups, not exclusive cases.

| Group | Selection under backend/tests | Actual result |
| --- | --- | --- |
| T01 | test_shop_owner_deliveries.py | 37 passed, 7.80s |
| T02 | test_shop_owner_delivery_summary.py; test_day13_delivery_workflows.py::test_owner_tracks_driver_http_progress_after_database_reload; test_delivery_notifications.py | 7 passed, 8.69s |
| T03 | test_shop_owner_deliveries_concurrency.py; test_day13_delivery_workflows.py::test_two_owners_with_separate_businesses_cannot_access_each_others_requests; test_day13_delivery_workflows.py::test_repeated_create_is_distinct_requests_not_an_idempotent_operation; test_driver_jobs_concurrency.py; test_driver_deliveries_concurrency.py; test_driver_security_review.py; test_delivery_final_review.py | 20 passed, 7.53s |

From `frontend`, ran `node --test` with `tests/shopOwnerDeliveries.test.js`,
`tests/shopOwnerDeliveriesView.test.js`, `tests/deliveryTracking.test.js`,
`tests/driverJobs.test.js`, `tests/driverDeliveries.test.js`.
**65 passed, 0 failed/skipped**, 6.54s. These include API parsing, required field
validation, mutation concurrency/uncertainty, refresh/tracking, safe errors and
rendered empty/loading/authorization states. No production mock data was added.

Ignored execution logs: `.server-logs/day13-T01.log`, `day13-T02.log`,
`day13-T03.log`, `day13-frontend.log`. Each backend group emitted the pre-existing
PytestCacheWarning for the Windows `.pytest_cache/v/cache/nodeids` path conflict;
it did not prevent collection/execution. No full-project suite or complete Day12
rerun is claimed; selected Driver regression coverage passed.

## Exact changes and remaining blockers

Created only:

- `backend/tests/test_day13_delivery_workflows.py`: three tests for HTTP progress
  after database reload, bidirectional two-owner/two-business isolation, and
  repeated-create semantics.
- `docs/day13-delivery-test-execution.md`: this report.

No isolated Day13 execution blocker was encountered. Manual browser verification
remains unexecuted. The previously documented development schema/Admin approval
dependency is separate: same-day read-only investigation reported revision
`b8c4d7e6f126` and missing Admin/order/catalogue tables. This task did not recheck
or modify development or claim operational approval readiness. See
`docs/admin-dashboard-schema-investigation.md`. Fresh isolated migration-chain
execution verification remains **BLOCKED**, awaiting the separately documented
DBA database creation/access in `docs/day17-database-operations.md`. Test-schema
success does not resolve that blocker.
