# Day 13 Step 13.4 — Delivery tracking and notifications

> Day 13 final verification and local checkpoint: [Step 13.5 report](day13-final-regression-security-review.md).

## Verified foundation

Inspected the current `main` working tree rather than relying on earlier prompts. Steps 13.1–13.3 are implemented: business-scoped Shop Owner APIs and management page, Driver discovery/acceptance/progress/history, shared `DeliveryRequest` and unique `DeliveryAssignment`, persisted `DeliveryStatusEvent`, JWT role guards, ownership checks and MySQL locking. Earlier uncommitted work and unrelated `.gitignore` changes were preserved. No commit or push was made.

The existing notification model, internal creation service, recipient-owned APIs, bell, dropdown, role inboxes and provider already serve Shop Owner, Driver, Customer and Admin. Their existing 60-second notification polling pauses in background tabs, avoids overlap, uses bounded retry backoff and disposes on unmount. Provider keys include user, role and token, preventing account-switching state reuse. There is no existing delivery notification preference system to bypass.

## Implementation and files

Extended:

- `backend/app/models/notification.py`: expand the existing type/entity checks.
- `backend/app/schemas/notification.py`: delivery types in response/filter contracts.
- `backend/app/services/notification_service.py`: resolve recipients from real delivery records, assignment and progress history; reuse existing transactional upsert.
- `backend/app/services/driver_service.py`: call notification creation only in successful, flushed assignment/pickup/transit/completion branches, before the router commits.
- `frontend/src/utils/notification.js`: supported delivery types and role-specific, business/request-scoped delivery links.
- `frontend/src/pages/shopOwner/ShopOwnerDeliveries.jsx`: reuse detail panel, support notification query links and render the shared timeline.
- `frontend/src/pages/driver/DriverDeliveries.jsx`: render the same timeline in existing details.
- `frontend/src/pages/shopOwner/ShopOwnerNotifications.jsx`: constrain the existing reminder business selector to the viewport; real mobile QA exposed overflow for long business names. No layout or color redesign.

Created:

- `backend/alembic/versions/b8c4d7e6f126_delivery_notifications.py`.
- `frontend/src/utils/deliveryTimeline.js`.
- `frontend/src/components/delivery/DeliveryTimeline.jsx`.
- `backend/tests/test_delivery_notifications.py`.
- `frontend/tests/deliveryTracking.test.js`.
- `frontend/scripts/verifyDeliveryTracking.mjs`.
- This report.

Updated regression coverage in `backend/tests/test_driver_concurrency.py`, `test_driver_jobs_concurrency.py`, `test_driver_deliveries_concurrency.py`, `test_driver_security_review.py`, and `frontend/tests/shopOwnerDeliveriesView.test.js`. Concurrency teardown now removes only its own delivery notifications before deleting the fixture business. Financial regression snapshots still compare all financial records and pre-existing financial notifications; four new delivery notifications are explicitly asserted separately.

## Actual routes and tracking data

API prefix: `/api/v1`.

| Method | Route | Scope |
| --- | --- | --- |
| GET | `/shop-owner/deliveries/{id}?business_id={business_id}` | Active Shop Owner with authorized owner membership in the requesting business |
| GET | `/driver/deliveries/{id}` | Active authenticated Driver assigned to this delivery |
| GET | `/notifications` | Current JWT recipient only; existing pagination/type/read filters |
| GET | `/notifications/unread-count` | Current recipient only |
| PATCH | `/notifications/{id}/read` | Current recipient's notification only |
| PATCH | `/notifications/read-all` | Current recipient only |

No second tracking or notification API was introduced. Existing status-changing APIs remain `POST /driver/jobs/{id}/accept`, `POST /driver/deliveries/{id}/status` with `expected_status` and `status`, and business-scoped `POST /shop-owner/deliveries/{id}/cancel`.

Both tracking detail responses retain their existing schemas: current status/reference, appropriate shop or assigned Driver summary and `events: [{status, occurred_at}]`. Assignment time comes from `DeliveryAssignment.assigned_at`; later timestamps come from persisted `DeliveryStatusEvent.occurred_at`, ordered by time and event ID. No backfilled stages or dates are invented. Creation/update dates remain displayed on the owner detail panel. Notes and precise operational addresses are not stored by this model.

The shared timeline shows recorded stages and dates, explicitly identifies the current recorded stage, and labels future stages “Upcoming.” Missing earlier history is labelled “History unavailable.” Cancellation shows its recorded time and labels unrecorded stages as cancelled. Empty history has an explicit message. Existing layouts, colors, logo and typography remain in place.

## Notification policy and atomicity

| Persisted action | Notification type | Recipients |
| --- | --- | --- |
| Driver accepts | `delivery_assigned` | Active Shop Owner users with active owner membership in the requesting business |
| Driver confirms pickup | `delivery_picked_up` | Same business-owner policy |
| Driver starts transit | `delivery_in_transit` | Same business-owner policy |
| Driver marks delivered | `delivery_delivered` | Same business-owner policy |

Names follow the existing lowercase notification convention. Completion wording says the Driver marked delivery as delivered; it does not claim independent verification. Messages contain no financial balances, customer contacts or precise addresses.

No creation broadcast: an available request has no assigned Driver recipient. No public cancellation notification: Shop Owner cancellation is restricted to unassigned requests, so there is no assigned Driver to notify. Existing internal cancellation compatibility is preserved; public cancellation after assignment remains forbidden. No new public cancellation, self-approval or notification-creation endpoint was added.

