# LankaPex Day 8 - Final integration and security checkpoint

Date: 2026-11-04 (Asia/Colombo). This report supersedes earlier step reports for final verification results. Original navy/teal layouts and Day 1-7 functionality are preserved.

## Supported features and APIs

Under /api/v1/shop-owner, with business_id required:
- POST /credit-sales
- POST /repayments
- GET /repayments/{repayment_id}/receipt
- GET /customers/{customer_id}/statement (inclusive start_date/end_date)
- GET /outstanding-payments (search, outstanding_only, page, page_size)

Existing customer details/list, account management, dashboard and recent transactions reuse the shared effective-ledger calculations. No duplicate routes or financial models were introduced.

All financial endpoints enforce real JWT Shop Owner role, active owner membership, approved business and business-scoped customer/account/document relationships. Request schemas reject unsupported fields, invalid precision, nonpositive amounts and unsupported manual methods. Database failures are rolled back and return sanitized errors. Document GETs are read-only and send no-store responses.

## Business and integrity rules

- Money uses Decimal on the server; form values are decimal strings with BigInt minor-unit checks. New entries have at most two decimal places within Numeric(14,2).
- New sales require an active account and may not exceed available credit. Repayments can settle active or suspended accounts; closed accounts reject new payments. No overpayments/new advances are accepted.
- Repayment methods: cash, bank_transfer, card, approved by the user. These are manual records, not verified electronic settlements.
- Both writers lock the same account row and use current locking ledger reads under MySQL REPEATABLE-READ. Existing database UNIQUE constraints protect global idempotency keys, receipt numbers and one reversal per original.
- An identical key/payload retry confirms its original entry (HTTP 200) with current balances; new writes return 201. Changed payload/account/type conflicts. Replays never reinstate a reversed entry.
- Database races test real independent connections and a blocking MySQL row lock, not just mocked APIs. Excessive simultaneous sales/repayments cannot jointly exceed the authoritative available amount. Failed writes roll back.
- Frontends block duplicate clicks, retain an uncertain request key, and prevent silently dispatching a changed intent. A new operation after uncertainty requires explicit manual ledger verification. Only an opaque hash/key/pending flag is persisted per user/browser tab. JWT uses existing sessionStorage; no Day 8 plaintext financial records or tokens are stored in localStorage.

## Receipts, statements and balances

Receipt retrieval reads only committed repayments. Existing receipt numbers stay unchanged. All receipts carry the primary-key-based stable ledger-repayment:{id} identifier; legacy unnumbered rows get a stable display reference without a numbering write. Current reversed receipts prominently show REVERSED / VOID; reversal rows cannot be ordinary receipts. Print/PDF controls use a fetched backend document and print-specific styles.

Statements preserve originals and apply the opposite full original delta at the reversal recorded time. Opening includes earlier activity; closing is opening + period sales - repayments + reversal impact. End dates are inclusive in the stored database clock, which has no offset. Negative raw balances are preserved as advances. Invalid reversal chronology/targets produce an explicit conflict. These are reconstructions, not immutable issued snapshots; historical edits and historical identity cannot be reconstructed from this schema.

Current per-customer debt is max(effective net balance, 0), available credit is max(limit - debt, 0), and business outstanding sums debts without offsetting another customer's advance. Search and result pagination keep business-wide totals unchanged. No-account customers have zero debt and null limit/available credit. Exact overdue remains unavailable: there are no reliable repayment-to-sale allocation records, and no FIFO policy was invented.

## Step 8.7 stabilization

Six new frontend regression cases reproduced two Credit Sales defects before the fix, then passed:
1. A 401/403/404/409/422 response while retrying an earlier uncertain sale could clear the persisted pending flag. The pending identity now remains unresolved until confirmed or explicitly checked; editing the intent cannot bypass it.
2. The saving state previously ended before the post-success refresh, permitting context/form changes while old reads were refreshing. It now remains locked through refresh completion.

