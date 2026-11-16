# Phase 1, Step 1.1: Database and UI compatibility audit

Audit date: 2026-11-08. Scope: repository source, all 26 approved reference PNGs, and fresh read-only MySQL schema metadata. This is a proposal, not implementation approval or a migration execution certificate.

## Verified findings

- `SELECT DATABASE()` returned **lankapex_db**, with APP_ENV **development**, local host, MySQL **8.0.46**.
- **17 application tables**, **18 including alembic_version**. There are **20 SQLAlchemy model tables** and no unexpected application tables or views.
- Database revision: **c9d5e8f7a237**. Single repository head: **03b9c2d1e671**. Four unapplied revisions are listed below.
- Missing modeled tables: **orders, order_items, admin_audits**. **products and product_categories now exist**; older reports of their absence do not describe this snapshot.
- All columns of the 17 existing model tables are present, with matching effective types/lengths/precision/nullability after normalizing inherited collations, MySQL BOOL/TINYINT, and NUMERIC/DECIMAL aliases. These aliases are not reasons to alter columns. Existing indexes/checks/relationships and pending constraint differences are inventoried in the appendices.
- All **10 Shop Owner, 10 Customer and 6 Driver** reference files exist and decoded successfully. Their exact paths, dimensions and SHA-256 hashes are in Appendix C. They have been visually inspected in the UI restoration work in this session. Screenshot examples are illustrative, not records to seed into production.
- Existing orders, driver_profiles, delivery_requests, delivery_assignments, delivery_status_events, ledger and audit structures should be preserved. New dashboard/summary/chart/badge tables are unnecessary.

Recommended next compatibility milestone: **25 application tables**: the 20 already modeled, plus customer_addresses, vehicles, vehicle_documents, user_preferences and business_settings. This is a proposed scope, not a claim that five new tables are required just to render the current pages. A minimal operational baseline is **20** after separately authorized migration reconciliation. Persistent carts and monetary driver earnings/payouts remain conditional; see the explicit count scenarios below.

## Evidence and limits

The diagnostic `.server-logs/phase1-db-ui-audit.py` checked environment/target before connecting, enabled session read-only transactions, asserted the connected database, and permitted only SELECT/SHOW/DESCRIBE metadata SQL and the exact read-only session setting. It retrieved table definitions and Alembic version, not user rows, passwords, tokens, financial amounts or record counts. The diagnostic engine was disposed afterward; no session was switched to read-write.

Full raw metadata is locally retained in `.server-logs/phase1-schema-inventory.json`; the durable schema, route and reference inventory is included in this report. No application code, model, migration, environment file or reference image was changed. No database-changing tests, DDL, DML, Alembic commands, new database creation, deployment or push were executed. Existing tests are not relabelled as fresh passes. A schema-compatible database alone does not prove runtime authorization or UI pixel compatibility. Live endpoint execution and new browser visual verification were not part of this read-only metadata audit.

## Connection resolution

`backend/app/core/config.py` uses Pydantic Settings. For development/testing, precedence is explicit initialization, process environment, backend `.env`, file secrets. Production excludes dotenv and requires selection via the process environment. MYSQL_DATABASE is required; there is no fallback database. Testing configuration requires lankapex_test_db. Production validates non-local targets and TLS requirements.

`backend/app/core/database.py` constructs a mysql+pymysql SQLAlchemy URL from settings, without string interpolation. Engine options include pool_pre_ping, pool_recycle=1800, echo=False, hide_parameters=True and a bounded connection timeout. TLS uses CA verification when configured and is enforced for production. SessionLocal uses autocommit=False/autoflush=False. `backend/alembic/env.py` imports the same engine and Base metadata with compare_type=True. The audit used ScriptDirectory to read revisions, without executing env.py. No credentials or connection URLs are reproduced here.

## Revision chain and schema drift

Dependency order (one linear chain):

| Revision | Change | State |
|---|---|---|
| 79d8d51548c6 | Initial users/businesses/members/customer_profiles/credit_accounts/ledger_entries | Applied ancestry |
| b2a1c4d6e8f0 | Business approval audit | Applied ancestry |
| c3d9e2f1a601 | Payment reminders | Applied ancestry |
| d4e0f3a2b702 | In-app notifications | Applied ancestry |
| e5f1a4b3c803 | Communication consents/attempts | Applied ancestry |
| f6a2b5c4d904 | Driver profiles/delivery requests/assignments | Applied ancestry |
| a7b3c6d5e015 | Delivery status events | Applied ancestry |
| b8c4d7e6f126 | Delivery notification constraints | Applied ancestry |
| c9d5e8f7a237 | Product categories/products | Current recorded revision |
| d0e6f9a8b348 | Orders/items; notification constraint expansion | Pending |
| e1f7a0b9c459 | Order/delivery composite business FK and unique link | Pending |
| f2a8b1c0d560 | Order/delivery notification compatibility | Pending |
| 03b9c2d1e671 | Admin audits; driver approval notifications | Pending head |

Revision ancestry is recorded history, not proof each historical statement ran without manual drift. Appendix A provides actual definitions.

Pending effects include missing `uq_delivery_id_business` on delivery_requests and notification checks that do not yet allow the latest order/admin event types. The nullable `orders.delivery_request_id` and its business-scoped FK exist only in the model/future migration, since orders itself is absent. Notification check changes must follow the dependency chain: do not jump directly to the last constraint definition.

`ledger_entries.order_id` is already present and nullable in both the database and model, **without an FK to orders**. The authoritative order credit link is `orders.credit_sale_id` (unique FK to ledger_entries). Do not infer ledger ownership from the unvalidated order_id field or add an FK blindly before checking its provenance and orphan values. No records were read to assess those values. Retain the authoritative credit_account ownership chain and reversal logic.

The three missing tables are enough to make order-dependent screens and some Admin aggregates fail when their queries execute. This audit does not claim a particular HTTP exception was reproduced. Schema prerequisites and live application failures are different evidence.

## UI contract map: all 26 approved screens

All routes below are existing routes relative to **/api/v1**. Router files are under backend/app/routers; backend services under backend/app/services; frontend services under frontend/src/services. Page names refer to frontend/src/pages unless otherwise stated. New API capabilities described as proposals are not current endpoints. Shared identity/sidebar/heading/date/icon/tab/count/empty/loading/error presentations do not warrant tables. All monetary values must come from scoped server calculations.

### Shop Owner: 10 screens

| Reference / React page | Displayed data and frontend service | Backend route/service and models | Compatibility and required work |
|---|---|---|---|
| 01-dashboard / shopOwner/ShopOwnerDashboard.jsx, OverviewCards, RecentCreditTransactions, NeedsAttention | Outstanding, collected today, overdue, customer/activity rows, pending orders/deliveries, quick actions; shopOwnerDashboardService | GET /shop-owner/business-context, /dashboard/summary, /dashboard/recent-transactions; shop_owner.py; shop_owner_dashboard_service; businesses, members, customer_profiles, credit_accounts, ledger_entries | Outstanding/customer counts/recent scoped ledger exist. Collected-today/overdue/pending-orders/active-deliveries summary values are currently unavailable in the dashboard service. Today totals can be derived from effective ledger with timezone policy; order/delivery counts from existing models after migration. Aging needs payment allocation policy. No dashboard table. Preserve user-requested removal of the extra Viewing business row. |
| 02-customers / ShopOwnerCustomers.jsx, AddCustomerModal, ManageCustomerModal | Name/phone/address, status, limit, outstanding, available credit, terms, summary/search/filter/page; shopOwnerCustomerService | GET/POST /shop-owner/customers; GET/PATCH /customers/{customer_id}; POST/PATCH /customers/{customer_id}/credit-account; shop_owner.py; shop_owner_customer_* services; customer_profiles, accounts, ledger | Business-owned records and ledger-backed details exist. UI filtering across a bounded loaded collection is not a full-dataset server search. Add scoped search/pagination contracts if required. Overdue needs aging policy, not another balance column. |
| 03-credit-sales / ShopOwnerCreditSales.jsx and creditSaleWorkflow | Customer/credit position, amount, notes, transaction result; screenshot item/product/quantity detail; shopOwnerCreditSaleService | POST /shop-owner/credit-sales; shop_owner.py; shop_owner_credit_sale_service, ledger_service; accounts, ledger, profiles | Amount-based idempotent ledger sale exists. Direct credit sale has no product-line persistence. Reuse orders/order_items for product-based credit purchases; do not create purchase_orders. Historical date editing and itemized direct-sale workflow are unsupported, not safe inferred fields. |
| 04-Repayments / ShopOwnerRepayments.jsx | Customer, balance, amount, method/reference/notes, receipt and remaining position; shopOwnerRepaymentService, shopOwnerFinancialDocumentsService | POST /shop-owner/repayments; GET /repayments/{repayment_id}/receipt; GET /customers/{customer_id}/statement; shop_owner.py; repayment/financial_documents/ledger services; accounts, ledger, profiles | Existing repayment and receipt records suffice. Recorded time is server-owned, not editable screenshot input. Receipt/statement export does not need a documents table. Remaining preview must be confirmed by server transaction. |
| 05-Credit-orders / customer/OrderHistory.jsx owner branch, OrderFulfilment | Reference/customer/items/qty/prices/totals, method/status, approval/rejection, delivery link; orderService | GET /shop-owner/orders and /{order_id}; POST /{order_id}/decision; GET/POST /{order_id}/delivery; orders.py; order_service, order_delivery_service; orders/items, accounts, ledger, deliveries | Backend already implemented but tables absent in dev. Credit approval posts exactly once with unique credit_sale_id/idempotency; preserve it. Available-credit projection can reuse scoped account data. No duplicate order model. |
| 06-Deliveries / ShopOwnerDeliveries.jsx | Reference, pickup/destination areas, status, assigned driver/time, timeline, summary/create/cancel; shopOwnerDeliveryService | GET/POST /shop-owner/deliveries; GET /summary, /{request_id}; POST /{request_id}/cancel; shop_owner_deliveries.py; shop_owner_delivery_service, driver_service; requests/assignments/events/profiles, order link | Current areas/status/history persist. Exact recipient/contact/addresses/fee/map/ETA are not stored. Add private delivery snapshots only if required, and restrict disclosure to authorized owner/customer/assigned driver; public jobs should retain coarse areas. |
| 07-shop $ Products / ShopOwnerProducts.jsx | Shop context, category/product/name/description/price/manual availability/publication, category totals/filter/actions; shopOwnerCatalogueService | GET /shop-owner/catalogue/summary; GET/POST/PATCH /products and /categories; catalogue.py; catalogue_service; businesses, products/categories | Catalogue tables now exist. Photos, numeric stock, low-stock rules, shop logo upload and detailed public shop information are unsupported. Existing business phone/address need DTO exposure before new columns. Images require storage policy, not a fake URL. |
| 08-Reports / ShopOwnerReports.jsx | Period filters, sales/repayment/outstanding metrics, trend and aging charts, export; shopOwnerDashboardService currently | Existing dashboard summary only; no report endpoint; dashboard/ledger services; ledger/accounts/profiles | Current page has limited real summary. Period metrics/trends derive from ledger with stable cutoff and reversal policy; historical versus current-effective reporting must be explicit. Aging requires allocation rules. Scoped report/export API proposed; no chart/report table initially. |
| 09-Notifications / ShopOwnerNotifications.jsx, ShopOwnerInbox | Recipient messages, types/date groups/read flags/unread tabs/actions; notificationService, reminder/communication services | GET /notifications, /unread-count; PATCH /{id}/read, /read-all; notifications.py; notification_service; notifications; reminders/consents/attempts use their existing separate owner routes | Supported event/read state already stored. Groups/icons/filters derive from records. External message handoff is not delivery confirmation. Preference persistence requires user_preferences; no new notification delivery claims. |
| 10-Settings / ShopOwnerSettings.jsx | Shop details/logo, default credit terms/delivery range, language/alerts, security controls; auth/business context | Existing GET /auth/me, /shop-owner/business-context; auth.py/shop_owner.py; users/businesses/members | Present cards are read-only. Business phone/address and user language exist but are not fully projected. Persist genuine defaults in business_settings; do not rewrite existing accounts when changing defaults. Password/session/2FA controls require separate auth work, not enabled decorative switches. |

### Customer: 10 screens

