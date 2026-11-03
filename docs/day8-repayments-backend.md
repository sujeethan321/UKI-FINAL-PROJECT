# Day 8 Step 8.4: Customer Repayments Backend

Implemented and verified on 2026-11-03 (Asia/Colombo).

## Inspection and reuse

There was no repayment writer, request schema, or repayment API. Existing LedgerEntry storage, CreditAccount/CustomerProfile relationships, repayment/reversal interpretation, and Decimal balance calculations were functioning and were reused.

Step 8.2's account locking, idempotency matching, receipt generation, transaction response formatting, and retry/rollback handling were extracted into shared helpers used by both Credit Sales and Repayments. Existing effective-balance calculations were not changed. Sales retain their prior API contract and CS-prefixed receipt scheme. No alternate ledger, repayment table, or stored balance was introduced.

## Confirmed payment methods and policy

The live payment_method column is VARCHAR(30), not an enum. The user explicitly confirmed cash, bank transfer, and card for manual recording. The application allowlist is therefore cash, bank_transfer, card. Inputs are trimmed/lowercased; other values return 422. These records do not represent electronic gateway verification or bank settlement verification.

New repayments:

- Must have positive finite Decimal amounts within Numeric(14,2) capacity and currency precision.
- May partially or fully settle current effective debt.
- Cannot exceed outstanding debt. No new advances are accepted; historical advances remain readable and are not rewritten.
- Require an account belonging to the selected business and customer.
- Are allowed on active or suspended accounts so suspended customers can settle debt.
- Are rejected on closed/unsupported-status accounts; no correction workflow is introduced.
- Never change the credit limit, payment terms, or account status, including after full settlement.
- Append a new repayment entry; historical sales, payments, reversals, dates, notes, and references remain unchanged.

An identical replay after settlement/closure is confirmation of an existing record, not a new repayment. A replay of a reversed repayment does not reinstate it.

## API contract

POST /api/v1/shop-owner/repayments?business_id=<selected-business-id>

Authenticated active Shop Owner, active owner membership, and approved business are required. Customer and account lookups are scoped to that business.

```json
{
  "customer_id": 456,
  "amount": "100.10",
  "payment_method": "bank_transfer",
  "receipt_number": "BANK-OPTIONAL-UNIQUE-REFERENCE",
  "notes": "Manually recorded payment",
  "idempotency_key": "repayment:unique-intended-operation"
}
```

| Request field | Validation |
| --- | --- |
| business_id | Required positive signed-BIGINT query parameter |
| customer_id | Required strict positive signed-BIGINT integer |
| amount | Required positive finite Decimal; max 14 total digits, two decimal places; decimal strings recommended |
| payment_method | Required cash, bank_transfer, or card; whitespace/case normalized |
| receipt_number | Optional existing model field, max 60 characters; trimmed, blank -> null; printable characters only |
| notes | Optional, max 2000 characters; trimmed, blank -> null |
| idempotency_key | Required existing 1-100 character ASCII identifier grammar shared with Credit Sales |

Unknown fields are rejected. Actor, entry type, account ID, and recording timestamp are server-controlled. No backdating, due-date input, external gateway identifier field, or electronic-verification flag is invented.

Response fields: entry_id, business_id, customer_id, credit_account_id, currency (LKR), amount, payment_method, outstanding_balance, advance_balance, available_credit, recorded_at, due_at (null for repayment), receipt_number, reference, notes, replayed. Money fields are two-decimal strings. Balances reflect the serialized transaction's current effective financial position.

Status codes:

- 201: newly recorded repayment.
- 200: identical idempotent replay.
- 401: missing/invalid authentication.
- 403: role, inactive-user, membership, ownership, or approval failure.
- 404: missing customer/account or customer/account outside the selected business scope.
- 409: overpayment, closed/unsupported account, conflicting key, or duplicate receipt reference.
- 422: malformed amount, method, identifiers, reference, notes, or unsupported fields.
- 500: sanitized database failure; internal SQL diagnostics are not returned.

## Receipt/reference handling

If receipt_number is omitted/blank, the server generates RP- followed by the same UUID-based scheme already used for CS sale references. Otherwise the supplied value is stored directly in the existing receipt_number column. It is not a separate external-bank-reference field. References remain globally unique under the existing database constraint.

CS- and RP- prefixes are reserved for server-generated references. This allows exact replay checking to distinguish an originally omitted reference from an originally supplied reference without adding a database column or modifying notes. Adding, changing, or removing an explicit reference with the same key returns a conflict; references using a reserved prefix are invalid input.

