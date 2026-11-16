# Day 11 Customer financial failure investigation

Date: **2026-11-08, Asia/Colombo**. Investigated in order D11-T03 → D11-T01 →
D11-T02. The user confirmed the three FAIL labels had no captured logs or
expected-versus-actual results and requested reproduction before any application fix.

**Result: all three named scenarios PASS in the controlled current-source
reproductions. No cross-Customer disclosure, incorrect balance or broken history
was reproduced.** The cause of the original FAIL labels is **not established**;
this is not a claim that an unobserved manual failure could never occur.
No speculative application change or ledger repair was applied.

## Environment and safety

- Configured APP_ENV testing and MYSQL_DATABASE lankapex_test_db only in test
  processes. Verified settings, engine database, local host and actual
  SELECT DATABASE() before baseline tests. Session-start guard verifies identity
  again; test fixtures use request savepoints inside rollback-scoped transactions.
- Used synthetic Customer A/B, shared approved shop, separate CustomerProfile and
  CreditAccount rows, unlinked profile and synthetic ledger activity. No real
  Customer data was read/copied and lankapex_db was not connected to or modified.
- No balance recalculation/repair, migration, schema change or database reset.
- Development ports 8000 and 5173 were confirmed not accepting connections.
  No server was restarted. A process inventory query was permission-denied;
  loopback TCP checks independently confirmed the stopped state.
- Existing unrelated staged/untracked work is preserved. No commit, push,
  deployment or AI Summary work occurred.

## D11-T03 — cross-Customer isolation (checked first)

**Root-cause finding:** no authorization vulnerability reproduced. Current backend
scope is based on JWT User identity, not a supplied customer/user ID, matching
names/phone, or the ledger entry's author. The original failing observation is
unknown; there is no evidence supporting an IDOR fix at present.

Synthetic setup: Customers A/B share identical names/phone and an approved shop,
but have separate profile/account mappings. A owes **100.25**, B owes **777.77**.
Ledger records are authored by a synthetic Shop Owner to verify that created_by
does not determine the debtor. Both A→B and B→A attempts execute.

| Attempt | Expected | Actual HTTP/result |
| --- | --- | --- |
| Foreign account detail | Generic denial indistinguishable from nonexistent account | **404**, `{"detail":"Credit account not found"}` for both |
| Foreign filtered transaction history | Same generic denial | **404**, same body |
| Foreign statement and PDF | Authorize before calculating/rendering; generic denial | **404**, same body for both formats and absent IDs |
| Change user_id/customer_id query parameters | Must not select another Customer | **200**, authenticated user's own summary/history only |
| Supply foreign identity in GET request body | Body cannot replace authenticated identity | **200**, same own summary as legitimate request |
| POST to read-only transaction history | No mutation or identity-selection API | **405** |
| Read own account | Authorized scope works | **200** |

200 for undeclared identity selectors is **not an access grant to the selected
foreign identity**: the backend ignores those selectors and returns only the JWT
identity's records. No foreign balances/history/names are disclosed. Foreign and
nonexistent object IDs have the same status/body; no existence distinction was
observed. Authenticated responses carry no-store.

Affected/reviewed implementation:

- `backend/app/core/auth_dependencies.py`: fixed HS256 validation, required
  sub/exp/iat/access type, database User lookup, active status, Customer role.
- `backend/app/routers/customer.py`: all routes use authenticated Customer;
  no caller-selected customer/user identity feeds the service.
- `backend/app/services/customer_dashboard_service.py`: scoped_accounts joins
  CustomerProfile.user_id to JWT identity, profile/account business keys must
  agree, business must be approved. Detail/history/statement/PDF authorize that
  exact mapping. Ledger joins use credit_account_id, never name/phone/created_by.
- `backend/app/models/customer_profile.py`, `credit_account.py`, `ledger_entry.py`:
  User → business-specific CustomerProfile → CreditAccount → LedgerEntry mapping.
  A User ID is not a CustomerProfile ID. A ledger author is not account ownership.
- Frontend session keys and aborted/versioned readers prevent former-session or
  superseded responses repopulating the current view; backend enforcement remains
  necessary and independently exercised.

**Changes:** added two bidirectional regression instances in
`backend/tests/test_day11_customer_reported_failures.py`; no authorization or UI
code change justified. Existing JWT/role/expired/forged tests run separately below.

## D11-T01 — credit balances

**Root-cause finding:** no calculation defect reproduced. SQL positions aggregate
complete scoped effective ledger history, not the displayed/paginated history.
Existing Decimal/reversal rules are reused. The original FAIL cause remains unknown.

Controlled account: limit **1000.00**; January 31 sale **40.10** opening the tested
February period; February 1 sale **60.15**. An unlinked same-contact profile has
its own **999.99** sale and must not affect this User's amounts.

| Repayment | Expected/actual current outstanding and February closing | Statement opening | Period sales | Period repayments | HTTP |
| --- | --- | --- | --- | --- | --- |
| None | **100.25 / 100.25** | 40.10 | 60.15 | 0.00 | All reads **200** |
| Partial 25.10 | **75.15 / 75.15** | 40.10 | 60.15 | 25.10 | All reads **200** |
| Full 100.25 | **0.00 / 0.00** | 40.10 | 60.15 | 100.25 | All reads **200** |

