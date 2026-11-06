# Day 11 Step 11.4 - Customer Transaction History and Credit Statements

> Final Day 11 audit, security fixes, checkpoint and unresolved linking/browser limitations are recorded in [Step 11.5](day11-final-regression-security-review.md). The results below describe this earlier step.

## Audit and reused implementation
Steps 11.1-11.3 are present: customer JWT/role dependencies, explicit CustomerProfile.user_id links, approved-business/account scope, full-history ledger balance projections, paginated shops/accounts/transactions, customer layout/sidebar, My Shops, account details and existing tests. Shop Owner financial statements already reconstruct opening/closing positions using Decimal and post reversals on their recorded date. Credit sales and repayments are LedgerEntry event types, not separate models.

There was no customer statement route, history business/type/date filtering, or server-side PDF exporter. The Shop Owner UI uses a print workflow. This step reuses its trusted customer_statement calculation internally after explicit customer account authorization, without invoking Shop Owner HTTP endpoints or altering its financial rules. Existing AuthContext, protected roles, Axios JWT/session handling, notification polling, money formatter and customer resource reader are retained.

## Routes and UI
- /customer/transactions: Transaction History. Optional ?accountId=ID scopes history to one account. Shop choices come only from the existing paginated authorized shop list. All linked shops, credit-sale/repayment/all-types, inclusive start/end dates and previous/next result controls are supported.
- /customer/credit/:accountId/statement: Credit Statement viewer for one authorized linked account and an explicit period. Account details links to both account history and this statement route.

The existing Customer-only ProtectedRoute and layout wrap both pages. The sidebar Transactions link now uses its real route; Dashboard/My Shops/My Credit/Notifications retain supported destinations. No other role UI, login, registration, landing page or palette was changed.

History uses responsive cards with reference, recorded date, business, event type/status and exact LKR amount. An accessible inline details disclosure shows only fields already returned by the scoped list, with real account/statement links. There is no invented transaction-detail endpoint or description. Sales are credit purchases; repayment wording does not imply independent settlement verification. Reversals remain distinct.

Statements show shop/customer name, account reference, inclusive period, opening balance, period sales, repayment records, reversal impact, closing balance and all period entries with debit/credit/running balances. Reversal, clock and reconstruction limitations are displayed. The browser verifies exact amounts using BigInt minor units; this is response validation, not replacement financial calculation or a source of totals. Money rendering preserves exact decimal strings.

## Backend contracts
Prefix: /api/v1. All routes are authenticated Customer-only GETs.
- GET /customer/shops?page=N&page_size=10: existing linked-shop choices, bounded pagination.
- GET /customer/transactions: existing endpoint extended with optional business_id (positive), entry_type (credit_sale, repayment or reversal), start_date and end_date, preserving credit_account_id, page and page_size. Filters execute in SQL before counting/pagination; no browser-side unbounded history fetch. Order remains recorded_at descending, then entry_id descending. Response schema is unchanged.
- GET /customer/credit-accounts/{credit_account_id}/statement?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD: new complete read-only customer statement snapshot.
- GET /customer/credit-accounts/{credit_account_id}/statement.pdf with the same period: new authorized server-rendered PDF download.

Statement response contains currency=LKR, credit_account_id, business_id, business_name, customer_name, start_date, end_date, time_basis, reversal_policy, historical_limitations, opening_balance, total_credit_sales, total_repayments, reversal_impact, closing_balance, outstanding_balance, advance_balance, transactions. Entry fields are entry_id, entry_type, recorded_at, reference, amount, debit, credit, running_balance and status. Money is an exact two-decimal string.

Statement snapshots are complete, not paginated or silently truncated. To bound the existing full-history reconstruction, accounts above 5,000 ledger entries receive 422 and require shop assistance. The viewer explains this account-level limit. History itself remains available through SQL pagination.

## Authorization and isolation
Identity comes exclusively from the verified JWT and active Customer role. Account authorization explicitly requires CustomerProfile.user_id == authenticated user, profile business == account creditor business and approved Business status. Business filters require an approved explicit link; unauthorized/unknown businesses use the same safe 404. Foreign, unlinked, pending-business and inconsistent-business accounts use the same safe account 404. No client user_id, email/phone matching or automatic linking is used. Every JSON/PDF request independently checks ownership; PDF generation accepts no client financial totals.

The existing statement service is called only after authorization of the exact account/profile/business relationship. Its output is projected into customer-specific schemas, excluding profile IDs, phone/address, staff IDs, internal notes, payment method, idempotency keys and reversal linkage metadata. SQL failures and PDF generation failures use safe messages. Successful financial responses use Cache-Control: no-store; PDFs also use nosniff, application/pdf and an integer/date-only attachment filename.

## Financial definitions and dates
The existing Shop Owner statement service is the sole calculation source. It loads complete authorized account history, orders recorded events, computes Decimal opening position before the inclusive start, posts each period delta and provides period-end totals. A reversal posts the opposite full original delta on its recorded date, regardless of a legacy descriptive reversal amount. Invalid/cross-account/misordered reversal originals are rejected. Statement reversed status is as of period end, not current date. History-list status retains its existing current stored-reversal interpretation even when a date filter is applied.

Opening + credit sales - repayments + reversal impact = closing. Negative closing positions remain advances; outstanding is nonnegative. Period statements are reconstructed from currently stored recorded_at activity and current identity details, not immutable issued documents or an edit history. The original full-history balance rules remain unchanged.

