# Day 11 Step 11.1 — Customer Dashboard backend foundation

> Final Day 11 audit, security fixes, checkpoint and unresolved linking/browser limitations are recorded in [Step 11.5](day11-final-regression-security-review.md). The results below describe this earlier step.

## Model and identity audit
Authenticated identity is User.user_id from the existing verified JWT dependency. CustomerProfile has a nullable, indexed user_id and a required business_id. Multiple profiles can explicitly link one user to different shops, or to more than one profile in the same shop. CreditAccount references customer_id and creditor_business_id; the query requires the account creditor and profile business to agree. The database permits one credit account per customer profile. Multiple accounts for one registered user therefore come through multiple profiles.

Credit sales, repayments and reversals are LedgerEntry rows, not separate CreditSale or Repayment models. The existing ledger service defines effective current balances, including full removal of originals referenced by same-account reversals. Notification endpoints already scope records by authenticated recipient and are unchanged.

Customer registration currently creates only a User. Shop-managed customer creation explicitly sets user_id=None. No authorized linking workflow was found. This step neither discovers links from name/phone/email nor creates, reassigns or activates links. Existing explicit database links are honored; individual development customer records were not read or altered. A newly registered/unlinked customer receives successful empty/zero responses until a future authorized linking workflow supplies an explicit link.

## Security and visibility contract
All four routes require the customer role through require_roles("customer"), including an active account and validated JWT. Missing credentials return 401; Shop Owners, Drivers, Admins and unsupported roles return 403. Admin identity does not permit customer impersonation. Suspended/disabled user accounts remain blocked by the existing dependency.

Every query starts from CustomerProfile.user_id == authenticated user.user_id. No browser user_id or customer_id is used to establish ownership. Only explicitly linked, approved businesses are visible, preserving the existing approved-business restriction on financial reads. A valid linked profile without a credit account still appears in My Shops with zero accounts and zero debt. Pending/rejected businesses and their accounts/activity are excluded. Suspended/closed credit accounts remain readable with their stored account_status; these GETs grant no new credit or account permissions.

There are no mutation endpoints, ORM writes, commits or locks in the new service. Existing schemas/relationships are sufficient; no migration is needed. Successful responses carry Cache-Control: no-store. SQL/database failures return a generic 500 detail without underlying exception text. Query validation uses normal FastAPI 422 responses.

No profile names, phone numbers, addresses, email, password hashes, user IDs, creator IDs, order IDs, notes or idempotency keys are returned. Shop-private free-text notes are deliberately omitted; there is no distinct customer-public description field in the model. Only the business display name is exposed.

## Endpoints for Step 11.2
Prefix: /api/v1/customer. Use the existing bearer-token authentication mechanism; no new authentication or token store is introduced.

| Method | Path | Parameters | Response model |
| --- | --- | --- | --- |
| GET | /dashboard/summary | none | CustomerSummary |
| GET | /shops | page=1, page_size=20 | CustomerShops |
| GET | /credit-accounts | page=1, page_size=20 | CustomerCreditAccounts |
| GET | /transactions | page=1, page_size=20, optional credit_account_id | CustomerTransactions |

The full paths include the prefix, e.g. GET /api/v1/customer/dashboard/summary. Pagination bounds: page 1–1,000,000, page_size 1–100. Positive integer credit_account_id filters history only after rechecking ownership and approved-business scope. Foreign, unlinked, mismatched-business, pending-business and nonexistent account IDs all return the same 404 detail: Credit account not found. Zero/negative/non-integer IDs return 422. Unknown identity query parameters do not change scope.

Shops sort by business_id ascending. Accounts sort by opened_at descending, then credit_account_id descending. History sorts by recorded_at descending, then entry_id descending. High pages return empty lists while preserving total. Offset pagination is deterministic for a fixed dataset; newly inserted records between requests may shift page boundaries.

### Summary
Example for an unlinked user:

~~~json
{
  "currency": "LKR",
  "linked_shop_count": 0,
  "credit_account_count": 0,
  "total_outstanding_balance": "0.00",
  "recent_activity": []
}
~~~

linked_shop_count counts distinct approved shops, rather than profiles or ledger rows. credit_account_count counts scoped accounts, including closed/suspended accounts. total_outstanding_balance sums each account's nonnegative debt independently; an advance on one account never offsets another account's debt. recent_activity contains at most five transaction objects with the same structure as history.

### My Shops
Envelope: currency, total, page, page_size, shops.
Each shop: business_id, business_name, credit_account_count, outstanding_balance.
Repeated profiles in one business produce one shop row and do not multiply balances. No-account shops remain visible.

