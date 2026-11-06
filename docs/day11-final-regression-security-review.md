# Day 11 Step 11.5 - Customer Module Final Regression and Security Review

## A. Overall result: PARTIAL
The implemented read-only Customer module is verified by automated tests and build. Day 11 is not marked fully complete: there is no authorized product workflow to link a newly registered User to an existing shop-managed CustomerProfile, and authenticated desktop/mobile browser verification remains unavailable. Existing explicit CustomerProfile.user_id links are securely supported. No automatic phone/email matching or manual development-record linking was introduced to conceal this limitation.

A local checkpoint contains the verified Day 11 implementation and regression work only. It does not certify missing onboarding/linking or unperformed browser checks. Day 12 was not started.

## Repository audit
- Branch: main. Starting HEAD: 8d8a995 - Day 10: checkpoint tested authentication integration and regression review.
- Before this task, Step 11.1-11.4 application changes, tests and notes were uncommitted. The unrelated .gitignore additions for pem/key/credentials patterns were already present and remain excluded from the checkpoint.
- Reviewed all modified integration files and all untracked Day 11 source, test, fixture and documentation files. No unrelated application edits were found in the checkpoint inventory.
- Step 11.1 exists: Customer-only summary, linked shops, accounts and transactions, minimal Pydantic projections and complete-history ledger aggregates.
- Step 11.2 exists: CustomerLayout/sidebar, dashboard, welcome identity, scoped Axios reads, cancellation/session isolation and authorized notification reuse.
- Step 11.3 exists: My Shops, explicit multi-account chooser, account detail API/view, pagination and authoritative allowance/status.
- Step 11.4 exists: SQL-filtered history, transaction disclosures, period statement snapshot, authenticated server-side PDF export and exact response reconciliation.
- Models use CustomerProfile, CreditAccount and LedgerEntry. Sales/repayments are ledger event types. One credit account is permitted per customer profile; one User may have multiple explicitly linked profiles/accounts per shop.
- Existing auth, Shop Owner ledger/statement rules and Driver placeholder remain unchanged.

## B. Feature verification
| Feature | Route | Verification |
| --- | --- | --- |
| Dashboard | /customer/dashboard | Authenticated welcome name, actual aggregate counts/debt, bounded recent activity, loading/empty/error/expiry states |
| My Shops | /customer/shops | Distinct authorized businesses, actual shop totals, no-account state, paginated account choices |
| Account details | /customer/credit/:accountId | Ownership, exact balance/limit/available credit/status, authorized history and safe navigation |
| Transaction History | /customer/transactions | SQL shop/type/inclusive-date filters, stable bounded pagination, correct event labels/details, request replacement |
| Credit Statement | /customer/credit/:accountId/statement | Complete period snapshot, opening/sales/repayments/reversal/closing totals, running entries and date semantics |
| PDF export | Customer statement.pdf API | Authorized server calculation, branding, period/identity/LKR, safe filename/type, no client totals, failure handling |
| Notifications | /customer/notifications | Existing recipient-scoped bell/inbox workflow, no duplicate polling |

The sidebar uses real supported routes/anchors. Account pages link to filtered history and the statement viewer. Customers have no transaction-edit, shopping, ordering or payment actions. No production mock/fixture references were found in the customer source audit.

## Confirmed repair and coverage gaps
1. Reproduced a revoked-link case: after loading a statement, a PDF GET returning 404 left the previous snapshot visible because the downloader only escalated 401/403. A regression test failed before the fix. The minimal fix also escalates safe 404 account-unavailable responses, clearing the statement viewer through its existing denied-access path. The download is not saved and raw backend details are not displayed.
2. Strengthened the existing expired-JWT test with the required iat claim. Previously a missing iat could produce 401 before expiry was actually evaluated. No auth implementation changed.
3. Added two-Customer A/B isolation across summary/shops/accounts/history/details/statements/PDF, including a shared shop, distinct shops and ignored identity tampering.
4. Added direct agreement checks between Customer totals and existing Shop Owner positions for the same authorized accounts, including repayments, reversal, advance and unrelated debt.
5. Added a 5,001-entry account regression: history remains paginated and complete statements/PDFs reject rather than truncate.
6. Added SQL instrumentation verifying that statement/PDF GETs issue no INSERT/UPDATE/DELETE/REPLACE operations.

