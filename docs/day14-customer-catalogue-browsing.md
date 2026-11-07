# Day 14 Step 14.3 — Customer shop and product browsing

Status: **PASS**. Targeted/full frontend and backend tests, production build and actual Chrome verification pass. Development catalogue use still requires the intentionally deferred Step 14.1 migration. No Step 14.4 cart/order/credit approval work was started.

## Verified foundation and audit

Inspected actual Step 14.1/14.2 models, catalogue router/service/schemas, migration, tests, owner UI/workflow, shared Axios client, Customer dashboard/My Shops/credit routes, sidebar, layout/header and existing Customer components. Their code and successful verification logs are present. Starting branch is `main`, with the earlier Day 14 work and unrelated `.gitignore` edit already uncommitted; all were preserved. Nothing was staged, committed or pushed.

Existing Customer catalogue APIs provided approved-shop discovery, published products, active category browsing, product name/category/availability filters and bounded pagination. Missing capabilities were shop-name search and a direct public shop-detail read. Existing `/api/v1/customer/shops` serves private linked-credit relationships and is not catalogue discovery.

Only two small read-only backend additions were needed: optional server-side shop-name search and public shop detail. Public products now include the actual category name, resolved in a bounded batch query. Owner response behavior is preserved, and Customer responses continue to omit publication state, internal timestamps and private owner/business/financial fields. Existing approval, category visibility and publication rules remain authoritative. No model/table/migration change was needed in this step.

## UI routes and navigation

| Route | Page |
| --- | --- |
| `/customer/shops/explore` | Explore Shops — “Discover products from local businesses.” |
| `/customer/explore/:businessId` | Public Shop Catalogue and published products |
| `/customer/explore/:businessId/products/:productId` | Published Product Details |

All mount inside the existing Customer-only ProtectedRoute and CustomerLayout. Page session keys include user ID, token, shop and product IDs; direct identifiers are validated before API requests. CustomerSidebar adds one Explore Shops item while retaining My Shops, Dashboard, My Credit, Transactions and Notifications. My Shops stays `/customer/shops`; exact matching prevents it being highlighted as the exploration list. The existing mobile dialog/navigation and header are retained, with appropriate browsing titles.

Cards, buttons and pagination reuse `CustomerData.jsx` rather than introducing global styles. Existing logo, typography, navy/teal/green/amber/red/background palette and layout are preserved. New product placeholders use the existing Package icon system with an accessible missing-image label and fixed aspect ratio. No Customer shopping images, ratings, locations or discounts were invented. There is no cart, Buy Now or ordering action.

## Actual API contract

All calls use the existing authenticated Axios instance. Paths are relative to `/api/v1`, and browsing requires an active authenticated Customer.

| Method | Path | Parameters / public response |
| --- | --- | --- |
| GET | `/customer/catalogue/shops` | `page`, `page_size`, optional `q` shop-name substring; `{page,page_size,total,shops:[{business_id,business_name,product_count}]}` |
| GET | `/customer/catalogue/shops/{business_id}` | `{business_id,business_name,product_count}` |
| GET | `/customer/catalogue/shops/{business_id}/categories` | `page`, `page_size`; active public category rows |
| GET | `/customer/catalogue/shops/{business_id}/products` | `page`, `page_size`, optional `q`, `category_id`, `availability_status` |
| GET | `/customer/catalogue/shops/{business_id}/products/{product_id}` | One published visible product in the exact shop |

Frontend page size is 10; API bounds remain 1–100, page 1–1,000,000. Shop/product search is bounded to 200 characters, parameterized, and escaped so user `%` and `_` are literal search text. No location search or client sort selector is offered because those capabilities are not supported. Lists use the existing stable ascending-ID order. Filters/search reset their respective page; products are never downloaded without limits for client-side filtering.

Customer category fields remain `category_id`, `business_id`, `name`, `description`. Categories have active status rather than a publication field; the UI shows the actual active categories returned by the backend, including a category that may currently have no matching products. Category choices are loaded through independent bounded pages and retained only within the current shop session. Product labels do not depend on the first category page, because the API supplies `category_name` directly.

Customer product fields are exactly:

```json
{"product_id":31,"business_id":7,"category_id":11,"category_name":"Retail essentials","name":"Rice","description":"Retail unit","unit_price":"125.25","currency":"LKR","availability_status":"available"}
```

