# Day 14 Step 14.2 — Shop Owner product and category management

> Step 14.3 adds Customer exploration, server-side shop search/details and public category labels. See [the Customer browsing report](day14-customer-catalogue-browsing.md) for the current public API contract.

Status: **PASS**. Required frontend/backend tests, build and actual browser workflow pass. Development use still requires the explicitly deferred catalogue migration.

## Audit and scope

Verified Step 14.1 from the actual catalogue models, migration, schemas, owner/Customer routers, services and real JWT/SQL tests. No substitute mock production catalogue was introduced. Starting branch is `main`; the Day 14 backend and unrelated `.gitignore` changes were already uncommitted and are preserved. No files were staged, committed or pushed in this step.

The existing Shop Owner sidebar reserved `/shop-owner/products` but disabled it; App had no product route. Existing layout/header, card/form/button patterns, mobile navigation, role guards, notification provider and shared JWT Axios instance are reused. Global CSS contains the Tailwind import rather than a separate product token system; this page uses the same existing navy/teal/green/amber/red/background classes, without global CSS or dashboard redesign. Customer/Driver/Admin UI, financial calculations and delivery rules are unchanged.

## Implementation and files

Created:

- `frontend/src/pages/shopOwner/ShopOwnerProducts.jsx`: Shop & Products page and reusable view, responsive cards, forms, filtering and category management.
- `frontend/src/services/shopOwnerCatalogueService.js`: existing Axios GET/POST/PATCH contracts; no duplicate token storage.
- `frontend/src/utils/shopOwnerCatalogue.js`: strict response parsing, decimal-string handling, scoped workflow, request cancellation/versioning and uncertain-creation protection.
- `frontend/tests/fixtures/catalogueFixtures.js`, `shopOwnerCatalogue.test.js`, `shopOwnerCatalogueView.test.js`.
- `frontend/scripts/verifyShopOwnerCatalogue.mjs`: real-database browser workflow and width/accessibility checks.
- `backend/scripts/catalogue_browser_fixture.py`: verified test-only setup and exact nonce/ID cleanup; no production seed.
- `backend/tests/test_catalogue_summary.py`.
- This report.

Modified:

- `frontend/src/App.jsx`: one product route under the existing Shop Owner guard/layout.
- `frontend/src/components/shopOwner/ShopOwnerSidebar.jsx`: enable the existing item and label it Shop & Products.
- `frontend/src/layouts/ShopOwnerLayout.jsx`: matching existing header title.
- `frontend/tests/repaymentsView.test.js`: update the old assertion that Products must remain disabled; repayment links/styles are still asserted.
- `backend/app/schemas/catalogue.py`, `backend/app/services/catalogue_service.py`, `backend/app/routers/catalogue.py`: owner summary aggregation and owner-only category-name projection.
- `docs/day14-catalogue-backend.md`: link to this current UI contract.

No new migration was needed for the summary/projection. The Step 14.1 migration remains required before development catalogue use; it was not automatically applied to development in Step 14.2.

## Route and actual API contracts

UI route: **`/shop-owner/products`**, using existing `ProtectedRoute allowedRoles={["shop_owner"]}`, active-account page guard, ShopOwnerLayout and header/sidebar. Other Shop Owner routes remain present; no duplicate sidebar/route was created.

API paths below are relative to `/api/v1`; every owner call includes required `business_id` query context.

| Method | Path | Usage |
| --- | --- | --- |
| GET | `/shop-owner/business-context` | Actual owner identity and authorized businesses |
| GET | `/shop-owner/catalogue/summary` | New database-wide counts for the selected business |
| GET / POST | `/shop-owner/products` | Paginated list and creation |
| GET / PATCH | `/shop-owner/products/{product_id}` | Current authorized edit details and explicit changed fields |
| GET / POST | `/shop-owner/categories` | Paginated category management and creation |
| PATCH | `/shop-owner/categories/{category_id}` | Category edit, activation/deactivation |

Product list calls send `page`, `page_size=10` and non-empty `q`, `category_id`, `availability_status`, `publication_status` filters. Category calls send `page` and `page_size=10`. Both use the existing AbortSignal and Axios JWT interceptor. Empty filters are omitted. Prices stay strings, including the exact maximum `9999999999.99`; no Number/parseFloat price transformation is used.

