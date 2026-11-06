# Day 13 Step 13.2 — Shop Owner Delivery Management Frontend

> Day 13 final verification and local checkpoint: [Step 13.5 report](day13-final-regression-security-review.md).

> Step 13.3 now verifies the complete cross-role journey through delivery completion with the existing shared record and UI. See [Shop-to-Driver integration verification](day13-shop-driver-integration.md).

## Result and repository audit

Delivery Management is implemented at **`/shop-owner/deliveries`**, within the existing Shop Owner protected route, layout, header and sidebar. Title: “Delivery Management”. Subtitle: “Create delivery requests and track your shop's deliveries.” No new delivery backend or assignment system was built.

Before implementation, verified Step 13.1's actual router, schemas, ownership services, Day 12 lifecycle, test coverage and current uncommitted files. Its create/list/detail/cancel APIs were present and secured. The sidebar already had a disabled Deliveries item but App had no corresponding page. The existing Shop Owner layout is responsive; its visual styles, typography, colors, logo, header and business-selection conventions were reused. Existing auth, notifications, shared Axios client and test framework were inspected.

No global CSS variables for the supplied palette exist in `src/index.css`; the existing pages use Tailwind color utilities. This page follows those existing utilities and the supplied Navy/Teal/Green/Amber/Red/background values. It does not replace fonts, images, gradients or other dashboards.

Branch remains `main`, HEAD `c7e50c6`. Existing Step 13.1 work and unrelated `.gitignore` changes are preserved. No staging, commit or push was performed.

## Files created or modified in Step 13.2

Created:

- `frontend/src/pages/shopOwner/ShopOwnerDeliveries.jsx`
- `frontend/src/services/shopOwnerDeliveryService.js`
- `frontend/src/utils/shopOwnerDeliveries.js`
- `frontend/tests/shopOwnerDeliveries.test.js`
- `frontend/tests/shopOwnerDeliveriesView.test.js`
- `frontend/tests/fixtures/shopOwnerDeliveryFixtures.js`
- `frontend/scripts/verifyShopOwnerDeliveries.mjs`
- `backend/tests/test_shop_owner_delivery_summary.py`
- This report.

Modified:

- `frontend/src/App.jsx`: adds the nested Shop Owner `deliveries` route.
- `frontend/src/components/shopOwner/ShopOwnerSidebar.jsx`: enables the existing Deliveries item, with no duplicate entry or other navigation change.
- `frontend/src/layouts/ShopOwnerLayout.jsx`: sets its existing page title to Delivery Management.
- `backend/app/schemas/shop_owner_delivery.py`, `backend/app/services/shop_owner_delivery_service.py`, `backend/app/routers/shop_owner_deliveries.py`: small authorized summary read endpoint, described below.
- `docs/day13-shop-owner-delivery-backend.md`: links to this updated frontend/summary contract.

Customer/Driver sidebars, Login/Registration, credit calculations, existing notifications, database models/migrations, frontend dependencies and global styles are unchanged.

## Verified API contract

The service reuses `src/services/api.js`, including JWT injection, timeout and current-session expiry behavior. It does not duplicate authentication or automatically retry POST requests.

