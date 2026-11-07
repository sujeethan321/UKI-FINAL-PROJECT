# Day 14 Step 14.1 — Shopping and product catalogue backend

> Step 14.3 adds Customer exploration, server-side shop search/details and public category labels. See [the Customer browsing report](day14-customer-catalogue-browsing.md) for the current public API contract.

> Step 14.2 adds the owner UI, a secured catalogue summary endpoint and owner-only category labels. See [the UI integration report](day14-shop-owner-products-ui.md).

Status: **PASS**. Required tests pass. Ready for Step 14.2; local development use first requires the manual migration below. Review date: 2026-11-06.

## Audit and scope

Verified actual branch `main` and Day 13 checkpoint `aa5eed8` (`Day 13: complete shop-to-driver delivery integration and verification`), including models, services, routers, prior progress notes, migrations and tests. The initial working tree contained only the unrelated `.gitignore` change, which is preserved.

No Product, Category, stock or catalogue model/API existed. Business owners have active owner memberships through `BusinessMember` and may operate multiple businesses. Existing management policy requires an active Shop Owner account and an approved business. Customer registration/authentication uses the existing Customer role and JWT dependencies. Existing `/api/v1/customer/shops` is a private credit-linked shop list, not general shopping discovery; it remains unchanged.

This step adds backend catalogue functionality only. No frontend, cart, order, checkout, payment, credit approval, inventory, delivery, ledger or notification behavior was changed. General business location is omitted: the existing address is not a separate public/general location field. Images are deliberately unsupported in this minimal foundation rather than accepting unvalidated paths or external URLs.

## Files

New:

- `backend/app/models/catalogue.py`: `ProductCategory`, `Product`.
- `backend/app/schemas/catalogue.py`: explicit validated inputs, separate owner/customer projections and paginated contracts.
- `backend/app/services/catalogue_service.py`: ownership, publication, search/filter/discovery and catalogue writes.
- `backend/app/routers/catalogue.py`: two role-scoped routers.
- `backend/alembic/versions/c9d5e8f7a237_add_business_catalogue.py`.
- `backend/tests/test_catalogue.py`.
- This report and frontend handoff contract.

Modified only `backend/app/models/__init__.py` to register models and `backend/app/main.py` to mount the routers at the real `/api/v1` prefix. No changes to existing financial or delivery services. No commit, push or staging performed.

## Database models and migration

`product_categories`: category ID, business FK, name (100), optional description (2000), active boolean and created/updated UTC timestamps. Category names are unique within a business using explicit MySQL `utf8mb4_unicode_ci` collation (case/accent insensitive). Names are trimmed; duplicate conflicts return 409. An inactive category retains its name and records; reactivate or rename it rather than creating another conflicting category.

`products`: product ID, business FK, optional category, name (200), optional description (4000), `DECIMAL(12,2)` unit price, fixed LKR currency, availability/publication states and created/updated UTC timestamps. Python uses `Decimal`; prices are serialized as two-decimal strings. Valid range is `0.01` to `9999999999.99`. Floating-point and boolean inputs are rejected; use decimal strings. Exact integer inputs are also accepted. Fractional values beyond two decimal places and non-finite values are rejected.

The composite `(category_id, business_id)` foreign key references a unique category/business pair, enforcing shop isolation at the database level as well as in the API. Category IDs are strict positive integers in JSON. Foreign keys restrict deletion; there are no hard-delete APIs. Product names need not be unique: distinct IDs are authoritative, and different businesses can price the same name independently.

Indexes cover category business/active lists, product business/publication lists and category/business joins. All list endpoints use ascending IDs for deterministic pagination. Search is a bounded name substring query, parameterized and escaped so `%` and `_` are literal characters rather than client-controlled wildcards. No full-text or stock system is claimed.

Migration `c9d5e8f7a237` follows `b8c4d7e6f126` and creates only these two new tables, foreign keys, checks, unique constraints and indexes. It preserves existing tables/data. Downgrade refuses to discard catalogue records. Test-schema reflection matches the new model metadata with no drift. Offline SQL generation succeeds, and Alembic reports one head.

Applied only to verified `lankapex_test_db`. **The development database was not migrated.** Existing development schema remains at `b8c4d7e6f126`; new catalogue APIs require the migration before local development use. From `backend`, after reviewing the configured database:

```powershell
$env:MYSQL_DATABASE = 'lankapex_db'
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic upgrade head
```