The new owner summary response is:

```json
{"business_id":7,"total_products_count":25,"available_products_count":23,"categories_count":1,"unpublished_products_count":23}
```

Counts are SQL aggregates across the entire authorized business, independent of product filters/page size. Total includes archived products; Available counts the manual availability flag excluding archived products (including drafts); Categories includes inactive categories; Unpublished counts drafts only. Card notes state these definitions. Failed/loading summaries show unavailable/unknown, never invented zero. True zero comes from the API.

Owner product responses add `category_name` (nullable for uncategorized products) so each paginated card can display its actual category even when that category is on another page. Names are fetched in one bounded query for the returned rows. Customer response schemas remain unchanged.

## Product/category behavior

Product cards show actual name, category, decimal-safe LKR price, availability/publication badges, persisted update time and supported actions. Package icon uses the established icon system as a placeholder: the backend has no image/upload field and this UI does not invent one.

Add Product and Edit Product are inline sections using existing form styles. Edit fetches current authorized details first and sends only normalized changed fields. Required name, plain-text/length rules, positive two-decimal price, same-business category, valid availability and draft/published state are validated before submit and again by the server. Descriptions and category IDs may be cleared according to the actual schema. The UI has no writable business ID/currency, stock or image fields. Backend versioning is not supported; edits therefore follow the documented last-successful-write policy, without claiming stale-version protection.

Categories have paginated management, add/edit forms and active/inactive actions. Deactivation hides the category's published products from Customer browsing; reactivation restores their eligibility. Category choices are loaded as the user visits category pages and retained in a business-scoped cache. This avoids falsely assuming the first page contains all categories, preserves a selected option across pages and never auto-downloads an unbounded category collection. Duplicate names remain authoritatively validated by MySQL/backend, with a conflict message and the form retained.

Availability (`available`, `unavailable`) and publication (`draft`, `published`, `archived`) remain distinct. Action success is shown only after a matching valid server response. A published product with an inactive category is not made customer-visible by the UI; server restrictions remain authoritative. Publication/unpublication and category/availability changes refresh current products, categories and summary. Archive requires an explicit confirmation, uses `PATCH {publication_status:"archived"}` and leaves the historical record read-only. No hard delete/restore feature is invented.

Search and filters use the server, reset the product page and reject superseded responses. Product/category pagination is independent; categories can be loaded from the product editor as well as the management section. Requests never derive global statistics from displayed rows.

## Safety and failure behavior

Backend checks remain authoritative: current JWT account/role, approved business and active owner membership, request/product/category business isolation, immutable ownership, publication/category rules and Decimal validation. The summary endpoint applies the same policy. Its tests include zero counts, 25 records with page-size two, foreign-business isolation, wrong roles and unapproved business denial.

Frontend session keys include user ID and token. Business switching aborts/replaces reads and clears forms, rows, summaries, filters and category cache. Generation/per-section versions suppress late responses; duplicate writes share one mutation lock. Account expiry/forbidden access conceals prior data. Malformed/foreign response schemas fail closed. No raw backend diagnostics or customer credit data is displayed.

Create operations have no backend idempotency-key contract. Before a creation request, only a non-sensitive per-user/business unresolved flag is stored in tab sessionStorage. Ambiguous failure or invalid confirmation blocks further writes until explicit review/acknowledgement; the flag survives remount. Names, descriptions, prices and product records are never stored there. Storage failure blocks new creation. A flag does not guarantee exactly-once creation: an earlier network request may still finish; the review message states this limitation. Failed edits retain the form with a refresh/reopen instruction instead of claiming success or automatically replaying writes.

## Verification

- Targeted backend catalogue/summary suite: **66 passed**, zero failed/skipped, **14.77s**.
- Full backend regression: **920 passed**, zero failed/skipped, **208.05s**. Includes all existing financial, customer, notification and delivery tests. Existing intentionally short HMAC test-key warning remains.
- Targeted frontend workflow/render/service suite: **28 passed**, zero failed/skipped, **7.09s**.
- Final full frontend suite: **560 passed**, zero failed/skipped, **47.84s** using the existing single-worker execution approach.
- Initial production Vite build: **passed**, **6.14s**, main bundle approximately **719.18kB / 197.36kB gzip**. Existing >500kB chunk warning remains; no new dependency was added.
- Full configured ESLint reports the same existing **8 errors, 1 warning** in ShopOwnerCustomers, ShopOwnerDashboard and unused repayment-test imports. Changed catalogue files pass targeted ESLint. No separate typecheck/backend linter is configured.

