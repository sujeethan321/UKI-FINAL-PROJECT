# Day 9 Step 9.2 — Payment Reminder Backend

Date: 2026-11-04 (Asia/Colombo).

## Audit foundations and scope

Step 9.1 found no existing reminder/notification models or APIs. Customer phone is optional; customer communication consent, opt-out and verified email are not recorded. Due dates exist but repayments have no sale allocations, so exact overdue remains unavailable. This implementation adds one reminder table, not a notification system, consent system or delivery integration.

Reuses ledger_service.account_balances/load_ledger_entries and lock_customer_credit_account, existing real-JWT require_roles and get_approved_owned_business checks, SQLAlchemy request sessions, and existing isolated MySQL fixtures. No alternate financial arithmetic, ledger/account writes, frontend changes, providers, external requests, jobs, commits or pushes.

## Files

New:
- backend/app/models/payment_reminder.py
- backend/app/schemas/payment_reminder.py
- backend/app/services/shop_owner_reminder_service.py
- backend/app/routers/shop_owner_reminders.py
- backend/alembic/versions/c3d9e2f1a601_add_payment_reminders.py
- backend/tests/test_payment_reminders.py
- backend/tests/test_payment_reminders_concurrency.py
- docs/day9-payment-reminders-backend.md

Modified: backend/app/models/__init__.py (model registration), backend/app/main.py (router registration), backend/app/core/config.py (bounded cooldown setting). The pre-existing .gitignore edit is untouched.

## Model and migration

PaymentReminder records business/customer/account/initiating-user foreign keys, Numeric(24,2) outstanding snapshot, LKR currency, intended channel, language, versioned rendered message, optional internal note, recorded status, case-sensitive idempotency key and UTC created/updated timestamps. Timestamps use second precision matching the existing MySQL DATETIME storage; API timestamps explicitly carry UTC. Notes are stored separately and never appended to messages.

Database constraints restrict positive amounts, LKR, en/ta languages, supported channels and recorded-only status. Unique (business_id, idempotency_key) arbitrates concurrent requests. Indexes support business date ordering and customer cooldown/history. Snapshot precision accommodates aggregated balances beyond an individual ledger entry's Numeric(14,2); larger unsupported aggregates fail explicitly.

Revision chain: 79d8d51548c6 -> b2a1c4d6e8f0 -> c3d9e2f1a601 (sole head).

The additive migration creates only payment_reminders, constraints and indexes. It was upgraded and round-trip tested on lankapex_test_db after verifying actual connection and an empty reminder table. No development migration was applied. Development application requires explicit user approval and a deliberate command against the intended configured database; do not run a downgrade on a database with reminder records.

## API contract

POST /api/v1/shop-owner/payment-reminders?business_id={id}

```json
{
  "customer_id": 123,
  "channel": "internal",
  "language": "en",
  "note": "Optional internal note",
  "idempotency_key": "reminder-unique-operation"
}
```

channel defaults to internal; allowed intended channels: internal, copy, whatsapp, sms. language defaults to en; en/ta supported. customer_id is a strict positive signed-BIGINT-range integer. Key is 1–100 ASCII alphanumeric/dot/underscore/colon/hyphen characters, starting alphanumeric. Note is optional, trimmed, at most 1000 characters, with unsupported controls rejected. Unknown fields, including amount, message, status and created_by, are rejected. Email is unsupported.

New record: HTTP 201. Identical authorized retry: HTTP 200 and replayed=true. Response includes reminder_id, business_id, customer_id, credit_account_id, created_by, outstanding_amount decimal string, currency, message, template_version, channel, language, note, status, created_at, updated_at, replayed and delivery limitation fields. All records report consent_status=unknown and delivery_allowed=false. These express absent evidence, not consent. There is no send or status-update endpoint.

GET /api/v1/shop-owner/payment-reminders?business_id={id}

Optional customer_id, status=recorded, ordering=newest|oldest, page (default 1), page_size (default 20, max 100). Result: business_id, page, page_size, total, reminders. Ordering uses created_at and reminder_id for stable ties. A customer filter is independently verified within the selected business, even if no records match. Both APIs return Cache-Control: no-store on success.

