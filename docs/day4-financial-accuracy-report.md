# Day 4 — financial accuracy and end-to-end regression

Date: 2026-11-09 (Asia/Colombo). This report records automated tests of current source, not a fresh browser test of the running demo.

## Safety and scope

- Backend test process set `APP_ENV=testing` and `MYSQL_DATABASE=lankapex_test_db`. Before any write test, a read-only connection verified settings, engine URL target, and `SELECT DATABASE()` all identified **lankapex_test_db**. Pytest's session-start guard checks these again. The database was at revision `03b9c2d1e671`, with 21 total tables and no `customer_link_invitations` table.
- No connection or write to `lankapex_demo_db` or `lankapex_db` was made for this audit. No migration, schema change, reset, seed, grant, or live financial write was performed. Synthetic tests use the existing isolated test fixtures.
- No application code was changed during Day 4. Existing worktree changes were preserved.

## Results

| Area | Result | Evidence |
| --- | --- | --- |
| Credit sales, Owner and Customer balances, statements, financial documents, concurrency, cash/credit orders | **PASS** | 238 backend tests passed in the first focused run. |
| Repayments, repayment races, catalogue, delivery, Admin approvals/security | **PASS** | 225 backend tests passed in the second focused run. |
| Credit, statements, customer linking UI, order tracking/fulfilment, delivery tracking, Admin management | **PASS** | 210 frontend tests passed. |
| Catalogue, cart/shopping, Driver jobs/deliveries, Owner deliveries, Admin dashboard | **PASS** | 214 frontend tests passed. |
| Six-digit invitation issue/accept/replay integration | **BLOCKED** | Backend test schema lacks `customer_link_invitations`; `test_customer_link.py` was not run. Frontend form/API contract test passed, but cannot establish backend replay behavior. |

Total executed: **463 backend passed, 424 frontend passed, 0 failed, 0 skipped**. The first backend run emitted one pytest cache-permission warning after tests passed; the second disabled the cache provider. These selected suites are not a full repository regression run.

## Financial invariants verified in the passing tests

- `ledger_entries.amount` is `NUMERIC(14,2)`; Pydantic rejects zero, negative, over-precision, non-finite, oversized, and malformed amounts with 422. A 600.30 credit sale followed by a 100.10 repayment yields 500.20 outstanding and 499.80 available on a 1000.00 limit. Full 600.30 repayment yields 0.00 outstanding without closing the account. A 600.31 repayment is rejected with 409 and no new entry.
- Effective ledger balances use `Decimal`, count credit sales positively and repayments negatively, and exclude reversed originals. Legacy advances are reported separately; they cannot fund new credit beyond the account limit or offset a different customer's debt.
- Repeated requests with the same idempotency key and identical payload return the original entry; changed payloads and cross-account/cross-type key reuse conflict. Concurrent sale/repayment tests verify account locking and a single winning financial write. Unique receipt and idempotency constraints are enforced by MySQL.
- Owner customer rows, Owner statements, linked Customer summary/accounts/history/statement, and order credit posting were exercised. Tests compare Owner and Customer balances for the same authorized accounts, including a 100.25 sale and 25.10 partial repayment yielding 75.15.
- Credit order submission creates no debt. Owner approval creates one linked credit sale; repeated approval does not post again. Rejected or cancelled pending credit orders create no ledger entry. Cash orders never create credit debt and retain their quoted price snapshot.
- JWT role and account checks, business ownership, CustomerProfile `user_id` scoping, foreign account 404 responses, and foreign statement/history isolation passed. This is evidence for the tested paths, not an assertion about all possible attack paths.

## Remaining risks and next actions

1. **High priority:** the isolated test database is behind the current migration head `6e3f2c1a9b04`. A separately reviewed, guarded test-schema upgrade is needed before running the six-digit invitation backend test, especially expiry, recipient binding, single use, replay, and concurrency. Do not use the demo database for that test.
2. Six-digit codes have limited entropy. The development app applies a per-account and per-peer acceptance rate limit; production external rate-limit enforcement must be configured and verified before any public rollout. Code-collision handling and concurrent reissuance also need a targeted test on the upgraded isolated schema.
3. The automated suites use synthetic fixtures and do not prove the current running demo process, demo schema, or real browser session is aligned with current source. Preserve the working viva data; use read-only checks for demo verification until a separate change window is authorized.
4. Manual/external cash settlement is recorded as `unpaid` in the cash-order flow. The automated tests confirm no false payment claim; they do not verify physical cash collection.