Printable receipts and immutable snapshots of party details remain Step 8.6. Applications requiring both a separately generated receipt and a distinct external reference will need a separately scoped storage decision.

## Atomicity, locking, idempotency

Both writers resolve and lock the same CreditAccount row with SELECT FOR UPDATE, refreshing ORM state. Originals and reversals are read using a locking current read, avoiding an earlier repeatable-read authorization snapshot. The existing shared Decimal balance calculation determines current repayable debt.

Validation, ledger insertion, receipt assignment, and response construction must succeed before commit. HTTP/database failures roll back the request. Unique-index races and MySQL deadlocks/lock timeouts use the existing bounded retry pattern: at most three complete transaction attempts, each rechecking business ownership/approval.

Identical requests reuse the original entry, reference, timestamp, and method with replayed=true and current balances. Changes to account, operation type, amount, normalized method, notes, or reference are conflicts. Keys are globally unique across Credit Sales and Repayments: a sale key never replays a repayment or vice versa. Clients should use distinct descriptive prefixes when generating their unique operation IDs; the server does not silently transform key namespaces.

Database uniqueness protects both keys and receipts, including independent concurrent account requests. Pre-insert SELECT is not relied on as the sole duplicate protection.

## Executed verification

| Check | Actual result |
| --- | --- |
| Configured database and SELECT DATABASE() | Both lankapex_test_db |
| Ledger engine/isolation | InnoDB / REPEATABLE-READ |
| Existing key/receipt/reversal unique indexes | Verified present |
| Focused repayment tests | 90 passed, 0 failed, 0 skipped; 30.92 seconds |
| Full backend regression | 400 passed, 0 failed, 0 skipped; 90.60 seconds |
| Syntax checks | All 8 new/changed Python files parsed successfully |
| API/OpenAPI registration | Credit Sales and Repayments each registered once; repayment required fields/method enum verified |
| Test-table counts before/after focused and complete suite | Unchanged in all seven checked tables |

Commands:

```powershell
$env:MYSQL_DATABASE='lankapex_test_db'
.\.venv\Scripts\python.exe -m pytest tests/test_shop_owner_repayments.py tests/test_repayments_concurrency.py -v -p no:cacheprovider
.\.venv\Scripts\python.exe -m pytest -v -p no:cacheprovider
```

The cache plugin was disabled because of previously observed cache-directory permissions, without weakening assertions. One existing InsecureKeyLengthWarning remains in the tampered-token test's deliberately short incorrect key.

Coverage includes partial/full repayments, validation, all three approved manual methods, missing/foreign records, real JWT authorization and business isolation, overpayment/status policies, reference uniqueness, same/different-payload retries, historical advances/reversals, immutable history, post-repayment credit sales, generic database-error responses, and rollback after a real INSERT has been flushed.

Seven repayment/mixed concurrency cases use actual MySQL connections and locks: jointly excessive repayments; identical full-payment retries; changed-method key reuse; global key uniqueness across accounts; global receipt uniqueness across accounts; a sale racing a repayment; and cross-type key reuse. Both requests must reach and wait for account locks before a blocking connection releases them. No original assertions in the Credit Sales concurrency tests were weakened.

Ordinary fixtures use outer rollback transactions. The reused independent-connection fixture must commit its uniquely owned test seeds for visibility; its exact account/customer/membership/business/user IDs and ledger rows are removed during teardown. No development financial transactions, resets, drops, truncation, or unrelated row deletion occurred.

## Files created

- backend/app/services/shop_owner_repayment_service.py
- backend/tests/test_shop_owner_repayments.py
- backend/tests/test_repayments_concurrency.py
- docs/day8-repayments-backend.md

## Files modified in Step 8.4

- backend/app/schemas/ledger.py: shared schema bases and explicit repayment schemas.
- backend/app/services/ledger_service.py: shared account lock, idempotency, receipt, and response helpers.
- backend/app/services/shop_owner_credit_sale_service.py: reuse shared helpers while preserving its contract.
- backend/app/routers/shop_owner.py: repayment endpoint and shared transaction retry handler.
- backend/tests/test_credit_sales_concurrency.py: make its race harness accept per-request paths; existing tests/assertions preserved.

## Scope and remaining limitations

No migrations were required or applied. No frontend files were changed in Step 8.4, and no commit/push was made. Previous uncommitted Day 8 work and the unrelated .gitignore edit were preserved.

This step implements manual account-level repayment recording only. Repayment frontend integration is Step 8.5; printable receipts, allocation/overdue management, and reversal recording remain later steps. Electronic payment verification, separate external-reference storage, backdating, timezone-policy changes, and immutable receipt party snapshots are not implemented here.