Dashboard error logging now records generic messages rather than Axios error objects that may include authorization headers or financial responses. No layout/design change.

Added two real-JWT MySQL API lifecycle tests covering sale -> partial repayment -> full settlement -> stable receipts/retries, and repayment/sale reversals with retained originals and database rejection of a repeated reversal. At every stage they compare Customer Details, list, statement, outstanding and dashboard balances. Existing frontend tests verify the Credit Sales and Repayments views consume those scoped detail responses.

No public reversal-writing API was added. Reversal integrity tests exercise the existing LedgerEntry mechanism and database constraints directly in isolated fixtures; a future reversal-creation workflow needs its own authorization and account-lock policy.

## Verification environment and migrations

Before pytest, configured database, engine database and actual SELECT DATABASE() all verified lankapex_test_db. Initial tracked test-table counts were zero. Ordinary tests use outer transactions/savepoints. Real concurrent tests commit unique fixture-owned seeds and remove only their owned IDs. No development tables are reset or modified.

Executed read-only Alembic current, heads and history against the test configuration. Current and sole head are b2a1c4d6e8f0; chain is 79d8d51548c6 -> b2a1c4d6e8f0. No Day 8 schema migration is required or created/applied. Existing databases must have the listed head and existing ledger uniqueness constraints; read-only development Alembic/index metadata inspection also confirmed b2a1c4d6e8f0 and all three ledger uniqueness constraints. No development financial records were read or changed.

## Security and Git scope

Reviewed all Day 8 candidate source/tests/docs and tracked diffs. Pattern checks found no literal private keys, AWS/GitHub credentials, signed JWT literals or hardcoded application/database secrets in the candidates. No environment files, database dumps, dependency folders, virtualenv, generated build output or cache files are included. This is a focused source review/pattern scan, not a full external security audit.

The pre-existing unrelated .gitignore modification remains unstaged. Only reviewed Day 8 application code, tests and documentation are selected for the authorized local checkpoint. No push is authorized or performed.

## Browser limitations and manual checks

Browser tool inventory returned no enabled apps or browsers. Interactive login/navigation, browser console behavior, modal focus and print/PDF preview are UNVERIFIED; automated JSX/contract/CSS tests and a successful build do not substitute for them.

Manual checklist: log in as an approved Shop Owner; switch businesses/customers during loading; record partial/full payments in an isolated test environment; compare fresh Credit Sales, Repayments, Customer Details, statement and dashboard balances; verify a same-request retry after interrupting a response; view a reversed repayment receipt through a statement; print the receipt while a statement is open and confirm only the top document prints; test statement page breaks/PDF, search/no-account/empty/error states and protected-route redirects. Do not create financial test data in the development database.

## Remaining limitations

Exact overdue needs an approved allocation policy/design. Immutable issued snapshots and a timezone convention are separate requirements. Outstanding results are paginated but the current implementation materializes business ledger/customer rows for totals; large datasets may need SQL aggregation optimization. Existing unrelated onboarding/auth modules were not refactored. SMS/WhatsApp reminders, gateway integrations and unrelated Reports features remain outside scope.

## Actual final results