Summary, My Shops, paginated account list, account detail and statement all agree.
Available credit is 899.75, 924.85 and 1000.00 respectively. Opening + period sales
− period repayments equals closing exactly using Decimal comparisons.
Unlinked rows are deliberately excluded; matching phone/name does not auto-link
them. A zero/empty response for an unlinked Customer is correct behavior, not a
reason to auto-repair a relationship or import a shop's other debts.

Affected/reviewed files: customer_dashboard_service.py account_positions,
account_data, dashboard_summary and scoped_accounts; ledger_service.py effective
entry/balance_position rules; shop_owner_financial_documents_service.py
customer_statement; customer_dashboard.py response schemas; frontend
CustomerDashboard.jsx, CreditAccountDetails.jsx, MyShops.jsx and money parsers.
Current account/summary balances and historical period closing may legitimately
differ if later activity exists; compare the same cutoff before declaring failure.

**Changes:** three exact no/partial/full repayment regressions added. No financial
formula or existing balance changed. No incorrect balance or security defect confirmed.

## D11-T02 — transaction/repayment history

**Root-cause finding:** no history/query/response-format defect reproduced.
The original FAIL cause remains unknown. Existing API type is **repayment**,
not `payment`; unsupported types are validation errors, not missing history.

Controlled history: January opening sale 40.10; February sale 60.15; partial
repayment 25.10 and remaining full repayment 75.15 at the same final-day second.

| Check | Expected | Actual |
| --- | --- | --- |
| February history, page_size 1, pages 1–3 | Total 3; descending timestamp then entry_id | **200**, full repayment → partial repayment → February sale |
| Types/amounts/deltas | repayment 75.15/-75.15; repayment 25.10/-25.10; credit_sale 60.15/+60.15 | Exact strings/types returned |
| Inclusive period boundaries | Include Feb 1 00:00:00 and Feb 28 23:59:59; exclude January opening row | Correct inclusion/exclusion |
| Type filters | Repayment two rows; sale one | **200**, correct IDs/order |
| Page beyond last | Empty list, stable total | **200**, empty transactions |
| Invalid `payment` type or reversed date period | Validation denial | **422** |
| Read side effects | Ledger rows unchanged | Exact pre/post row snapshot equal |

Response includes currency LKR, total/page/page_size, transactions with entry_type,
recorded_at, amount, signed balance_delta, reference and recorded/reversed/reversal
status. Dates follow recorded database clock semantics; the frontend does not
silently convert date-filter boundaries. Same-second ties are deterministic by ID.
Reversals remain distinct from repayments and baseline reversal tests pass.

Reviewed path: customerDashboardService.js GET history parameters →
TransactionHistory.jsx/HistoryPage → useCustomerRead → customerAccounts.js
parseCustomerPage → customerHistory.js parseHistory; recent dashboard uses
customerDashboard.js validators/reader. Parsers enforce currency, exact decimal
strings, requested account/shop/filter scope, bounded pagination and safe error
handling. Summary totals do not come from the latest five rows.

**Changes:** one focused history/repayment/date/pagination regression added. No
query, response schema or frontend rendering change is justified by execution.

## Tests and practical limits

- New named reproductions: **6 passed, 0 failed/skipped**, 6.20 seconds
  (T03 two, T01 three, T02 one).
- Existing Customer dashboard/history backend baseline: **80 passed**, 0 failed/
  skipped, 17.15 seconds, including JWT/role scope, reversal/statement/PDF, malformed
  account mapping, multiple shops and cross-session cases.
- Frontend Customer/dashboard/account/history/error/session selection:
  **104 passed**, 0 failed/skipped, 32.15 seconds.
- Additional finance/JWT/RBAC/password/statement regression: **238 passed**,
  0 failed/skipped, 105.22 seconds. Existing deliberately short wrong HMAC key
  warning and pytest cache-path warning were emitted, not suppressed.
- Across the three backend runs: **324 passes, zero failures/skips**. The
  frontend selection passed **104**. These are selected regressions, not a fresh
  full-application test-suite result.
- Existing pytest cache-path warning was emitted, not suppressed. No weakening of
  test assertions or authorization bypass. Dependency override changes only the
  test database session; actual JWT/role dependencies execute.

Logs under ignored `.server-logs/`: d11-customer-baseline.log,
d11-reproductions.log, d11-frontend.log, d11-finance-auth.log.
No live browser walkthrough was executed. No full-suite/build rerun is required
for a test/documentation-only change after relevant regressions pass.

## Remaining blockers and disposition

Separate migration-chain execution for lankapex_migration_verify_20261107 remains
**BLOCKED** by the previously documented MySQL permission failure. No new evidence
resolves it; no creation/elevation attempt or test-DB substitution. Read-compatible
test schema and passing synthetic API tests do not certify the development schema,
migration chain, restore or deployment. Existing broader release blockers remain.

The original FAIL labels should be tracked as **not reproduced under the stated
controlled cases**, with the original trigger/root cause unknown. The controlled
tests themselves are PASS. If a manual failure recurs, capture the role/session,
endpoint/query, timestamp/cutoff, expected and redacted actual status/body and
authorized relationship IDs, without passwords/tokens or real financial payloads.
Do not diagnose a missing link, stale schema, UI error or vulnerability without
that evidence. No speculative repair script or application change was made.

Files added in this task: this report and
`backend/tests/test_day11_customer_reported_failures.py`. All unrelated work is
preserved; no deployment/push or AI Summary work.
