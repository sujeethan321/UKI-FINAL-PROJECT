# Day 14 Step 14.5 — Shopping final regression and financial security review

## Overall status

**PASS for the Day 14 module.** Required functional/financial regressions, production build and executed browser checks pass. Repository-wide lint retains the documented Day 13 baseline of eight errors and one warning. These unchanged files are outside this checkpoint; all Day 14 frontend files pass scoped lint. No Day 15 development is included.

## Repository audit and implemented scope

Audited branch main at aa5eed8 (Day 13 checkpoint), tracked/untracked changes, actual API registration, schemas, SQLAlchemy models, Decimal pricing, transaction services, React routes/providers, migrations, tests and Day 14 progress notes. Steps 14.1–14.4 are implemented, not placeholders:

| Step | Verified implementation |
|---|---|
| 14.1 Catalogue backend | Business-owned ProductCategory/Product, strict prices and publication, approved owner management, safe Customer projections and migrations |
| 14.2 Owner product UI | Add/edit categories and products, prices, manual availability, publication/unpublication/archive, paginated filters and business selection |
| 14.3 Customer browsing | Eligible shop discovery/search, shop/product details, category/availability filters, pagination, image placeholders and exact LKR formatting |
| 14.4 Cart and orders | Single-shop memory cart, explicit replacement, current server quotes, cash/credit checkout, persisted price snapshots, retry keys, Customer history and owner management |

There is no separate CreditSale or Repayment model: the existing LedgerEntry entry_type values implement those financial records. Order and OrderItem were added in Step 14.4 and reuse CreditAccount and the existing trusted sale service. Actual order values are submitted/approved/rejected/processing/completed/cancelled; payment methods cash/credit; payment states unpaid/pending/posted. The optional delivery link is intentionally absent, and order APIs never create a delivery request or assignment. Inventory, online payments, taxes, fees and cash-settlement records are outside the supported schema.

## Database safety and migrations

Before mutation, settings.MYSQL_DATABASE, engine.url.database and SELECT DATABASE() all independently reported lankapex_test_db. backend/tests/conftest.py aborts before collection for any other configured/actual database. Browser seed/cleanup utilities repeat the guard and validate exact nonce-owned business/user identities. Fixtures are rollback-isolated except the independent-connection races and browser fixtures, which clean their exact owned rows. Committed browser fixtures are never run concurrently with backend suites.

Test revision is d0e6f9a8b348 after c9d5e8f7a237. Alembic check reports no new upgrade operations. Existing additive migrations preserve prior tables/data and destructive downgrades are refused. Development remains at b8c4d7e6f126; test remains at d0e6f9a8b348, independently read again after cleanup. Development migration/reset was not performed. Pending catalogue/order migration instructions remain in [shopping implementation](day14-shopping-orders.md). No database credentials are printed or staged.

## Actual API contracts and authorization

All paths below are under /api/v1:

- Owner: GET/POST /shop-owner/categories and /shop-owner/products; PATCH /shop-owner/categories/{category_id}; GET/PATCH /shop-owner/products/{product_id}; GET /shop-owner/catalogue/summary. Required business_id is verified through current approved-business/active-owner membership checks.
- Customer catalogue (base /customer/catalogue): GET /shops, /shops/{business_id}, /shops/{business_id}/categories, /shops/{business_id}/products and /shops/{business_id}/products/{product_id}.
- Customer orders: POST /customer/orders/quote, POST/GET /customer/orders, GET /customer/orders/{order_id}, POST /customer/orders/{order_id}/decision (cancel own submitted order only).
- Owner orders: GET /shop-owner/orders, GET /shop-owner/orders/{order_id}, POST /shop-owner/orders/{order_id}/decision; business_id is required and checked independently of order IDs.

Customer frontend routes: /customer/shops/explore, /customer/explore/:businessId, product detail under /products/:productId, /customer/cart, /customer/checkout, /customer/orders and /customer/orders/:orderId. Owner frontend: /shop-owner/products, /shop-owner/orders and /shop-owner/orders/:orderId?business_id=... . The legacy /shop-owner/credit-orders route redirects to Orders.

JWT signature/expiry/type/sub and active stored user/role are authoritative. Customer, Driver and Admin roles cannot use owner management routes; owners/Drivers/Admin cannot create Customer orders. Public Admin registration remains blocked by the existing authentication suite. Foreign order/product/business IDs cannot bypass scope. Public catalogue excludes draft/archive/inactive-category/unapproved-business data. Responses use explicit projections, safe errors and no-store headers. User contact details, account IDs, idempotency keys/hashes and private notes are not exposed through order responses. No contact-matching account link or client-supplied account/customer ID is accepted.