401: missing/invalid authentication. 403: wrong role, inactive user, inactive/non-owner membership, unowned or unapproved business. 404: customer/account absent in selected business. 409: no debt, inactive account, missing contact for non-internal channel, changed-key intent or cooldown. 422: invalid input/query. Database failures are rolled back and sanitized.

## Financial, idempotency and cooldown policy

Creation acquires the same account-row lock as sales/repayments. It reads effective ledger entries using current locking reads under MySQL REPEATABLE READ. Reversed sales and repayments, partial/full payments, advances and no-account states therefore follow existing Day 8 semantics. Only active accounts with positive outstanding qualify. Suspended/closed accounts reject new reminders.

Exact key replay compares customer, initiating owner, channel, language and normalized note; it returns the original immutable amount/message snapshot even after settlement, without changing history or consuming cooldown again. Reusing another owner's operation key conflicts. Business-scoped database uniqueness and transaction retries handle cross-account races; same-account requests serialize on the account row. Reads used for replay and cooldown are current locking reads.

REMINDER_COOLDOWN_SECONDS defaults to 86400 (24 hours), configurable via existing settings/environment, range 0–31536000. Zero disables cooldown. Every recorded reminder, including internal-only records, consumes cooldown across ALL channels for that business/customer. There is no separate draft state or override API. Only a matching idempotent retry bypasses fresh eligibility and cooldown checks. This prevents switching intended channels to bypass frequency limits.

## Messages and delivery limitations

English and Tamil outstanding-v1 templates include customer/shop names, exact grouped LKR amount, UTC snapshot time and polite payment wording. No overdue, fabricated due dates or fees. Tamil production wording still needs language review. Unknown permission blocks all future sending; there is no mechanism in this step to mark permission verified. A customer without a phone may record an internal reminder only. Intended phone channels with a phone are still merely recorded and never sent. Phone ownership/format must be revalidated in a later delivery implementation.

No provider metadata or credentials are added prematurely. There are no sent/delivered statuses, callbacks, background tasks or external communication calls. Existing contact information does not imply permission. Recording history is creation history, not a mutable delivery-status/event history; a later delivery design must add authenticated evidence and append-only events before status transitions.

## Verification

Configured database, engine URL database and actual SELECT DATABASE() all verified lankapex_test_db before tests. Existing pytest collection guard repeats those checks. Ordinary fixtures use outer transaction rollback/savepoints; concurrency fixtures commit unique owned rows and remove only their own reminder/ledger/account/customer/business/user IDs in foreign-key order.

Focused tests: 51 passed, 0 failed, exit 0 (22.17 seconds). Covers real JWT/role/ownership/approval, business/customer/account isolation, financial snapshots, partial/full payments, reversals/advances, no account, exact replay after settlement, payload conflicts, DB uniqueness/case sensitivity, cooldown/expiry/configuration, pagination/filtering/Tamil, safe errors, aggregate precision, unchanged ledger/details and route/schema registration. Four real races verify identical-key replay, changed-input conflict, different-key cooldown and same-key cross-account conflict, with both requests demonstrably blocked on the MySQL account lock.

Initial focused run exposed MySQL timestamp precision mismatches; timestamps now match stored precision and zero cooldown explicitly bypasses the query. Assertions were retained.

Full backend regression: MYSQL_DATABASE=lankapex_test_db ./.venv/Scripts/python.exe -m pytest -v -p no:cacheprovider: **511 passed, 0 failed, 0 skipped**, exit 0, 196.52 seconds. One existing InsecureKeyLengthWarning comes from the deliberately short incorrect signing key in test_tampered_token_rejected.

Python syntax/import checks passed. Alembic comparison of the migrated reminder table against ORM metadata returned no differences. Migration upgrade/downgrade/upgrade round trip passed on the verified empty test reminder table, and the sole final head is c3d9e2f1a601. Success/error responses and real API route registration are covered by focused tests. All eight test application tables were verified empty after the full suite. Git diff whitespace check passed. No live development data or environment secrets were read into the report or changed.

Backend implementation and required test-database verification are complete. Development activation remains pending explicit migration approval, as required by the Step 9.2 request. No commit/push performed. Remaining limitations: no consent/preferences management, no verified contact ownership, no external delivery, no overdue allocation, no frontend, no mutable delivery statuses or automated scheduler, and Tamil wording awaits production language review.