## C. Commands and actual results
Database preflight ran before mutating tests in a fresh Python child process. MYSQL_DATABASE was set to lankapex_test_db before importing configuration/database modules. Both settings.MYSQL_DATABASE and engine.url.database were asserted, then SELECT DATABASE() was asserted against the same name. Verified connection: mysql+pymysql, localhost:3306, database lankapex_test_db; credentials were omitted. Existing rollback/savepoint fixtures and database guards stayed enabled. No tests, resets or migrations were run against lankapex_db.

| Check | Command | Result |
| --- | --- | --- |
| Initial customer/financial/Shop Owner targeted backend | Guarded Python launcher -> pytest -q --tb=short -p no:cacheprovider tests/test_customer_dashboard.py tests/test_customer_history.py tests/test_shop_owner_dashboard.py tests/test_financial_documents.py | 202 passed, 0 failed/skipped |
| Updated targeted backend | Same command after added coverage | 206 passed, 0 failed/skipped |
| Revoked-access reproduction | node --test tests/customerHistory.test.js before repair | Expected failure: 9 passed, 1 failed; confirms defect |
| Targeted frontend after repair | node --test --test-concurrency=1 tests/customerHistory.test.js tests/customerHistoryView.test.js | 19 passed, 0 failed/skipped |
| Final full frontend | npm run test -- --test-concurrency=1 | 427 passed, 0 failed/skipped; 72.08 seconds |
| Final full backend | Guarded Python launcher -> pytest -q --tb=short -p no:cacheprovider | 725 passed, 0 failed/skipped; exit 0; 251.87 seconds |
| Full frontend lint | npm run lint | Existing baseline: 8 errors, 1 warning; no Day 11 finding |
| All reviewed Day 11 JS/JSX | node node_modules/eslint/bin/eslint.js with the explicit Day 11 source/test/fixture file list | Passed |
| Backend static check | ast.parse of all backend/app Python files | 51 files parsed successfully; no configured backend lint/type-check command was found |
| Production build after repair | npm run build | Passed, 2,177 transformed modules; existing large chunk warning |
| Patch whitespace | git diff --check and staged equivalent | Both passed |

Full-project lint findings are in unchanged Day 10 files: three set-state-in-effect errors in ShopOwnerCustomers.jsx, an unused Store import plus set-state-in-effect error and dependency warning in ShopOwnerDashboard.jsx, and three unused imports in repayments.test.js. git diff HEAD on those three files is empty. They are not new regressions and were not rewritten during this task.

The existing JWT tampered-token test can emit an HMAC key-length warning for its deliberately short alternate test key. No conclusion about production secrets is drawn from that test warning. No package vulnerability or external penetration scan was requested or performed.

## D. Security results
Verified JWT claims plus the active Customer role determine identity. Queries require CustomerProfile.user_id to match the authenticated User, profile business to match creditor business and business approval to be approved. Caller user_id/customer_id parameters do not prove ownership. Names, phone and email never create links. Admin/Shop Owner/Driver roles cannot impersonate Customers through ordinary customer endpoints.

Tests cover A/B/shared-business isolation, foreign/unlinked/pending/inconsistent-business accounts, unknown IDs, positive-ID/date/page bounds, missing/expired JWTs, wrong roles, safe 404 equivalence, private-field projection and read-only methods. Statements/PDFs re-authorize every request and expose neither staff/internal notes nor unrelated profile data. Financial results remain in memory; session/route/filter disposal aborts requests and rejects old generations. The new 404 downloader regression closes stale-view exposure after a revoked link is detected.

Successful financial reads use no-store; PDF responses use application/pdf, attachment filenames derived only from validated account/date parameters and nosniff. PDF inputs are server-authorized snapshots, never browser-supplied totals. Customer-controlled text is escaped and unsupported font glyphs fail safely.