| Method | Actual endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/v1/shop-owner/business-context` | Trusted current-user businesses; verify returned user_id and allowed business identities |
| GET | `/api/v1/shop-owner/deliveries?business_id={id}&page={page}&page_size=10&status={status}` | Business-scoped list with optional exact-status filter |
| POST | `/api/v1/shop-owner/deliveries?business_id={id}` | Create with exactly pickup_area and delivery_area |
| GET | `/api/v1/shop-owner/deliveries/{request_id}?business_id={id}` | Details, authorized assigned Driver summary, events and can_cancel |
| POST | `/api/v1/shop-owner/deliveries/{request_id}/cancel?business_id={id}` | Empty JSON `{}` cancellation body |
| GET | `/api/v1/shop-owner/deliveries/summary?business_id={id}` | New minimal authoritative summary read |

The summary endpoint shares Step 13.1's active-account, Shop Owner role, approved-business and active owner-membership checks. It is registered before the dynamic request-ID route. One database GROUP BY query, explicitly filtered by the selected business, counts all stored requests independently of list pagination/filtering:

```json
{
  "business_id": 1,
  "total_requests_count": 6,
  "available_requests_count": 1,
  "in_progress_count": 3,
  "completed_count": 1
}
```

The numbers above are a contract example, not application defaults. Total includes cancelled requests. In Progress includes `assigned`, `picked_up` and `in_transit`; Completed means `delivered`, without claiming payment. Summary failures/loading show an unavailable dash and clear message. No global counts are inferred from one list page.

No migration is needed. The new summary has explicit Pydantic nonnegative fields, safe projections, no-store caching and existing sanitized database errors. It neither creates nor updates records.

## Form, list, filtering and details

“New Delivery Request” has only two supported fields: **Pickup area** (`pickup_area`) and **Delivery destination** (`delivery_area`). Labels, placeholders, required fields and length limits are visible. The workflow trims values, validates 1–160 Unicode characters and rejects embedded control characters. It sends no business/creator/Driver identity in the body; query business identity can only come from trusted business context and is still authorized by the backend. Pending/rejected businesses cannot load delivery data or submit.

Only a validated backend confirmation displays creation success. The form clears, pagination/filter reset to the newest unfiltered page, and the list, authoritative summary and opened detail refresh. Duplicate clicks share one in-flight operation; form edits and business selection are blocked while saving. No order, fee, earnings, package, vehicle requirement or contact field is invented.

“My Delivery Requests” shows real request reference, pickup/destination areas, status, creation date and View Details. Pagination uses the backend total and bounded ten-item pages. Filters are exactly `available`, `assigned`, `picked_up`, `in_transit`, `delivered`, `cancelled`, plus All. User-facing `delivered` label is Completed; pickup/transit stages retain their actual distinct labels. Filters reset to page one.

Details open inline, following the existing Driver and Shop Owner disclosure conventions. They show the selected business, request reference, areas, status, created/updated dates, assigned Driver name or Not assigned, and actual recorded events. Missing event history is an explicit empty state; old dates are not reconstructed. Dates are labelled UTC, matching the backend's naive UTC serialization. No unrestricted JSON, customer ledger or Driver private profile is displayed.

## Cancellation and assignment

Cancel Request appears only when a freshly validated detail response returns `can_cancel=true`, consistently with `available` status and no assignment. It requires explicit confirmation with Confirm Cancellation / Keep Request controls. The workflow permits only one mutation at a time and waits for a validated cancelled response before claiming success. Successful cancellation refreshes detail, list and summary.

If a Driver accepts first, 409 feedback explains the state changed and cancellation is unconfirmed; real detail/list/counts reload. An assigned Driver's returned name and actual progress appear, and cancellation disappears. The owner cannot supply or overwrite a Driver ID. Network-loss cancellation also refreshes actual state without inventing success. Retry safety remains enforced by the existing backend lifecycle and idempotent cancellation service.

There is no real-time subscription or polling added: owners use Refresh deliveries to observe later Driver progress. Refresh also retries failed reads. Existing Driver acceptance/status code is unchanged.

## Uncertain creation and privacy safeguards

Step 13.1 has no durable keyed creation replay. The UI therefore never automatically retries creation after an uncertain response. It writes a non-sensitive `unconfirmed` attempt flag in **tab sessionStorage** before sending. The key is scoped by authenticated user and business; it contains no delivery ID, areas, contact details, tokens or complete records. Delivery form/details remain in memory only. The existing auth session token storage is unchanged.

A timeout, network failure, malformed success or other uncertain result blocks another submission, including after route remount/reload in that tab. Recovery requires an explicit Refresh requests for review followed by “I reviewed requests; start a new request”. The warning states that the earlier request might still finish: a missing row is not treated as proof of failure. The form is cleared after explicit acknowledgement so the same request is not silently resent. Definitive 401/403/404/409/422 rejections do not claim creation and clear the attempt flag where safe.

Storage failure prevents submission before sending, or blocks subsequent creation until the flag can be managed. Different user/business flags are isolated. This is duplicate-click and uncertain-result protection, not a claim of backend or cross-tab idempotency. Durable replay and cross-tab deduplication remain backend follow-up work if required.

Every delivery response is validated for expected business/request identity, supported statuses, pagination, fields, timestamps, unique IDs, counts and minimal Driver/event structure. Private extras are projected away. Abort controllers, request versions, business generations and session/token component keys prevent late responses from a previous request/business/account repopulating a newer view. Auth failures clear private state. No production mock data is imported.

## Automated verification

Before backend mutation tests, effective settings, SQLAlchemy engine URL database and `SELECT DATABASE()` were verified as **`lankapex_test_db`**. Existing pytest guards repeat the check before collection. No test targets `lankapex_db`.

| Check | Actual result |
| --- | --- |
| Targeted new frontend workflow/view tests | **29 passed, 0 failed, 0 skipped** |
| Full frontend, `npm test -- --test-concurrency=1` | **524 passed, 0 failed, 0 skipped**, 73.92 s |
| Targeted summary/Shop Owner delivery backend tests | **43 passed, 0 failed, 0 skipped** |
| Full backend regression | **842 passed, 0 failed, 0 skipped**, 213.89 s |
| `npm run build` | **Passed**, 2,191 modules; 684.61 kB main JS, 189.92 kB gzip; existing large-bundle warning remains |
| ESLint on all changed frontend source/integration files and QA script | **Passed** |
| Full-project `npm run lint` | **8 existing errors and 1 warning**, unchanged ShopOwnerCustomers, ShopOwnerDashboard and repayments.test files |
| Backend summary AST parsing | **4 files passed** |
| Git whitespace check | **Passed** |

The existing single-worker frontend invocation avoids the previously documented 15 ms repayment-test timing sensitivity without deleting or weakening tests. The backend full run has the existing intentionally short HMAC test-key warning. No frontend typecheck or backend lint/typecheck tool is configured.

Tests cover actual business/role protection and private-field filtering; authoritative counts versus a one-item page; summaries excluding a second owned business; empty/loading/error/unapproved/missing-business states; input validation; creation confirmation, rejection, duplicate clicks and remount-safe uncertainty; detail/Driver/timeline rendering; confirmation visibility; cancellation success, conflict and response loss; duplicate cancellation submission; filters/pagination; late business/response replacement; expiry; sessionStorage isolation/failure; exact Axios contracts; real routing/sidebar; and preservation of existing Customer, Driver, Shop Owner, auth and financial workflows in full regression.

The last summary test refinement added a second owned business to explicitly verify per-selected-business totals; its final targeted rerun passes. No production source changed after the full-suite/build runs.

## Real-database browser verification and cleanup

Ran `frontend/scripts/verifyShopOwnerDeliveries.mjs` with a temporary backend on **127.0.0.1:8013** configured only for independently verified `lankapex_test_db`. Temporary uniquely identified Shop Owner/Driver/admin accounts and an owned approved business were created after the full backend suite finished, so they could not contaminate regression fixtures. The Driver fixture used the existing privileged review service, not an automatic approval feature. No delivery requests were pre-seeded.

The actual built React app used real JWTs and real FastAPI/MySQL responses. Browser interception forwarded API calls to the test-only backend and never continued them to development port 8000. The checks:

- Loaded the empty list, entered the two real form fields, created a request through the page, and verified listing/detail/count refresh.
- Checked **1536, 1366, 1024, 768 and 375 px** with no document horizontal overflow or clipped reference; visible field labels were asserted. Screenshots were captured and desktop/mobile output visually inspected. Full-page captures can show sticky/fixed navigation at its scroll-relative position; the existing navigation design was preserved.
- Opened cancellation confirmation, kept the request without mutation, then confirmed cancellation and verified the persisted cancelled status. Exactly one cancellation POST occurred.
- Created a second request, accepted it through the real existing Driver API with the eligible test Driver, refreshed the owner page, verified the returned Driver name and cancellation removal, and checked real totals (two requests, one in progress, none available).
- Exercised status filtering, mobile sidebar open/close and visible input focus styling.

Final browser run exited zero: **five responsive checks, two real creations, one cancellation, assignment visibility and summary checks passed**. An intermediate runner serialization error was corrected by making DOM assertions return booleans; no product change was required.

Afterwards the temporary backend was stopped. Exact-ID/unique-business cleanup removed both browser-created requests and their events/assignment, temporary membership, reviewed Driver profile, business and users **only from the verified test database**. Cleanup replaced the local token fixture with `{database:"lankapex_test_db",cleaned:true}`. No database reset, destructive migration or development seed occurred.

Logs/results/screenshots are ignored under `.server-logs/day13-ui-*`. The temporary fixture helper is local verification infrastructure, not application data. The user's development frontend/backend remain running. Live checks confirm the summary route is registered on port 8000 and `/shop-owner/deliveries` responds on port 5173.

## Remaining limits and readiness

**Ready for Step 13.3 — Shop-to-Driver Integration.** Creation, listing, details, filtering, assignment visibility, recorded progress and permitted cancellation use the real backend. No blocking implementation dependency remains for this scope.

Existing backend limits remain: no editing, draft publishing, assigned cancellation, keyed creation replay, per-job vehicle matching, package fields, precise private delivery addresses/contact/instructions, earnings or settlement. The UI does not fabricate them. Updates are refresh-based. Unrelated full-project lint failures and bundle warning remain documented. No extra Driver UI, shopping/checkout, financial calculation, GPS or payment gateway was added. No commit or push was made.
