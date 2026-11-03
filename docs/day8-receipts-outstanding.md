# Day 8 Step 8.6 - Receipts and outstanding payment management

## Existing features reused

Reused LedgerEntry, CreditAccount, CustomerProfile, Business, existing unique receipt/idempotency/reversal constraints, JWT Shop Owner authorization, active owner membership and approved-business helper. Existing ledger_service effective balances, customer listing, financial write services, account locks, and reversal behavior are unchanged. The Repayments page, customer selection, styling, request persistence, and safe retries remain intact. Reports remains an unimplemented sidebar item; this step uses existing Repayments cards and tables rather than creating another dashboard.

## APIs

All routes are under /api/v1/shop-owner and require JWT Shop Owner role, an active owner membership and an approved selected business. Positive signed BIGINT identifiers are validated. Successful responses send Cache-Control: no-store. SQLAlchemy failures return a generic 500 without internal diagnostics.

- GET /repayments/{repayment_id}/receipt?business_id=...
- GET /customers/{customer_id}/statement?business_id=...&start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
- GET /outstanding-payments?business_id=...&search=...&outstanding_only=true&page=1&page_size=20

Outstanding search is literal, case-insensitive over name, phone and address (maximum 150 characters). Defaults include all customers; page size 1-100. Business-wide totals and debtor count are independent of filters and page. filtered_customers reports matching rows. Responses include customers without accounts with zero debt and null limit/available credit.

## Receipt identity and status

The receipt query joins repayment -> credit account -> customer and verifies both creditor business and customer business. Non-repayments, missing rows and foreign records return 404. Normal independent request sessions only read committed rows; real independent-connection tests confirm uncommitted and rolled-back entries cannot be receipted.

Use the existing receipt_number exactly, including customer-supplied references. Every returned receipt also carries receipt_identifier = ledger-repayment:{entry_id}, protected by the existing primary key namespace. Legacy rows with no number remain unmodified and display 'Ledger repayment #{entry_id}' as a stable reference, not a newly assigned receipt number. GET never allocates or saves numbers. Existing repayment writers already generate RP-UUID references with a database UNIQUE constraint; existing concurrency regression covers simultaneous duplicate submissions and references. No numbering migration or historical backfill is needed.

Receipt status is current: recorded or reversed, with reversal transaction ID/time. Original amount/reference remain visible. Reversed receipts prominently say REVERSED / VOID and state that the repayment no longer settles debt. A reversal row itself is not a repayment receipt. Receipt data includes actual business/customer identity, shop address/phone, amount as a decimal string, LKR, recorded method/time and notes. Stored method values are preserved for legacy records; this does not perform electronic payment verification. There is no separate transaction-reference field; the existing receipt_number is the transaction reference when populated.

## Statements: chronological event rules

Dates are inclusive calendar dates in the existing database recorded_at clock. SQL DATETIME has no timezone offset; no new timezone assumption or conversion is introduced. Entries are ordered by recorded_at, entry_id. End date 9999-12-31 is rejected to avoid exclusive-end overflow; reversed ranges and malformed dates return 422.

Opening balance = signed activity strictly before the start-day midnight.
Closing balance = opening + period credit sales - period repayments + signed period reversal impact.
Sale delta is positive, repayment delta negative. A reversal posts the opposite full original delta on the reversal's recorded date, without deleting the original event from the statement. That matches current effective-ledger cancellation when all valid events are included. A later reversal does not retrospectively alter an earlier statement period. Original statuses are as of the selected period end; receipt status, fetched separately, is current.

Debit, credit and running balance show effective signed impacts. amount preserves each actual stored amount, even if a legacy reversal's descriptive amount differs from its original; the original is canceled in full to match existing ledger semantics. Negative opening/closing balances are preserved as advances rather than silently clamped. Outstanding at period end is max(closing, 0); advance is max(-closing, 0). No historical credit limit or available credit is invented.

