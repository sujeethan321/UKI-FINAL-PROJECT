# Day 15 Step 15.1 — Order-to-delivery backend

## Dependency audit

Verified main at Day 14 checkpoint d917e4f (customer shopping and credit order integration). Inspected Order/OrderItem, credit approval, delivery models, services, routers, notifications, migrations and tests. Initially only an unrelated .gitignore edit was present; it is preserved. Orders and deliveries had no existing relationship. No split fulfilment domain was found.

Day 14 credit approval locks the order/account and posts through the existing ledger service within the caller-owned transaction. Existing sale/retry uniqueness remains unchanged. Cash processing does not establish payment. Existing delivery creation accepts only public pickup_area and delivery_area; no stored recipient contact, coordinates, package or vehicle requirements are available to derive. No private Customer contact is copied.

## Implementation and relationship

Modified:
- backend/app/models/order.py
- backend/app/models/delivery.py
- backend/app/routers/orders.py

Created:
- backend/app/services/order_delivery_service.py
- backend/app/schemas/order_delivery.py
- backend/alembic/versions/e1f7a0b9c459_link_order_delivery.py
- backend/tests/test_order_delivery.py
- backend/tests/test_order_delivery_concurrency.py
- docs/day15-order-delivery-backend.md

Reuses Order, OrderItem, DeliveryRequest, DeliveryAssignment and DeliveryStatusEvent. Orders now have nullable delivery_request_id. A unique constraint prevents sharing a delivery between orders. A composite foreign key (delivery_request_id, business_id) requires the delivery to belong to the same business. The delivery composite unique key supports that FK. Existing records retain null links; no backfill or table replacement occurs.

MVP policy: one permanently retained delivery link per order, including cancelled deliveries. There is no split fulfilment or implicit replacement. This is stricter than one active delivery and prevents retries from reopening cancelled work. A future explicit replacement workflow requires a separate policy/schema change. Already-linked orders return their existing request; conflicting areas return 409. Cancelled links are never cleared.

## Eligibility and authorization

New requests require an authenticated active Shop Owner, active authorized business membership and approved business under existing catalogue/delivery policies. business_id is a required selector, never proof of ownership. Cross-business/missing orders return 404. Other roles receive 403; invalid/expired JWT receives 401.

- Cash: processing and unpaid.
- Credit: approved or processing, payment_status posted, with the matching unreversed credit_sale for the same order/account/business and exact order total.
- Submitted, rejected, cancelled or completed orders cannot create new deliveries.

A posted sale is validated without making another sale or rechecking available credit as if charging again. A subsequently closed account or exhausted limit does not invalidate an already-posted sale. Existing-link equivalent retries remain safe after cancellation, delivery or order completion. They create nothing.

## Actual API contract

All endpoints use JWT Bearer authentication and Cache-Control: no-store.

| Method | Endpoint | Result |
| --- | --- | --- |
| POST | /api/v1/shop-owner/orders/{order_id}/delivery?business_id={id} | 201, including equivalent replay |
| GET | /api/v1/shop-owner/orders/{order_id}/delivery?business_id={id} | Owner operational summary |
| GET | /api/v1/customer/orders/{order_id}/delivery | Own-order safe progress |

POST body (required public areas, trimmed, 1–160 characters each, single line; unknown fields rejected):

~~~json
{"pickup_area":"Colombo Fort","delivery_area":"Nugegoda"}
~~~

Do not send totals, recipient contact, private addresses, driver IDs, coordinates, fees or vehicle fields. Unsupported/invalid input returns 422. Ineligible orders/conflicting retries return 409. SQL errors are rolled back and sanitized (409 constraint conflict or 503 unconfirmed operation); refresh/retry identical input after uncertainty.

Step 15.2 adds read-only owner fields can_request_delivery and delivery_unavailable_reason using the same eligibility policy as POST; these fields do not change the Customer projection.

Illustrative owner response structure (IDs/timestamps are examples only):

~~~json
{
  "order_id": 123,
  "can_request_delivery": false,
  "delivery_unavailable_reason": "This order already has a retained delivery request.",
  "delivery_requested": true,
  "delivery": {
    "delivery_request_id": 456,
    "reference": "DLV-example",
    "business_id": 7,
    "pickup_area": "Colombo Fort",
    "delivery_area": "Nugegoda",
    "status": "available",
    "created_at": "2026-11-07T08:00:00",
    "updated_at": "2026-11-07T08:00:00",
    "assigned_driver": null,
    "events": [],
    "can_cancel": true
  }
}
~~~

Once assigned, assigned_driver contains only full_name and assigned_at from the existing authorized owner projection. Existing owner delivery detail/tracking and cancellation APIs continue operating on delivery_request_id. No new cancellation or assignment system was introduced.