Start/end are inclusive calendar dates in the existing naive database recorded clock. SQL uses start midnight <= recorded_at < midnight after end. End 9999-12-31 and reversed/impossible dates are rejected. The browser does not shift recorded dates into UTC or localize the stored clock. PDF generation date alone is explicitly UTC.

## Loading, errors and lifecycle
Invalid/unsafe route IDs show a generic unavailable message. Empty history identifies unmatched filters/unlinked accounts. Empty statement periods preserve real opening/closing values and show no activity. Invalid date periods hide the old resource and avoid dispatching invalid requests. Filter changes reset page to one; resource keys include filters/account/page and session identity. Statement date edits immediately remove the prior snapshot/download control until a new period is submitted.

Readers abort disposed/replaced requests, reject late generations and keep financial data only in memory. 401/403 from either lists, statements or PDF generation clears the page through the existing session/authorization flow. Network failures, slow responses and generation/download failures have safe retry controls. PDF download requests also cancel on resource disposal and cannot save late former-account results. Temporary download links are removed and blob URLs are revoked.

The Download PDF button exists only after a verified statement snapshot. The server independently regenerates current authorized records, so the UI explicitly notes a downloaded snapshot may reflect records committed after the displayed view. Response content type, Blob type and PDF signature are checked before saving. Raw Blob/error payloads are not displayed.

## PDF implementation and verification
Added ReportLab 4.4.10 as the only new application runtime requirement. It generates A4 PDFs in memory with LankaPex word branding, navy/teal, shop/customer identity, inclusive dates, UTC generation time, exact LKR totals, repeated table headings, full entries, calculation/clock limitations and page footers. Customer-controlled text is XML-escaped; numeric/date-only filenames avoid injection. Negative fractions such as LKR -0.01 retain their sign.

The embedded bundled Vera font makes exports portable/searchable and checks character coverage. Its supported characters do not cover all scripts, including Sinhala/Tamil. Unsupported text fails safely instead of generating incorrect boxes; the statement viewer remains available. Broader script shaping/font support is a known export limitation for a later improvement.

QA generated an 85-entry seven-page synthetic statement and an empty-period negative-fraction statement. pypdf verified complete final references, identity, totals, pagination and negative balances. PyMuPDF rendered all pages; the full contact sheet plus first/final pages were inspected for wrapping, table/header/footer alignment, clipping and readability. QA outputs are ignored under .server-logs, not production fixtures. pypdf/PyMuPDF were installed only as local verification tools and are not runtime requirements.

## Files
Created:
- backend/app/services/customer_statement_pdf.py
- backend/tests/test_customer_history.py
- frontend/src/pages/customer/TransactionHistory.jsx
- frontend/src/pages/customer/CreditStatement.jsx
- frontend/src/utils/customerHistory.js
- frontend/tests/customerHistory.test.js
- frontend/tests/customerHistoryView.test.js
- frontend/tests/fixtures/customerHistoryFixtures.js
- docs/day11-customer-history-statements.md

Extended:
- backend/app/routers/customer.py
- backend/app/services/customer_dashboard_service.py
- backend/app/schemas/customer_dashboard.py
- backend/requirements.txt
- frontend/src/App.jsx
- frontend/src/services/customerDashboardService.js
- frontend/src/components/customer/CustomerSidebar.jsx
- frontend/src/layouts/CustomerLayout.jsx
- frontend/src/pages/customer/CreditAccountDetails.jsx
- frontend/tests/customerDashboardView.test.js (Transactions destination)

Existing uncommitted Day 11 work and .gitignore changes are preserved. No commit/push, migrations, database resets, automatic customer links or financial edits were performed.

## Test/build results
- Targeted backend customer history plus dashboard/account tests: 76 passed, zero failures/skips. Before pytest, the launcher verified configured SQLAlchemy database and actual SELECT DATABASE() both equal lankapex_test_db. No tests were directed at lankapex_db.
- Targeted frontend history, statements, existing dashboard and account tests: 46 passed, zero failures/skips.
- Production npm run build: passed, 2,177 transformed modules. Existing large JavaScript chunk warning remains.
- Final ESLint on all changed customer frontend source/tests: passed. After removing one unused test import, the affected history/statement view file was rerun: 9 passed.
- Full frontend regression: node --test --test-concurrency=1 - 426 passed, zero failures/skips (141.37 seconds). Existing auth, customer and Shop Owner workflows remain covered.
- Full isolated backend regression on verified lankapex_test_db: 721 passed, zero failures/skips, exit 0 (472.25 seconds). One existing JWT-test HMAC-key-length warning remains.
- git diff --check: passed.

## Browser limitations and Step 11.5 readiness
No browser/native application surface was connected. React server rendering, protected routes, filters/API contracts and responsive class checks passed; actual desktop/mobile clicks, overflow measurements and authenticated download behavior in a browser were not verified. Perform that walkthrough before release.

Ready for Step 11.5 development with the passing regression results above. Known limitations are the 5,000-entry statement reconstruction cap, unsupported PDF font scripts, reconstructed/current rather than immutable issued snapshots, unavailable browser verification and the pre-existing bundle/full-project lint baseline. No blocker prevents authorized history or supported statement/PDF use.