## Financial integrity and lifecycle

Submission reads current eligible products/categories and authoritative Decimal prices, validates 1–99 quantities and at most 50 distinct products, computes bounded totals and saves immutable name/unit-price/line-total snapshots. Client prices/totals are forbidden. Submission of Credit creates no debt or delivery record; pending requests do not reserve credit. Available credit is checked again at approval using existing effective-ledger balance/limit rules, including reversals and advances.

Approval requires an active approved owner, current Customer linkage and the saved active same-business credit account. Current user/order/account/ledger locks serialize approval and limit checks. The existing record_credit_sale service creates the only sale; it does not commit. LedgerEntry.order_id, the unique Order.credit_sale_id, posted payment state and approved order status are persisted in one route transaction. A colliding manual sale is not adopted. Replays and concurrent approvals cannot create a second debt or notification; competing orders cannot jointly exceed the available limit. Approval/rejection races produce a single valid outcome. Errors after ledger flush and at commit roll back order, ledger and notifications.

Credit transitions: submitted -> approved -> processing -> completed. Submitted may instead be rejected/cancelled; both create no debt. Cash: submitted -> processing -> completed, or submitted -> rejected/cancelled. Cash always remains unpaid; no credit entry or invented collection confirmation is created. Customer can cancel only their own submitted order. Posted credit cannot be rejected/cancelled without a separate supported reversal workflow. Terminal orders cannot be reopened. Same successful action replays do not repeat side effects.

The final integration test starts with a real 100.00 sale and 30.00 repayment, approves a 250.50 order, and verifies owner/customer statements and account details agree on 320.50. The generated CS receipt reference appears in both statements. Existing repayment rows are byte-for-byte unchanged; later product price/archive changes preserve the order total. Existing delivery suites and the new order/delivery snapshot assertion verify delivery isolation.

## Notifications and privacy

New order events go to active authorized owners; approval/rejection/processing/completion/cancellation events go to the active Customer. Financial sale notification remains its own existing event. Recipient resolution uses persisted identities, not client metadata. All notifications share the order transaction; event/recipient uniqueness and replay branches prevent duplicates. Failed approval/commit leaves no success event. Foreign users cannot list/read-mark these notifications; event links resolve protected routes and recheck backend scope. No WhatsApp or other external message is sent.

## Confirmed fixes in Step 14.5

1. Reproduced an unconfirmed Credit checkout displaying Cash after the page remounted, even though its frozen retry payload was Credit. Added a failing regression and derived the selected radio from pending.payment_method. The existing key/payload remains unchanged, and the new test passes. Browser coverage reopens the checkout before retrying the deliberately lost successful response.
2. Restored the landing headline from Ma2xnagement to Management after the user explicitly chose that correction. Existing headline tests were preserved and the full frontend suite passes.
3. Expanded safe browser checks for keep/replace shop-cart choices and credit rejection. The owner catalogue harness ignores only Chrome's expected cancelled-interception error when a UI request is aborted; actual request failures still fail verification.

4. Visual review found that fixed mobile menu buttons could float over shopping content after scrolling. Kept Customer and Shop Owner headers sticky below the desktop breakpoint, retaining desktop positioning and all colors/spacing. Added a browser bounding-box assertion that the menu remains within the header after scrolling; screenshots reset scroll before capture.

No financial calculation, delivery assignment, dashboard design or LankaPex palette was rewritten.

## Actual test/build results

| Check | Passed | Failed | Skipped | Notes |
|---|---:|---:|---:|---|
| New final MySQL integration tests | 6 | 0 | 0 | Statements, balances, repayment preservation, notifications, rollback, delivery isolation |
| Full backend regression | 969 | 0 | 0 | 159.89s; includes catalogue, orders, financial services, JWT/RBAC, notifications and independent MySQL concurrency |
| Targeted shopping frontend | 22 | 0 | 0 | Includes the new pending-method regression |
| Full frontend regression | 610 | 0 | 0 | Final rerun after mobile fix: 55.84s (initial run: 95.87s); single worker uses established suite configuration without weakening assertions |
| Production npm build | — | 0 | — | npm.cmd --prefix frontend run build; Vite 8.3.5, final build 2.79s |
| Scoped Day 14 ESLint | 33 files | 0 | — | Application sources, tests and scripts |
| Full repository ESLint | — | 8 errors | — | Existing 1 warning; unchanged baseline files |
| Python syntax | 80 files | 0 | — | AST parse of app/scripts/migrations; no configured backend linter/typecheck exists |
| Alembic metadata check | — | 0 | — | No new upgrade operations detected |

