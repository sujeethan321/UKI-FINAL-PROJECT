# Day 13 Step 13.1 — Shop Owner Delivery Request Backend Foundation

> Day 13 final verification and local checkpoint: [Step 13.5 report](day13-final-regression-security-review.md).

> Step 13.2 now adds the Shop Owner Delivery Management frontend and a tested, business-scoped `GET /api/v1/shop-owner/deliveries/summary` read endpoint for authoritative counts. See [the frontend contract and verification report](day13-shop-owner-delivery-frontend.md). The four-operation contract below is the Step 13.1 foundation snapshot.

## Repository audit and Day 12 dependencies

Verified branch `main`, HEAD `c7e50c6` — `Day 12: complete driver delivery workflows and regression verification`. Day 12's committed report records 799 passing backend tests, the complete passing single-worker frontend run and browser verification; the models, services, router, migrations and tests are present. The only initial working-tree change was the unrelated `.gitignore` edit, which is preserved. This step does not commit or push.

Day 12 already provides DriverProfile, DeliveryRequest, DeliveryAssignment and DeliveryStatusEvent, registered `/api/v1/driver` APIs, active-account/JWT/Driver enforcement, approval/vehicle eligibility, unique assignment, current locking reads, lifecycle transitions and atomic status events. Requests belong to `business_id` and do not require customer/order records. Existing initial status is `available`; no draft state exists.

Before this step, Shop Owner creation/cancellation existed only as internal Day 12 services. The Shop Owner API selects an authorized business using the required `business_id` query parameter; existing business selection and access restrict membership to an active `owner` of an approved business. That policy is preserved, not expanded to arbitrary staff roles.

The existing internal cancellation service permits available/assigned cancellation. The new public request-management API deliberately supports **only available requests with no assignment**, deferring assigned cancellation rather than releasing a Driver's job. Existing internal behavior and Driver APIs are unchanged.

## Implemented files

Created:

- `backend/app/schemas/shop_owner_delivery.py`
- `backend/app/services/shop_owner_delivery_service.py`
- `backend/app/routers/shop_owner_deliveries.py`
- `backend/tests/test_shop_owner_deliveries.py`
- `backend/tests/test_shop_owner_deliveries_concurrency.py`
- This report.

Modified: `backend/app/main.py`, only to register the new Shop Owner delivery router under the existing `/api/v1` prefix.

No frontend, financial calculation, existing delivery model, notification model or migration file is modified. No new delivery system is created.

## Step 13.2 API contract

All requests require the existing Bearer JWT, active User, stored `shop_owner` role, active owner membership and an approved business. The selected business is required in the query string for every endpoint, is validated as a positive signed BIGINT, and is authorized server-side. It is forbidden in the body. Missing/foreign/inactive/non-owner membership returns a generic 404; unapproved business and inactive account/wrong role return 403; missing/expired/invalid JWT returns 401.

| Method | Actual path | Behavior |
| --- | --- | --- |
| POST | `/api/v1/shop-owner/deliveries?business_id={id}` | Create a new available request; 201 only after validated response and commit |
| GET | `/api/v1/shop-owner/deliveries?business_id={id}&page=1&page_size=10` | Own-business paginated summaries |
| GET | `/api/v1/shop-owner/deliveries/{request_id}?business_id={id}` | Own-business detail and recorded timeline |
| POST | `/api/v1/shop-owner/deliveries/{request_id}/cancel?business_id={id}` | Cancel an available unassigned request; empty `{}` JSON body |

List query `status` accepts the actual existing values: `available`, `assigned`, `picked_up`, `in_transit`, `delivered`, `cancelled`. Pagination: page 1–1,000,000 and page_size 1–100, default ten. Sorting: created_at descending, then unique delivery_request_id descending. Out-of-range pages return an empty list with the real total. There is no cross-business aggregate endpoint.

Successful responses have `Cache-Control: no-store`. Database errors return sanitized 503 responses; write conflicts return 409. Unknown or other-business delivery IDs return a generic 404 even when the caller owns the selected business. Query/path validation and forbidden/missing body fields return 422.

