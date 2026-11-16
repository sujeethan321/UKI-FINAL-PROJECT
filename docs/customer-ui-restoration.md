# Customer approved UI restoration

## Pre-edit audit — 2026-11-08

All ten images in `design-references/customer/` were opened and inspected before
editing. Existing Customer pages, layout, services, parsers, request readers,
shopping provider and matching FastAPI response schemas/routes were traced.

| Reference | Current mismatch | Backend/interaction boundary |
| --- | --- | --- |
| Shared shell | Header title instead of broad search/avatar menu; flat active sidebar, muted labels, no actual user bottom profile. | Search can route to existing shop-name catalogue search; no global product search endpoint. |
| 01 Dashboard | Four unrelated summary cards, stacked shop/account/activity cards rather than financial trio, credit table and recent orders. | Aggregate due-soon/overdue/deadline fields absent. Do not calculate them from a visible history page. |
| 02 Browse Shops | Already a three-column grid, but plain icon cards, small headings, narrow search and no reference visual hierarchy. | Approved eligible shops only; API projects name/product count, not photos/location/category/hours/delivery promises. |
| 03 Shop & Products | Compact identity card, shallow placeholders, plain product cards and no cart preview. | Manual availability, not inventory counts; no stored images. Existing AddToCart and scoped catalogue filters must remain. |
| 04 Cart & Checkout | Stacked cart/payment panels, no sticky summary, plain vertical item rows. | Cash and credit supported; no delivery mode/address/fee or terms-document API. Quote/submit totals and debt policy must remain unchanged. |
| 05 My Orders | Stacked record cards rather than table/selected-detail arrangement. | Preserve actual order statuses, confirmation/cancel and scoped delivery tracking. No unsupported global date/search parameters. |
| 06 Credit Accounts | Dashboard anchor and per-account routes, no dedicated overview page matching reference. | Existing authoritative summary, paginated accounts, transactions, account details and PDF statements can be reused. No global running-balance inference. |
| 07 My Deliveries | Tracking exists only within orders; no dedicated page. | No aggregate Customer delivery endpoint, ETA/GPS/driver/contact/address projection. May join bounded owned-order pages to existing per-order tracking. |
| 08 Notifications | Generic inbox with selects, no prominent reference row/icon treatment. | Reuse recipient-scoped read/type/page filters and mark-read workflow; no promotions endpoint. |
| 09 My Profile | Missing page, sidebar disabled. | Authenticated /auth/me supports basic identity/account state; no saved-address, photo, DOB/gender, verification or profile-edit API. |
| 10 Settings | Missing page, sidebar disabled. | No preference/privacy/password/2FA/session editing APIs. Render honest sections and existing navigation/logout. |

Other role layouts and business workflows must remain unchanged. Reference
names, dates, photos and balances must not enter production UI as sample data.

## Implemented restoration and remaining visual differences

