# Day 9 Step 9.4 — Notification Management Backend

Date: 2026-11-04 (Asia/Colombo).

## Audit and existing structures reused

No existing notification model, route, service or event bus was present. The sole migration head before this change was c3d9e2f1a601, following the existing business-approval audit migration. The implementation reuses the SQLAlchemy Base, request-scoped sessions, existing JWT active-account checks, the four supported platform roles, business-owner memberships, CustomerProfile.user_id, ledger/reminder IDs and approval audit IDs.

Financial routes already authorize approved owned businesses and commit after their services return. The services hold the existing credit-account lock and distinguish a new event from a replay. Reminder creation has the same transactional boundary. Business decisions lock the business, update its status and create an audit before committing. These boundaries allow notifications to join the original transaction without helper commits or ledger arithmetic changes.

Existing user changes, including Steps 9.2/9.3 and .gitignore, were preserved. The active backend .env was not edited or printed.

## Notification model

notifications contains notification_id (BIGINT primary key), recipient_user_id (required users FK), business_id (nullable businesses FK), controlled notification_type, server-generated title (120 characters) and message (300 characters), controlled related_entity_type and positive related_entity_id, a case-sensitive event_key, is_read (default false), created_at (UTC), and nullable read_at (UTC).

Check constraints restrict notification types, match each type to its entity kind, require positive related IDs, and keep read_at consistent with is_read. Both FKs use RESTRICT. Event references are polymorphic IDs; the service validates them against actual event rows. No arbitrary metadata, URLs, contact details, financial amounts, customer names, notes, ledger bodies or provider credentials are stored in the notification content.

A unique (recipient_user_id, event_key) index deduplicates events. Composite indexes cover recipient + creation order, recipient + read state + creation order, and recipient + type + creation order. All ordered indexes include notification_id to break timestamp ties. business_id also has its FK index.

## Migration verification

New additive migration: backend/alembic/versions/d4e0f3a2b702_add_notifications.py.

Chain: 79d8d51548c6 -> b2a1c4d6e8f0 -> c3d9e2f1a601 -> d4e0f3a2b702 (sole head).

Settings database, engine URL database and actual SELECT DATABASE() were explicitly checked as lankapex_test_db before applying upgrade head. Upgrade succeeded; a second upgrade was a no-op. Alembic comparison of notifications against ORM metadata returned no differences. The migration creates only the new table, constraints and indexes. Its downgrade intentionally refuses to delete notification data; rollback requires an additive forward migration.

No migration was applied to lankapex_db. Development activation requires applying the new additive migration to the deliberately selected development database before using the new inbox or event hooks. No existing migration was rewritten.

## Service functions and transactions

- notify_event(db, notification_type, entity_id): validates a real event, resolves authorized recipients and creates/deduplicates minimal records. Internal only; never commits.
- active_owners: active owner memberships joined to active shop_owner users, excluding the event actor.
- current_recipient_row: current shared locking reads for linked customer/user records, avoiding stale MySQL REPEATABLE READ snapshots from earlier JWT queries.
- list_notifications: recipient-only predicates, validated filters, count and bounded pagination; newest created_at then notification_id.
- unread_count: indexed recipient/unread count.
- mark_read: conditional atomic update for an unread owned row; current locked read; returns the same read_at on repeats.
- mark_all_read: one conditional update restricted to the authenticated recipient; returns affected rows. Already read rows and other users remain unchanged.
- notification_response: explicit response fields and UTC-aware timestamps.

The caller commits event + notification together. Notification persistence failure rolls back the event; retries use existing financial idempotency and retry logic. Failed validation, conflicts and replay branches do not create new notifications. Notification helpers never write ledger entries, account balances or payment-reminder status.

## Actual API contracts

All endpoints are under /api/v1, require the existing Bearer JWT, require an active supported user, and return Cache-Control: no-store on successful responses. The authenticated user is the sole source of recipient ownership. Administrators receive no wider inbox access.

GET /api/v1/notifications

Query: page (default 1; 1..1000000), page_size (default 20; 1..100), unread_only (default false), is_read (optional boolean), notification_type (optional supported type). Unknown query fields are rejected; unread_only=true with is_read=true is rejected. Ordering is fixed to newest first.

Response: {"page": 1, "page_size": 20, "total": 1, "notifications": [{"notification_id": 123, "business_id": 12, "notification_type": "repayment_recorded", "title": "Repayment recorded", "message": "A manual repayment was recorded for your linked customer account. This does not verify an electronic payment.", "related_entity_type": "ledger_entry", "related_entity_id": 456, "is_read": false, "created_at": "2026-11-04T10:00:00Z", "read_at": null}]}

GET /api/v1/notifications/unread-count

Response: {"unread_count": 1}.

PATCH /api/v1/notifications/{notification_id}/read

No request body. ID must be a positive signed-BIGINT-range integer. Returns the owned NotificationResponse shown above, with is_read=true and read_at set. Foreign/nonexistent IDs both return 404 Notification not found. Repeats leave read_at unchanged.

PATCH /api/v1/notifications/read-all

No request body. Response: {"updated_count": 1}; subsequent unchanged requests return zero.