### Creation schema

`DeliveryRequestCreate` accepts only existing model fields:

```json
{
  "pickup_area": "Colombo district",
  "delivery_area": "Jaffna district"
}
```

Both fields are required strings, trimmed, nonblank, at most 160 characters after trimming. Embedded control characters are rejected. Unicode, ordinary punctuation and special characters are preserved as JSON text; they are never interpreted as SQL or HTML. The UI must render them as ordinary escaped React text.

The service obtains `created_by` from authenticated identity, authorizes the query-selected business, generates the existing `DR-...` reference, and sets `available` through Day 12's creation service. Body attempts to set business/creator/Driver identity, status, order_id or unmodeled fields are rejected. No order, customer, payment, ledger or notification record is created.

There are no stored package type/quantity/weight, description, vehicle requirement, private address/contact, order reference or instruction fields. They are **not silently accepted**, and no new required fields or vehicle enum is invented. Unsupported `required_vehicle_type`, including invalid types, is rejected as an extra field.

### Detail response

Illustrative shape only; no development fixtures were seeded:

```json
{
  "delivery_request_id": 31,
  "reference": "DR-example",
  "business_id": 4,
  "pickup_area": "Colombo district",
  "delivery_area": "Jaffna district",
  "status": "available",
  "created_at": "2026-11-06T10:00:00",
  "updated_at": "2026-11-06T10:00:00",
  "assigned_driver": null,
  "events": [],
  "can_cancel": true
}
```

List response is `{business_id,total,page,page_size,deliveries:[...]}`. Each summary contains the first eight fields above; assignment information/events/cancellation capability are provided only by detail responses.

After assignment, `assigned_driver` is `{full_name,assigned_at}`. No Driver email, phone, user ID, registration, review data or unrelated profile is exposed. `events` contains `{status,occurred_at}` for the genuine assignment timestamp and persisted progress/cancellation events. `can_cancel` is true only when status is available and there is no assignment.

The timestamps use Day 12's existing naive-UTC convention and MySQL DATETIME precision. Label them UTC. New requests use `created_at` as the recorded creation date; no synthetic available-event row is inserted. Old progress dates are never inferred from `updated_at` or current status.

## Cancellation, retry and editing rules

Cancellation locks and refreshes the business-owned request, then performs a current locking read of the assignment. It requires available status **and** no assignment. The existing Day 12 service writes `cancelled` and the actual event in the same transaction. A retry on an already cancelled request with no assignment returns the existing record without adding an event or changing its timestamp. Assigned, picked-up, in-transit or delivered requests return 409; historical assignments are not deleted or released.

Original cancellation responses and retries are read back at persisted database precision. Tests caught a fractional-second in-memory `updated_at` discrepancy on the first response; a current read now makes the original and replay exactly consistent with MySQL's stored seconds.

Creation **does not support idempotency keys** in the existing schema. Each intentional POST creates a new request. The API rejects an `idempotency_key` field rather than claiming retry protection. Step 13.2 must prevent duplicate clicks and must not automatically retry creation after timeout/503: first refresh the authorized list and let the owner verify whether the request was recorded. A 503 may be an uncertain result; the error message tells the caller to check the list. Durable keyed creation retries require a separately reviewed persistence change and are deferred.

No editing endpoint is exposed. PUT/PATCH are unsupported; pickup/drop-off details cannot silently change after acceptance. Assigned cancellation and generic status updates by Shop Owners remain deferred. The UI must refresh on a cancellation conflict and rely on the backend rather than stale `can_cancel` visibility.

## Driver integration and transactional authorization

Created requests use the same DeliveryRequest table, business relationship and available status queried by the existing Driver jobs API. Eligible Driver criteria remain approved profile plus the authenticated Driver's stored vehicle pair; per-job vehicle compatibility is not modeled. Unassigned available jobs from approved businesses are visible as safe area previews. Cancelled/assigned jobs are excluded. Acceptance uses the unchanged Day 12 assignment service and unique assignment constraint.