| Reference / React page | Displayed data and frontend service | Backend route/service and models | Compatibility and required work |
|---|---|---|---|
| 01-Dashboard / CustomerDashboard.jsx, CustomerCreditOverview, CustomerRecentOrders | Customer identity, linked shops, outstanding/available credit, account rows, recent orders, next payment; customerDashboardService, orderService | GET /customer/dashboard/summary, /shops, /credit-accounts, /transactions; customer.py/customer_dashboard_service; orders.py/order_service; profiles, accounts, ledger, orders/items | Credit summary exists; order tables absent. Next-payment/due aggregates unsupported without aging policy. Keep account totals independent of displayed history page. No summary table. |
| 02-Browse-shops / CustomerCatalogue.jsx explore | Shop/name/photo/category/location/availability/credit/delivery filters, search/page; customerCatalogueService | GET /customer/catalogue/shops; catalogue.py/catalogue_service; approved businesses, published products | Current public DTO gives ID/name/product count; real photos/location/hours/eligibility flags largely absent. Expose safe existing business fields first. Do not treat business_type as product category or mere linked account as guaranteed credit eligibility. |
| 03-shop-products / CustomerCatalogue.jsx shop/product, CartPreview | Shop detail, categories, product names/descriptions/prices/images/availability, quantity/cart; customerCatalogueService, ShoppingProvider | GET /customer/catalogue/shops/{business_id}, /categories, /products, /products/{product_id}; catalogue.py/catalogue_service; businesses/products/categories | Current catalogue works with manual availability and placeholder media. No numeric stock/reservations. Cart is single-shop React memory. Server quote rechecks actual prices and eligibility. |
| 04-Shop-cart / ShoppingCart.jsx | Items/qty/price/subtotal/total, cash/credit, credit position, delivery option/address/fee, submit; orderService, ShoppingProvider | POST /customer/orders/quote and /customer/orders; orders.py/order_service; orders/items/accounts/ledger/products | Existing quote/submit implemented but dev order tables absent. No saved cart/address/delivery fee. Existing check subtotal=total forbids adding fees without deliberate financial changes. Persist address snapshots separately from editable address book; do not imply cash collected or add fees solely in React. |
| 05-My-Orders / OrderHistory.jsx, CustomerOrderTable/Tracking | Reference/shop/date/items/amount/method/status/detail/cancel/progress; orderService | GET /customer/orders and /{order_id}; POST /{order_id}/decision; GET /{order_id}/delivery; orders.py/order_service/order_delivery_service; orders/items/requests/events | Tables missing in dev, service exists. Order completion and delivery completion are distinct. Search/sort of a displayed page is not global filtering. Customer DTO intentionally limits delivery data. |
| 06-Mycredit-Accounts / CustomerCreditAccounts.jsx, CreditAccountDetails, TransactionHistory, CreditStatement | Shop/account/limit/outstanding/available/advance/status, credit sale vs repayment, period statement/running balances/PDF; customerDashboardService | GET /customer/credit-accounts and /{id}; /transactions; /credit-accounts/{id}/statement and .pdf; customer.py/customer_dashboard_service/customer_statement_pdf/ledger_service; profiles.user_id, accounts.creditor_business_id, ledger | Existing model provides these fields. Overdue/next due need policy, not stored mutable balance. Ownership must require authenticated user linked to business-owned profile and matching account business; arbitrary account IDs cannot widen scope. |
| 07-Mydeliveries / CustomerDeliveries.jsx | Own order/delivery reference/status/times/progress, expected driver/contact/location UI; customerDeliveryService | Lists one page of owned orders, then GET /customer/orders/{order_id}/delivery; orders.py/order_delivery_service; orders/requests/assignments/events | Current projection gives status/times/events, not driver contact/GPS/ETA/addresses. Current first-page fan-out is not a complete delivery history. Propose authorized paginated aggregate projection using existing joins before adding tables. |
| 08-Notifications / CustomerNotifications.jsx, CustomerInbox | Own messages/event/read state/date tabs; notificationService | Shared /notifications routes; notification_service; notifications recipient FK | Already supported for current event types. Marketing/push settings/provider delivery unsupported. No separate customer_notifications table. |
| 09-Myprofile / CustomerProfile.jsx | Name/email/phone/member-since/language/account, avatar, personal details/saved addresses/edit; authService/AuthContext | GET /auth/me; auth.py; users | DTO currently exposes only core identity/role/status. users already has phone, preferred_language, created_at: extend safe own-user DTO first. No DOB/gender/avatar/address book; do not collect optional sensitive demographics merely to fill screenshot fields. customer_profiles.address is shop-owned, not a global address book. |
| 10-settings / CustomerSettings.jsx | Language/theme/alerts/privacy/security/session controls; AuthContext | No settings write API; auth.py/users existing | Current settings are honest read-only controls. Use existing user language field and scoped preferences if enabled. Password changes/session revocation/2FA need real backend behavior and separate acceptance/security requirements. |

### Driver: 6 screens

| Reference / React page | Displayed data and frontend service | Backend route/service and models | Compatibility and required work |
|---|---|---|---|
| 01-dashboard / DriverDashboard.jsx, DriverJobsPanel | Identity/eligibility, available jobs, active/completed counts, own preview/accept, today/earnings/presence expectations; driverDashboardService/driverJobsService | GET /driver/profile, /dashboard/summary, /deliveries, /jobs; POST /jobs/{job_id}/accept; driver.py/driver_service; profiles/requests/assignments/events | Real counts available; completed is all-time, not today. No fees/earnings/online presence/distance. Today counts derive with timezone rules. Preserve latest user removal of Profile & Vehicle section from this page; separate profile/vehicle pages remain. No automatic approval or presence toggle. |
| 02-my-deliveries / DriverDeliveries.jsx | Own references/areas/status/timestamps/timeline/detail/allowed actions/history; driverDeliveriesService | GET /driver/deliveries, /history, /deliveries/{job_id}; POST /deliveries/{job_id}/status; driver.py/driver_service; assignments/requests/events | Existing lifecycle available -> assigned -> picked_up -> in_transit -> delivered; business cancellation follows existing policy. Uniqueness/transaction ownership and expected status prevent conflicting changes. Exact route/contact/fee/map data absent. Persisted delivery time can derive from delivered event. |
| 03-my-earnings / DriverEarnings.jsx | Today/period/lifetime earnings, trend/history, withdrawable/payout details | No earnings/payout service/API/model | Currently unavailable placeholders; must remain so until fee, entitlement, adjustments and settlement rules exist. Completed count is not earnings. Requires dedicated immutable financial records if activated; deferred scope below. |
| 04-my-vehicle / DriverVehicle.jsx, DriverProfileForm | Vehicle type/registration, make/model/year/photo, verification/documents/expiry | GET/POST /driver/profile; driverDashboardService; driver.py/driver_service; driver_profiles | Only vehicle_type and registration_reference stored, initial submission constrained. Driver approval is not vehicle document verification. vehicles/docs proposals add detail/history without replacing driver_profiles or migrating unverified strings into approved facts. |
| 05-notifications / DriverNotifications.jsx, DriverInbox | Personal delivery/approval/read/date groups/unread | notificationService; /notifications; notification_service; notifications | Existing recipient-owned messages suffice. Earnings/payout/document alerts require their future domain events and constraint changes. Visual icons and date groups are derived. |
| 06-my-profile / DriverProfile.jsx, useDriverProfile | Name/email/account/driver approval/vehicle, phone/address/personal/verification/edit controls | GET /auth/me and /driver/profile; authService/driverDashboardService; auth.py, driver.py/driver_service; users/driver_profiles | Current own identity/approval supported. Existing users phone/time not projected. No NIC/identity verification/location editing/presence records. Account active does not mean verified; no self-approval endpoint. Optional sensitive profile expansion deferred. |

## Proposed schema and contracts

These are **design recommendations**, not implemented endpoints. Existing routes above are real; new capabilities below deliberately name a proposed service operation rather than inventing a live URL. All new IDs BIGINT PK, all dates UTC DATETIME, all money DECIMAL and serialized as strings, all FKs RESTRICT unless an explicit retention decision permits otherwise. Every proposal must retain authenticated identity and object scope in its backend query, not trust client user/business/driver IDs. Required new fields should initially be nullable for legacy rows and become NOT NULL only after separately approved validation/backfill; unknown values must not be invented.

### New tables justified for the next compatibility milestone

| Table / priority | Recommended columns and nullability | Relationships, checks and indexes | UI/API changes |
|---|---|---|---|
| customer_addresses / Important | address_id PK; user_id BIGINT NOT NULL; label VARCHAR(50) NOT NULL; recipient_name VARCHAR(150) NOT NULL; phone VARCHAR(20) NULL; address_line VARCHAR(500) NOT NULL; city VARCHAR(100) NULL; latitude DECIMAL(9,6) NULL; longitude DECIMAL(10,6) NULL; created_at/updated_at NOT NULL | user_id -> users; index(user_id,address_id); nonblank label/name/address; coordinate pair and latitude -90..90/longitude -180..180. Default address optional nullable preferred_address_id on user_preferences with composite ownership FK(address_id,user_id) -> addresses unique(address_id,user_id), or omit default until needed. | Customer profile/cart: proposed own-address list/create/update/archive operations; select only own address and snapshot it server-side into order. Do not reuse shop customer_profiles as addresses or physically delete snapshots. |
| vehicles / Important | vehicle_id PK; driver_user_id BIGINT NOT NULL; vehicle_type VARCHAR(50) NOT NULL; registration_reference VARCHAR(50) NOT NULL; make/model VARCHAR(100) NULL each; model_year SMALLINT NULL; image_storage_key VARCHAR(500) NULL; lifecycle_status VARCHAR(20) NOT NULL; created_at/updated_at NOT NULL | driver_user_id -> driver_profiles.user_id; index(driver_user_id,vehicle_id); status active/retired; year 1900..2100; nonblank registration. Local registration uniqueness/normalization needs jurisdiction decision before a global unique constraint. | DriverVehicle: proposed own vehicle read/update; Admin review projections. Preserve original profile pair for compatibility, explicitly mark unverified imports. Do not infer make/model from free text. |
| vehicle_documents / Important | document_id PK; vehicle_id BIGINT NOT NULL; document_type VARCHAR(30) NOT NULL; storage_key VARCHAR(500) NOT NULL; review_status VARCHAR(20) NOT NULL default pending; expires_on DATE NULL; reviewed_by BIGINT NULL; reviewed_at DATETIME NULL; rejection_reason VARCHAR(500) NULL; created_at NOT NULL | FKs vehicle, reviewer users; pending/approved/rejected/expired enum check; review fields required for approved/rejected, no auto approval; index(vehicle_id,document_type,created_at). Version documents instead of overwriting evidence; one-current-version rule transactional if adopted. | Private upload/download/own status and authorized Admin review operations; short-lived authorized access, file validation/retention. No public storage URL in job list. |
| user_preferences / Important | user_id BIGINT PK NOT NULL; theme VARCHAR(10) NOT NULL default system; in_app_notifications BOOLEAN NOT NULL default true; email_notifications BOOLEAN NULL; preferred_address_id BIGINT NULL if default needed; updated_at NOT NULL | user FK; theme light/dark/system; boolean checks; composite default-address ownership FK as above. NULL email preference means unset, not consent. Keep mandatory security/operational notices unaffected. | All role Settings: proposed own preferences read/patch; use existing users.preferred_language rather than duplicate language column. External delivery/consent remains separate. |
| business_settings / Important | business_id BIGINT PK NOT NULL; default_credit_limit DECIMAL(14,2) NULL; default_payment_term_days INT NULL; delivery_enabled BOOLEAN NOT NULL default false; delivery_radius_km DECIMAL(7,2) NULL; updated_at NOT NULL | business FK; limit >=0, terms >0, radius >0 when set; owner membership required on every operation. No credit eligibility inferred from a default. | Owner Settings: proposed owner-scoped settings read/patch; optional defaults apply to future accounts only. Existing accounts unchanged; shop catalogue eligibility projection must explicitly evaluate policy. |

These five are important for functioning address/vehicle/settings controls in the approved designs; none is essential for purely visual layout. Essential immediate work is reconciling the existing schema and exposing already stored safe fields. The preferred-address FK may require creating preferences after addresses or adding the FK afterward; it does not require a sixth table.

### Existing-table extensions and changes requiring no new table