Unsupported missing/cross-account/reversal-of-reversal targets or original events ordered after their reversal cause a 409 disclosure rather than an invented balance. No entries are edited. These are reconstructions from stored recorded timestamps, not immutable issued snapshots: there is no transaction edit history or historical business/customer identity snapshot. The API and displayed statement disclose those limits. Clock convention and immutable issued statements would need a separate approved design if required.

## Outstanding and overdue rules

Reuse list_business_customers, which calculates the existing effective ledger and excludes reversed originals. Per-account debt = max(net ledger balance, 0). Business total sums each customer's debt; another customer's advance cannot offset it. Available credit = max(limit - debt, 0). Suspended/closed balances remain included. No unrelated balance cache is created.

No repayment-to-sale allocation records exist. due_at and payment terms alone cannot establish exactly which sale remains unpaid. Therefore overdue_amount is null throughout this API and the UI shows 'Unavailable' with the allocation explanation. Existing dashboard overdue remains unavailable. No FIFO allocation policy or fabricated KPI was introduced.

The API paginates results server-side and uses a constant number of customer/account/ledger queries. To preserve established calculations and whole-business totals, it currently materializes business customer/ledger rows before filtering/pagination. Large businesses may need a tested SQL aggregation optimization later; no N+1 query loop was added.

## Frontend integration and printing

Repayments now has View Receipt and Print Receipt on confirmed success and effective history records. Print Receipt first fetches/validates the backend document, then opens browser printing only after rendering. The existing repayment submission response is never fabricated into a receipt. Failed/unknown records show an error, no successful document or enabled print control.

A compact Outstanding Payments & Statements section reuses existing navy/teal cards and tables. It shows real business totals, debtor count, customer balances, limits, available credit, search, outstanding-only filter, pagination, loading/error/empty states and a customer selection action. It refreshes after customer detail refreshes, including confirmed repayments. Selected customer statements have date-range inputs, opening/closing amounts, transaction history, reversal details and receipt actions, including for reversed repayments omitted from effective history.

Documents use modal portals, keyboard Escape/Tab handling, print/PDF controls and print-only styling. Printing hides application chrome and all but the top document, hides controls, repeats statement table headings, wraps long references, and preserves ordinary page printing when no document is open. JSX escapes customer/shop/notes text. Browser rendering and print-preview verification still require manual confirmation below.

Read controllers abort and ignore superseded results, validate business/customer/transaction/date-range scope, clear on failure, and never write financial transactions. Modal statement scope follows customer/detail changes. Receipt/status and outstanding values are server authoritative. Exact decimal-string formatting also supports business aggregates larger than a single Numeric(14,2) entry.

## Files in this step

Created backend:
- backend/app/schemas/financial_documents.py
- backend/app/services/shop_owner_financial_documents_service.py
- backend/tests/test_financial_documents.py

Modified backend:
- backend/app/routers/shop_owner.py (three GET routes and read/error helper)
- backend/tests/test_day7_integration.py (replace outdated six-route count with the exact seven-route set, keeping duplicate/OpenAPI checks)

Created frontend:
- frontend/src/pages/shopOwner/FinancialDocuments.jsx
- frontend/src/pages/shopOwner/financialDocuments.css
- frontend/src/services/shopOwnerFinancialDocumentService.js
- frontend/src/utils/financialDocuments.js
- frontend/tests/financialDocuments.test.js
- frontend/tests/financialDocumentsView.test.js

Modified frontend:
- frontend/src/pages/shopOwner/ShopOwnerRepayments.jsx (receipt actions and compact outstanding/statement integration)

Created report: docs/day8-receipts-outstanding.md. Earlier dirty working-tree files were preserved; no commit or push.

## Database safety and migration status

Before pytest, settings.MYSQL_DATABASE, engine.url.database and SELECT DATABASE() all verified lankapex_test_db. Actual isolation REPEATABLE-READ. Existing unique receipt, idempotency and single reversal indexes verified. Initial counts for users, businesses, business_members, customer_profiles, credit_accounts, ledger_entries and business_approval_audits were all zero.

Rollback/savepoint fixtures isolate ordinary tests. The existing independent-connection fixture commits unique fixture-owned seeds, then deletes only its exact owned IDs; no table reset or development transaction is used. Frontend tests use mocked APIs/Axios adapters, with no development-database financial writes.

