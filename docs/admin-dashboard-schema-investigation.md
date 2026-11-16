# Admin Dashboard unavailable — confirmed schema mismatch

Investigated **2026-11-08 (Asia/Colombo)**. **Root cause confirmed; operational
repair remains BLOCKED pending reviewed migrations.** No migrations, schema/data
changes, database reset, balance repair, deployment, push or AI Summary work.
Application changes clarify this failure; they do **not** create missing tables
or claim that Dashboard information now loads on the stale development schema.

## Exact request and component trace

1. `frontend/src/utils/adminDashboard.js`, `adminReadError`, contains the literal
   **Platform information is unavailable. Check your connection and retry.**
2. `createAdminDashboardReader` fetches overview/activity independently; 401/403
   invalidate both sections. Other errors enter each section's error state; a
   malformed successful response uses a different validation message.
3. `frontend/src/services/adminDashboardService.js` uses the shared authenticated
   Axios client for `GET /admin/overview` and `GET /admin/audit-events` with
   `limit=5&offset=0`. Axios base supplies the actual `/api/v1` prefix.
4. `frontend/src/pages/admin/AdminDashboard.jsx`, `AdminDashboardView`, renders
   section errors through `Failure`, preserving section retry and unavailable
   metrics rather than presenting missing data as zero.
5. `backend/app/routers/admin.py`: `/api/v1/admin/overview` calls
   `admin_service.overview`; `/api/v1/admin/audit-events` calls
   `admin_service.audit_events`. Router-wide `require_admin` uses actual JWT User
   identity, active account and stored Admin role. Both operations return no-store.
6. `backend/app/services/admin_service.py`: overview uses a single SELECT of
   scalar SQL counts over users, businesses, driver_profiles, orders and
   delivery_requests. Activity unions admin_audits and business_approval_audits,
   then applies count/order/limit/offset. Neither query calculates credit balances.

## Actual local development diagnosis (read-only)

The servers had been stopped; no browser request/DevTools session was available.
The failure was reproduced through the actual FastAPI ASGI app/TestClient with
the **current local development database** bound to a MySQL session explicitly
set **TRANSACTION READ ONLY**. No authentication dependency was disabled. An
in-memory signed diagnostic JWT referenced an existing active Admin; tokens,
credentials, private identity values and financial records were not printed.
This is a read-only diagnosis, not a synthetic write-test run against development.

| Check | Actual result |
| --- | --- |
| Actual SELECT DATABASE / connectivity | Local lankapex_db reachable |
| Missing JWT → Admin overview | **401** |
| Existing active Admin JWT → `/api/v1/auth/me` | **200** (private values withheld) |
| Admin overview before change | **503**, `{"detail":"Administrator operation could not be confirmed; refresh before retrying"}` |
| Admin recent activity before change | **503**, same generic response |
| Underlying overview exception | SQLAlchemy/PyMySQL ProgrammingError, **1146**, table lankapex_db.orders does not exist |
| Underlying activity exception | SQLAlchemy/PyMySQL ProgrammingError, **1146**, table lankapex_db.admin_audits does not exist |

Connectivity and Admin authentication succeeded before these SELECTs failed.
This rules out the reproduced failure being a lost connection, invalid JWT,
missing Admin role or successful-response parsing error. It does not certify an
unobserved browser session's token/network configuration; the current database
failure independently reproduces the reported message.

Sanitized evidence: ignored `.server-logs/admin-schema-diagnostic.log` (before),
`admin-schema-diagnostic-verified.log` (after). Only schema names/missing-table
messages and safe response bodies are recorded, not SQL parameters or user data.

## Current schema, columns, relationships and revisions

Actual development revision: **b8c4d7e6f126**, unchanged from the earlier report
but **freshly verified**, not assumed. Repository has one head **03b9c2d1e671**.

| Required/related structure | Current actual schema |
| --- | --- |
| users, businesses | Present; no missing mapped columns in inspected tables |
| driver_profiles, delivery_requests | Present; no missing mapped columns |
| business_approval_audits | Present; no missing mapped columns |
| orders, order_items | **Missing** |
| products, product_categories | **Missing** |
| admin_audits | **Missing** |

Inspected existing foreign keys: DriverProfile.user_id/reviewed_by → users;
DeliveryRequest.business_id → businesses, created_by → users;
BusinessApprovalAudit.business_id → businesses, admin_user_id → users. Expected
relationships for the missing structures cannot exist until their tables are
created by the reviewed migration chain. No existing relationships were altered.

Pending revisions, in order:

1. `c9d5e8f7a237_add_business_catalogue.py`: product_categories/products.
2. `d0e6f9a8b348_shopping_orders.py`: orders/order_items and related constraints.
3. `e1f7a0b9c459_link_order_delivery.py`: order/delivery linking.
4. `f2a8b1c0d560_order_delivery_notifications.py`: integration notification changes.
5. `03b9c2d1e671_admin_foundation.py`: admin_audits and review notifications.