These are application instructions, not commands executed against development during this task. Do not downgrade/reset or create replacement tables. A clean database should follow the existing revision chain through `alembic upgrade head`; no separate `create_all` shortcut is required.

## Actual API routes

All paths are relative to `/api/v1`. Owner routes require a `business_id` query parameter on every operation; it is never accepted as a writable body field.

| Method | Owner path | Purpose |
| --- | --- | --- |
| POST | `/shop-owner/categories` | Create category |
| GET | `/shop-owner/categories` | Paginated categories, including inactive |
| PATCH | `/shop-owner/categories/{category_id}` | Explicit name/description/active changes |
| POST | `/shop-owner/products` | Create draft or explicitly published product |
| GET | `/shop-owner/products` | Paginated products, including draft/archive |
| GET | `/shop-owner/products/{product_id}` | Own product details |
| PATCH | `/shop-owner/products/{product_id}` | Edit fields, availability, publish/unpublish or archive |

| Method | Customer path | Purpose |
| --- | --- | --- |
| GET | `/customer/catalogue/shops` | Approved shops with at least one customer-visible product and actual product count |
| GET | `/customer/catalogue/shops/{business_id}/categories` | Active categories for an approved shop |
| GET | `/customer/catalogue/shops/{business_id}/products` | Published visible shop products |
| GET | `/customer/catalogue/shops/{business_id}/products/{product_id}` | One published visible product in that shop |

Customer routes require an active Customer JWT; they are not anonymous or Shop Owner management routes. No credit-account/customer-profile linkage is required to browse eligible catalogues. Existing credit-linked `/customer/shops` semantics remain unchanged.

All lists accept `page` (1–1,000,000, default 1) and `page_size` (1–100, default 20). Product lists additionally accept `q` (name substring, maximum 200 characters), `category_id`, and `availability_status=available|unavailable`. The owner list also accepts `publication_status=draft|published|archived`. Lists are bounded, stable and expose actual totals. A category filter from another business returns no matching products; it cannot broaden the shop scope.

## Example contracts for Step 14.2

Create category: `POST /api/v1/shop-owner/categories?business_id=7`:

```json
{"name":"Groceries","description":"Everyday products","is_active":true}
```

Create product: `POST /api/v1/shop-owner/products?business_id=7`:

```json
{"name":"Rice","description":"One retail unit","category_id":11,"unit_price":"125.25","currency":"LKR","availability_status":"available","publication_status":"draft"}
```

Publication, availability and archive actions reuse PATCH rather than creating competing mutation endpoints:

```json
{"publication_status":"published"}
```

```json
{"availability_status":"unavailable"}
```

```json
{"publication_status":"archived"}
```

An owner product response includes `product_id`, `business_id`, `category_id`, `name`, `description`, `unit_price` (string), `currency`, `availability_status`, `publication_status`, `created_at`, `updated_at`. Timestamps are persisted naive UTC using the existing project convention; consumers should format them as UTC rather than interpreting them as browser-local times.

Illustrative Customer list shape (IDs/data are examples, not seeded production records):

```json
{"page":1,"page_size":20,"total":1,"products":[{"product_id":23,"business_id":7,"category_id":11,"name":"Rice","description":"One retail unit","unit_price":"125.25","currency":"LKR","availability_status":"available"}]}
```

Shop discovery returns `{page,page_size,total,shops:[{business_id,business_name,product_count}]}`. Category lists return `{page,page_size,total,categories:[...]}`. Customer category fields are only `category_id`, `business_id`, `name`, `description`; owner category rows additionally include `is_active`, `created_at`, `updated_at`. No owner/account/approval notes or credit records are exposed.

## Publication and availability policy

- New products default to `draft` and `available`; availability does not publish a draft.
- Draft may publish or archive. Published may return to draft (unpublish) or archive. Archived products remain owner-readable but are immutable; no restore/hard-delete endpoint exists.
- Published `available` and published `unavailable` products both remain browseable, with truthful availability text; customers can filter either state. Unavailable is a manual owner flag, not an inventory quantity.
- A category may be optional; uncategorized published products remain visible. A category from another business is rejected even if the owner operates both businesses.
- Deactivating a category hides its products from Customer lists, details and discovery counts without rewriting their publication state. Explicit reactivation restores visibility for retained published products. Publishing into or explicitly assigning a published product to an inactive category is rejected with 409. An existing hidden product may still have its price/description edited without publishing it.
- Unapproved shops, draft/archive products and inactive-category products return no public product detail (404). Approved shops with empty catalogues yield empty lists and are omitted from general discovery.