- Backend: MYSQL_DATABASE=lankapex_test_db ./.venv/Scripts/python.exe -m pytest -v -p no:cacheprovider: **460 passed, 0 failed, 0 skipped**, no collection/fixture errors, exit 0, 154.68 seconds. One pre-existing warning from the deliberately short wrong signing key in the tampered-token test.
- New full API lifecycle tests: **2 passed**, exit 0 (3.56 seconds).
- New frontend regression cases: initially 6 failures proving the defects, then **6 passed** after the two-line repair. No assertions were weakened.
- Frontend: npm.cmd test: **159 passed, 0 failed, 0 skipped**, exit 0 (28.052 seconds).
- Production: npm.cmd run build: **passed**, exit 0 (11.92 seconds), 2138 modules transformed.
- Targeted ESLint of the 11 Day 8 financial workflow/page/utility/service modules: passed, exit 0. Including ShopOwnerDashboard additionally reports two pre-existing errors (unused Store import and synchronous effect state reset) plus one dependency warning; all three were independently reproduced using the committed HEAD source. They are baseline lint debt, not new failures introduced by this checkpoint; broad Dashboard hook refactoring was left outside scope.
- Final test-table counts returned to their verified zero baseline. Test guard checks both configured and actual test DB before collection. No automated tests ran against lankapex_db.
- Alembic current/heads/history: no pending revision. Development metadata-only inspection also confirms the same head and required unique indexes. No migration applied.
- Browser/console/print-preview smoke tests: UNVERIFIED (no enabled browser), manual checks above.
- Git diff whitespace checks: passed; staged checks and checkpoint outcome are recorded below.

## Reviewed Day 8 checkpoint file inventory

- backend/app/routers/shop_owner.py
- backend/app/schemas/financial_documents.py
- backend/app/schemas/ledger.py
- backend/app/services/ledger_service.py
- backend/app/services/shop_owner_credit_sale_service.py
- backend/app/services/shop_owner_customer_details_service.py
- backend/app/services/shop_owner_customer_manage_service.py
- backend/app/services/shop_owner_customer_service.py
- backend/app/services/shop_owner_dashboard_service.py
- backend/app/services/shop_owner_financial_documents_service.py
- backend/app/services/shop_owner_repayment_service.py
- backend/tests/test_credit_sales_concurrency.py
- backend/tests/test_day7_integration.py
- backend/tests/test_day8_integration.py
- backend/tests/test_financial_documents.py
- backend/tests/test_repayments_concurrency.py
- backend/tests/test_shop_owner_credit_sales.py
- backend/tests/test_shop_owner_repayments.py
- docs/day8-credit-sales-backend.md
- docs/day8-credit-sales-frontend.md
- docs/day8-development-report.md
- docs/day8-receipts-outstanding.md
- docs/day8-repayments-backend.md
- docs/day8-repayments-frontend.md
- frontend/package.json
- frontend/src/App.jsx
- frontend/src/components/shopOwner/QuickActions.jsx
- frontend/src/components/shopOwner/ShopOwnerSidebar.jsx
- frontend/src/pages/shopOwner/FinancialDocuments.jsx
- frontend/src/pages/shopOwner/ShopOwnerCreditSales.jsx
- frontend/src/pages/shopOwner/ShopOwnerCustomers.jsx
- frontend/src/pages/shopOwner/ShopOwnerDashboard.jsx
- frontend/src/pages/shopOwner/ShopOwnerRepayments.jsx
- frontend/src/pages/shopOwner/creditSaleWorkflow.js
- frontend/src/pages/shopOwner/financialDocuments.css
- frontend/src/pages/shopOwner/repaymentWorkflow.js
- frontend/src/services/shopOwnerCreditSaleService.js
- frontend/src/services/shopOwnerFinancialDocumentService.js
- frontend/src/services/shopOwnerRepaymentService.js
- frontend/src/utils/creditSale.js
- frontend/src/utils/financialDocuments.js
- frontend/src/utils/repayment.js
- frontend/tests/creditSales.test.js
- frontend/tests/creditSalesView.test.js
- frontend/tests/financialDocuments.test.js
- frontend/tests/financialDocumentsView.test.js
- frontend/tests/repayments.test.js
- frontend/tests/repaymentsView.test.js

Staged review passed: 48 Day 8 source/test/documentation files, 4758 insertions and 140 deletions before this final note. git diff --cached --check and --stat were reviewed, and staged blobs were independently scanned for secret patterns and forbidden generated/environment artifacts. The unrelated .gitignore edit is excluded. Authorized local checkpoint message: feat: complete day 8 credit sales and repayment workflows. The commit ID is available from git log -1 after checkpoint creation; no remote push is performed.