Ownership and approval are checked under current shared User/membership/business locks, followed by the exact business-owned request row and assignment locks for cancellation. Concurrent acceptance and cancellation serialize on the same request row: one succeeds, the other observes current state and returns 409. Concurrent cancellation retries return the same record and one event. Response validation occurs before commit; HTTP/database failures roll back. No authorization check is based solely on a client field.

The new schemas explicitly project supported delivery fields. No customer financial data, other-business history or unnecessary Driver private fields are returned. Existing Customer and Shop Owner financial authorization and notification infrastructure remain untouched; no unsupported delivery notification types were invented.

## Database safety and validation

No database change or migration is needed. Both existing Day 12 migrations remain unchanged. **The development database was not modified** by this step; no seed, approval, reset, destructive migration or mutating development test was run.

Before tests, effective settings, SQLAlchemy engine database and `SELECT DATABASE()` were verified as exactly `lankapex_test_db`, at revision `a7b3c6d5e015`. The existing session guard repeats verification. HTTP fixtures use rollback/savepoints; real concurrency tests reuse unique committed test fixtures and exact-ID cleanup on the verified test database.

Validation results:

- Combined targeted Shop Owner delivery and complete Driver regression: **115 passed, 0 failed, 0 skipped**, 14.91 seconds.
- Full backend regression: **840 passed, 0 failed, 0 skipped**, 202.35 seconds. Includes authentication/registration, Customer and Shop Owner financial workflows, reminders, notifications, WhatsApp handoff and the entire Day 12 Driver module. One pre-existing warning is the deliberately short HMAC key in the JWT tampering test.
- Full unchanged frontend regression: **495 passed, 0 failed, 0 skipped**, 73.17 seconds, using `npm test -- --test-concurrency=1` to avoid the pre-existing 15 ms repayment-test timing sensitivity documented in Day 12. No frontend implementation or test was changed.
- Python AST parsing: **62 files passed**; Git whitespace check passed. No configured backend lint/typecheck tool was found.

Coverage includes approved creation, JWT/role/suspension, pending/rejected business, owner versus staff/inactive/foreign membership, multiple owned businesses, cross-business IDs, required/invalid/control-character/maximum-length fields, unsupported vehicle/order/identity/status fields, real initial state, Driver availability and acceptance, safe Driver summary, pagination/filtering/tie ordering, unassigned and duplicate cancellation, assigned/progress/terminal restrictions, three independent MySQL acceptance-versus-cancellation races, concurrent cancellation replay, rollback and sanitized failures. Financial tests snapshot credit-sale/repayment ledger rows, accounts, reminder rows and financial-reference notifications before creation/cancellation and assert no changes.

Targeted logs: `.server-logs/day13-deliveries-targeted.log`. Full regression logs: `.server-logs/day13-deliveries-backend-regression.log` and `.server-logs/day13-deliveries-frontend-regression.log`. Generated artifacts remain ignored.

## Readiness and limitations

Step 13.1 core backend behavior and required tests pass. **Ready for Step 13.2** within the supported contract. That UI can use existing authorized business selection, the exact schema above, real lists/details/statuses, and unassigned cancellation without changing the Driver module.

The existing development backend reloader stalled while the new router was being added; only its verified Uvicorn process tree was restarted. Live OpenAPI now exposes POST/GET collection, GET detail and POST cancellation at the paths above. A live anonymous listing request returns 401. The frontend still responds 200 and remains running. These probes made no authenticated data changes. Final checks confirmed frontend, existing models and migrations are unchanged from HEAD; no Git staging, commit or push was performed.

Documented deferrals: keyed creation replay, request editing, draft publishing, assigned cancellation, package fields, precise private addresses/contacts/instructions and per-job vehicle matching. None is represented as implemented. No earnings, shopping, ordering, GPS, payment gateway, auto-approval or financial calculation was added. No frontend design work or additional Driver frontend feature was started. No commit or push is performed.
