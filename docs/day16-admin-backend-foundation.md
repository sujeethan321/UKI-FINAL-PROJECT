# Day 16 Step 16.1 — Administrator backend foundation

Backend implementation and required tests complete. Development rollout remains an explicit operator action.

## A. Repository audit

The branch is main; HEAD is d917e4f (Day 14 shopping integration). The 43 staged Day 15 files were already present and are preserved. Contrary to the supplied checkpoint assumption, the Day 15 checkpoint is not committed. No commit, push or index changes were made for this task. The unrelated .gitignore edit is preserved.

Existing platform_role is a stored string: admin, shop_owner, customer, driver. Public registration permits only the last three through distinct fixed-role handlers. User.account_status already supports active/suspended. Existing JWT login and /access/admin work for Administrators. A read-only development-database check found one existing Admin; no identity or credentials were exposed and no real Admin was provisioned.

Existing /admin/businesses APIs were functional: pending-only decisions, row locking, BusinessApprovalAudit and transactional notifications. DriverProfile already stores approval, vehicle and reviewer metadata, and Driver job services enforce approval and active-account eligibility. Missing capabilities were platform aggregates, bounded user/Driver management, public Admin Driver review, safe account mutations, unified audit access and explicit operator provisioning. Existing financial and delivery services were reused without financial-policy edits.

## B. Administrator authentication and provisioning

All management endpoints use centralized require_admin, which reuses the existing get_current_user/require_roles dependency. JWT signature, expiry, access-token type, identity and stored active account/role are authoritative. A client role claim cannot grant access. Missing/invalid JWT returns 401; inactive or wrong-role accounts return 403. Writes recheck and lock the current actor. Suspension blocks existing JWTs on their next authenticated request; reactivation restores account access without changing approvals.

There is no public Admin registration or role-edit endpoint. Generic management excludes every Admin target, including self and the last Admin. No impersonation, password reset, account deletion or financial role bypass was added.

Operator-only provisioning is implemented in backend/scripts/provision_admin.py and app/services/admin_provisioning.py. It requires local execution, explicit database-name confirmation and two hidden password prompts, uses existing normalized registration validation and password hashing, and records admin_provisioned in the same transaction. Existing Admins are returned unchanged (including password and suspension); an existing non-Admin email is refused. Nothing runs at startup. No default credentials or passwords in command arguments, environment variables or logs.

After explicit authorization, an operator with appropriate database access can run from backend in PowerShell:

~~~powershell
$env:PYTHONPATH = (Get-Location).Path
# Set MYSQL_DATABASE to the explicitly authorized target first.
.\.venv\Scripts\python.exe -m scripts.provision_admin --email "<operator email>" --name "<operator name>" --confirm-database "<authorized database>"
~~~

This command was not executed against the development database. Provisioning tests use only the guarded test database and roll back their accounts.

## C. Actual API contracts

Every route below requires an active Administrator Bearer JWT. Prefix: /api/v1. No separate Admin login. GET responses use Cache-Control: no-store. Lists use limit=20 (1–100), offset=0 (0–1,000,000), deterministic ordering and database total counts. There are no export endpoints.

| Method | Route | Filters/body and result |
|---|---|---|
| GET | /admin/overview | Ten database count fields shown below |
| GET | /admin/users | role=shop_owner/customer/driver; status=active/suspended; q; users envelope |
| GET | /admin/users/{user_id} | Safe user DTO; Admin/unknown targets 404 |
| GET | /admin/users/{user_id}/businesses | Shop Owner associations; businesses envelope with user_id |
| PATCH | /admin/users/{user_id}/status | account_status active/suspended and required reason; safe user DTO |
| GET | /admin/drivers | status; approval_status=pending/approved/rejected/suspended/not_submitted; q; drivers envelope |
| GET | /admin/drivers/{user_id} | Safe user DTO plus profile (nullable) |
| PATCH | /admin/drivers/{user_id}/decision | decision approve/reject; optional review_note; Driver DTO |
| GET | /admin/businesses | Existing route extended: status=pending/approved/rejected/all; q; businesses envelope |
| GET | /admin/businesses/{business_id} | Existing business details plus active owners |
| PATCH | /admin/businesses/{business_id}/decision | decision approve/reject; optional review_note; existing message + business DTO |
| GET | /admin/businesses/{business_id}/audit-history | Existing history plus total/limit/offset |
| GET | /admin/audit-events | target_type=user/driver/business; events envelope |

