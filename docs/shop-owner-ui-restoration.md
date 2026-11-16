# Shop Owner approved-design restoration

## Audit before editing — 2026-11-08

All ten PNGs in `design-references/shop-owner/` were opened and inspected.
Comparison below is against the existing React implementation before editing.
Reference names, balances, photos, dates and counts are illustrative, not data.

| Page | Visual mismatches before restoration | Functional limits to preserve |
| --- | --- | --- |
| Shared shell | Flat active navigation; muted labels; logo dark on navy; no bottom shop card; header has page title instead of greeting/business/date/search. Main spacing/cards lack reference consistency. | Identity/business must be actual authenticated/API data; no stock profile photos. |
| 01 Dashboard | Six overview cards; Quick Actions vertical beside activity; Needs Attention absent. | Existing summary fields only; no fabricated overdue-customer/unassigned counts. |
| 02 Customers | Inconsistent card/heading/table typography and spacing relative to reference; existing customer management/detail flows must remain. | Use current backend financial/ledger projections. |
| 03 Credit Sales | Customer selector, credit summary and amount form are separate cards; reference has one product-based form. | Direct credit-sale API records amount/notes, not product items/date; cannot imitate product posting. |
| 04 Repayments | Separate customer/summary/form sections and inconsistent hierarchy versus unified reference form/history. | Preserve current supported fields and server dates/payment behavior. |
| 05 Credit Orders | Redirect to Orders; shared Customer/Owner page renders stacked cards instead of table and selected detail. | Preserve all cash/credit orders and existing confirmation/fulfilment workflow; no invented eligibility balances. |
| 06 Deliveries | Request list uses stacked cards; extra creation/summary sections precede list; reference uses compact table and details/timeline. | No map/GPS, private addresses, driver phone/vehicle fields in owner projection. |
| 07 Shop & Products | No shop overview; products are stacked cards rather than table. | No product/shop images or numeric inventory stored; preserve publication/availability/category actions. |
| 08 Business Reports | No implemented page/route; sidebar disabled. | No trend/aging/period report endpoint; current summary can be shown with accurate labels only. |
| 09 Notifications | Shared generic inbox plus full reminder workflow; reference emphasizes unread/category/navigation list. | Preserve reminder/communication workflow and actual inbox filters; no fake alert categories. |
| 10 Settings | No implemented page/route; sidebar disabled. | No save-preferences, logo upload, password/session-management API; show unavailable controls honestly. |

## Verification limits identified before editing

Computer-use inventory returned no apps or browsers. Interactive rendered-page
screenshot comparison is unavailable in this session. Reference inspection and
automated React render/service tests will be used; pixel/browser verification
must not be described as passed.

## Restoration completed within existing API support