| Page | Completed | Remaining screenshot differences / unsupported interactions |
| --- | --- | --- |
| Shared shell | Scoped Inter font, navy sidebar with white/teal transparent logo, white navigation/icons, teal gradient active links, authenticated identity footer, white header search and avatar/account menu, responsive card/table spacing. | Initials replace unstored profile photos. Search is explicitly shop-name search, not an unsupported global product search. Legacy My Shops, Cart and Transactions links remain available alongside new destinations. |
| 01 Dashboard | Three financial cards, account table with View Ledger actions, independently loaded Recent Orders table, Next Payment banner, personalized welcome. Existing linked-shop and recent-transaction previews remain. | Due Soon/Overdue values and next payment date/amount are unavailable, not inferred. Extra legacy preview sections remain below the primary sections. Greeting remains personalized Welcome rather than a fabricated screenshot identity/date. |
| 02 Browse Shops | Three-column desktop cards with large intentional image placeholders, teal View Shop buttons, real names/product counts, existing bounded shop search/pages, improved title/card hierarchy. | No stored photos, public category/location/hours/credit/delivery flags. No fake location, sort, open badge or category controls. |
| 03 Shop & Products | Larger shop identity card, three-column product grid, prominent image placeholders, real prices/availability, working category buttons and existing filters, quantity input/Add to Cart, actual cart-content preview. | Manual availability is not stock quantity. Photos, numerical inventory, global sort and shop contact/location projection are unavailable. Cart preview directs to the server-quoted cart instead of calculating a partial product-page subtotal. |
| 04 Cart & Checkout | Two-column responsive cart and sticky summary/payment area, compact item rows, existing quantities/removal/clear/price refresh, actual server subtotal/total and credit guidance, retained cash/credit methods. | No supported delivery/pickup/address/fee/terms-document selection. Explicit unavailable delivery panel replaces those controls. Cash remains unpaid; credit submission creates no debt. |
| 05 My Orders | Actual-state status tabs, table/selected-detail arrangement, page-specific search/sort, original cancellation confirmation and recorded Customer tracking, existing direct detail URLs. | No global order search/date/sort API: search/sort are explicitly current-page only. Completed order is not relabelled Delivered; delivery/payment states remain distinct. No product photos or recipient address projection. |
| 06 My Credit Accounts | New guarded overview route with backend-authoritative summary, paginated account selection, existing scoped account detail/activity, statement/PDF navigation and recent transactions table. | No due/overdue aggregates, support messaging or invented global running balance. Select an account to access its actual statement and supported PDF download. |
| 07 My Deliveries | New guarded page joins one bounded owned-order page with actual per-order delivery projections; selection, recorded timeline, search/status tabs and refresh. | No aggregate Customer deliveries endpoint. Pagination counts orders; page-local filters and incomplete cross-page totals are clearly labelled. No ETA/GPS/distance/driver/contact/recipient/address data is invented. |
| 08 Notifications | Customer-only inbox with actual unread count, supported event tabs, read/type filters, icon rows, date/read/action display, mark-one/all and server pagination. | No promotions/system announcements API or invented category statuses. Existing exact event filters are used; shared inbox designs for other roles remain unchanged. |
| 09 My Profile | New guarded profile page with actual authenticated identity, personal information, address and verification sections; Settings navigation. | /auth/me returns ID/name/email/role/account status only. Phone/DOB/gender, photos, member-since, saved delivery addresses, edit controls and verification flags are unavailable. Active account is not labelled Verified. Business-specific financial customer addresses are not repurposed as a saved address book. |
| 10 Settings | New guarded Notifications/Application Preferences/Privacy/Security sections with supported inbox/profile/accounts navigation and logout. | No fake toggles, enabled counts, preference saves, visibility/sharing analytics settings, password/2FA/session management or help-center service. Current LKR/light presentation is described without claiming editable persisted preferences. |

## API and architecture preservation

Existing authenticated shared Axios, Router role guard, shopping provider/session
keys, request cancellation, customer response parsers and read workflows remain
in use. No endpoint, backend code, schema, migration or financial formula changed.
No ledger balances are calculated by summing visible transactions. No real data,
database write, deployment, commit, push or AI Summary action occurred.

Actual `/api/v1` endpoints reused:

- `/auth/me`: existing authenticated identity loaded by AuthProvider.
- `/customer/dashboard/summary`, `/customer/shops`, `/customer/credit-accounts`,
  `/customer/credit-accounts/{id}`, `/customer/transactions`, and existing account
  `/statement` / `/statement.pdf` endpoints. `routers/customer.py` enforces
  authenticated stored Customer role; services scope records to that identity.
- `/customer/catalogue/shops`, `/shops/{businessId}`, and its categories/products
  subpaths from `routers/catalogue.py`, preserving eligible public projections.
- `/customer/orders/quote`, `/customer/orders`, `/customer/orders/{id}`, existing
  decision and `/delivery` endpoints from `routers/orders.py`.
- Existing recipient-scoped notification list/count/read endpoints and workflow.

The new delivery service performs at most ten tracking reads after one bounded
owned-order list read. Wrong tracking identity or any failed read fails the page
closed rather than treating missing/unauthorized responses as no deliveries.
The new order projection parser validates actual IDs/statuses/Decimal strings
and discards unrelated fields. Financial pages retain their original parsers.
Repayment navigation seeds only the existing validated transaction-type filter.

Customer UI additions remain within the existing Customer Router guard. Existing
Customer paths and dashboard hash targets remain valid. Shop Owner order table
and shared decision handling are retained; new Customer table rendering is on
the Customer branch. Shared NotificationItem gained an optional leading icon;
other roles receive no new icon or styling. No other role layout was edited.

## Exact files changed by this task

Modified:

- `frontend/src/App.jsx`: four Customer routes.
- `frontend/src/layouts/CustomerLayout.jsx`.
- `frontend/src/components/customer/CustomerSidebar.jsx`, `AddToCart.jsx`.
- `frontend/src/pages/customer/CustomerDashboard.jsx`, `CustomerCatalogue.jsx`,
  `ShoppingCart.jsx`, `OrderHistory.jsx`, `CreditAccountDetails.jsx`,
  `TransactionHistory.jsx`, `CustomerNotifications.jsx`.