This is an illustrative contract, not production seed data. Descriptions are displayed as text. Unit prices remain authoritative two-decimal strings; the shared formatter never converts monetary values to Number/parseFloat. `9999999999.99` displays as `LKR 9,999,999,999.99`. No sale price, equivalent-product comparison or discount is calculated.

## Visibility, authorization and failure behavior

- General discovery includes approved businesses with at least one visible published product, with the actual visible count. Empty approved catalogues can be opened directly and display zero/empty state, but are omitted from discovery.
- Products must be `published`; categorized products additionally require an active same-business category. Drafts, archived products, inactive-category products and products from unapproved businesses cannot be read through public detail IDs. Unavailable published products remain visible with their actual availability badge/message.
- Shop detail returns only the public display name/identifier/count. Existing Business.address is not a separate public general-location field, so it is not exposed. No owner contact, registration/approval metadata, credit accounts, balances or other customers' data is included.
- JWT, stored-role/account checks and database scope enforce access independently of React. Customer identity does not grant management access; direct attempts to read owner management routes are denied. Product IDs from another shop do not broaden the path scope. New shop-detail reads reject missing JWT and non-Customer roles.
- Frontend schema parsing projects public fields, rejects wrong business/product identities, duplicate/malformed pages, numeric prices, owner-style publication DTOs and mismatched filters. It never treats client role hints as authority.
- Abort controllers, per-section versions and session generations prevent replaced searches/pages/shops/users from repopulating newer state. Refresh aborts prior product/category reads before revalidating shop eligibility. Unmount discards all state; no catalogue or financial data is persisted to browser storage.
- Missing/ineligible shops clear related products/categories/detail. A missing/unpublished product displays its safe unavailable state while retaining still-public shop context. Authentication/role failures conceal all previously loaded catalogue data. Errors use safe messages, not raw database diagnostics.
- Loading shops/products/details/categories, empty catalogue, no search matches, empty later page, unavailable product, network failure and expired session have distinct states. Refresh re-reads the server without a full page reload. No instant-push behavior is claimed.

## Files created or modified in Step 14.3

Created:

- `frontend/src/pages/customer/CustomerCatalogue.jsx`.
- `frontend/src/services/customerCatalogueService.js` (GET only).
- `frontend/src/utils/customerCatalogue.js`.
- `frontend/src/utils/catalogueMoney.js` (extracted unchanged decimal-string behavior for both roles).
- `frontend/tests/fixtures/customerCatalogueFixtures.js`.
- `frontend/tests/customerCatalogue.test.js` and `customerCatalogueView.test.js`.
- `frontend/scripts/verifyCustomerCatalogue.mjs`.
- `backend/tests/test_customer_catalogue.py`.
- This report.

Modified:

- `frontend/src/App.jsx`: three routes under existing Customer guard/layout.
- `frontend/src/components/customer/CustomerSidebar.jsx`: separate exploration link and matching behavior.
- `frontend/src/layouts/CustomerLayout.jsx`: browsing header titles.
- `frontend/src/utils/shopOwnerCatalogue.js`: re-export/use the shared unchanged price formatter; owner behavior remains covered by regression tests.
- `backend/app/routers/catalogue.py`: optional shop-name query and public shop-detail endpoint.
- `backend/app/services/catalogue_service.py`: search/detail queries and explicit owner/public product projections with category names.
- `backend/app/schemas/catalogue.py`: public category-name field; owner schema inherits it.
- `backend/tests/test_catalogue.py`: retain exact public response-key assertion including the new safe category-name field.
- Earlier Day 14 reports link to this current public contract.

No financial service, delivery service, global CSS, Customer financial page, owner page design or database model changed. No new dependency was added.

## Actual test, build and static-check results

| Check | Passed | Failed | Skipped | Evidence |
| --- | ---: | ---: | ---: | --- |
| Catalogue/summary/Customer targeted backend | 72 | 0 | 0 | `day14-browsing-targeted-backend.log`, 8.21s |
| Full backend regression | 926 | 0 | 0 | `day14-browsing-backend-regression.log`, 158.46s |
| Customer + owner catalogue targeted frontend | 56 | 0 | 0 | `day14-browsing-targeted-frontend.log`, 5.85s |
| Final full frontend regression | 588 | 0 | 0 | `day14-browsing-frontend-regression.log`, 67.13s |
| Production Vite build | — | 0 | — | `day14-browsing-build.log`, 3.14s, exit 0 |
| Changed-file configured ESLint | — | 0 | — | Exit 0 |
| Actual Chrome responsive checks | 50 | 0 | 0 | Five widths across ten browsing states |
| Actual Chrome basic accessibility checks | 50 | 0 | 0 | Labels, named controls, overlap and native Tab focus |