All routes in the table are relative to /api/v1. No new paths were substituted for the existing business endpoints. Invalid filters/bounds and extra mutation fields return 422. Missing targets return 404. Ineligible transitions return 409 (inactive target Driver returns 403). New management database failures return sanitized 503/409; existing business-decision database failures retain sanitized 500. After an uncertain response, refresh before retrying.

Search q is nonblank single-line text, at most 100 characters. User/Driver search covers only name/email; business search covers business name/registration number. SQL is parameterized and LIKE wildcard characters are escaped as literals. Names, email and business contact fields are restricted to authenticated Admin management, never public lists. User DTOs exclude phone, hashes, tokens, reset metadata, balances and transaction history. Business application contact fields remain available for registration review.

Illustrative structures (IDs and names below describe shapes, not seeded production records):

~~~json
{"total_shop_owners":0,"total_customers":0,"total_drivers":0,"pending_driver_approvals":0,"approved_drivers":0,"total_businesses":0,"pending_business_approvals":0,"approved_businesses":0,"total_orders":0,"total_delivery_requests":0}
~~~

Totals count all stored accounts of each role, including suspended accounts. Driver approval counts describe stored application states, not current job eligibility. Business counts describe registration status. Orders/delivery totals count stored rows of every lifecycle status. Aggregate SQL does not derive totals from pages; absent records yield zero.

~~~json
{"total":1,"limit":20,"offset":0,"users":[{"user_id":123,"full_name":"Example Customer","email":"customer@example.com","platform_role":"customer","account_status":"active","created_at":"2026-11-07T00:00:00"}]}
~~~

A Driver DTO has those six user fields plus:

~~~json
{"profile":{"approval_status":"pending","vehicle_type":"van","registration_reference":"EXAMPLE-123","reviewed_by":null,"reviewed_at":null}}
~~~

A missing application returns profile:null, not fabricated vehicle data. Driver list envelope uses drivers. Owner associations use businesses entries containing business_id, business_name, approval_status, membership_status and business_role. An empty page returns an empty collection and accurate total. Existing database DATETIME values are UTC; management timestamp formatting follows the existing business API convention.

Mutation examples:

~~~json
{"decision":"approve","review_note":"Reviewed stored application"}
~~~

~~~json
{"account_status":"suspended","reason":"Operational review"}
~~~

~~~json
{"total":1,"limit":20,"offset":0,"events":[{"source":"administrative","audit_id":1,"admin_user_id":100,"target_type":"driver","target_id":123,"action":"driver_approved","previous_state":"pending","new_state":"approved","reason":"Reviewed stored application","created_at":"2026-11-07T00:00:00"}]}
~~~

Audit IDs are unique within source; clients should key by source + audit_id. Business-history entries retain audit_id, admin_user_id, reviewer_name, reviewer_email, decision, previous_status, new_status, review_note and created_at.

## D. Management areas

Shop Owners and Customers use /admin/users with a role filter, avoiding duplicate models/routers. Shop Owner business associations are separately bounded. Drivers add stored profile/vehicle/reviewer fields and approval filters. Business review reuses the existing owner relationship and application endpoints. No financial detail is exposed by generic management.

## E. Approval workflows

Driver public reviews are pending -> approved or pending -> rejected only. They require an existing active Driver/application; approval additionally requires both stored vehicle fields. Missing fields/application and repeat/conflicting decisions return 409. Current locked state, reviewer ID/time, AdminAudit and notification belong to one transaction. Existing internal Driver review helpers remain available to established service callers; no broad internal transition was newly exposed publicly. No document-verification claim or resubmission/reversal API was added. Approval does not create deliveries or earnings. Existing eligibility still requires an active account, approved profile and stored vehicle fields.

Business reviews remain pending -> approved/rejected, preserving registration/ownership/history. Approval requires an active Shop Owner. Existing BusinessApprovalAudit and notification are committed with the decision. Replays conflict rather than duplicate events. Existing catalogue, order, credit and delivery guards continue enforcing approved businesses and unrelated membership/role/account restrictions.

## F. Account management

Only active <-> suspended is supported for Shop Owners, Customers and Drivers; reason is required, single-line, trimmed and at most 500 characters. Same-state retries succeed without another audit event. Other stored states cannot be overwritten by this API. All Admin targets are excluded; Admin lifecycle changes require a separately defined operational policy.