| Page | Result | Remaining reference differences |
| --- | --- | --- |
| Shared shell | Scoped Inter typography, navy sidebar, white labels, teal gradient selection, reference navigation order, actual shop card, greeting/name/business/date, working page-search links, bell and account menu. All ten destinations enabled. | Existing navy wordmark uses a white backing for contrast rather than a separately recolored logo; initials/store icons replace unavailable profile/shop photos. City/contact/image are absent from business-context projection. Multiple-business accounts show a neutral shared identity instead of guessing the page selection. |
| Dashboard | Three financial cards; Recent Activity and Needs Attention columns; three horizontal working Quick Actions for sales/repayments/products. | Unsupported summary values remain unavailable. Attention uses actual credit customer count and existing pending/active fields; no fabricated overdue-customer/unassigned counts. |
| Customers | Existing reference-style summary/table/details/ledger retained; shared typography, panel borders, focus states and table spacing aligned; customer row padding refined. | Overdue count remains unavailable; no invented customer financial values. |
| Credit Sales | Grouped new-sale panel with existing customer selection, credit overview and amount/notes form; styled two-column fields and Credit Sales History. | Product picker, quantity basket and editable sale date are unsupported by direct amount-posting API. No product basket or new financial calculation was added. History remains the selected customer's effective ledger. |
| Repayments | Unified repayment panel with customer/account information, supported method/reference/notes fields, two-column form and Repayment History. | Recorded dates remain server-owned; no editable date or new pre-submit balance arithmetic. Existing full-payment/receipt/financial-document behavior remains. |
| Credit Orders | Owner-only table of real orders with selection and Order Details, Ordered Products table, existing approval/rejection confirmation and link to full fulfilment. | Existing cash and credit orders both remain accessible. No unsupported customer-credit eligibility balance is manufactured; actual server approval validates current limits/stock under existing rules. |
| Deliveries | Reference-style delivery table before details, selected-row treatment, actual pickup/destination/status/time, recorded Driver/timeline and preserved creation/cancel controls. | No map/GPS/vehicle/contact information in current owner projection; no fake map or tracking. Creation and four actual summary cards are retained as useful existing functions. |
| Shop & Products | Shop Overview from actual linked-business identity; Product Management table with category, real price, manual availability/publication and preserved edit/publish/archive actions. | Neutral icons replace unstored product/shop images. Numeric stock and low-stock filter cannot be shown; actual availability/publication filters and category management remain. |
| Business Reports | New protected route/page matching overview/trend/aging panel hierarchy. Overview reuses real current dashboard API values with accurate current-period labels. | Date-range reports, trends, aging buckets and exports remain explicitly unavailable; no illustrative charts or fake zero totals. |
| Notifications | New Owner-only inbox with actual unread count, read-status tabs, supported event-type categories, date groups, existing safe record links and mark-read/all actions. | Categories use the actual single-type backend filter rather than invented aggregate categories. Existing reminder and communication workflows remain below the inbox. Server pagination is retained instead of fake Load More. |
| Settings | New protected page with four reference sections, read-only actual business/account/language values, existing customer/delivery/inbox navigation and working logout. | Business editing/logo uploads/default delivery preferences/notification toggles/translation/password/session management have no supported APIs; no fake Save, Verified, switches or security actions were added. |

## Exact files changed by this restoration

- `frontend/src/App.jsx`: protected Reports/Settings routes.
- `frontend/src/layouts/ShopOwnerLayout.jsx`, new `shopOwner.css`: scoped shell,
  locally bundled font, business identity read and responsive table/panel styles.
- `frontend/src/components/shopOwner/ShopOwnerSidebar.jsx`, `ShopOwnerHeader.jsx`,
  `OverviewCards.jsx`, `RecentCreditTransactions.jsx`, `QuickActions.jsx`.
- New `frontend/src/components/shopOwner/NeedsAttention.jsx`, `ShopOwnerInbox.jsx`.
- `frontend/src/pages/shopOwner/ShopOwnerDashboard.jsx`, `ShopOwnerCustomers.jsx`,
  `ShopOwnerCreditSales.jsx`, `ShopOwnerRepayments.jsx`, `ShopOwnerDeliveries.jsx`,
  `ShopOwnerProducts.jsx`, `ShopOwnerNotifications.jsx`.
- New `frontend/src/pages/shopOwner/ShopOwnerReports.jsx`, `ShopOwnerSettings.jsx`.
- `frontend/src/pages/customer/OrderHistory.jsx`: Owner-only table/detail branch;
  Customer rendering remains on its existing branch, tested explicitly.
- `frontend/package.json`, `package-lock.json`: `@fontsource/inter` for locally
  bundled 400/500/600/700 font weights. No external runtime font request.
- New `frontend/tests/shopOwnerRestoration.test.js`; updated intentional old-label
  assertions in `creditSalesView.test.js` and `notificationsView.test.js`.
- `docs/shop-owner-ui-restoration.md`: pre-edit audit and completion report.

## Functional preservation