Backend tests use real JWTs/HTTP/MySQL with the existing rollback/savepoint guard: settings, engine database and actual `SELECT DATABASE()` must all be `lankapex_test_db` before mutation. No mutating test targeted `lankapex_db`. New backend tests cover escaped shop search/pagination, minimal shop/product projections, real category names, visible counts, empty approved shops, unapproved denial, missing/wrong-role JWT and cross-shop/hidden product IDs. Existing financial, Customer, owner and delivery suites pass unchanged in behavior.

Frontend tests cover discovery/search/pagination, shop/product detail, all filters, exact prices, placeholders, hidden-owner DTO rejection, unavailable/empty/error states, role guards, identifier tampering, stale responses, shop/session replacement, shared GET/Axios contract, separate My Shops navigation and retained financial/owner routes. The final full run follows reuse of the actual CustomerData card/button/pagination components. Existing single-worker test execution is preserved; no unrelated test assertions were weakened.

Full ESLint retains its existing **8 errors and 1 warning** in ShopOwnerCustomers, ShopOwnerDashboard and unused repayment-test imports. No separate typecheck/backend linter is configured. The build retains the >500kB chunk warning; current main bundle is approximately **737.24kB / 200.41kB gzip**, CSS **63.48kB / 13.07kB gzip**. The backend retains the existing intentionally short HMAC test-key warning. No secret was printed or modified.

## Browser verification and cleanup

Used actual compiled React, signed Customer JWT, real FastAPI/MySQL and the existing guarded catalogue fixture utility on an isolated test-only API at port 8013. Browser API interception forwards to that API only and never continues to development. Test products were prepared through secured owner APIs, including two publicly visible first-shop products, a draft, an archive, an inactive-category product and a separate shop's product. No mock API response was presented as a real catalogue.

Verified real shop search/no-results, shop navigation, product search, category/availability filters, exact maximum-price details, unavailable details, hidden draft denial, missing shop, directly opened empty approved shop and the native mobile sidebar moving to the distinct My Shops route. Draft/archive/inactive-category/foreign-shop names did not appear in the selected shop. Customer access to owner management was denied. All Customer UI API methods were GET/OPTIONS; no ordering or product mutation request was made by the browsing UI.

Widths: **1536, 1366, 1024, 768, 375px**. Ten states: exploration, empty shop search, matching shop search, shop catalogue, unavailable filter, unavailable product, maximum-price details, hidden-product failure, missing/ineligible-shop failure and empty approved shop. No page overflow or clipped headings/overlapping main buttons was detected; fields/actions had labels and keyboard focus remained visible. The mobile product-detail and desktop Explore Shops screenshots were visually inspected. No broader assistive-technology certification is claimed.

An initial verifier run encountered Chrome's invalid interception ID when the UI cancelled a superseded filter request. The runner now ignores only that expected cancelled-request interception error and still fails other errors; the complete fresh-fixture rerun passed. No application stale-response protection was bypassed.

Evidence lives only in ignored `.server-logs/day14-customer-browser/results.json`, 50 screenshots and `day14-browsing-browser-run.log`. The temporary API process tree was stopped. Nonce/ID-checked fixture cleanup removed only the test products/categories/members/businesses/users and sanitized the ignored token JSON to `cleaned:true`. Existing development servers remain running. Do not run global-count mutation suites concurrently with committed browser fixtures.

## Remaining setup and Step 14.4 readiness

No functional blocker remains in the verified test environment. **Development migration `c9d5e8f7a237` remains deliberately unapplied** under the earlier explicit instruction. Read-only verification confirms development is still `b8c4d7e6f126` with neither catalogue table. Apply the Step 14.1 manual migration before local catalogue use; no additional migration is required for this step.

Limits: no public location/description/image fields for shops, product images, client-selectable sorting, equivalence matching/price comparison, inventory quantities, cart, checkout, orders, payments or credit approval. Only actual supported fields are shown. Baseline lint debt and bundle warning remain documented follow-ups.

Ready for **Day 14 Step 14.4 — Shopping Cart, Orders and Credit Approval**, using the existing documented future-order contract. That step has not been started; client-supplied prices must never become authoritative in future checkout.


Final Day 14 verification and scoped local checkpoint: [regression and financial-security review](day14-final-regression-security-review.md). The final report supersedes historical test-count snapshots in this step report.