| Table / priority | Columns/types/nullability or no-column decision | Constraints/relationships | UI / associated API/service |
|---|---|---|---|
| businesses / Important | logo_storage_key VARCHAR(500) NULL; public_description VARCHAR(2000) NULL; city VARCHAR(100) NULL; latitude DECIMAL(9,6) NULL/longitude DECIMAL(10,6) NULL; opening_hours JSON NULL only if hours are required | Coordinate pair/range checks; validate structured hours in schema; no sensitive registration values in public DTO. Existing phone/address stay unchanged. | Owner shop settings; Customer browse/shop. Extend catalogue_service safe ShopPublic projection and owner business update capability; media upload authorization/size/type policy prerequisite. |
| products / Important | image_storage_key VARCHAR(500) NULL; unit_label VARCHAR(30) NULL | Nonblank values when set; storage validation. Retain manual availability. | ShopOwnerProducts/CustomerCatalogue; existing product CRUD/public DTO through catalogue_service. |
| products / Deferred | stock_quantity INT NULL, low_stock_threshold INT NULL only after inventory rules are agreed | >=0 checks are insufficient alone: atomic reservation/consumption/restock/cancellation and stock movement audit needed; a dedicated inventory model may then be justified. | Numeric stock/low-stock product UI; quote/placeOrder inventory integration. Not included in recommended count; do not present manual availability as stock. |
| customer_profiles / Essential no-column | Existing phone VARCHAR(20) NULL, address VARCHAR(500) NULL and linked user_id suffice for current business-owned contact UI | Preserve business_id plus account creditor consistency. user_id nullable for unregistered customers; never link solely by client assertion/email resemblance. | Existing shop_owner_customer_* services and customer_dashboard_service. No global address/profile duplication; optional tags/photo deferred. |
| credit_accounts / Essential no-column | Keep credit_limit DECIMAL(14,2), payment_term_days INT and existing status; do not add outstanding_balance/available_credit/due_balance caches | Preserve unique customer, business pair, one-debtor check. Derive from full scoped effective ledger including reversals. Aging allocation policy prerequisite. | Customer credit and owner reports/dashboard; ledger_service and customer_dashboard_service. No balance repair or automatic historical due backfill. |
| orders / Essential existing pending migration | Existing orders/items and nullable delivery_request_id are already modeled; apply no new duplicate model | Existing total>0/subtotal=total, exact-once credit sale unique FK, customer request key/hash, composite delivery/business FK | Customer cart/orders; owner fulfilment; order_service/order_delivery_service. Schema reconciliation first. |
| orders / Important conditional checkout enhancement | fulfillment_method VARCHAR(20) NULL initially; recipient_name VARCHAR(150) NULL; recipient_phone VARCHAR(20) NULL; delivery_address VARCHAR(500) NULL; delivery_latitude DECIMAL(9,6) NULL; delivery_longitude DECIMAL(10,6) NULL; delivery_instructions VARCHAR(1000) NULL; delivery_fee DECIMAL(14,2) NULL; pricing_policy_version VARCHAR(30) NULL | pickup/delivery check; delivery fields required for newly placed delivery orders, legacy unknown permitted. Snapshot from own address, immutable after acceptance policy. Fee >=0, replace total check only after explicit rules for total=subtotal+fee and who owes fee. Order hash must cover all binding fields; quote and approval revalidate consistently. | ShoppingCart/OrderHistory/fulfilment; extend quote/placeOrder and owner/customer order projections. Never silently increase existing debt or mark cash paid. Fee rules are blocked pending business decisions. |
| driver_profiles / Important conditional | active_vehicle_id BIGINT NULL if multiple vehicle history adopted | Composite FK(active_vehicle_id,user_id) -> vehicles unique(vehicle_id,driver_user_id); keep approval/reviewer constraints. Resolve circular FK by separate constraint phase. | DriverVehicle/Profile and driver_service safe projection; no duplicate delivery_providers. No online flag absent genuine presence TTL/availability rules. |
| delivery_requests / Important | pickup_address VARCHAR(500) NULL; destination_address VARCHAR(500) NULL; recipient_name VARCHAR(150) NULL; recipient_phone VARCHAR(20) NULL; instructions VARCHAR(1000) NULL; pickup_latitude DECIMAL(9,6) NULL/pickup_longitude DECIMAL(10,6) NULL; destination_latitude/longitude same; quoted_fee DECIMAL(14,2) NULL; currency CHAR(3) NULL; pricing_policy_version VARCHAR(30) NULL | Paired coordinates/ranges; fee >=0/currency LKR when quoted; do not backfill unknown fees as zero. Preserve public coarse areas, assignment uniqueness, status events, composite business key. Optional assignment vehicle_id BIGINT NULL with composite driver ownership FK if historical vehicle snapshot needed. | Owner deliveries, Driver jobs/detail, customer tracking; shop_owner_delivery_service/driver_service/order_delivery_service. Contact/exact address available only where operationally authorized; not broadly exposed to available jobs. Fee not driver earnings. |
| notifications / Essential constraint synchronization; Deferred extra columns | No new columns needed for present read/date/category UI. Apply pending type/entity checks in sequence. Add new supported event types only with their implemented domain events | Keep unique(recipient,event_key), recipient/read indexes and read_at check. Polymorphic related IDs must be validated by service before action links. | notification_service + all role inboxes. Preferences do not disable mandatory notices. No GPS, push delivery, earning or document verification implied by a notification. |
| users / Important DTO only initially | Existing phone, preferred_language, created_at can be projected safely to self; optional avatar_storage_key VARCHAR(500) NULL later | Own-user updates; language allowlist; re-authentication for sensitive identity/security changes. No password_hash in responses. DOB/NIC/gender deferred for data minimization. | /auth/me and proposed own profile operation; CustomerProfile/DriverProfile/Settings. |

### Optional and deferred new tables

| Candidate / priority | Recommended design if scope is approved | Constraints, API/UI and dependency |
|---|---|---|
| shopping_carts / Deferred | cart_id BIGINT PK; customer_user_id BIGINT NOT NULL; business_id BIGINT NOT NULL; version INT NOT NULL; created_at/updated_at NOT NULL | User/business FKs, unique(customer_user_id) for the current one-shop cart rule, version>=1; unique(cart_id,business_id) for scoped item FK. Proposed own cart synchronization for Customer cart. Needed for cross-device/reload persistence, not current in-memory checkout correctness. No stored authoritative cart total. |
| shopping_cart_items / Deferred | cart_item_id BIGINT PK; cart_id BIGINT NOT NULL; business_id BIGINT NOT NULL; product_id BIGINT NOT NULL; quantity INT NOT NULL; updated_at NOT NULL | Unique(cart_id,product_id), qty1..99; composite(cart_id,business_id) FK, composite(product_id,business_id) requires unique(product_id,business_id) on products. Quote prices/availability afresh; no stale cart price entitlement. Add only together with carts. |
| driver_payouts / Deferred | payout_id BIGINT PK; driver_user_id BIGINT NOT NULL; amount DECIMAL(14,2) NOT NULL; currency CHAR(3) NOT NULL; status VARCHAR(20) NOT NULL; request_key VARCHAR(100) NOT NULL; provider_reference VARCHAR(100) NULL; requested_at NOT NULL; settled_at DATETIME NULL | Driver FK; amount>0/currencyLKR; unique(driver,request_key), unique provider ref when set; pending/processing/paid/failed state machine and audited provider reconciliation. Sensitive payout destination must be encrypted/tokenized in a separately designed payment system, not cleartext bank details. Proposed own payout request/history + authorized settlement service. No public self-settlement. |
| driver_earnings / Deferred | earning_id BIGINT PK; assignment_id BIGINT NOT NULL; driver_user_id BIGINT NOT NULL; event_kind VARCHAR(20) NOT NULL; amount DECIMAL(14,2) NOT NULL signed; currency CHAR(3) NOT NULL; event_key VARCHAR(100) NOT NULL; reverses_earning_id BIGINT NULL; payout_id BIGINT NULL; recorded_at NOT NULL | Assignment/driver composite ownership FK (add unique assignment_id,driver_user_id), self reversal FK, payout/driver composite FK; unique event_key; one base entitlement per assignment (enforce via generated unique base key or separate base entitlement constraint); signed kind checks, amount!=0, currencyLKR. Earnings immutable, payout allocation exactly once transactionally. One earning fully belongs to at most one payout; if partial/split allocations are required, add driver_payout_items and revise count. Never calculate from completed delivery count or customer ledger. |

Earnings and payouts are blocked on fee ownership, entitlement timing, cancellation/refund/adjustment, cash handling, rounding, timezone, commission, settlement authority and audit decisions. Withdrawal controls remain unavailable until these are implemented and tested. These two draft tables alone do not constitute a compliant payment integration.

Disputes, subscriptions and group purchasing are **Deferred**, outside the approved core data flow: no proposed executable schema or count allocation. They need separate state machines, authorization, evidence/retention and financial rules. Do not infer recurring billing or group debt from existing credit accounts. **AI Summary remains deferred**, with no provider configuration.

## Count basis and implementation order

| Scope | Application tables excluding alembic_version |
|---|---:|
| Verified development now | 17 |
| Existing implemented model baseline after reviewed pending migrations (+orders/items/admin_audits) | 20 |
| Recommended next compatibility milestone (+addresses, vehicles, documents, preferences, business_settings) | **25** |
| Optional persistent-cart pair | 27 |
| Optional earnings/payout pair in addition to the above | 29 |
| If payout splits require a separate allocation table | 30 |

These are scope scenarios, not a target of 26 tables because there are 26 screens. Column extensions, derived metrics and screenshot-only visual elements do not increase the count. Default-address/active-vehicle FKs and media storage keys do not add tables. Inventory, identity verification, payout destinations, recurring billing or disputes could need additional structures after separate design; they are deliberately not hidden inside the recommended 25.

Ordered plan, requiring future authorization before any database changes:

1. Preserve this actual schema inventory and establish a verified backup/restore rehearsal and maintenance/rollback-forward plan. Assess operational locks, foreign key/index compatibility and data volumes using approved read-only checks. Keep development and test targets distinct.
2. Resolve the documented isolated migration verification database permission blocker with a DBA. The user previously chose to leave it documented: **do not retry elevated creation or request an administrator password**. Fresh-chain migration execution remains **BLOCKED**, not PASSED. Do not substitute a populated database or stamp away the gap.
3. Rehearse current chain in that separately authorized empty isolated database once access is confirmed. For real dev advancement, preflight existing notification types against **each intermediate** replacement CHECK, not just final head; inspect potential orphan/duplicate relationships and ledger.order_id provenance. MySQL DDL is not transactionally rollback-safe; constraint replacement can lock/fail. Existing late downgrades intentionally refuse to remove financial/audit history; plan forward corrections and verified restore instead.
4. Only after explicit approval, reconcile d0e6 -> e1f7 -> f2a8 -> 03b9 in dependency order; verify actual columns/FKs/indexes/checks afterward. This audit did not execute this step. Retest existing order, Admin, credit, assignment, ownership and notification workflows against verified isolated synthetic fixtures, not development financial data.
5. Implement safe DTO/query gaps first: self phone/language/member-since, public shop contact projection, paginated customer delivery aggregate, scoped owner report/count projections. Define cutoff/timezone and reversal policy. No schema change needed for these. Preserve existing page layout/colors and honest unavailable states.
6. Introduce the five recommended compatibility tables in additive revisions, with nullable legacy-compatible extensions/media metadata. Addressbook -> preferences default-address FK; vehicles -> documents -> optional active-vehicle FK. Keep driver approval separate from document review. Validate before imposing stronger legacy constraints. No automated balance repairs or destructive table renames.
7. Implement authorized read/write APIs, Pydantic validation and response schemas, then connect existing frontend services/hooks. Add request cancellation/stale-data handling, consistent pages/server filters and explicit loading/error/empty/unsupported states. Cart checkout must quote and confirm on server; field edits cannot bypass account/driver/business permissions.
8. Treat inventory, delivery pricing and earnings/payouts as separate gated domain work. Add nullable snapshots only after rules are approved, cover request hashes/exact-once postings, immutable historical prices and concurrency. Leave unsupported controls disabled until real endpoints exist.
9. Execute synthetic migration/backward compatibility, cross-customer/business/driver isolation, JWT/role, assignment race, reversal/repayment/credit approval and frontend contract tests in verified isolated targets under a future authorized test task. Verify browser screenshots at desktop/tablet/mobile; do not claim automated markup equals manual visual acceptance.

## Risks and remaining blockers

- Current dev schema is behind four revisions; orders and Admin audit functionality cannot be considered ready there. No automatic upgrade is authorized.
- Empty isolated migration execution verification remains blocked by previously documented database permission failure; required DBA action is recorded in docs/day17-database-operations.md. Audit completion does not complete migration verification.
- Aging is not a new balance column: existing due_at helps but partial payments, advances, reversal handling and allocation policy must be defined before publishing overdue/next due/aging values.
- Quote/checkout currently has subtotal=total and cash stays unpaid. Delivery fees, cash collection and driver earnings cannot be inferred or silently introduced.
- Broad public shop projections, private delivery contacts, document storage, address defaults, active vehicle ownership and payout linkage all require object-level authorization and privacy tests. IDs supplied in query/body are selectors, not authorization evidence.
- No GPS/presence/ETA/provider notification delivery/stock reservation/payout provider is implemented by matching screenshot fields. Those require actual services and truthful states.
- The screenshots have been inspected and files verified; this task did not perform a new live browser acceptance run. Prior regression results remain historical. No mutation or migration tests were run here by design.