Build: JS 756.46 kB / gzip 204.92 kB; CSS 63.53 kB / gzip 13.08 kB. Existing >500 kB chunk advisory remains. The backend warning is the existing intentionally short HMAC key in test_tampered_token_rejected, not an application credential change. No separate frontend typecheck is configured.

Full lint failures remain in unchanged ShopOwnerCustomers.jsx (three effect-state resets), ShopOwnerDashboard.jsx (unused Store, effect reset, dependency warning), and repayments.test.js (three unused imports). Git confirms these files are unchanged from aa5eed8. This known repository debt is distinguished from Day 14 regressions and is not hidden by disabling lint rules or deleting tests.

Evidence is ignored under .server-logs/day14-final-backend.log, day14-final-frontend-after-mobile-fix.log (and initial day14-final-frontend.log), day14-final-lint.log, day14-final-scoped-lint.log and day14-final-build.log.

## Responsive/accessibility execution

Fresh fixtures and the actual production build/test API were used, not production mock data. Final reruns after the mobile fix passed:

| Browser suite | Responsive | Basic accessibility |
|---|---:|---:|
| Owner catalogue, add/edit forms and business selection | 50 | 50 |
| Customer catalogue, filters/details and mobile navigation | 50 | 50 |
| Cart, shop replacement, checkout, retry, owner actions and history | 70 | 70 |
| Total | 170 | 170 |

The actual order journey deliberately loses a successful create response, visits My Orders/cart, reopens checkout, verifies Credit is still selected and retries the same key. It then approves/processes/completes that order, completes one cash order while unpaid, and rejects another credit order. The final fixture database has exactly three intended orders and one 250.50 credit sale. Both keep-current-cart and explicit shop replacement are exercised. No rejected/cash order adds debt. All mobile states additionally scroll the page and assert the menu button remains inside its header.

Visually inspected fresh edit-product-375, product-details-1366 and credit-retry-reopened-375 screenshots. Evidence: .server-logs/day14-catalogue-browser/results.json, day14-customer-browser/results.json, day14-orders-browser/results.json and their screenshots. After each suite, exact fixtures were removed; the final token JSON contains only database/cleaned=true. Temporary ports 8013/5187/9237 were verified closed.

Each page/state is checked at 1536, 1366, 1024, 768 and 375 px for horizontal overflow, overlapping buttons, associated input labels, named actions and visible native-Tab focus. UI exposes readable status/payment text and exact LKR amounts; missing images use the established placeholder. Existing colors/layouts are preserved. This is basic accessibility verification, not assistive-technology certification.

## Git checkpoint and progress

Only verified Day 14 paths are included; .gitignore remains an unrelated user edit. Before staging, reviewed every tracked/untracked path, scanned changed text for private keys, literal JWTs, provider tokens and credential URLs, checked whitespace, verified environment/build/cache/fixture exclusions and confirmed the index was initially empty. No secret pattern finding was detected.

The verified Steps 14.1–14.5 are included in the local checkpoint on main, with message: Day 14: complete customer shopping and credit order integration. This report is part of that commit; its exact hash is available with git log -1 --oneline and is reported in the task response. The 61 explicitly reviewed paths exclude the unrelated .gitignore edit and all environment/build/cache/browser artifacts.

Both full functional suites and production build pass. The historical repository lint baseline is documented as non-blocking for this scoped local checkpoint, consistent with the prior Day 13 checkpoint. No push, amend, empty commit, reset or destructive Git operation was performed. No Day 15 work was started.

## Remaining issues and next milestone

No critical/high shopping or financial defect was found. Medium: pre-existing repository-wide lint debt (eight errors/one warning in unchanged files). Low: the existing bundle-size advisory. Manual development migration is an operational prerequisite, not an automatically executed action. Supported limitations: memory-only cart (reload/logout clears it), no stock quantities, no cash receipt confirmation, no posted-order cancellation/refund, no automatic order-to-delivery link and refresh-based updates.

Next recommendation: review the Day 15 plan for an explicitly authorized order-to-delivery handoff using the existing DeliveryRequest service, including same-business linkage and independent delivery/financial states. No Day 15 implementation was started.