Writes reuse the same SQLAlchemy transaction as the status/assignment. SQL failure or commit failure rolls back the delivery state, event and notification together. There is no external call. New-event branches alone generate notifications. Assignment retry returns the existing assignment; stale/unchanged progress retries return 409 and create nothing.

The existing unique `(recipient_user_id, event_key)` index and MySQL no-op upsert deduplicate a transition for each recipient, preserving read state and original timestamp. Event keys use `delivery_<status>:<delivery_request_id>`. This is valid for the current irreversible lifecycle: a request cannot revisit a stage or be reassigned. Any future reopening/reassignment feature must use distinct persisted transition identifiers before extending this behavior.

Notification links are allowlisted, generated from validated positive business/request IDs, and restricted to Shop Owner delivery routes. Query context is resolved through the existing membership-scoped business workflow; detail APIs enforce authorization independently. Foreign IDs cannot expose records. Driver/Customer/Admin notifications do not receive these owner destinations. Existing ProtectedRoute, JWT, account restrictions and provider isolation remain authoritative.

## Refresh behavior

Tracking reads run on navigation and through the existing Refresh controls without a full page reload. Driver progress and owner cancellation refresh server data after successful actions. Notification navigation selects the authorized business and opens the request detail panel. Existing abort controllers, generation checks and mutation locks prevent superseded responses from replacing current context.

No new tracking timer or WebSocket was added. Notifications continue to use the existing visibility-aware polling. This is recorded status tracking, not live GPS or instant push.

## Database safety

Migration `b8c4d7e6f126` follows `a7b3c6d5e015`. It expands the two existing notification check constraints in place; no table, column, record or unique index is removed. Downgrade refuses to discard supported notification data. Applied successfully to verified `lankapex_test_db`, then to the local development schema `lankapex_db` so the running app can store the new types. No tests or browser fixtures ran against the development schema.

Before mutating tests, the suite guard verifies settings, engine URL and actual `SELECT DATABASE()` all equal `lankapex_test_db`. No reset, destructive migration or ledger calculation change was performed. Temporary browser fixtures use unique identities, exact-ID cleanup and ignored local token files.

## Validation

- Initial targeted backend delivery/notification/cancellation/concurrency tests: **17 passed**. Final expanded targeted backend run, including Driver dashboard and financial security review: **38 passed**, zero failed/skipped, **6.16s**.
- Full backend regression: **851 passed**, zero failed/skipped, **174.43s**. Existing intentionally short test HMAC-key warning remains.
- Full frontend regression: **532 passed**, zero failed/skipped, **79.22s**, single-worker execution consistent with the existing suite.
- Final focused frontend tracking/notification/detail suites: **70 passed**, zero failed/skipped, **8.76s**, including the final mobile selector change. Full suite was run before that class-only correction.
- Final production Vite build: **passed**, **3.21s**. Existing large-chunk warning remains.
- Full configured ESLint: existing **8 errors and 1 warning** in ShopOwnerCustomers, ShopOwnerDashboard and repayments tests. Changed tracking/notification application files passed targeted ESLint. No separate typecheck is configured.
- JWT/role/expired-token, cross-business/cross-driver isolation, stored event ordering/timestamps, financial/reminder/customer regression, stale frontend responses and account-switching notification isolation are exercised by the existing suites plus new delivery notification tests.
- New backend cases cover all four notification types, unrelated Driver exclusion, recipient read denial, duplicate retries, notification replay deduplication and commit rollback. Independent HTTP races assert one assignment/progress notification; owner cancellation versus acceptance locks remain intact.

Real Chrome browser verification passed **40 responsive checks**: eight workflow states/pages at 1536, 1366, 1024, 768 and 375px. The runner exercised actual compiled React pages, real signed JWTs and the isolated FastAPI/MySQL backend, forwarding browser API requests exclusively to test port 8013. No mocked API responses or development-database delivery records were used.

The browser created exactly one request through the owner form, accepted it as Driver A, rejected pending/competing Driver access, confirmed all three progress updates and compared owner/Driver histories. It verified the four real owner notifications, no notification for Driver B, the rendered delivery link opening the correct completed tracking panel, and unread count decreasing from four to three after a real PATCH. The inbox and tracking screenshots at 375px were visually inspected. No document-level overflow or clipped references remained. The reminder history retains its existing internal horizontal table scrolling.

Evidence: ignored `.server-logs/day13-tracking-browser/results.json`, 40 screenshots in that directory, and `.server-logs/day13-tracking-browser-run.log`. Backend/frontend/build/lint logs use the `day13-tracking-` prefix. An initial browser run exposed the selector overflow; the final run passed after correction. Initial test failures from fixture teardown and pre-delivery notification assumptions were corrected; the final counts above are successful runs.

The temporary test API process tree was stopped. Exact nonce/ID-checked fixture cleanup removed the request, history, assignment, four notifications, membership, profiles, business and users. The ignored fixture JSON was sanitized to `{database: "lankapex_test_db", cleaned: true}`. No reset or broad deletion was used. Existing development servers were left running.

## Scope and next step

No GPS, map, external messaging, earnings, shopping, payment integration or financial calculation changes. No synthetic delivery events or production mock data. No new design or colors.

The implementation is ready for Step 13.5. No functional blocker remains for this scope. Existing repository-wide lint debt and bundle sizing remain unrelated follow-up work. No Step 13.5 changes have been started.