## E. Financial integrity
Complete SQL ledger positions, existing Decimal entry_delta/balance_position and the trusted Shop Owner statement reconstruction are the calculation sources. No financial business rule was changed. Tests verify sale/partial/full repayment, zero debt, separate advances, distinct shop counting, no duplicate account aggregation, very large exact decimals, reversal of the full original, current-vs-period status, date boundaries, complete running balances and Shop Owner/customer agreement for the same accounts.

Opening + credit sales - repayments + reversal impact = closing. Outstanding remains nonnegative; negative positions are separately represented as advances. Browser BigInt minor units validate received statement reconciliation without fabricating authoritative totals or summing incomplete transaction pages. Recorded times retain the existing naive database clock. Periods are inclusive; historical statements are reconstructed from stored events/current identity details, not immutable issued documents.

PDF text/totals and multi-page layout verification from Step 11.4 is retained; this task reruns actual authorized PDF generation through backend tests. The renderer itself is unchanged in Step 11.5.

## F. UI and live checks
No browser/native app surface was connected (fresh inventory returned empty). Therefore 1536, 1366, 1024, 768 and 375 pixel measurements, real horizontal overflow/amount clipping checks, native mobile sidebar interaction, focus traversal and authenticated browser downloads were NOT performed. Responsive classes, wrapping, ARIA/disclosure markup, role-protected rendering and existing palette are covered by source/render tests, not presented as visual verification.

The local preview servers had stopped and were restarted for read-only probes. Frontend SPA shells for all five Customer pages returned 200. Backend health returned 200; anonymous summary/shops/accounts/history/statement/PDF requests returned 401. Those probes confirm routing and unauthenticated denial; they do not prove authenticated browser rendering. No development customers or financial records were created/read for fixture verification. Automated mutations remained on the test database.

## G. Build
The final production build after the confirmed fix passed. The existing JavaScript bundle remains above Vite's 500 kB warning threshold. No missing import/build error occurred. Day 11 lint and backend syntax checks passed; full-project baseline lint remains as listed above.

## H. Local Git checkpoint
Branch: main. The containing commit uses: Day 11: checkpoint customer credit views and regression verification.

Only the explicit reviewed Day 11 application/test/documentation list is staged. No git add -A, amend, reset, clean, force operation or push is used. Environment files, node_modules, dist, Python caches, .venv, server logs, synthetic QA artifacts and local database files are excluded. The pre-existing unrelated .gitignore edit remains uncommitted. The exact 39-file staged list matched the reviewed allowlist; staged blobs passed credential-pattern review and git diff --cached --check. No environment, generated, dependency, cache, database or unrelated file was staged.

The commit's own hash is reported after creation rather than embedded recursively in this file. It can also be obtained with git log -1 --format="%h %s" -- docs/day11-final-regression-security-review.md. The final assistant report states the actual remaining Git status.

## I. Remaining issues and severity
- High functional rollout gap: no authorized account-linking/onboarding workflow. Only existing explicit links yield data; newly registered/unlinked Customers receive safe empty results. This keeps overall Day 11 status PARTIAL rather than claiming onboarding complete. Adding such a workflow is outside this regression task.
- Medium verification gap: no authenticated desktop/mobile browser walkthrough at the requested widths. Manual checks are required before release.
- Medium export limitation: the embedded PDF font does not cover every script, including Sinhala/Tamil; unsupported text fails safely while the statement viewer remains available.
- Low bounded-export limitation: complete statement reconstruction is capped at 5,000 account ledger entries; larger accounts keep paginated history and need a larger verified export workflow.
- Low historical limitation: statements reconstruct recorded events and current identity, without immutable issuance/edit history.
- Low existing baseline: full-project lint findings and the large JavaScript bundle warning remain; no new Day 11 lint/build issue.

No unresolved cross-customer authorization or financial reconciliation failure has been found in the implemented read-only paths. Final full frontend/backend tests, Day 11 lint and production build passed before checkpoint staging.

## J. Next step
Day 12 - Delivery Driver Dashboard is the next planned module. It was not started. Resolve the account-linking rollout decision and complete the manual browser checks before treating Day 11 as fully complete for release.