Alembic chain remains 79d8d51548c6 -> b2a1c4d6e8f0. No models changed, no migration created/applied, and no development schema/data modification was performed by this step.

## Manual browser verification

Browser automation inventory reported no enabled apps or browsers. Interactive authenticated navigation and print preview could not be tested. Actual JSX rendering, Axios contracts, modal/action gating, print stylesheet conditions, existing page regression and Vite compilation are covered automatically; those do not verify browser pagination or physical print output.

1. Start backend on 8001 and frontend using existing environment, then sign in as an approved Shop Owner. Prefer an isolated test environment for new financial entries.
2. Open Repayments from the existing sidebar and select the business/customer. Confirm original styling, navigation, current balance and method controls remain intact.
3. On an existing committed payment, view the receipt twice: identity/reference/amount must remain the same. Print and Save PDF: only that receipt should appear, with shop details, LKR, method and recorded date; no sidebar, application form, or modal controls.
4. Open a customer statement spanning sales, partial payments and later reversals. Compare opening/closing and date boundaries with known test fixtures. Fetch a reversed repayment receipt from the statement: it must show REVERSED / VOID. Print it while the statement is open and confirm only the top receipt prints; close it and print the statement separately.
5. Search and page outstanding customers, toggle outstanding-only, include a no-account customer, and verify total debt is unchanged by filters. Compare a selected customer's fresh details, Credit Sales and Repayments balances. Overdue must say Unavailable.
6. Switch business/customer during loading, retry reads after a simulated failure, test keyboard close/tab behavior, and verify failed receipt requests never show or print a successful receipt.

## Remaining decisions and limitations

No business decision blocks supported receipt, statement or outstanding functionality. Exact overdue requires a confirmed sale-allocation policy and an allocation design; it was deliberately left unavailable. A confirmed timezone convention, immutable issued-document snapshots, separate bank-reference storage, or statutory/sequential receipt numbering would be separate requirements. Existing UUID receipt numbering is preserved. Reminder sending, payment gateway verification and unrelated Reports features are outside this step.

## Verification results

- Focused backend: MYSQL_DATABASE=lankapex_test_db ./.venv/Scripts/python.exe -m pytest tests/test_financial_documents.py -v -p no:cacheprovider: 58 passed, 0 failed, 0 skipped, exit 0 (30.42 seconds).
- Frontend: npm.cmd test: 153 passed, 0 failed, 0 skipped, exit 0 (29.750 seconds). All API responses are controlled/mocked. Includes existing Credit Sales, Repayments and Customer Management regression coverage.
- Production build: npm.cmd run build: passed, exit 0, 2138 modules transformed (7.27 seconds).
- Targeted ESLint: financialDocuments.js, shopOwnerFinancialDocumentService.js and FinancialDocuments.jsx passed, exit 0.
- Python syntax: all five new/changed Python files parsed successfully. All three GET routes registered once with their typed OpenAPI response schemas.
- git diff --check passed.

The first full backend regression found an existing route-count assertion expecting six customer operations. The new statement route made seven; 457 other tests passed. The test now checks the exact complete route set, while retaining duplicate and OpenAPI checks. No financial assertion was weakened. Final regression result and cleanup verification follow below.

Final backend regression: MYSQL_DATABASE=lankapex_test_db ./.venv/Scripts/python.exe -m pytest -v -p no:cacheprovider: 458 passed, 0 failed, 0 skipped, exit 0 (116.03 seconds). One existing InsecureKeyLengthWarning arises from the deliberately short wrong key in the tampered-token test; no new warnings.

After the complete suite, configured and actual database were reverified as lankapex_test_db. All seven tracked test-table counts returned to their zero baseline, and Alembic revision remained b2a1c4d6e8f0. No tests ran against lankapex_db.

Supported Step 8.6 features and required automated checks are complete. Interactive print preview remains a documented manual verification limitation; exact overdue remains unavailable pending repayment allocation rules.