There is no notification-generation endpoint and no user-supplied destination URL. Future navigation must resolve controlled event/entity types and still enforce the destination API's own authorization.

401: absent/invalid JWT. 403: inactive account or unsupported role. 404: missing/foreign owned notification. 422: invalid query/ID/filter. SQLAlchemy errors roll back and produce a generic 500, without SQL diagnostics. Business-decision SQLAlchemy errors are also sanitized while preserving their rollback behavior.

## Integrated event types and recipient rules

- credit_sale_recorded: emitted only after a new sale is flushed and its due date is validated. Recipient is the active customer user explicitly linked through the matching business CustomerProfile and credit account.
- repayment_recorded: emitted only after a new manual repayment is validated and flushed. Same explicit linked-customer rule; wording does not verify electronic settlement.
- payment_reminder_recorded: emitted after a new internal reminder snapshot is flushed. Recipients are other active shop_owner owners of the approved business. No customer-facing reminder is delivered, preserving Step 9.2's unknown-permission/internal-only policy.
- business_approved / business_rejected: emitted after a real pending-business decision and audit are flushed. Recipients are active shop_owner owners of that business. Private reviewer notes are excluded.

Actors are excluded. Unlinked customers, inactive users, users linked under a different platform role, inactive memberships and unrelated business owners are not notified. Identity is never guessed from names, phone numbers or email. Recipients can retain minimal historical inbox records after membership changes, but an inbox record never grants access to a business or financial endpoint; those authorization checks remain intact.

## Deduplication and concurrency

The deterministic key is notification_type + ':' + confirmed entity ID, unique per recipient. MySQL no-op ON DUPLICATE KEY UPDATE handles independent concurrent creation without swallowing other errors or rolling back the outer event transaction. A duplicate never rewrites original content, creation/read timestamps or read state. Replay branches do not invoke recipient resolution, so changing a customer link and replaying a past financial request cannot send that past event to a newly linked user.

Recipient links, account status and active owner membership queries use current shared locks where needed. Read-state transitions use atomic predicates. Notification ordering is deterministic within the database snapshot; offset pagination may naturally shift between separate requests when new events arrive.

## Verification

Completed verification on lankapex_test_db only:

- New notification tests: **60 passed, 0 failed, 0 skipped**, including six independent-session concurrency cases.
- Focused notification + existing reminder, sale and repayment regression: **263 passed, 0 failed**, exit 0 (114.50 seconds). This preceded the final recipient-snapshot test; the full final suite includes that test and the final current-read hardening.
- Full final backend suite: **571 passed, 0 failed, 0 skipped**, exit 0 (154.46 seconds). Existing payment-reminder, credit-sale, repayment, concurrency, financial-document, database, JWT and role-authorization checks all passed.
- One existing InsecureKeyLengthWarning arises from the deliberately short incorrect signing key in test_tampered_token_rejected. No new warnings or test exclusions.
- All nine application tables were verified empty after the suite; rollback fixtures and scoped committed-fixture cleanup left no notification/financial test rows behind.
- Sole Alembic head and applied test revision: d4e0f3a2b702. New notification ORM/migration comparison returned no differences.
- Python syntax/import/OpenAPI checks and Git diff whitespace check passed. All existing routes remain mounted without circular imports.
- Tests used the existing pytest session guard plus explicit configuration, engine URL and actual SELECT DATABASE() checks. No automated test connected to lankapex_db.

Initial focused tests exposed an unsanitized business-decision database failure and a MySQL CHECK-violation exception-class mismatch in the new test. The route handling and test assertion were corrected without removing checks. The final complete suite passes.

Day 9 Step 9.4 backend implementation and required test-database verification are complete. Development migration activation is still pending.

## Limitations and deferred work

No Step 9.5 frontend, polling, WebSockets, jobs, external providers, SMS, WhatsApp, email or delivery-driver events were introduced. Delivery workflows are not implemented, so there is no driver event hook. Customers without an explicit verified database link receive no financial notification. Reminder customer delivery remains intentionally unavailable; a sole actor owner produces no redundant reminder notification.

Notifications are minimal historical event records. Later reversals do not rewrite them; reversal notifications were outside this step. Messages use fixed English templates; notification translation/preferences and link navigation belong to later work. No development migration or deployment was performed. No commits or pushes were made.

## Files created

- backend/app/models/notification.py
- backend/app/schemas/notification.py
- backend/app/services/notification_service.py
- backend/app/routers/notifications.py
- backend/alembic/versions/d4e0f3a2b702_add_notifications.py
- backend/tests/test_notifications.py
- backend/tests/test_notifications_concurrency.py
- docs/day9-notification-management-backend.md

## Files modified for this step

- backend/app/models/__init__.py: register Notification while retaining PaymentReminder.
- backend/app/main.py: mount notification router under /api/v1 while retaining all existing routes.
- backend/app/services/shop_owner_credit_sale_service.py: new-event hook only.
- backend/app/services/shop_owner_repayment_service.py: new-event hook only.
- backend/app/services/shop_owner_reminder_service.py: new-event hook only.
- backend/app/routers/admin_businesses.py: transactional approval/rejection hook and sanitized SQLAlchemy errors.