No FastAPI/service URLs, backend code, schemas, migrations, stored balances,
posting arithmetic, JWT or role dependencies changed. Existing financial workflow
controllers, API services, submission handlers, confirmation states, pending-key
retries, validation, receipt actions and uncertainty guards remain in use. Order
approval still uses the original confirmation flow. Product actions and delivery
creation/cancellation dispatch the same operations and payloads as before.
No Customer/Driver/Admin layouts or shared role inbox designs were changed.
The Shop Owner inbox is a separate component reusing the existing notification
workflow and item routing. All new routes remain inside the Shop Owner guard.

No database operations or real-data submissions were performed for this visual
task. Automated tests use synthetic frontend fixtures, not production mock data.
Actual browser interaction with a live authenticated backend remains unverified.

## Actual validation results

- **335 frontend tests passed, zero failed/skipped** in 18.49s, using `node --test`
  on `shopOwnerRestoration`, `creditSales`, `creditSalesView`, `repayments`,
  `repaymentsView`, `shopOwnerDeliveries`, `shopOwnerDeliveriesView`,
  `shopOwnerCatalogue`, `shopOwnerCatalogueView`, `reminders`, `remindersView`,
  `notifications`, `notificationsView`, `shopping`, `shoppingView`,
  `orderFulfilment`, `orderFulfilmentView`, `customerOrderTrackingView` under
  `frontend/tests/` (all `.test.js`). These verify controller submissions,
  schema payloads, role guards, backend-authoritative amounts, retries,
  notification integration and rendered forms/tables. New restoration tests also
  verify all ten sidebar links, unavailable-feature boundaries and unchanged
  Customer detail rendering.
- After the final delivery section reorder, reran `shopOwnerRestoration.test.js`
  and `shopOwnerDeliveriesView.test.js`: **17 passed**, zero failed/skipped, 2.87s.
- Production compilation: **PASS**. Local `.env.local` uses a development API URL
  rejected by existing production validation. The initial build therefore failed
  safely. Rebuilt with process-only
  `VITE_API_URL=https://api.example.invalid/api/v1`; no env file changed. This is
  compilation verification, not a deployed/live endpoint. Existing large-chunk
  warning remains. See `.server-logs/owner-ui-build-final.log`.
- Full `npm run lint`: **FAIL**, **7 errors and 1 warning** remaining in existing
  code: synchronous state updates in effects (Customers x3, Dashboard x1), three
  unused test imports in `repayments.test.js`, and Dashboard effect dependency
  warning. These baseline hook/test issues were not rewritten during visual
  restoration. Removed one pre-existing unused Dashboard icon import.
- Scoped ESLint on App, layout, shell components, new components/pages, modified
  transaction/delivery/product/notification pages and Owner order view: **PASS**.
  Customers/Dashboard retain the baseline effect diagnostics above; full lint is
  not represented as passing.
- `git diff --check`: no whitespace errors in frontend changes (existing Git
  line-ending notices only).
- Initial test run had two obsolete label/disabled-feature assertions (and their
  parent suite failures); updated them for the intentionally restored Quick
  Actions and Owner inbox. Final selections above pass.

Ignored logs: `.server-logs/owner-ui-tests-final.log`,
`owner-ui-final-check.log`, `owner-ui-build-final.log`, `owner-ui-lint-final.log`,
`owner-ui-scoped-lint.log`.

## Remaining verification and implementation limits

All ten references were visually inspected, but no browser was available in the
computer-use inventory. Automated React rendering is not pixel comparison,
viewport interaction, focus navigation or live end-to-end testing. Those checks
remain **NOT RUN**; screenshot parity is not certified. The differences in the
table above remain visible by design where backend capabilities do not support
the screenshot. Full lint remains blocked by the listed existing diagnostics.

Existing development database schema/operational blockers are unchanged; this
frontend restoration does not resolve them or verify migration execution. No
database reset/upgrade, production-data change, deployment, commit, push or AI
Summary work was performed.