## Appendices

The following appendices are generated from the fresh metadata snapshot and source AST, with no application-record contents. Column defaults are schema defaults, not live values. Appendix A includes every live table (including the separately counted Alembic metadata table), full columns, PK/FKs/indexes/unique/check constraints. Appendix B lists current API routes; Appendix C verifies the 26 approved PNGs.

## Appendix A: actual schema inventory


### alembic_version

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| version_num | VARCHAR(32) COLLATE utf8mb4_unicode_ci | NO | (none) |

**primary_key**

```json
{
  "constrained_columns": [
    "version_num"
  ],
  "name": null
}
```

**foreign_keys**

```json
[]
```

**indexes**

```json
[]
```

**unique_constraints**

```json
[]
```

**checks**

```json
[]
```

### business_approval_audits

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| audit_id | BIGINT | NO | (none) |
| business_id | BIGINT | NO | (none) |
| admin_user_id | BIGINT | NO | (none) |
| decision | VARCHAR(20) COLLATE utf8mb4_unicode_ci | NO | (none) |
| previous_status | VARCHAR(30) COLLATE utf8mb4_unicode_ci | NO | (none) |
| new_status | VARCHAR(30) COLLATE utf8mb4_unicode_ci | NO | (none) |
| review_note | VARCHAR(500) COLLATE utf8mb4_unicode_ci | YES | (none) |
| created_at | DATETIME | NO | (now()) |

**primary_key**

```json
{
  "constrained_columns": [
    "audit_id"
  ],
  "name": null
}
```

**foreign_keys**

```json
[
  {
    "name": "business_approval_audits_ibfk_1",
    "constrained_columns": [
      "business_id"
    ],
    "referred_schema": null,
    "referred_table": "businesses",
    "referred_columns": [
      "business_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "business_approval_audits_ibfk_2",
    "constrained_columns": [
      "admin_user_id"
    ],
    "referred_schema": null,
    "referred_table": "users",
    "referred_columns": [
      "user_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  }
]
```

**indexes**

```json
[
  {
    "name": "admin_user_id",
    "column_names": [
      "admin_user_id"
    ],
    "unique": false
  },
  {
    "name": "ix_business_approval_audits_business_id",
    "column_names": [
      "business_id"
    ],
    "unique": false
  }
]
```

**unique_constraints**

```json
[]
```

**checks**

```json
[]
```

### business_members

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| membership_id | BIGINT | NO | (none) |
| business_id | BIGINT | NO | (none) |
| user_id | BIGINT | NO | (none) |
| business_role | VARCHAR(30) COLLATE utf8mb4_unicode_ci | NO | 'owner' |
| membership_status | VARCHAR(30) COLLATE utf8mb4_unicode_ci | NO | 'active' |

**primary_key**

```json
{
  "constrained_columns": [
    "membership_id"
  ],
  "name": null
}
```

**foreign_keys**

```json
[
  {
    "name": "business_members_ibfk_1",
    "constrained_columns": [
      "business_id"
    ],
    "referred_schema": null,
    "referred_table": "businesses",
    "referred_columns": [
      "business_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "business_members_ibfk_2",
    "constrained_columns": [
      "user_id"
    ],
    "referred_schema": null,
    "referred_table": "users",
    "referred_columns": [
      "user_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  }
]
```

**indexes**

```json
[
  {
    "name": "ix_business_members_business_id",
    "column_names": [
      "business_id"
    ],
    "unique": false
  },
  {
    "name": "ix_business_members_user_id",
    "column_names": [
      "user_id"
    ],
    "unique": false
  },
  {
    "name": "uq_business_member_business_user",
    "column_names": [
      "business_id",
      "user_id"
    ],
    "unique": true
  }
]
```

**unique_constraints**

```json
[
  {
    "name": "uq_business_member_business_user",
    "column_names": [
      "business_id",
      "user_id"
    ],
    "duplicates_index": "uq_business_member_business_user"
  }
]
```

**checks**

```json
[]
```

### businesses

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| business_id | BIGINT | NO | (none) |
| business_name | VARCHAR(200) COLLATE utf8mb4_unicode_ci | NO | (none) |
| business_type | VARCHAR(50) COLLATE utf8mb4_unicode_ci | NO | (none) |
| registration_number | VARCHAR(100) COLLATE utf8mb4_unicode_ci | YES | (none) |
| phone | VARCHAR(20) COLLATE utf8mb4_unicode_ci | YES | (none) |
| address | VARCHAR(500) COLLATE utf8mb4_unicode_ci | YES | (none) |
| approval_status | VARCHAR(30) COLLATE utf8mb4_unicode_ci | NO | 'pending' |
| created_at | DATETIME | NO | (now()) |

**primary_key**

```json
{
  "constrained_columns": [
    "business_id"
  ],
  "name": null
}
```

**foreign_keys**

```json
[]
```

**indexes**

```json
[]
```

**unique_constraints**

```json
[]
```

**checks**

```json
[]
```

### communication_attempts

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| attempt_id | BIGINT | NO | (none) |
| business_id | BIGINT | NO | (none) |
| customer_id | BIGINT | NO | (none) |
| reminder_id | BIGINT | NO | (none) |
| consent_id | BIGINT | NO | (none) |
| requested_by | BIGINT | NO | (none) |
| channel | VARCHAR(20) COLLATE utf8mb4_unicode_ci | NO | (none) |
| phone | VARCHAR(15) COLLATE utf8mb4_unicode_ci | NO | (none) |
| status | VARCHAR(30) COLLATE utf8mb4_unicode_ci | NO | (none) |
| idempotency_key | VARCHAR(100) COLLATE utf8mb4_bin | NO | (none) |
| created_at | DATETIME | NO | (none) |

**primary_key**

```json
{
  "constrained_columns": [
    "attempt_id"
  ],
  "name": null
}
```

**foreign_keys**

```json
[
  {
    "name": "communication_attempts_ibfk_1",
    "constrained_columns": [
      "business_id"
    ],
    "referred_schema": null,
    "referred_table": "businesses",
    "referred_columns": [
      "business_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "communication_attempts_ibfk_2",
    "constrained_columns": [
      "customer_id"
    ],
    "referred_schema": null,
    "referred_table": "customer_profiles",
    "referred_columns": [
      "customer_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "communication_attempts_ibfk_3",
    "constrained_columns": [
      "reminder_id"
    ],
    "referred_schema": null,
    "referred_table": "payment_reminders",
    "referred_columns": [
      "reminder_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "communication_attempts_ibfk_4",
    "constrained_columns": [
      "consent_id"
    ],
    "referred_schema": null,
    "referred_table": "communication_consents",
    "referred_columns": [
      "consent_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "communication_attempts_ibfk_5",
    "constrained_columns": [
      "requested_by"
    ],
    "referred_schema": null,
    "referred_table": "users",
    "referred_columns": [
      "user_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  }
]
```

**indexes**

```json
[
  {
    "name": "consent_id",
    "column_names": [
      "consent_id"
    ],
    "unique": false
  },
  {
    "name": "customer_id",
    "column_names": [
      "customer_id"
    ],
    "unique": false
  },
  {
    "name": "ix_handoff_reminder_created",
    "column_names": [
      "business_id",
      "reminder_id",
      "created_at",
      "attempt_id"
    ],
    "unique": false
  },
  {
    "name": "reminder_id",
    "column_names": [
      "reminder_id"
    ],
    "unique": false
  },
  {
    "name": "requested_by",
    "column_names": [
      "requested_by"
    ],
    "unique": false
  },
  {
    "name": "uq_handoff_business_key",
    "column_names": [
      "business_id",
      "idempotency_key"
    ],
    "unique": true
  }
]
```

**unique_constraints**

```json
[
  {
    "name": "uq_handoff_business_key",
    "column_names": [
      "business_id",
      "idempotency_key"
    ],
    "duplicates_index": "uq_handoff_business_key"
  }
]
```

**checks**

```json
[
  {
    "name": "ck_handoff_channel",
    "sqltext": "(`channel` = _utf8mb4'whatsapp')"
  },
  {
    "name": "ck_handoff_status",
    "sqltext": "(`status` = _utf8mb4'handoff_requested')"
  }
]
```

### communication_consents

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| consent_id | BIGINT | NO | (none) |
| business_id | BIGINT | NO | (none) |
| customer_id | BIGINT | NO | (none) |
| recorded_by | BIGINT | NO | (none) |
| channel | VARCHAR(20) COLLATE utf8mb4_unicode_ci | NO | (none) |
| consent_status | VARCHAR(20) COLLATE utf8mb4_unicode_ci | NO | (none) |
| phone | VARCHAR(15) COLLATE utf8mb4_unicode_ci | YES | (none) |
| evidence | VARCHAR(500) COLLATE utf8mb4_unicode_ci | NO | (none) |
| idempotency_key | VARCHAR(100) COLLATE utf8mb4_bin | NO | (none) |
| created_at | DATETIME | NO | (none) |

**primary_key**

```json
{
  "constrained_columns": [
    "consent_id"
  ],
  "name": null
}
```

**foreign_keys**

```json
[
  {
    "name": "communication_consents_ibfk_1",
    "constrained_columns": [
      "business_id"
    ],
    "referred_schema": null,
    "referred_table": "businesses",
    "referred_columns": [
      "business_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "communication_consents_ibfk_2",
    "constrained_columns": [
      "customer_id"
    ],
    "referred_schema": null,
    "referred_table": "customer_profiles",
    "referred_columns": [
      "customer_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "communication_consents_ibfk_3",
    "constrained_columns": [
      "recorded_by"
    ],
    "referred_schema": null,
    "referred_table": "users",
    "referred_columns": [
      "user_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  }
]
```

**indexes**

```json
[
  {
    "name": "customer_id",
    "column_names": [
      "customer_id"
    ],
    "unique": false
  },
  {
    "name": "ix_consent_customer_latest",
    "column_names": [
      "business_id",
      "customer_id",
      "consent_id"
    ],
    "unique": false
  },
  {
    "name": "recorded_by",
    "column_names": [
      "recorded_by"
    ],
    "unique": false
  },
  {
    "name": "uq_consent_business_key",
    "column_names": [
      "business_id",
      "idempotency_key"
    ],
    "unique": true
  }
]
```

**unique_constraints**

```json
[
  {
    "name": "uq_consent_business_key",
    "column_names": [
      "business_id",
      "idempotency_key"
    ],
    "duplicates_index": "uq_consent_business_key"
  }
]
```

**checks**

```json
[
  {
    "name": "ck_consent_channel",
    "sqltext": "(`channel` = _utf8mb4'whatsapp')"
  },
  {
    "name": "ck_consent_phone",
    "sqltext": "((`consent_status` = _utf8mb4'opted_out') or (`phone` is not null))"
  },
  {
    "name": "ck_consent_status",
    "sqltext": "(`consent_status` in (_utf8mb4'granted',_utf8mb4'opted_out'))"
  }
]
```

### credit_accounts

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| credit_account_id | BIGINT | NO | (none) |
| creditor_business_id | BIGINT | NO | (none) |
| customer_id | BIGINT | YES | (none) |
| debtor_business_id | BIGINT | YES | (none) |
| credit_limit | DECIMAL(14, 2) | NO | (none) |
| payment_term_days | INTEGER | NO | (none) |
| account_status | VARCHAR(30) COLLATE utf8mb4_unicode_ci | NO | (none) |
| opened_at | DATETIME | NO | (now()) |

**primary_key**

```json
{
  "constrained_columns": [
    "credit_account_id"
  ],
  "name": null
}
```

**foreign_keys**

```json
[
  {
    "name": "credit_accounts_ibfk_1",
    "constrained_columns": [
      "creditor_business_id"
    ],
    "referred_schema": null,
    "referred_table": "businesses",
    "referred_columns": [
      "business_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "credit_accounts_ibfk_2",
    "constrained_columns": [
      "customer_id"
    ],
    "referred_schema": null,
    "referred_table": "customer_profiles",
    "referred_columns": [
      "customer_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "credit_accounts_ibfk_3",
    "constrained_columns": [
      "debtor_business_id"
    ],
    "referred_schema": null,
    "referred_table": "businesses",
    "referred_columns": [
      "business_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  }
]
```

**indexes**