### My Credit Accounts
Envelope: currency, total, page, page_size, credit_accounts.
Each account: credit_account_id, business_id, business_name, account_status, credit_limit, outstanding_balance, advance_balance, available_credit, opened_at.
credit_limit, outstanding_balance, advance_balance and available_credit are exact two-decimal strings; opened_at is a datetime. Credit limit is the stored Numeric value on the user's own account. available_credit is the existing arithmetic position, not an authorization to make purchases on an inactive account.

### Transaction History and Recent Activity
Envelope: currency, total, page, page_size, transactions.
Each transaction: entry_id, credit_account_id, business_id, business_name, entry_type, recorded_at, amount, balance_delta, reference, status.
entry_type is credit_sale, repayment or reversal. status is recorded, reversed or reversal. reference is the stored receipt number, otherwise TXN-{entry_id}. amount is the stored positive amount; balance_delta is signed and represents the original sale/repayment effect or the opposite full original effect for a reversal. Original rows are retained and marked reversed; don't remove a reversed original and also apply its reversal when reconstructing a chronological total.

Legacy reversal amounts can differ from their original. For example a recorded reversal amount of 1.00 can cancel a full 100.25 sale; balance_delta then equals -100.25. Invalid reversal targets/types/chronology on a displayed page return a generic 409 rather than inventing a financial effect or exposing another account's original. No running balance is calculated from a history page.

All money is currency LKR, serialized as strings with exactly two decimal places. Keep Decimal/string precision in the UI; format for display rather than summing currency with binary floating point. opened_at and recorded_at follow the existing naive database wall-clock timestamps, serialized as ISO datetimes without adding a timezone offset. The frontend must not silently treat these as UTC.

## Financial implementation
Complete effective histories are aggregated in SQL using a same-account NOT EXISTS reversal predicate, matching ledger_service.effective_entries. No unbounded ledger/profile ORM list is materialized. Account/shop/history lists have bounded SQL LIMIT/OFFSET queries; totals and summary values use SQL aggregates. Existing entry_delta and balance_position helpers are reused for displayed transaction effects and account positions. Decimal arithmetic and exact string formatting are retained throughout. No Shop Owner service or financial rule was changed.

## Files
Created:
- backend/app/routers/customer.py
- backend/app/schemas/customer_dashboard.py
- backend/app/services/customer_dashboard_service.py
- backend/tests/test_customer_dashboard.py
- docs/day11-customer-dashboard-backend.md

Modified: backend/app/main.py only to register the customer router under the existing /api/v1 prefix. Frontend, login/registration, ledger, reminder, WhatsApp, notification and database implementations are unchanged. The user's pre-existing .gitignore changes remain untouched. No commit or push.

## Verification
Before tests, the Python child process sets MYSQL_DATABASE=lankapex_test_db before importing settings, checks both settings and engine database names, executes SELECT DATABASE(), and requires the actual selected database to equal lankapex_test_db. Existing pytest guards and outer rollback fixtures remain enabled. No database reset, migration or development-account seeding occurs.

Targeted command: guarded Python launcher -> pytest -q --tb=short -p no:cacheprovider tests/test_customer_dashboard.py.
Targeted result: 38 passed, 0 failed, 0 skipped.

Coverage includes unlinked identities with matching contact details, one/multiple shops/profiles/accounts, no-account shops, empty histories, sales/partial/full repayment, per-account advances, complete-history totals, same-account reversals, cross-account malformed reversals, large Decimal totals, all role boundaries, inactive users, hidden/unlinked/pending/mismatched records, identifier tampering, bounded pagination and stable ordering, minimal schemas, sanitized errors, write-method rejection and absence of data-mutation SQL.

Full regression command: guarded Python launcher -> pytest -q --tb=no -p no:cacheprovider --junitxml=../.server-logs/day11-backend-full.xml.
Full result: 683 passed, 0 failed, 0 skipped in 110.52 seconds. This includes the 38 new customer tests and all 645 existing regression tests. The only warning is from the existing tampered-token test deliberately using a different short signing key. OpenAPI inspection confirmed exactly four customer paths, each exposing GET only. git diff --check passed.

## Readiness and limitations
The read-only contract is ready for Step 11.2; targeted and full backend regression verification passed. No Customer Dashboard frontend, shopping, order or delivery feature is implemented here. The existing Customer frontend remains a placeholder. New/unlinked users will see empty dashboards; secure account linking is a future product/security workflow, not silently activated in this step. Existing running backend processes must reload/restart to expose newly registered routes if they were started without --reload.