The first full frontend run identified the obsolete navigation test expecting Products to be disabled; it was updated to verify the newly enabled route rather than removing the check. Another run hit the existing fixed-delay repayment test flake. After browser/background verification finished, the final full suite passed all 560 tests; no repayment logic or timing-test assertions were weakened. Targeted ESLint passed for all new catalogue UI/workflow/service/test/browser files plus the updated navigation test. Python source syntax and final whitespace checks passed.

All backend mutation tests were guarded against non-test settings/engine/actual database; only `lankapex_test_db` was used. No schema reset or destructive migration was run. Development migration remains pending deliberately; new APIs return unavailable until it is applied using the Step 14.1 instructions.

## Actual Chrome verification

Real compiled React, actual signed JWTs, real FastAPI and MySQL on a temporary test-only API at port 8013. API requests were intercepted and forwarded only to that API, never continued to development. The fixture utility created unique test identities/businesses, no seeded products. Browser UI created exactly two products and one category.

Verified category creation/edit/deactivation/reactivation, draft creation, current-value edit to `199.99`, publication/unpublication, availability, Customer catalogue eligibility after each relevant action, search returning no matches without changing global counts, explicit archiving, exact maximum price display and switching between two authorized businesses. Foreign-business summary access was denied. Customer eligibility was checked through real Customer GET APIs, without building Customer pages.

**50 responsive checks and 50 basic accessibility checks passed**: ten page/states at 1536, 1366, 1024, 768 and 375px. States: empty, category form, product add, draft, product edit, published, archive confirmation, archived, maximum price and second business. No document overflow, clipped references, overlapping main buttons or unlabeled fields/actions were detected; native Tab focus remained visible. Mobile edit and desktop maximum-price screenshots were visually inspected. Existing logo/colors/header/sidebar remain intact. This is basic keyboard/label/responsiveness QA, not a full assistive-technology certification.

Initial browser automation clicked Add Product while the preceding category refresh still disabled it. The runner was corrected to wait for enabled controls and rerun with fresh fixtures; no application behavior was bypassed.

Evidence: ignored `.server-logs/day14-catalogue-browser/results.json`, 50 screenshots, `day14-ui-browser-run.log`, and other `day14-ui-*` test/build/lint logs. The temporary API process tree was stopped, exact nonce/ID-checked products/categories/member/business/users were cleaned and the ignored fixture token JSON was sanitized to `cleaned:true`. Normal development servers remain running.

To repeat: finish mutating suites first, build the frontend, set test database and `PYTHONPATH=.` from backend, run `scripts/catalogue_browser_fixture.py seed`, start test-only Uvicorn on 8013, then run `node scripts/verifyShopOwnerCatalogue.mjs` from frontend. Stop only the temporary API and run the fixture utility with `cleanup`. Never seed browser fixtures into development or run global-count tests concurrently with them.

## Readiness and remaining dependencies

Step 14.2 uses real, secured catalogue contracts. Development use requires the intentionally pending Step 14.1 migration `c9d5e8f7a237`; see the backend report for the manual command. No additional schema migration was introduced here. Existing lint debt and bundle warning remain. Images, inventory, versioned updates, durable creation idempotency, checkout and orders are unsupported by this backend and are not fabricated.

Ready for Step 14.3 (Customer Shop & Product Browsing) using these real contracts, after applying the manual development migration when local catalogue use is desired. Step 14.3 has not been started. No functional blocker remains in the verified test environment. The only local setup dependency is the deliberately unapplied development migration, confirmed by read-only inspection: development remains at `b8c4d7e6f126` with neither new catalogue table.


Final Day 14 verification and scoped local checkpoint: [regression and financial-security review](day14-final-regression-security-review.md). The final report supersedes historical test-count snapshots in this step report.