```json
[
  {
    "name": "debtor_business_id",
    "column_names": [
      "debtor_business_id"
    ],
    "unique": false
  },
  {
    "name": "ix_credit_account_creditor_status",
    "column_names": [
      "creditor_business_id",
      "account_status"
    ],
    "unique": false
  },
  {
    "name": "ix_credit_accounts_creditor_business_id",
    "column_names": [
      "creditor_business_id"
    ],
    "unique": false
  },
  {
    "name": "uq_credit_account_business_pair",
    "column_names": [
      "creditor_business_id",
      "debtor_business_id"
    ],
    "unique": true
  },
  {
    "name": "uq_credit_account_customer",
    "column_names": [
      "customer_id"
    ],
    "unique": true
  }
]
```

**unique_constraints**

```json
[
  {
    "name": "uq_credit_account_business_pair",
    "column_names": [
      "creditor_business_id",
      "debtor_business_id"
    ],
    "duplicates_index": "uq_credit_account_business_pair"
  },
  {
    "name": "uq_credit_account_customer",
    "column_names": [
      "customer_id"
    ],
    "duplicates_index": "uq_credit_account_customer"
  }
]
```

**checks**

```json
[
  {
    "name": "ck_credit_account_limit_nonnegative",
    "sqltext": "(`credit_limit` >= 0)"
  },
  {
    "name": "ck_credit_account_one_debtor",
    "sqltext": "(((`customer_id` is not null) and (`debtor_business_id` is null)) or ((`customer_id` is null) and (`debtor_business_id` is not null)))"
  },
  {
    "name": "ck_credit_account_payment_term_positive",
    "sqltext": "(`payment_term_days` > 0)"
  }
]
```

### customer_profiles

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| customer_id | BIGINT | NO | (none) |
| business_id | BIGINT | NO | (none) |
| user_id | BIGINT | YES | (none) |
| customer_name | VARCHAR(150) COLLATE utf8mb4_unicode_ci | NO | (none) |
| phone | VARCHAR(20) COLLATE utf8mb4_unicode_ci | YES | (none) |
| address | VARCHAR(500) COLLATE utf8mb4_unicode_ci | YES | (none) |
| created_at | DATETIME | NO | (now()) |

**primary_key**

```json
{
  "constrained_columns": [
    "customer_id"
  ],
  "name": null
}
```

**foreign_keys**

```json
[
  {
    "name": "customer_profiles_ibfk_1",
    "constrained_columns": [
      "business_id"
    ],
    "referred_schema": null,
    "referred_table": "businesses",
    "referred_columns": [
      "business_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "customer_profiles_ibfk_2",
    "constrained_columns": [
      "user_id"
    ],
    "referred_schema": null,
    "referred_table": "users",
    "referred_columns": [
      "user_id"
    ],
    "options": {
      "ondelete": "SET NULL"
    }
  }
]
```

**indexes**

```json
[
  {
    "name": "ix_customer_profiles_business_id",
    "column_names": [
      "business_id"
    ],
    "unique": false
  },
  {
    "name": "ix_customer_profiles_user_id",
    "column_names": [
      "user_id"
    ],
    "unique": false
  }
]
```

**unique_constraints**

```json
[]
```

**checks**

```json
[]
```

### delivery_assignments

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| assignment_id | BIGINT | NO | (none) |
| delivery_request_id | BIGINT | NO | (none) |
| driver_user_id | BIGINT | NO | (none) |
| assigned_at | DATETIME | NO | (none) |

**primary_key**

```json
{
  "constrained_columns": [
    "assignment_id"
  ],
  "name": null
}
```

**foreign_keys**

```json
[
  {
    "name": "delivery_assignments_ibfk_1",
    "constrained_columns": [
      "delivery_request_id"
    ],
    "referred_schema": null,
    "referred_table": "delivery_requests",
    "referred_columns": [
      "delivery_request_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "delivery_assignments_ibfk_2",
    "constrained_columns": [
      "driver_user_id"
    ],
    "referred_schema": null,
    "referred_table": "driver_profiles",
    "referred_columns": [
      "user_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  }
]
```

**indexes**

```json
[
  {
    "name": "ix_assignment_driver_date",
    "column_names": [
      "driver_user_id",
      "assigned_at",
      "assignment_id"
    ],
    "unique": false
  },
  {
    "name": "uq_delivery_assignment_request",
    "column_names": [
      "delivery_request_id"
    ],
    "unique": true
  }
]
```

**unique_constraints**

```json
[
  {
    "name": "uq_delivery_assignment_request",
    "column_names": [
      "delivery_request_id"
    ],
    "duplicates_index": "uq_delivery_assignment_request"
  }
]
```

**checks**

```json
[]
```

### delivery_requests

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| delivery_request_id | BIGINT | NO | (none) |
| reference | VARCHAR(50) COLLATE utf8mb4_unicode_ci | NO | (none) |
| business_id | BIGINT | NO | (none) |
| created_by | BIGINT | NO | (none) |
| pickup_area | VARCHAR(160) COLLATE utf8mb4_unicode_ci | NO | (none) |
| delivery_area | VARCHAR(160) COLLATE utf8mb4_unicode_ci | NO | (none) |
| status | VARCHAR(20) COLLATE utf8mb4_unicode_ci | NO | 'available' |
| created_at | DATETIME | NO | (none) |
| updated_at | DATETIME | NO | (none) |

**primary_key**

```json
{
  "constrained_columns": [
    "delivery_request_id"
  ],
  "name": null
}
```

**foreign_keys**

```json
[
  {
    "name": "delivery_requests_ibfk_1",
    "constrained_columns": [
      "business_id"
    ],
    "referred_schema": null,
    "referred_table": "businesses",
    "referred_columns": [
      "business_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "delivery_requests_ibfk_2",
    "constrained_columns": [
      "created_by"
    ],
    "referred_schema": null,
    "referred_table": "users",
    "referred_columns": [
      "user_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  }
]
```

**indexes**

```json
[
  {
    "name": "created_by",
    "column_names": [
      "created_by"
    ],
    "unique": false
  },
  {
    "name": "ix_delivery_business",
    "column_names": [
      "business_id"
    ],
    "unique": false
  },
  {
    "name": "ix_delivery_status_created",
    "column_names": [
      "status",
      "created_at",
      "delivery_request_id"
    ],
    "unique": false
  },
  {
    "name": "reference",
    "column_names": [
      "reference"
    ],
    "unique": true
  }
]
```

**unique_constraints**

```json
[
  {
    "name": "reference",
    "column_names": [
      "reference"
    ],
    "duplicates_index": "reference"
  }
]
```

**checks**

```json
[
  {
    "name": "ck_delivery_status",
    "sqltext": "(`status` in (_utf8mb4'available',_utf8mb4'assigned',_utf8mb4'picked_up',_utf8mb4'in_transit',_utf8mb4'delivered',_utf8mb4'cancelled'))"
  }
]
```

### delivery_status_events

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| event_id | BIGINT | NO | (none) |
| delivery_request_id | BIGINT | NO | (none) |
| actor_user_id | BIGINT | NO | (none) |
| status | VARCHAR(20) COLLATE utf8mb4_unicode_ci | NO | (none) |
| occurred_at | DATETIME | NO | (none) |

**primary_key**

```json
{
  "constrained_columns": [
    "event_id"
  ],
  "name": null
}
```

**foreign_keys**

```json
[
  {
    "name": "delivery_status_events_ibfk_1",
    "constrained_columns": [
      "delivery_request_id"
    ],
    "referred_schema": null,
    "referred_table": "delivery_requests",
    "referred_columns": [
      "delivery_request_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "delivery_status_events_ibfk_2",
    "constrained_columns": [
      "actor_user_id"
    ],
    "referred_schema": null,
    "referred_table": "users",
    "referred_columns": [
      "user_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  }
]
```

**indexes**

```json
[
  {
    "name": "actor_user_id",
    "column_names": [
      "actor_user_id"
    ],
    "unique": false
  },
  {
    "name": "uq_delivery_event_status",
    "column_names": [
      "delivery_request_id",
      "status"
    ],
    "unique": true
  }
]
```

**unique_constraints**

```json
[
  {
    "name": "uq_delivery_event_status",
    "column_names": [
      "delivery_request_id",
      "status"
    ],
    "duplicates_index": "uq_delivery_event_status"
  }
]
```

**checks**

```json
[
  {
    "name": "ck_delivery_event_status",
    "sqltext": "(`status` in (_utf8mb4'picked_up',_utf8mb4'in_transit',_utf8mb4'delivered',_utf8mb4'cancelled'))"
  }
]
```

### driver_profiles

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| user_id | BIGINT | NO | (none) |
| approval_status | VARCHAR(20) COLLATE utf8mb4_unicode_ci | NO | 'pending' |
| vehicle_type | VARCHAR(50) COLLATE utf8mb4_unicode_ci | YES | (none) |
| registration_reference | VARCHAR(50) COLLATE utf8mb4_unicode_ci | YES | (none) |
| reviewed_by | BIGINT | YES | (none) |
| reviewed_at | DATETIME | YES | (none) |
| created_at | DATETIME | NO | (none) |

**primary_key**

```json
{
  "constrained_columns": [
    "user_id"
  ],
  "name": null
}
```

**foreign_keys**

```json
[
  {
    "name": "driver_profiles_ibfk_1",
    "constrained_columns": [
      "user_id"
    ],
    "referred_schema": null,
    "referred_table": "users",
    "referred_columns": [
      "user_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "driver_profiles_ibfk_2",
    "constrained_columns": [
      "reviewed_by"
    ],
    "referred_schema": null,
    "referred_table": "users",
    "referred_columns": [
      "user_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  }
]
```

**indexes**

```json
[
  {
    "name": "reviewed_by",
    "column_names": [
      "reviewed_by"
    ],
    "unique": false
  }
]
```

**unique_constraints**

```json
[]
```

**checks**

```json
[
  {
    "name": "ck_driver_approval_status",
    "sqltext": "(`approval_status` in (_utf8mb4'pending',_utf8mb4'approved',_utf8mb4'rejected',_utf8mb4'suspended'))"
  },
  {
    "name": "ck_driver_review_required",
    "sqltext": "((`approval_status` = _utf8mb4'pending') or ((`reviewed_by` is not null) and (`reviewed_at` is not null)))"
  },
  {
    "name": "ck_driver_vehicle_pair",
    "sqltext": "(((`vehicle_type` is null) and (`registration_reference` is null)) or ((`vehicle_type` is not null) and (`registration_reference` is not null)))"
  }
]
```

### ledger_entries

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| entry_id | BIGINT | NO | (none) |
| credit_account_id | BIGINT | NO | (none) |
| order_id | BIGINT | YES | (none) |
| created_by | BIGINT | NO | (none) |
| reverses_entry_id | BIGINT | YES | (none) |
| entry_type | VARCHAR(30) COLLATE utf8mb4_unicode_ci | NO | (none) |
| amount | DECIMAL(14, 2) | NO | (none) |
| payment_method | VARCHAR(30) COLLATE utf8mb4_unicode_ci | YES | (none) |
| receipt_number | VARCHAR(60) COLLATE utf8mb4_unicode_ci | YES | (none) |
| notes | TEXT COLLATE utf8mb4_unicode_ci | YES | (none) |
| idempotency_key | VARCHAR(100) COLLATE utf8mb4_unicode_ci | NO | (none) |
| due_at | DATETIME | YES | (none) |
| recorded_at | DATETIME | NO | (now()) |

**primary_key**

```json
{
  "constrained_columns": [
    "entry_id"
  ],
  "name": null
}
```

**foreign_keys**

```json
[
  {
    "name": "ledger_entries_ibfk_1",
    "constrained_columns": [
      "created_by"
    ],
    "referred_schema": null,
    "referred_table": "users",
    "referred_columns": [
      "user_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "ledger_entries_ibfk_2",
    "constrained_columns": [
      "credit_account_id"
    ],
    "referred_schema": null,
    "referred_table": "credit_accounts",
    "referred_columns": [
      "credit_account_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "ledger_entries_ibfk_3",
    "constrained_columns": [
      "reverses_entry_id"
    ],
    "referred_schema": null,
    "referred_table": "ledger_entries",
    "referred_columns": [
      "entry_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  }
]
```

**indexes**

```json
[
  {
    "name": "created_by",
    "column_names": [
      "created_by"
    ],
    "unique": false
  },
  {
    "name": "ix_ledger_account_recorded",
    "column_names": [
      "credit_account_id",
      "recorded_at"
    ],
    "unique": false
  },
  {
    "name": "uq_ledger_entry_idempotency_key",
    "column_names": [
      "idempotency_key"
    ],
    "unique": true
  },
  {
    "name": "uq_ledger_entry_receipt_number",
    "column_names": [
      "receipt_number"
    ],
    "unique": true
  },
  {
    "name": "uq_ledger_entry_single_reversal",
    "column_names": [
      "reverses_entry_id"
    ],
    "unique": true
  }
]
```