- `frontend/src/components/notifications/NotificationItem.jsx` (optional icon).
- `frontend/src/services/customerDashboardService.js` (existing accounts endpoint,
  explicit full-page pagination helper).
- `frontend/src/utils/customerCatalogue.js` (bounded initial query for header search).
- `frontend/tests/customerDashboardView.test.js`,
  `frontend/tests/customerCatalogueView.test.js` (intentional layout/navigation
  assertions and Router wrapper for newly linked dashboard views).

Created:

- `frontend/src/layouts/customer.css` (Customer-scoped styles only).
- `frontend/src/components/customer/CustomerCreditOverview.jsx`,
  `CustomerRecentOrders.jsx`, `CustomerCartPreview.jsx`, `CustomerInbox.jsx`.
- `frontend/src/pages/customer/CustomerCreditAccounts.jsx`,
  `CustomerDeliveries.jsx`, `CustomerProfile.jsx`, `CustomerSettings.jsx`.
- `frontend/src/services/customerDeliveryService.js`.
- `frontend/src/utils/customerOrders.js`.
- `frontend/tests/customerRestoration.test.js`.
- `docs/customer-ui-restoration.md` (this audit/report).

No package changes were needed: the existing locally bundled Inter dependency
from the Shop Owner restoration is reused.

## Actual verification results

- **Full frontend suite: 836 passed, zero failed/skipped**, 76.97 seconds, using
  `npm test` / `node --test`. Includes Customer dashboard/accounts/history,
  catalogue, shopping/cart/checkout, order tracking, notifications and all
  existing Shop Owner/Driver/Admin frontend tests.
- New restoration coverage verifies actual navigation/identity, authoritative
  financial summary without due-date inference, statement links, bounded delivery
  join semantics, profile/verification boundaries, honest settings, inbox
  authorization concealment, header search initialization, validated order
  projections and JWT Axios endpoint/signal usage. Synthetic adapters test these
  contracts; this is not a live MySQL or browser end-to-end result.
- After improving the final cart unavailable-value label, reran
  `shoppingView.test.js` and `customerRestoration.test.js`: **20 passed**, zero
  failed/skipped, 13.25 seconds. Recorded in
  `.server-logs/customer-ui-final-check.log`.
- **Vite production build: PASS**, final recorded run 7.81 seconds. Used
  process-only `VITE_API_URL=https://api.example.invalid/api/v1` to satisfy
  production configuration validation; no environment file was changed and no
  deployment/live API claim is made. Existing >500 kB bundle warning remains.
- **Scoped ESLint: PASS** for Customer layout, all Customer components/pages,
  modified catalogue utility/new order parser, Customer services, shared item
  and App routes.
- **Full `npm run lint`: FAIL**, unchanged **7 pre-existing errors and 1 warning**:
  synchronous effect state updates in ShopOwnerCustomers (3) and
  ShopOwnerDashboard (1), unused repayment test imports (3), and the existing
  Dashboard dependency warning. No Customer lint diagnostic remains.
- `git diff --check`: no whitespace errors in changed frontend paths; existing
  Git line-ending notices only.
- The first focused run exposed obsolete label/anchor assertions and the direct
  Dashboard render fixture missing Router context after new navigation links.
  Updated those intentionally changed assertions/fixture. The first full run
  then found two remaining old catalogue copy/anchor assertions; corrected them.
  The final full suite above passed.

Ignored local logs: `.server-logs/customer-ui-full-tests-final.log`,
`customer-ui-final-check.log`, `customer-ui-build-final.log`,
`customer-ui-lint.log`, `customer-ui-scoped-lint-final.log`.

## Browser, screenshot and operational limits

All ten reference PNGs were visually inspected. Computer-use inventory again
returned `apps: []` and `browsers: []`. Consequently interactive viewport,
keyboard, live authenticated API and screenshot/pixel comparison are **NOT RUN**;
no restored-page screenshots are available. Automated React SSR and workflow
tests do not certify screenshot parity. The visual differences in the table
remain intentionally visible where the current backend cannot support them.

Backend tests were unnecessary for this frontend task; no database was accessed
for writes or migrated. Existing development schema/migration blockers documented
in earlier reports were not repaired or reverified live. Successful mocked
frontend contracts/build do not certify development or production API readiness.
Unsupported capabilities listed above require separate implementation, not fake
UI or automatic database remediation.