**Products are not the direct cause of these two Dashboard SELECT failures.**
The overview directly requires orders; recent activity directly requires
admin_audits. No automatic ORM relationship loading joins product tables for these
queries. Regression SQL observation confirms neither query accesses products,
product_categories, credit_accounts or ledger_entries. Catalogue migration is
nevertheless an upstream prerequisite of the intended order/Admin schema chain.
Do not manually create only two tables, stamp a revision, return fake zeros or
skip migrations to make the page look healthy.

## Minimal application correction

- `backend/app/routers/admin.py`: after rollback, detect MySQL missing-table error
  1146 and return a safe structured **503** diagnostic. Keep other database errors
  generic; authentication, role checks and write transaction policy unchanged.
- `frontend/src/utils/adminDashboard.js`: map only this verified 503/code pair to
  **Platform database setup is incomplete. Contact the platform operator.**
  Do not display server-supplied exception text. Unknown 503, network, timeout,
  invalid response, 401 and 403 keep existing behavior.

Current schema-failure response, confirmed by read-only recheck:

```json
{
  "detail": {
    "code": "ADMIN_SCHEMA_UNAVAILABLE",
    "message": "Required Administrator database structures are unavailable. Contact the platform operator."
  }
}
```

Both endpoints still return **503** until schema remediation. No raw database or
table names, SQL, passwords, tokens, balances or transaction histories are sent to
the browser. Dashboard layout/colors/components remain unchanged. Failed sections
remain unavailable; a working section is not discarded merely because another
section fails. No partial invented platform counts are returned.

## Automated regression evidence — lankapex_test_db only

Before write fixtures, verified APP_ENV testing, settings/engine exact database,
loopback host and actual SELECT DATABASE() = **lankapex_test_db**. Existing session
guard and rollback-isolated synthetic fixtures execute real JWT/Admin boundaries.
Missing-table conditions are simulated with the actual SQLAlchemy/PyMySQL exception
shape; no test table is dropped and no migration or reset is run.

- `backend/tests/test_admin_dashboard_schema_failure.py` adds **5 cases**:
  overview/activity missing-table safe response; unrelated connectivity error
  stays generic; missing/non-Admin JWT cannot obtain schema diagnostics; current
  valid test schema serves both endpoints with 200 and performs no catalogue/
  ledger queries or DML.
- Existing Admin foundation/final security tests retain counts, safe DTOs,
  active/role/ownership guards, approval/account behavior and financial snapshot
  preservation.
- Backend selection: **85 passed, 0 failed/skipped**, 13.44 seconds. Existing
  pytest cache-path warning emitted, not suppressed.
- Frontend Dashboard/management/React-view selection: **122 passed**, 0 failed/
  skipped, 22.43 seconds. New controller regression proves schema error clarity,
  no raw diagnostics, null failed overview and preservation of successful activity.
- Scoped ESLint on modified frontend utility/test: **PASS**.
- Vite production build: **PASS**, 3.15 seconds; existing large-chunk warning.
  Process-only `https://api.example.invalid/api/v1` is a verification URL, not a
  deployment endpoint; no dotenv change.

Logs: `.server-logs/admin-schema-tests.log`, `admin-schema-frontend.log`,
`admin-schema-build.log`. No browser render/session walkthrough or full-regression
run is claimed. Selected Admin financial/authorization regression passed.

## Remaining operational fix and blockers

**Dashboard data restoration is BLOCKED**, not completed. Required fix is bringing
the database into alignment through the reviewed migration chain. User instructions
prohibit automatic migration, so no upgrade/stamp/create_all/manual table creation
or schema write was attempted.

The separate isolated chain-verification target
`lankapex_migration_verify_20261107` remains **BLOCKED** after MySQL permission
denial. A local DBA must create the separate empty target/grant the intended
account and identity/access/emptiness must be verified before a separately
authorized guarded migration-chain run. No elevated retry, DBA password request
or test-database substitution. Use [database operations](day17-database-operations.md)
and [readiness gates](day17-production-readiness.md).

After isolated migration verification and an approved backup/recovery plan, an
authorized operator can review and separately approve updating development schema.
Then recheck revision/tables/constraints and authenticated Admin endpoints for
**200** with actual database values. Do not treat this error-message correction,
test-schema passes or an offline SQL preview as proof development was migrated.
Existing financial records must remain intact; no repair or recalculation script.

## Files changed

- backend/app/routers/admin.py
- frontend/src/utils/adminDashboard.js
- backend/tests/test_admin_dashboard_schema_failure.py (new)
- frontend/tests/adminDashboard.test.js
- docs/admin-dashboard-schema-investigation.md (this report)

Diagnostic helper/logs remain ignored under .server-logs. All unrelated working
tree/index changes are preserved. No commit, push, deployment or AI integration.