**unique_constraints**

```json
[
  {
    "name": "uq_ledger_entry_idempotency_key",
    "column_names": [
      "idempotency_key"
    ],
    "duplicates_index": "uq_ledger_entry_idempotency_key"
  },
  {
    "name": "uq_ledger_entry_receipt_number",
    "column_names": [
      "receipt_number"
    ],
    "duplicates_index": "uq_ledger_entry_receipt_number"
  },
  {
    "name": "uq_ledger_entry_single_reversal",
    "column_names": [
      "reverses_entry_id"
    ],
    "duplicates_index": "uq_ledger_entry_single_reversal"
  }
]
```

**checks**

```json
[
  {
    "name": "ck_ledger_entry_amount_positive",
    "sqltext": "(`amount` > 0)"
  },
  {
    "name": "ck_ledger_entry_reversal_reference",
    "sqltext": "((`reverses_entry_id` is null) or (`entry_type` = _utf8mb4'reversal'))"
  },
  {
    "name": "ck_ledger_entry_valid_type",
    "sqltext": "(`entry_type` in (_utf8mb4'credit_sale',_utf8mb4'repayment',_utf8mb4'reversal'))"
  }
]
```

### notifications

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| notification_id | BIGINT | NO | (none) |
| recipient_user_id | BIGINT | NO | (none) |
| business_id | BIGINT | YES | (none) |
| notification_type | VARCHAR(40) COLLATE utf8mb4_unicode_ci | NO | (none) |
| title | VARCHAR(120) COLLATE utf8mb4_unicode_ci | NO | (none) |
| message | VARCHAR(300) COLLATE utf8mb4_unicode_ci | NO | (none) |
| related_entity_type | VARCHAR(30) COLLATE utf8mb4_unicode_ci | NO | (none) |
| related_entity_id | BIGINT | NO | (none) |
| event_key | VARCHAR(100) COLLATE utf8mb4_bin | NO | (none) |
| is_read | TINYINT | NO | '0' |
| created_at | DATETIME | NO | (none) |
| read_at | DATETIME | YES | (none) |

**primary_key**

```json
{
  "constrained_columns": [
    "notification_id"
  ],
  "name": null
}
```

**foreign_keys**

```json
[
  {
    "name": "notifications_ibfk_1",
    "constrained_columns": [
      "recipient_user_id"
    ],
    "referred_schema": null,
    "referred_table": "users",
    "referred_columns": [
      "user_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "notifications_ibfk_2",
    "constrained_columns": [
      "business_id"
    ],
    "referred_schema": null,
    "referred_table": "businesses",
    "referred_columns": [
      "business_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  }
]
```

**indexes**

```json
[
  {
    "name": "ix_notification_recipient_created",
    "column_names": [
      "recipient_user_id",
      "created_at",
      "notification_id"
    ],
    "unique": false
  },
  {
    "name": "ix_notification_recipient_read_created",
    "column_names": [
      "recipient_user_id",
      "is_read",
      "created_at",
      "notification_id"
    ],
    "unique": false
  },
  {
    "name": "ix_notification_recipient_type_created",
    "column_names": [
      "recipient_user_id",
      "notification_type",
      "created_at",
      "notification_id"
    ],
    "unique": false
  },
  {
    "name": "ix_notifications_business_id",
    "column_names": [
      "business_id"
    ],
    "unique": false
  },
  {
    "name": "uq_notification_recipient_event",
    "column_names": [
      "recipient_user_id",
      "event_key"
    ],
    "unique": true
  }
]
```

**unique_constraints**

```json
[
  {
    "name": "uq_notification_recipient_event",
    "column_names": [
      "recipient_user_id",
      "event_key"
    ],
    "duplicates_index": "uq_notification_recipient_event"
  }
]
```

**checks**

```json
[
  {
    "name": "ck_notification_entity_id",
    "sqltext": "(`related_entity_id` > 0)"
  },
  {
    "name": "ck_notification_entity_type",
    "sqltext": "(((`notification_type` in (_utf8mb4'credit_sale_recorded',_utf8mb4'repayment_recorded')) and (`related_entity_type` = _utf8mb4'ledger_entry')) or ((`notification_type` = _utf8mb4'payment_reminder_recorded') and (`related_entity_type` = _utf8mb4'payment_reminder')) or ((`notification_type` in (_utf8mb4'business_approved',_utf8mb4'business_rejected')) and (`related_entity_type` = _utf8mb4'business_approval_audit')) or ((`notification_type` in (_utf8mb4'delivery_assigned',_utf8mb4'delivery_picked_up',_utf8mb4'delivery_in_transit',_utf8mb4'delivery_delivered')) and (`related_entity_type` = _utf8mb4'delivery_request')))"
  },
  {
    "name": "ck_notification_read_state",
    "sqltext": "(((`is_read` = 0) and (`read_at` is null)) or ((`is_read` = 1) and (`read_at` is not null)))"
  },
  {
    "name": "ck_notification_type",
    "sqltext": "(`notification_type` in (_utf8mb4'credit_sale_recorded',_utf8mb4'repayment_recorded',_utf8mb4'payment_reminder_recorded',_utf8mb4'business_approved',_utf8mb4'business_rejected',_utf8mb4'delivery_assigned',_utf8mb4'delivery_picked_up',_utf8mb4'delivery_in_transit',_utf8mb4'delivery_delivered'))"
  }
]
```

### payment_reminders

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| reminder_id | BIGINT | NO | (none) |
| business_id | BIGINT | NO | (none) |
| customer_id | BIGINT | NO | (none) |
| credit_account_id | BIGINT | NO | (none) |
| created_by | BIGINT | NO | (none) |
| outstanding_amount | DECIMAL(24, 2) | NO | (none) |
| currency | VARCHAR(3) COLLATE utf8mb4_unicode_ci | NO | (none) |
| channel | VARCHAR(20) COLLATE utf8mb4_unicode_ci | NO | (none) |
| language | VARCHAR(2) COLLATE utf8mb4_unicode_ci | NO | (none) |
| template_version | VARCHAR(30) COLLATE utf8mb4_unicode_ci | NO | (none) |
| message | TEXT COLLATE utf8mb4_unicode_ci | NO | (none) |
| note | VARCHAR(1000) COLLATE utf8mb4_unicode_ci | YES | (none) |
| status | VARCHAR(20) COLLATE utf8mb4_unicode_ci | NO | (none) |
| idempotency_key | VARCHAR(100) COLLATE utf8mb4_bin | NO | (none) |
| created_at | DATETIME | NO | (none) |
| updated_at | DATETIME | NO | (none) |

**primary_key**

```json
{
  "constrained_columns": [
    "reminder_id"
  ],
  "name": null
}
```

**foreign_keys**

```json
[
  {
    "name": "payment_reminders_ibfk_1",
    "constrained_columns": [
      "business_id"
    ],
    "referred_schema": null,
    "referred_table": "businesses",
    "referred_columns": [
      "business_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "payment_reminders_ibfk_2",
    "constrained_columns": [
      "customer_id"
    ],
    "referred_schema": null,
    "referred_table": "customer_profiles",
    "referred_columns": [
      "customer_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "payment_reminders_ibfk_3",
    "constrained_columns": [
      "credit_account_id"
    ],
    "referred_schema": null,
    "referred_table": "credit_accounts",
    "referred_columns": [
      "credit_account_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "payment_reminders_ibfk_4",
    "constrained_columns": [
      "created_by"
    ],
    "referred_schema": null,
    "referred_table": "users",
    "referred_columns": [
      "user_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  }
]
```

**indexes**

```json
[
  {
    "name": "created_by",
    "column_names": [
      "created_by"
    ],
    "unique": false
  },
  {
    "name": "credit_account_id",
    "column_names": [
      "credit_account_id"
    ],
    "unique": false
  },
  {
    "name": "customer_id",
    "column_names": [
      "customer_id"
    ],
    "unique": false
  },
  {
    "name": "ix_reminder_business_created",
    "column_names": [
      "business_id",
      "created_at",
      "reminder_id"
    ],
    "unique": false
  },
  {
    "name": "ix_reminder_customer_created",
    "column_names": [
      "business_id",
      "customer_id",
      "created_at"
    ],
    "unique": false
  },
  {
    "name": "uq_reminder_business_key",
    "column_names": [
      "business_id",
      "idempotency_key"
    ],
    "unique": true
  }
]
```

**unique_constraints**

```json
[
  {
    "name": "uq_reminder_business_key",
    "column_names": [
      "business_id",
      "idempotency_key"
    ],
    "duplicates_index": "uq_reminder_business_key"
  }
]
```

**checks**

```json
[
  {
    "name": "ck_reminder_channel",
    "sqltext": "(`channel` in (_utf8mb4'internal',_utf8mb4'copy',_utf8mb4'whatsapp',_utf8mb4'sms'))"
  },
  {
    "name": "ck_reminder_currency",
    "sqltext": "(`currency` = _utf8mb4'LKR')"
  },
  {
    "name": "ck_reminder_language",
    "sqltext": "(`language` in (_utf8mb4'en',_utf8mb4'ta'))"
  },
  {
    "name": "ck_reminder_positive_amount",
    "sqltext": "(`outstanding_amount` > 0)"
  },
  {
    "name": "ck_reminder_recorded_status",
    "sqltext": "(`status` = _utf8mb4'recorded')"
  }
]
```

### product_categories

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| category_id | BIGINT | NO | (none) |
| business_id | BIGINT | NO | (none) |
| name | VARCHAR(100) COLLATE utf8mb4_unicode_ci | NO | (none) |
| description | VARCHAR(2000) COLLATE utf8mb4_unicode_ci | YES | (none) |
| is_active | TINYINT | NO | '1' |
| created_at | DATETIME | NO | (none) |
| updated_at | DATETIME | NO | (none) |

**primary_key**

```json
{
  "constrained_columns": [
    "category_id"
  ],
  "name": null
}
```

**foreign_keys**

```json
[
  {
    "name": "product_categories_ibfk_1",
    "constrained_columns": [
      "business_id"
    ],
    "referred_schema": null,
    "referred_table": "businesses",
    "referred_columns": [
      "business_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  }
]
```

**indexes**

```json
[
  {
    "name": "ix_category_business_active",
    "column_names": [
      "business_id",
      "is_active",
      "category_id"
    ],
    "unique": false
  },
  {
    "name": "uq_category_business_name",
    "column_names": [
      "business_id",
      "name"
    ],
    "unique": true
  },
  {
    "name": "uq_category_id_business",
    "column_names": [
      "category_id",
      "business_id"
    ],
    "unique": true
  }
]
```

**unique_constraints**

```json
[
  {
    "name": "uq_category_business_name",
    "column_names": [
      "business_id",
      "name"
    ],
    "duplicates_index": "uq_category_business_name"
  },
  {
    "name": "uq_category_id_business",
    "column_names": [
      "category_id",
      "business_id"
    ],
    "duplicates_index": "uq_category_id_business"
  }
]
```

**checks**

```json
[
  {
    "name": "ck_category_name",
    "sqltext": "(char_length(trim(`name`)) > 0)"
  }
]
```

### products

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| product_id | BIGINT | NO | (none) |
| business_id | BIGINT | NO | (none) |
| category_id | BIGINT | YES | (none) |
| name | VARCHAR(200) COLLATE utf8mb4_unicode_ci | NO | (none) |
| description | VARCHAR(4000) COLLATE utf8mb4_unicode_ci | YES | (none) |
| unit_price | DECIMAL(12, 2) | NO | (none) |
| currency | VARCHAR(3) COLLATE utf8mb4_unicode_ci | NO | 'LKR' |
| availability_status | VARCHAR(20) COLLATE utf8mb4_unicode_ci | NO | 'available' |
| publication_status | VARCHAR(20) COLLATE utf8mb4_unicode_ci | NO | 'draft' |
| created_at | DATETIME | NO | (none) |
| updated_at | DATETIME | NO | (none) |

**primary_key**

```json
{
  "constrained_columns": [
    "product_id"
  ],
  "name": null
}
```

**foreign_keys**

```json
[
  {
    "name": "fk_product_category_business",
    "constrained_columns": [
      "category_id",
      "business_id"
    ],
    "referred_schema": null,
    "referred_table": "product_categories",
    "referred_columns": [
      "category_id",
      "business_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  },
  {
    "name": "products_ibfk_1",
    "constrained_columns": [
      "business_id"
    ],
    "referred_schema": null,
    "referred_table": "businesses",
    "referred_columns": [
      "business_id"
    ],
    "options": {
      "ondelete": "RESTRICT"
    }
  }
]
```