Customer response exposes only reference, status, timestamps and non-sensitive status events:

~~~json
{
  "order_id": 123,
  "delivery_requested": true,
  "delivery": {
    "reference": "DLV-example",
    "status": "assigned",
    "created_at": "2026-11-07T08:00:00",
    "updated_at": "2026-11-07T08:10:00",
    "events": [{"status":"assigned","occurred_at":"2026-11-07T08:10:00"}]
  }
}
~~~

Before linking, both summaries return order_id, delivery_requested false and delivery null. Customer summaries are scoped to the authenticated Customer's own order; they exclude Driver identity/contact/vehicle, areas, assignment notes, business internals and financial data. Existing Order DTOs remain unchanged.

## Transactions, concurrency and lifecycle

Creation locks the Customer user then Order in existing decision lock order, validates current state, calls existing shop_owner_delivery_service.create_request, links and flushes, validates the response, then commits once through the existing router transaction wrapper. Any failure rolls back both records. Equivalent normalized areas return the same retained delivery; differing areas conflict. The locked order and database constraints enforce this under concurrent HTTP requests, without a new client key.

Order-derived requests are ordinary available jobs for eligible Drivers. Existing acceptance locks and ownership checks apply. Lifecycle remains available → assigned → picked_up → in_transit → delivered, with existing cancellation restrictions. Owner cancellation is limited to available/unassigned work; acceptance and cancellation serialize on the same request. Status history and owner notifications use existing services. Summary reads use current shared locks and perform no writes.

Delivery events do not change Order status, payment state, totals, items, account balances or ledger entries. Delivered does not mean paid or automatically completed. Owner order decisions remain the existing separate workflow. Creating/accepting/cancelling/completing delivery never creates a sale, repayment, reversal or cash receipt. No automatic Driver assignment, GPS, pricing, online payment or frontend changes were added.

## Migration and rollout

Revision e1f7a0b9c459 follows d0e6f9a8b348. Applied and validated only on lankapex_test_db. Settings, engine URL and SELECT DATABASE() were verified as lankapex_test_db before mutating tests. Existing pytest session guards also reject any other database. Alembic check reports no new upgrade operations.

No migration or reset was run against lankapex_db. After reviewing/backing up the intended development database, the required manual command from backend with the intended database environment is:

~~~powershell
$env:MYSQL_DATABASE = "lankapex_db"
.\.venv\Scripts\python.exe -m alembic upgrade head
~~~

This applies all pending predecessors too. The migration is additive; downgrade deliberately refuses to discard relationship data. Deploy the migration before using these new model-backed endpoints.

## Verification

New database-backed integration/concurrency suite: 48 passed, 0 failed, 0 skipped. Covers JWT/roles, suspended users/business approval/membership, cross-business/Customer isolation, required/unsupported input, eligibility, invalid/reversed credit approval, retained links, equivalent/conflicting retries, FK/unique constraints, rollback/commit failure, no-write summaries, private-field filtering, actual Driver visibility/acceptance/progress and financial snapshots. Independent MySQL connections exercise simultaneous equivalent/conflicting creation, completion versus creation and cancellation versus acceptance.

Full backend regression: 1,017 passed, 0 failed, 0 skipped in 144.85 seconds. One existing InsecureKeyLengthWarning originates in test_jwt.test_tampered_token_rejected (short test-only key). The suite includes authentication, credit accounts/sales/repayments/statements, notifications, catalogue, cash/credit orders and Day 12–13 delivery coverage. Eight changed/new Python files parse successfully; git diff --check passes. Final settings/engine/actual database verification confirms lankapex_test_db at e1f7a0b9c459; Alembic check passes with no metadata drift.

Full frontend regression: 610 passed, 0 failed, 0 skipped (node --test --test-concurrency=1, 66.24 seconds), including shopping/cart/checkout, authorization and delivery view contracts. No frontend source or DTO was changed. Browser end-to-end QA, frontend build and full lint were not rerun for this backend-only change.

## Step 15.2 readiness and boundaries

Backend API contract is ready for Shop Owner fulfilment UI after the target database is migrated. Use the dedicated summary/create endpoints and existing delivery tracking APIs; refresh on 409/503. Keep payment/approval/order completion separate. Do not offer replacement after cancellation under this MVP policy. No required backend dependency remains missing; recipient contacts/vehicle requirements, split deliveries and cancelled-request reissue remain outside this step. No files were staged, committed or pushed.


## Consolidated Day 15 checkpoint

Step 15.5 reviews the complete Day 15 implementation and creates the requested local checkpoint. See [final verification and progress report](day15-final-regression-security-review.md) for fresh consolidated results, deployment limitations and Git checkpoint details. Earlier per-step test counts above are historical results.