Conservative operational guards:

- Driver suspension is deferred with 409 while assigned/picked_up/in_transit deliveries exist. No silent reassignment or deletion occurs.
- Customer suspension is deferred with 409 while submitted/approved/processing orders exist. Credit history and limits are preserved.
- Shop Owner suspension is deferred with 409 if an approved associated business would lose its last active owner. The business row serializes concurrent owner suspensions. Another active owner can continue operations; no business approval is changed.
- Reactivation changes only account status. It cannot approve a rejected/pending Driver or business, reopen a credit account or alter an order.

Writes lock current account state. Existing Driver acceptance holds the same account row in shared mode, so acceptance and suspension cannot both leave an assigned suspended Driver. Operational account-state mutation can conflict with other locked business operations; sanitized errors require refresh/retry. There is no automatic recovery/reassignment policy. Suspended users cannot read their inbox; account changes are audited rather than issuing inaccessible suspension alerts.

## G. Audit logging

New admin_audits stores actor ID (restricted FK), target type/ID, action, previous/new state, optional reason and UTC timestamp. Indexed by time/ID and target. Targets are polymorphic user/Driver IDs; no deletion APIs exist. Events: driver_approved, driver_rejected, account_suspended, account_reactivated, admin_provisioned. Successful events share the mutation transaction; rollback leaves no false successful event. Ordinary APIs cannot create, edit or delete audit entries.

Business decisions continue using business_approval_audits. /admin/audit-events merges both tables with bounded SQL pagination, preserving source and avoiding duplicate business audit rows. Failed attempts do not masquerade as successful state changes. Trusted database operators remain outside application API immutability. Review reasons must never contain passwords, tokens, documents or financial payloads.

## H. Notifications

Driver decisions add driver_approved/driver_rejected, related_entity_type=admin_audit, business_id=null, with the real audit ID. Recipient identity is resolved from current active Driver/database state. Generic messages exclude review reasons, private documents and financial values. Unique recipient/event keys prevent duplicates. Business review retains existing active-owner notifications. All writes are transactional; no alerts survive rollback.

Only frontend/src/utils/notification.js and its contract test were extended for compatibility with the existing strict notification client: a Driver alert links only to /driver/dashboard; injected URLs and wrong-role destinations are ignored. No Admin frontend or design/color changes were made. SMS/email/WhatsApp and account-state alerts were not added.

## I. Financial integrity

No ledger calculation/service, credit limit, financial statement, cash-paid flag or repayment policy was changed. Admin management cannot invoke Shop Owner/Customer financial endpoints by virtue of its role. Tests snapshot CreditAccount, LedgerEntry, Order and delivery/assignment rows around administrative actions and assert equality. Approval alone creates no order, delivery, sale or earnings. Existing financial regression tests remain required below.

## J. Database migrations and files

New migration: backend/alembic/versions/03b9c2d1e671_admin_foundation.py, following f2a8b1c0d560. It creates admin_audits with MySQL constraints/indexes and widens existing notification check constraints for the two Driver events. There are no row deletions, role rewrites or automatic account creation. Downgrade refuses to discard audit/notification history; use a forward migration.

Before applying to the test database, settings.MYSQL_DATABASE, engine.url.database and SELECT DATABASE() were each verified as lankapex_test_db. Only that database was upgraded. Alembic check reports no new upgrade operations. The development database was not migrated or reset; its inspected revision was b8c4d7e6f126, so review the intervening Day 14/15 migrations too before any authorized development upgrade.

Manual migration command from backend, after selecting and independently verifying the intended database:

~~~powershell
$env:MYSQL_DATABASE = 'lankapex_test_db'
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
~~~

Do not replace the target with lankapex_db without an explicit authorized operational migration. No reset command is needed.

Created: models/admin_audit.py, schemas/admin.py, schemas/admin_business.py, services/admin_service.py, services/admin_provisioning.py, routers/admin.py, scripts/provision_admin.py, the migration, tests/test_admin_foundation.py, tests/test_admin_concurrency.py and this document (backend paths relative to backend/app unless otherwise specified).

Modified: backend/app/core/auth_dependencies.py, main.py, models/__init__.py, models/notification.py, schemas/notification.py, services/notification_service.py, routers/admin_businesses.py; frontend/src/utils/notification.js and frontend/tests/notifications.test.js. Existing staged Day 15 content remains staged separately from these working-tree edits.