**indexes**

```json
[
  {
    "name": "ix_product_business_category",
    "column_names": [
      "category_id",
      "business_id"
    ],
    "unique": false
  },
  {
    "name": "ix_product_business_publication",
    "column_names": [
      "business_id",
      "publication_status",
      "product_id"
    ],
    "unique": false
  }
]
```

**unique_constraints**

```json
[]
```

**checks**

```json
[
  {
    "name": "ck_product_availability",
    "sqltext": "(`availability_status` in (_utf8mb4'available',_utf8mb4'unavailable'))"
  },
  {
    "name": "ck_product_currency",
    "sqltext": "(`currency` = _utf8mb4'LKR')"
  },
  {
    "name": "ck_product_name",
    "sqltext": "(char_length(trim(`name`)) > 0)"
  },
  {
    "name": "ck_product_price",
    "sqltext": "(`unit_price` > 0)"
  },
  {
    "name": "ck_product_publication",
    "sqltext": "(`publication_status` in (_utf8mb4'draft',_utf8mb4'published',_utf8mb4'archived'))"
  }
]
```

### users

| Column | Actual MySQL type | Nullable | Server default |
|---|---|---|---|
| user_id | BIGINT | NO | (none) |
| full_name | VARCHAR(150) COLLATE utf8mb4_unicode_ci | NO | (none) |
| phone | VARCHAR(20) COLLATE utf8mb4_unicode_ci | YES | (none) |
| email | VARCHAR(255) COLLATE utf8mb4_unicode_ci | NO | (none) |
| password_hash | VARCHAR(255) COLLATE utf8mb4_unicode_ci | NO | (none) |
| platform_role | VARCHAR(30) COLLATE utf8mb4_unicode_ci | NO | (none) |
| preferred_language | VARCHAR(10) COLLATE utf8mb4_unicode_ci | NO | (none) |
| account_status | VARCHAR(30) COLLATE utf8mb4_unicode_ci | NO | (none) |
| created_at | DATETIME | NO | (now()) |

**primary_key**

```json
{
  "constrained_columns": [
    "user_id"
  ],
  "name": null
}
```

**foreign_keys**

```json
[]
```

**indexes**

```json
[
  {
    "name": "ix_users_email",
    "column_names": [
      "email"
    ],
    "unique": true
  }
]
```

**unique_constraints**

```json
[
  {
    "name": "ix_users_email",
    "column_names": [
      "email"
    ],
    "duplicates_index": "ix_users_email"
  }
]
```

**checks**

```json
[]
```

## Appendix B: current source API routes

All paths below have /api/v1 prepended by app/main.py (health handling is separate). Listing a route proves source existence, not runtime availability.

| Router source | Method | Route |
|---|---|---|
| admin.py | GET | /admin/overview |
| admin.py | GET | /admin/users |
| admin.py | GET | /admin/users/{user_id} |
| admin.py | GET | /admin/users/{user_id}/businesses |
| admin.py | PATCH | /admin/users/{user_id}/status |
| admin.py | GET | /admin/drivers |
| admin.py | GET | /admin/drivers/{user_id} |
| admin.py | PATCH | /admin/drivers/{user_id}/decision |
| admin.py | GET | /admin/audit-events |
| admin_businesses.py | GET | /admin/businesses |
| admin_businesses.py | GET | /admin/businesses/{business_id} |
| admin_businesses.py | PATCH | /admin/businesses/{business_id}/decision |
| admin_businesses.py | GET | /admin/businesses/{business_id}/audit-history |
| auth.py | POST | /auth/register/customer |
| auth.py | POST | /auth/register/shop-owner |
| auth.py | POST | /auth/register/driver |
| auth.py | POST | /auth/login |
| auth.py | GET | /auth/me |
| catalogue.py | POST | /shop-owner/categories |
| catalogue.py | GET | /shop-owner/catalogue/summary |
| catalogue.py | GET | /shop-owner/categories |
| catalogue.py | PATCH | /shop-owner/categories/{category_id} |
| catalogue.py | POST | /shop-owner/products |
| catalogue.py | GET | /shop-owner/products |
| catalogue.py | GET | /shop-owner/products/{product_id} |
| catalogue.py | PATCH | /shop-owner/products/{product_id} |
| catalogue.py | GET | /customer/catalogue/shops |
| catalogue.py | GET | /customer/catalogue/shops/{business_id} |
| catalogue.py | GET | /customer/catalogue/shops/{business_id}/categories |
| catalogue.py | GET | /customer/catalogue/shops/{business_id}/products |
| catalogue.py | GET | /customer/catalogue/shops/{business_id}/products/{product_id} |
| customer.py | GET | /customer/dashboard/summary |
| customer.py | GET | /customer/shops |
| customer.py | GET | /customer/credit-accounts |
| customer.py | GET | /customer/credit-accounts/{credit_account_id} |
| customer.py | GET | /customer/transactions |
| customer.py | GET | /customer/credit-accounts/{credit_account_id}/statement |
| customer.py | GET | /customer/credit-accounts/{credit_account_id}/statement.pdf |
| driver.py | GET | /driver/profile |
| driver.py | POST | /driver/profile |
| driver.py | GET | /driver/dashboard/summary |
| driver.py | GET | /driver/deliveries |
| driver.py | GET | /driver/history |
| driver.py | GET | /driver/jobs |
| driver.py | GET | /driver/jobs/{job_id} |
| driver.py | GET | /driver/deliveries/{job_id} |
| driver.py | POST | /driver/deliveries/{job_id}/status |
| driver.py | POST | /driver/jobs/{job_id}/accept |
| health.py | GET | /health |
| health.py | GET | /health/database |
| notifications.py | GET | /notifications |
| notifications.py | GET | /notifications/unread-count |
| notifications.py | PATCH | /notifications/read-all |
| notifications.py | PATCH | /notifications/{notification_id}/read |
| orders.py | POST | /customer/orders/quote |
| orders.py | POST | /customer/orders |
| orders.py | GET | /customer/orders |
| orders.py | GET | /customer/orders/{order_id} |
| orders.py | POST | /customer/orders/{order_id}/decision |
| orders.py | GET | /shop-owner/orders |
| orders.py | GET | /shop-owner/orders/{order_id} |
| orders.py | POST | /shop-owner/orders/{order_id}/decision |
| orders.py | POST | /shop-owner/orders/{order_id}/delivery |
| orders.py | GET | /shop-owner/orders/{order_id}/delivery |
| orders.py | GET | /customer/orders/{order_id}/delivery |
| role_access.py | GET | /access/shop-owner |
| role_access.py | GET | /access/customer |
| role_access.py | GET | /access/driver |
| role_access.py | GET | /access/admin |
| shop_owner.py | POST | /shop-owner/businesses |
| shop_owner.py | GET | /shop-owner/business-context |
| shop_owner.py | GET | /shop-owner/dashboard/summary |
| shop_owner.py | GET | /shop-owner/dashboard/recent-transactions |
| shop_owner.py | GET | /shop-owner/customers |
| shop_owner.py | POST | /shop-owner/customers |
| shop_owner.py | GET | /shop-owner/customers/{customer_id} |
| shop_owner.py | PATCH | /shop-owner/customers/{customer_id} |
| shop_owner.py | POST | /shop-owner/customers/{customer_id}/credit-account |
| shop_owner.py | PATCH | /shop-owner/customers/{customer_id}/credit-account |
| shop_owner.py | POST | /shop-owner/credit-sales |
| shop_owner.py | POST | /shop-owner/repayments |
| shop_owner.py | GET | /shop-owner/repayments/{repayment_id}/receipt |
| shop_owner.py | GET | /shop-owner/customers/{customer_id}/statement |
| shop_owner.py | GET | /shop-owner/outstanding-payments |
| shop_owner_communication.py | GET | /shop-owner/payment-reminders/{reminder_id}/communication |
| shop_owner_communication.py | POST | /shop-owner/customers/{customer_id}/communication/consent |
| shop_owner_communication.py | POST | /shop-owner/payment-reminders/{reminder_id}/whatsapp-handoff |
| shop_owner_deliveries.py | POST | /shop-owner/deliveries |
| shop_owner_deliveries.py | GET | /shop-owner/deliveries |
| shop_owner_deliveries.py | GET | /shop-owner/deliveries/summary |
| shop_owner_deliveries.py | GET | /shop-owner/deliveries/{request_id} |
| shop_owner_deliveries.py | POST | /shop-owner/deliveries/{request_id}/cancel |
| shop_owner_reminders.py | POST | /shop-owner/payment-reminders |
| shop_owner_reminders.py | GET | /shop-owner/payment-reminders |

## Appendix C: verified approved references

| File | Dimensions | SHA-256 |
|---|---|---|
| design-references/customer/01-Dashboard.png | 1536 x 1024 | f8790ff4da130fa0ea3aaf582e21e8121dc1500b98d6e2d65f8dc93998fa6a37 |
| design-references/customer/02-Browse-shops.png | 1536 x 1024 | 704e5e90d135068c4cbc988b4c2edc31c9c6b4a34b6638ab18bfb031b8e539fc |
| design-references/customer/03-shop-products.png | 1418 x 1109 | c210710e94355d20d9a31191b4de86f869cb2a37636c2f19c05b8a5914d07567 |
| design-references/customer/04-Shop-cart.png | 1536 x 1024 | 0916d8ec8f296fb3571c34701d5f95b30d83f9409117d7a1d3032343286aa27b |
| design-references/customer/05-My-Orders.png | 1536 x 1024 | b49c94afe35664e62de31c8fbfd1eb55ce7754430ede228e807b0f8fdb4391da |
| design-references/customer/06-Mycredit-Accounts.png | 1536 x 1024 | 94e1a9a2a4b88a4dd75a59dda44f8a348bff83dcd02e41cc1312a58218c748d6 |
| design-references/customer/07-Mydeliveries.png | 1536 x 1024 | 6511dba93fdb2ac7d4bd3bba9cc097946ad285810db257182fd0e52173037478 |
| design-references/customer/08-Notifications.png | 1536 x 1024 | 6b18fb3bcc7849af2c4fe7f124444fff7384362c4d472e8aa9f59b8b575f645c |
| design-references/customer/09-Myprofile.png | 1536 x 1024 | da7437f9b934abc49694eab76af0b613e7d1c7b90b71202d5adc82fd5ca69e73 |
| design-references/customer/10-settings.png | 1536 x 1024 | 82059f5b35dfad6bcda0c4b67c938565a692106bbbde7c76e8882e1e37898d84 |
| design-references/driver/01-dashboard.png | 1536 x 1024 | 6180077d33742cfccf4ea45c74d64dcaa0d7520a72586d005c7a005a91fafe59 |
| design-references/driver/02-my-deliveries.png | 1418 x 1109 | 3847b9b95b54c1ba532e0db8606fa0fe598725228db5f34b290727dd9f70d91e |
| design-references/driver/03-my-earnings.png | 1419 x 1108 | 4f9cd7c4bdd4495aac2395de8c5a484a500e049c2f2484cbce4173a5529d225b |
| design-references/driver/04-my-vehicle.png | 1536 x 1024 | 77c8ebf31044c0443baf8e6b191e778201ddfbbbdf11d90a0f05255e534f2725 |
| design-references/driver/05-notifications.png | 1536 x 1024 | 2c1fcb201f766ce86eb8cac8df1d167450ffb1b6fec8835a88c3bed47c9b4138 |
| design-references/driver/06-my-profile.png | 1419 x 1108 | 4c1185010f4315b3832ffe42837d2f08d4f1224b643f80e0e2d66d9694a8c2c0 |
| design-references/shop-owner/01-dashboard.png | 1536 x 1024 | 52e3c9e565e77eb70526b4f39330e19b2bbb39a4bc3f703ff6a91379f445809b |
| design-references/shop-owner/02-customers.png | 1419 x 1108 | e9b478fce7c98a5a7feab2e1afe02c5e49262bc986463186cad1fc4b97f765aa |
| design-references/shop-owner/03-credit-sales.png | 1419 x 1108 | 4b0eeb3af31ca99c9707c85f4af2afc23f392a7f30178b4cdc03d0119719d2be |
| design-references/shop-owner/04-Repayments.png | 1536 x 1024 | 7d6a38ec90d4d22f6e50ccc7291e6e2de4b598f386d40476bd6dc2b99101b996 |
| design-references/shop-owner/05-Credit-orders.png | 1419 x 1108 | 6bb6364d5331a3cf1f2305b7baf9b0f41d3df7340320b3c878f7290029694b3c |
| design-references/shop-owner/06-Deliveries.png | 1536 x 1024 | 74f613195dd2ca74583eb60c7e198428aeadfc7eebc62ac129ece71a983c57c0 |
| design-references/shop-owner/07-shop $ Products.png | 1419 x 1108 | 92e10e9a81f70b712fc72775e8362d61909e5afbe042188f2ac9d8df044fdc2f |
| design-references/shop-owner/08-Reports.png | 1419 x 1108 | 5841f2501f61162a4c41cce0bc6bf99ab57fed58950a07b003c4571c0370bf6d |
| design-references/shop-owner/09-Notifications.png | 1536 x 1024 | 12e9405f3018070ab538c8c210e2fef55dc1e9a0d4e277e4d0278d454b55fc03 |
| design-references/shop-owner/10-Settings.png | 1419 x 1109 | a665d9833b810616fdb4e95a35ac6a715d5e3fa4e05df493713cf6b02b406c2f |