## Authorization and validation

Reuse the existing JWT/stored-role/account dependencies. Management independently checks current active owner membership, active Shop Owner account and approved business using shared/current reads; writes lock the target category/product. Wrong roles return 403; missing/expired JWT returns 401; missing/foreign business or entity returns 404; unapproved business management returns 403. This is enforced server-side and does not depend on frontend hiding.

Bodies forbid extra fields and identity/business mutation. Updates are explicit, non-empty patches; null may clear only descriptions or category assignment. Names are non-empty trimmed plain text, lengths are bounded, and HTML markup and control characters are rejected in names/descriptions. Currency is fixed and cannot be changed through PATCH. Image URLs/references, arbitrary paths, stock, owner IDs and other unsupported fields are rejected. Responses are JSON data, not executable markup.

The composite FK prevents accidental cross-business category assignment even through direct ORM writes. Category uniqueness is enforced by MySQL under concurrent calls. Constraint conflicts are sanitized as 409; database failures/commit errors roll back and return sanitized 503. Responses use `Cache-Control: no-store`. New catalogue creation is not an idempotent operation: after an ambiguous failure, clients must refresh/review rather than blindly recreate products. Concurrent valid edits use serialized row locks and the last successful edit wins; no version/ETag contract is introduced.

## Future Step 14.4 order contract — documentation only

A future order request should identify the business and product IDs plus validated quantities and a cash/credit selection; it must not supply authoritative prices, totals, credit balances, approval status or Driver identity. The backend must recheck product/business/category publication and availability inside the ordering transaction, read current Decimal prices and persist immutable product-name/unit-price/currency/quantity snapshots on order lines. Historical order totals must not change when catalogue prices are edited or products archived.

Credit purchase approval must reuse the existing Customer/business authorization and a separately designed approval/ledger transaction; catalogue publication does not grant credit. Optional delivery references should point to the existing `DeliveryRequest`, not a second delivery subsystem. Stock reservation/decrement needs a real inventory model before being claimed. No order tables, quantity handling, cash settlement, credit approval, checkout or delivery mutation was implemented here.

## Verification and remaining limits

Before mutation, effective settings, SQLAlchemy engine and actual `SELECT DATABASE()` were verified as `lankapex_test_db`; the existing pytest session guard repeats the checks. Tests use real JWT/HTTP/MySQL and rollback/savepoint fixtures, never development records.

Final targeted catalogue suite: **61 passed**, zero failed/skipped, **6.34s**. Covers categories/duplicates/validation/deactivation, ownership/multi-business isolation, composite FK enforcement, product lifecycle/price precision, search escaping/filtering/pagination, discovery/projections, draft/archive/approval privacy, roles/expired/missing JWT/suspended accounts, HTML/image/identity-field rejection, rollback and unchanged financial/delivery tables. Six new Python files parsed successfully. Catalogue metadata/migration comparison has zero differences and offline migration SQL generation passed.

Full backend regression: **915 passed**, zero failed/skipped, **127.44s**. This includes authentication/registration, business onboarding, financial/credit/customer/reminder/notification modules and all Driver/Day 13 delivery suites. The one existing warning comes from the deliberately short HMAC test key in `test_tampered_token_rejected`; no secret value was printed or modified. Evidence: ignored `.server-logs/day14-catalogue-targeted.log`, `day14-catalogue-regression.log` and offline `day14-catalogue-migration.sql`. Generated OpenAPI also confirms all eight catalogue route paths (eleven method/path operations).

No frontend tests/build/browser run is claimed because this is backend-only and no frontend files changed. No backend linter/typecheck is configured. Python syntax parsing and `git diff --check` passed. No files are staged and no commit/push was made; the older unrelated `.gitignore` change remains preserved.

Remaining limits: no inventory quantity/stock claims, image upload/reference system, public general-location field, durable creation idempotency key, advanced sorting/full-text search, orders or checkout. Development catalogue use requires the deliberately unapplied migration above. Step 14.2 should use these real owner routes, Decimal-string prices and server publication rules while preserving LankaPex's existing frontend design.


Final Day 14 verification and scoped local checkpoint: [regression and financial-security review](day14-final-regression-security-review.md). The final report supersedes historical test-count snapshots in this step report.