## K. Verification results

- Targeted Administrator suite: **76 passed, 0 failed, 0 skipped** (10.54s), including real JWT, role denial, safe response projections, bounds/search, Driver/business approvals, notification isolation, rollback, financial snapshots, provisioning, profile escalation denial and independent-transaction races.
- Full backend regression: **1,107 passed, 0 failed, 0 skipped** (190.57s), including existing authentication, onboarding, dashboards, catalogue, cash/credit orders, financial ledger, repayments, statements, reminders, notification, delivery and order-integration tests. One existing InsecureKeyLengthWarning comes from tests/test_jwt.py::test_tampered_token_rejected using its deliberately short test key.
- Full frontend regression: **680 passed, 0 failed, 0 skipped** (77.14s).
- Production build: **passed**, Vite 8.3.5; JS 772.26 kB (209.45 kB gzip), CSS 63.53 kB (13.08 kB gzip). Existing >500 kB chunk warning remains.
- Changed-file ESLint: **passed**, notification.js and notifications.test.js.
- Full frontend ESLint: **8 existing errors, 1 existing warning**, confined to unchanged ShopOwnerCustomers.jsx, ShopOwnerDashboard.jsx and repayments.test.js. This matches the Day 15 baseline; no new lint failures in this task.
- Backend AST syntax check: **76 application/script/migration files parsed**; no backend linter/typechecker is configured.
- Alembic upgrade/current/check: **passed on lankapex_test_db**, head 03b9c2d1e671, no pending metadata changes.
- git diff --check: **passed**. Existing CRLF conversion/config-access notices are environmental.

Initial targeted iterations exposed and corrected only test-harness issues: unsupported DELETE helper body, exact fixture notification cleanup and SQL lock observer support for MySQL FOR SHARE. The failed fixture's exact test rows were removed after database/identity verification; no database reset was performed. The final targeted run is clean. Logs are local ignored .server-logs/day16-*.log files.

## L. Remaining issues and operational limitations

No Admin was provisioned against development and no development schema upgrade was run. Runtime use of new APIs against that database requires an authorized migration. The existing Day 15 checkpoint remains uncommitted, and this task does not commit/push. Existing full-project frontend lint debt is reported with final results; no unrelated fixes are included. Identity verification, approved/rejected application re-review, Admin account lifecycle, automatic delivery reassignment, account-state alerts, financial reporting, exports and AI Summary remain outside this milestone.

## M. Next milestone

Day 16 Step 16.2 can build the Administrator Dashboard against these real authenticated endpoints after applying the schema in its authorized runtime environment. Use /admin/overview for aggregate cards, bounded role-filtered lists, server-confirmed decisions and refresh after conflicts. No mock production data or frontend-authoritative permissions are required. No Administrator Dashboard UI was built in Step 16.1.

## Consolidated Day 16 progress — Step 16.5 review

Steps 16.1 (backend), 16.2 (Dashboard) and 16.3 (management UI) are implemented. Step 16.4 operational reports/date filtering/CSV/full activity exploration is **not implemented**; the existing overview and recent audit preview do not substitute for it. Step 16.5 therefore remains **PARTIAL**, and no completion commit is allowed yet under its checkpoint conditions.

The final review adds distinct-Administrator concurrency, inactive/deactivated access-denial, audit and financial/order-preservation checks, runs fresh regressions/build, preserves the earlier 43 staged Day 15 files and leaves the development database unchanged. See [the consolidated security, regression and Git report](day16-final-security-regression-review.md) for authoritative current test counts, operational/visual limitations, Git state and remaining work. Earlier milestone counts in this document are historical results.

Final Step 16.5 results: **1,123 backend passed**, **801 frontend passed**, **92 targeted backend passed**, **121 targeted frontend passed**; every suite has 0 failed and 0 skipped. The Vite build, scoped Admin lint, test-schema metadata check and Python syntax checks pass. Full-project lint retains its pre-existing 8 errors/1 warning. Real two-Admin review/account races and financial/order snapshot/no-DML assertions pass. Test fixtures cleaned up without a reset. The development database remains at b8c4d7e6f126 (read-only verification); browser surfaces are unavailable. **No completion commit**: main remains d917e4f, all 43 earlier staged snapshots are unchanged, and Step 16.4/reporting plus operational/visual verification remain unresolved. Do not begin Day 17 yet.