## Appendix D: migration source inspection

| Revision | Parent | File | Source operation calls in upgrade |
|---|---|---|---|
| 79d8d51548c6 | (root) | 79d8d51548c6_create_initial_lankapex_core_tables.py | create_table(businesses); create_table(users); create_index(); create_table(business_members); create_index(); create_index(); create_table(customer_profiles); create_index(); create_index(); create_table(credit_accounts); create_index(ix_credit_account_creditor_status); create_index(); create_table(ledger_entries); create_index(ix_ledger_account_recorded); f(ix_users_email); f(ix_business_members_business_id); f(ix_business_members_user_id); f(ix_customer_profiles_business_id); f(ix_customer_profiles_user_id); f(ix_credit_accounts_creditor_business_id) |
| b2a1c4d6e8f0 | 79d8d51548c6 | b2a1c4d6e8f0_add_business_approval_audits.py | create_table(business_approval_audits); create_index(ix_business_approval_audits_business_id) |
| c3d9e2f1a601 | b2a1c4d6e8f0 | c3d9e2f1a601_add_payment_reminders.py | create_table(payment_reminders); create_index(ix_reminder_business_created); create_index(ix_reminder_customer_created) |
| d4e0f3a2b702 | c3d9e2f1a601 | d4e0f3a2b702_add_notifications.py | create_table(notifications); create_index(ix_notifications_business_id); create_index(ix_notification_recipient_created); create_index(ix_notification_recipient_read_created); create_index(ix_notification_recipient_type_created) |
| e5f1a4b3c803 | d4e0f3a2b702 | e5f1a4b3c803_add_communication_records.py | create_table(communication_consents); create_index(ix_consent_customer_latest); create_table(communication_attempts); create_index(ix_handoff_reminder_created) |
| f6a2b5c4d904 | e5f1a4b3c803 | f6a2b5c4d904_add_driver_delivery_foundation.py | create_table(driver_profiles); create_table(delivery_requests); create_index(ix_delivery_status_created); create_index(ix_delivery_business); create_table(delivery_assignments); create_index(ix_assignment_driver_date) |
| a7b3c6d5e015 | f6a2b5c4d904 | a7b3c6d5e015_add_delivery_status_events.py | create_table(delivery_status_events) |
| b8c4d7e6f126 | a7b3c6d5e015 | b8c4d7e6f126_delivery_notifications.py | execute(ALTER TABLE notifications DROP CHECK ck_notification_type, ADD CONSTRAINT ck_notification_type CHECK (notifica); execute(ALTER TABLE notifications DROP CHECK ck_notification_entity_type, ADD CONSTRAINT ck_notification_entity_type C) |
| c9d5e8f7a237 | b8c4d7e6f126 | c9d5e8f7a237_add_business_catalogue.py | create_table(product_categories); create_index(ix_category_business_active); create_table(products); create_index(ix_product_business_publication); create_index(ix_product_business_category) |
| d0e6f9a8b348 | c9d5e8f7a237 | d0e6f9a8b348_shopping_orders.py | execute(CREATE TABLE orders ( order_id BIGINT NOT NULL AUTO_INCREMENT, reference VARCHAR(40) NOT NULL, customer_user_i); execute(CREATE INDEX ix_order_business_status ON orders (business_id, status, order_id)); execute(CREATE INDEX ix_order_customer_created ON orders (customer_user_id, created_at, order_id)); execute(CREATE TABLE order_items ( order_item_id BIGINT NOT NULL AUTO_INCREMENT, order_id BIGINT NOT NULL, product_id ); execute(ALTER TABLE notifications DROP CHECK ck_notification_type, ADD CONSTRAINT ck_notification_type CHECK (notifica); execute(ALTER TABLE notifications DROP CHECK ck_notification_entity_type, ADD CONSTRAINT ck_notification_entity_type C) |
| e1f7a0b9c459 | d0e6f9a8b348 | e1f7a0b9c459_link_order_delivery.py | create_unique_constraint(uq_delivery_id_business); add_column(orders); create_unique_constraint(uq_order_delivery_request); create_foreign_key(fk_order_delivery_business) |
| f2a8b1c0d560 | e1f7a0b9c459 | f2a8b1c0d560_order_delivery_notifications.py | drop_constraint(ck_notification_type); create_check_constraint(ck_notification_type); drop_constraint(ck_notification_entity_type); create_check_constraint(ck_notification_entity_type) |
| 03b9c2d1e671 | f2a8b1c0d560 | 03b9c2d1e671_admin_foundation.py | create_table(admin_audits); create_index(ix_admin_audit_created); create_index(ix_admin_audit_target); drop_constraint(ck_notification_type); create_check_constraint(ck_notification_type); drop_constraint(ck_notification_entity_type); create_check_constraint(ck_notification_entity_type) |

## Appendix E: missing modeled table definitions (not executed)

Compiled from current SQLAlchemy metadata using the MySQL dialect; these definitions document expected structures, not a migration script to run. Historical migrations remain the deployment source of truth.

### admin_audits
```sql

CREATE TABLE admin_audits (
	audit_id BIGINT NOT NULL AUTO_INCREMENT, 
	admin_user_id BIGINT NOT NULL, 
	target_type VARCHAR(20) NOT NULL, 
	target_id BIGINT NOT NULL, 
	action VARCHAR(30) NOT NULL, 
	previous_state VARCHAR(30), 
	new_state VARCHAR(30) NOT NULL, 
	reason VARCHAR(500), 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (audit_id), 
	CONSTRAINT ck_admin_audit_target CHECK (target_type IN ('user','driver')), 
	CONSTRAINT ck_admin_audit_action CHECK (action IN ('driver_approved','driver_rejected','account_suspended','account_reactivated','admin_provisioned')), 
	CONSTRAINT ck_admin_audit_target_id CHECK (target_id > 0), 
	FOREIGN KEY(admin_user_id) REFERENCES users (user_id) ON DELETE RESTRICT
)


```
### order_items
```sql

CREATE TABLE order_items (
	order_item_id BIGINT NOT NULL AUTO_INCREMENT, 
	order_id BIGINT NOT NULL, 
	product_id BIGINT NOT NULL, 
	product_name VARCHAR(200) NOT NULL, 
	quantity INTEGER NOT NULL, 
	unit_price NUMERIC(12, 2) NOT NULL, 
	line_total NUMERIC(14, 2) NOT NULL, 
	PRIMARY KEY (order_item_id), 
	CONSTRAINT uq_order_product UNIQUE (order_id, product_id), 
	CONSTRAINT ck_order_quantity CHECK (quantity BETWEEN 1 AND 99), 
	CONSTRAINT ck_order_line_total CHECK (unit_price > 0 AND line_total = unit_price * quantity), 
	FOREIGN KEY(order_id) REFERENCES orders (order_id) ON DELETE RESTRICT, 
	FOREIGN KEY(product_id) REFERENCES products (product_id) ON DELETE RESTRICT
)


```
### orders
```sql

CREATE TABLE orders (
	order_id BIGINT NOT NULL AUTO_INCREMENT, 
	reference VARCHAR(40) NOT NULL, 
	customer_user_id BIGINT NOT NULL, 
	business_id BIGINT NOT NULL, 
	request_key VARCHAR(100) COLLATE utf8mb4_bin NOT NULL, 
	request_hash VARCHAR(64) NOT NULL, 
	payment_method VARCHAR(10) NOT NULL, 
	payment_status VARCHAR(10) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	subtotal NUMERIC(14, 2) NOT NULL, 
	total NUMERIC(14, 2) NOT NULL, 
	credit_account_id BIGINT, 
	credit_sale_id BIGINT, 
	delivery_request_id BIGINT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (order_id), 
	CONSTRAINT uq_order_customer_request UNIQUE (customer_user_id, request_key), 
	CONSTRAINT uq_order_reference UNIQUE (reference), 
	CONSTRAINT uq_order_credit_sale UNIQUE (credit_sale_id), 
	CONSTRAINT uq_order_delivery_request UNIQUE (delivery_request_id), 
	CONSTRAINT fk_order_delivery_business FOREIGN KEY(delivery_request_id, business_id) REFERENCES delivery_requests (delivery_request_id, business_id) ON DELETE RESTRICT, 
	CONSTRAINT ck_order_method CHECK (payment_method IN ('cash','credit')), 
	CONSTRAINT ck_order_status CHECK (status IN ('submitted','approved','rejected','processing','completed','cancelled')), 
	CONSTRAINT ck_order_financial_state CHECK ((payment_method = 'cash' AND payment_status = 'unpaid' AND credit_sale_id IS NULL AND credit_account_id IS NULL) OR (payment_method = 'credit' AND credit_account_id IS NOT NULL AND ((payment_status = 'pending' AND credit_sale_id IS NULL AND status IN ('submitted','rejected','cancelled')) OR (payment_status = 'posted' AND credit_sale_id IS NOT NULL AND status IN ('approved','processing','completed'))))), 
	CONSTRAINT ck_order_total CHECK (total > 0 AND subtotal = total), 
	FOREIGN KEY(customer_user_id) REFERENCES users (user_id) ON DELETE RESTRICT, 
	FOREIGN KEY(business_id) REFERENCES businesses (business_id) ON DELETE RESTRICT, 
	FOREIGN KEY(credit_account_id) REFERENCES credit_accounts (credit_account_id) ON DELETE RESTRICT, 
	FOREIGN KEY(credit_sale_id) REFERENCES ledger_entries (entry_id) ON DELETE RESTRICT
)


```

## Appendix F: model comparison review

Effective type comparison retained all string lengths and numeric precision/scale; it normalized only inherited collation suffixes and MySQL NUMERIC/DECIMAL and BOOL/TINYINT spellings. No missing/extra columns or effective type/nullability differences were found in the 17 shared tables. All model-declared indexes and FK column sets on those shared tables exist in the inspected metadata. This does not assert identical constraint names or complete semantic identity: the pending delivery composite unique key and notification checks are explicitly different.

### delivery_requests expected model constraints
- UNIQUE uq_delivery_id_business: delivery_request_id, business_id
- ck_delivery_status: `status IN ('available','assigned','picked_up','in_transit','delivered','cancelled')`
- UNIQUE None: reference
### notifications expected model constraints
- ck_notification_read_state: `(is_read = 0 AND read_at IS NULL) OR (is_read = 1 AND read_at IS NOT NULL)`
- UNIQUE uq_notification_recipient_event: recipient_user_id, event_key
- ck_notification_entity_type: `(notification_type IN ('driver_approved', 'driver_rejected') AND related_entity_type = 'admin_audit') OR (notification_type IN ('credit_sale_recorded', 'repayment_recorded') AND related_entity_type = 'ledger_entry') OR (notification_type = 'payment_reminder_recorded' AND related_entity_type = 'payment_reminder') OR (notification_type IN ('business_approved', 'business_rejected') AND related_entity_type = 'business_approval_audit') OR (notification_type IN ('delivery_requested', 'delivery_cancelled', 'delivery_assigned', 'delivery_picked_up', 'delivery_in_transit', 'delivery_delivered') AND related_entity_type IN ('delivery_request', 'order')) OR (notification_type IN ('order_submitted', 'order_approved', 'order_rejected', 'order_processing', 'order_completed', 'order_cancelled') AND related_entity_type = 'order')`
- ck_notification_entity_id: `related_entity_id > 0`
- ck_notification_type: `notification_type IN ('driver_approved', 'driver_rejected', 'credit_sale_recorded', 'repayment_recorded', 'payment_reminder_recorded', 'business_approved', 'business_rejected', 'delivery_requested', 'delivery_cancelled', 'delivery_assigned', 'delivery_picked_up', 'delivery_in_transit', 'delivery_delivered', 'order_submitted', 'order_approved', 'order_rejected', 'order_processing', 'order_completed', 'order_cancelled')`
