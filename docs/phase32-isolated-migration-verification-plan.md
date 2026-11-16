# Phase 3.2: isolated migration access and rehearsal plan

Latest evidence and prepared exact command: [completed preflight](phase32-completed-preflight.md).
The earlier 1044 observation below is historical: access now succeeds and the
dedicated target is empty. Required privileges exist, but an unescaped wildcard
database grant needs DBA scope correction before the guarded execution command.
No migration has run. Use the new standalone preflight, not old pytest commands.

2026-11-08. **Read-only investigation and preparation complete; migration execution remains BLOCKED.** No database was created, dropped, reset, migrated or populated; no grants were changed. Neither lankapex_db nor lankapex_test_db was modified. No application code or migrations were edited. AI integration remains deferred.

## Exact blocker: freshly observed evidence

The configured local connection was inspected without printing credentials, database URLs, raw grant statements or account identifiers. A separate target-specific connection attempt used **lankapex_migration_verify_20261107**. It failed with **MySQL 1044, OperationalError, access denied to that schema**.

| Check | Actual result |
|---|---|
| Current backend configuration | APP_ENV=development; MYSQL_DATABASE=lankapex_db; local server |
| Server version | 8.0.46 |
| Global privilege summary for configured account | USAGE only; no global CREATE or GRANT OPTION |
| Direct exact-target schema grant | None observed |
| Active roles / granted roles observed | None / none |
| information_schema visibility of preferred target | 0 rows visible to this account |
| Direct preferred-target access | Denied, MySQL 1044 |
| Existence and emptiness of preferred target | **UNCONFIRMED**; insufficient privileges |
| partial_revokes | OFF |
| Session time_zone | SYSTEM; UTC not established |
| lower_case_table_names | 1 |
| SQL mode | ONLY_FULL_GROUP_BY, STRICT_TRANS_TABLES, NO_ZERO_IN_DATE, NO_ZERO_DATE, ERROR_FOR_DIVISION_BY_ZERO, NO_ENGINE_SUBSTITUTION |

The historical CREATE DATABASE failure was also 1044. No creation was retried. **Zero visible rows does not prove absence**: MySQL filters schema metadata by privileges. A schema could exist but be hidden. Do not report it missing with certainty or run CREATE IF NOT EXISTS to conceal ambiguity. An authorized DBA must independently verify existence, emptiness and ownership. Only the configured identity was checked; no separate testing/migration principal's credentials or privileges were assumed. No administrator connection was attempted.

The metadata probe used guarded SELECT/SHOW plus a session-only read-only setting and returned no user/financial rows. The metadata connection selected the configured development database; all reads were identity/server/grant/information_schema metadata, not application data. The target connection failed before any target statements could run. Temporary local evidence script: `.server-logs/phase32-readonly-access-check.py`; raw credentials/grants were not exported.

## Configuration and connection safety

Settings resolve explicit initialization, environment, backend .env and file secrets in that precedence for development/testing; production excludes dotenv. URL.create and connection_options preserve password hiding, connection timeout and TLS policy. Do not print a Settings object, rendered URL or exception string containing a connection target. Record only safe identity/status/error-code fields.

Current normal Alembic execution uses app.core.database.engine and would therefore target **lankapex_db** with today's configuration. **Do not run plain alembic upgrade head.** Changing an unrelated shell tab or merely setting LANKAPEX_MIGRATION_VERIFY_DATABASE does not retarget normal env.py.

Testing Settings deliberately allow MYSQL_DATABASE=lankapex_test_db only. Do not bypass that guard or change it to the isolated name. The intended existing verification hook is a separately constructed SQLAlchemy engine whose URL.database is replaced with the exact isolated name; Alembic Config.attributes['connection'] receives that verified connection. env.py validates APP_ENV=testing plus the allowed isolated name and actual SELECT DATABASE(). It never needs to read/write the application test database for migration work. The ordinary test engine must never be used by this rehearsal.

Target replacement must use SQLAlchemy URL.set(database=exact_target), not text replacement, a SQL USE statement with fallback, or a CLI URL embedding a password. A reviewed future standalone execution harness must require an explicit target argument, verify configured isolated URL identity plus SELECT DATABASE(), reject both existing database names, inspect all tables/views/routines/events, and stop on any discrepancy. It must use safe secret loading and preserve verified TLS options. No such executor is created or run in this preparation step.

The older opt-in pytest in test_database_operations.py uses the supplied-connection hook, but importing its suite invokes conftest's mandatory lankapex_test_db connection and imports database fixtures. Other tests in that file still hard-code head 03b9c2d1e671, 13 revisions and 20 tables; those expectations are stale after Phase 3.1. **Do not run the old broad test command as this rehearsal.** Use a separately authorized/reviewed standalone harness or update the test tooling under separate code authorization. This task does not alter tests/application code or connect to lankapex_test_db.

## DBA actions, minimum permissions and SQL review

Prepared [DBA SQL review template](sql/phase32-isolated-migration-dba-review.sql.example). All mutating statements are **commented out**. The file is for separate authorized DBA review, not automatic execution. It requests no password and creates no account.

1. DBA checks the preferred schema authoritatively. If absent, create **only** lankapex_migration_verify_20261107 with utf8mb4/utf8mb4_unicode_ci/InnoDB-compatible server defaults after creation approval. If present, establish provenance and inspect every object. Any table, view, routine or event disqualifies it as an empty full-chain target; do not reset it. A replacement name would require new explicit designation/creation approval.
2. Choose an already approved local migration principal and its exact user@host. Prefer an existing identity with no grants to either application database. Do not broaden the normal application identity on existing schemas, grant global privileges, create a user or change its password as part of this template. If no suitable account exists, account provisioning is a separate DBA decision.
3. For the reviewed linear forward chain, scope **SELECT, INSERT, UPDATE, CREATE, ALTER, INDEX, REFERENCES** only to the designated schema. SELECT inspects/version-reads; INSERT initializes Alembic version and supports MySQL ALTER; UPDATE advances its one linear version row; CREATE builds tables/version table; ALTER changes/adds constraints/columns; INDEX creates explicit indexes; REFERENCES supports FKs. No downgrade/reset/rename is included. [MySQL privilege requirements](https://dev.mysql.com/doc/refman/8.0/en/privileges-provided.html).
4. DELETE is optional only for separately approved committed synthetic-fixture cleanup; rollback-only DML cases do not require it. It is not required to advance this single-head chain's existing version row. Reassess if the execution plan introduces merge/unmerge or different Alembic version-row behavior. No DROP, TRIGGER, CREATE VIEW/ROUTINE, EVENT, FILE, PROCESS, SUPER, CREATE USER, GRANT OPTION or global CREATE is needed for these forward migrations. Creating the schema is the DBA's separate action, not a runtime permission probe. REFERENCES is schema-scoped to the same target; no cross-schema parents exist.
5. With observed partial_revokes=OFF, escape every underscore in the database portion of a database-level GRANT: backticks alone do not remove wildcard meaning. Template uses `lankapex\_migration\_verify\_20261107`.*. DBA must recheck server semantics and resulting grants rather than toggle global partial_revokes. [MySQL GRANT scope rules](https://dev.mysql.com/doc/refman/8.0/en/grant.html).
6. DBA reviews resulting grants/roles locally and migration identity reconnects. Assert actual target, no objects and required grants. Do not paste raw grants or credentials into chat. Metadata-only grant inspection cannot prove every DDL permission by executing DDL; effective operations are verified only in an approved isolated rehearsal. No elevated permission test was made here.

The exact minimum is purpose-specific. An application account is not a backup account; dump/restore permissions are separate. A schema-scoped CREATE privilege may permit creation of that named schema if later absent; it is not authorization for this agent to do so. No grant should include matching wildcard database names. Do not revoke/change existing database privileges during this task; have the DBA choose a suitable confined identity.

## Revision and compatibility findings

Database-free validator rerun: **all seven check groups PASS** (31 Python files compiled, normal 25-model/mapper registration, five design column dictionaries, model/migration parity, FK/index/default checks, additive operation checks, downgrade refusal and offline MySQL rendering). Separate full-chain rendering with MySQL dialect server_version_info=8.0.46 compiled all **14 revision upgrade bodies into memory**, without env.py, a live connection, or executing SQL. It yielded 25 CREATE TABLE statements, excluding Alembic's own managed version table. That is compilation evidence, not server acceptance or execution success.

```text
79d8d51548c6 -> b2a1c4d6e8f0 -> c3d9e2f1a601 -> d4e0f3a2b702
 -> e5f1a4b3c803 -> f6a2b5c4d904 -> a7b3c6d5e015 -> b8c4d7e6f126
 -> c9d5e8f7a237 -> d0e6f9a8b348 -> e1f7a0b9c459 -> f2a8b1c0d560
 -> 03b9c2d1e671 -> 14c0d3e2f782
```

One root, one head; no new parent gap. Development's **last observed** revision was c9d5e8f7a237 in the preceding audit. It was not newly selected from alembic_version in this permissions-only task. No old migration is assumed applied. An isolated clean target starts with no version table; a staged fixture run within that new target can stop at c9d5e8f7a237 without touching either existing DB.

| Revision | Review finding and risk |
|---|---|
| d0e6f9a8b348 | Creates orders/items, scoped idempotency and unique credit_sale_id; CHECKs preserve cash/credit state and subtotal=total. Notification checks allow order events but not delivery_requested/cancelled. It also only permits delivery events referring to delivery_request. Existing unsupported notification rows would fail constraint replacement, even if a later revision permits them. No rows were inspected to assert this risk is present. |
| e1f7a0b9c459 | Adds unique(request_id,business_id), nullable unique orders.delivery_request_id and same-business composite FK. Legacy rows stay NULL. Parent composite uniqueness is structurally compatible with PK id; drift, missing tables/key or pre-existing conflicting constraint names can fail. |
| f2a8b1c0d560 | Expands type/entity checks for requested/cancelled and order-linked delivery notifications. Separate drop/create CHECK operations can fail midway; MySQL DDL is not transactionally rolled back as a whole. |
| 03b9c2d1e671 | Creates admin_audits and expands driver approval notifications. Reviewer/actor existence and required columns/types matter. Polymorphic audit target/notification entity IDs need service validation; no automatic FK to different entity tables is implied. |
| 14c0d3e2f782 | Creates only addresses/preferences/settings/vehicles/documents. Parent-first order, same-owner composite FKs, signed BIGINT, explicit referenced unique keys, supporting indexes, InnoDB/utf8mb4, ASCII SHA field, UTC-intended DATETIME(6), precise DECIMAL and review/default constraints compile. No existing rows/tables altered or copied. |

The new five table names and constraint names are unique in registered metadata. This does not prove an inaccessible target is empty. Review row format/key limits, charset/collation and identifier case behavior on target server; new indexes fit modern MySQL 8 InnoDB limits, but older/custom server settings still require execution verification. Strict mode is currently on; do not disable checks/FKs/strict mode to make migrations pass. CURRENT_TIMESTAMP(6) follows the session timezone: require rehearsal session +00:00 and validate UTC behavior without changing global server timezone. No defaults should silently convert unknown legacy facts to zero/approved/paid.

The document no-self-supersession CHECK was correctly omitted because document_id is AUTO_INCREMENT, which MySQL disallows in CHECK expressions. FK/unique constraints do **not** prevent self-reference or multi-record cycles. Required service validation before writes: reject self/cycles; replace only same vehicle and document type/current tip; validate SHA-256 hex; enforce driver ownership, active identity, authorized Admin reviewer, review-once concurrency, immutable file metadata, private signed access and audited review transitions. The current Admin audit enum does not implement document-review auditing. No new review/write APIs are authorized here. [MySQL CHECK restrictions](https://dev.mysql.com/doc/refman/8.0/en/create-table-check-constraints.html).

## Isolated execution checklist — proposed, NOT RUN

1. Obtain explicit DBA setup approval and complete authoritative schema/access checks above. Then obtain separate explicit execution approval for **only the exact dedicated schema**. Neither approval authorizes changes to lankapex_db/lankapex_test_db.
2. Use a dedicated process/harness with external integrations disabled, no HTTP server and secrets loaded privately. APP_ENV=testing retains normal Settings guard; its ordinary test engine must remain unused. Construct and pass only the dedicated URL/connection to Alembic; no plain CLI upgrade using the development environment. Review the harness before execution; no executor was added here.
3. Before any write, assert URL database and SELECT DATABASE() match preferred target; check authenticated principal/roles locally, MySQL version, session timezone, strict sql_mode, foreign_key_checks, default engine, charset/collation, privileges and capacity. Verify empty tables/views/routines/events authoritatively; no real-data dump may be loaded. Stop if any gate is uncertain.
4. Render/review entire chain and establish recovery plan. Clean-chain execution may stage at c9d5e8f7a237 (17 tables), d0e6f9a8b348 (19), e1f7/f2a8 (19), 03b9c2d1e671 (20), 14c0d3e2f782 (25). Record actual versions and schema inventory after each successful stage. Alembic version table adds one: final **26 total tables**, one version row **14c0d3e2f782**.
5. To test a representative populated upgrade without a second database/reset, first stage this **initially empty isolated target** at c9d5e8f7a237 and insert only approved synthetic prerequisite-compatible fixtures. Then advance in order, comparing pre-existing fixture rows/balance fingerprints. This is a staged full-chain and populated-tail rehearsal, not proof of two independent clean runs. A separate clean-only versus legacy-data repeat would require another separately authorized empty target or a DBA-reviewed reset; neither is authorized now.
6. After successful head, compare all 25 table structures to metadata including column precision/defaults/nullability, exact PK/unique/FK/index/check sets, table engine/collation and absence of unexpected tables. Verify constraints are enforced, not just named. Do not let a broad metadata comparator alone stand in for CHECK content or service authorization tests.
7. Run only explicitly approved positive/negative synthetic cases below, target-asserting before transactions. Rollback-only DML cases minimize residue; DDL is not rolled back. Concurrency cases may need committed synthetic rows and a separately reviewed cleanup/retention decision, not DELETE/RESET of unrelated data.
8. Preserve result/status, safe identity evidence, revision/stage, schema diff, error class/MySQL code and checks. Stop on failure; mark subsequent cases NOT RUN/BLOCKED. No downgrade, stamp, automatic drop/retry or schema reset. Report execution PASS only after access, full chain and intended assertions actually succeed.

Expected final application tables: users, businesses, business_members, customer_profiles, credit_accounts, ledger_entries, product_categories, products, orders, order_items, driver_profiles, delivery_requests, delivery_assignments, delivery_status_events, notifications, payment_reminders, communication_consents, communication_attempts, business_approval_audits, admin_audits, customer_addresses, user_preferences, business_settings, vehicles, vehicle_documents. No shopping_carts/items, earnings/payouts, disputes, group tables, subscriptions or AI provider tables.

## Rehearsal cases with expected outcomes

**Every case below is planned, NOT EXECUTED.** HTTP codes apply only after separately approved API implementation/testing; current checks here are SQL/schema or service acceptance expectations.

| Case | Positive / negative expectation |
|---|---|
| Access gates | Exact empty target accepted; missing access/foreign target/nonempty schema rejected before first write. Both existing DB names rejected. |
| Chain preservation | Staged synthetic legacy rows, customer contact/terms and ledger fingerprints unchanged across tail; no backfill into new tables, new tables initially empty. |
| Address/default ownership | Valid own address/default succeeds; unknown user, other user's default, one-sided/out-of-range coordinates, blank required strings fail FK/CHECK. Archived-address selection is service denial, not a DB CHECK guarantee. |
| Preferences | Missing row keeps documented defaults; valid theme/nullable email accepted; invalid theme/nonboolean/version 0 rejected. Concurrent compare/version updates yield one winner; customer-only/default archival rules require future service coverage. |
| Business defaults | NULL defaults and zero credit limit allowed; negative limit, zero/negative term/radius and invalid boolean/version rejected. Default change must never update existing account terms/balances. Membership gate is a service test. |
| Vehicles | Own driver vehicle with pending profile allowed to be stored; no automatic approval. Unknown driver, blank type/registration, invalid source/lifecycle/year fail. Duplicate registration is not globally unique by design. Active duplicate rules require locked service checks. |
| Documents | Pending/no-review default accepted; valid authorized approval/rejection evidence accepted at service layer. Invalid type, missing vehicle/reviewer, zero size, blank storage, incoherent pending/approved/rejected state fail constraints. |
| Supersession | Same-vehicle valid chain and first successor accepted; cross-vehicle FK and duplicate successor fail. Self-reference/cycles/wrong document type must be rejected by future service; direct SQL acceptance for these is a documented enforcement gap, not a passing security test. |
| Credit invariant | Synthetic sale 1000, repayments 300 and 700 gives outstanding 1000 -> 700 -> 0; reversing the 300 repayment gives 300. Use existing Decimal/effective ledger; no repairs or real-record tests. |
| Orders/assignment | Pending/rejected credit order no debt, approval retry one sale; cash unpaid/no credit sale; invalid business delivery link fails; concurrent job acceptance assigns once and unauthorized transitions denied by existing service. Only isolated integration harness, not existing shared DB pytest fixtures. |
| Notification preconditions | Seed only c9-compatible events before d0; verify all those survive and new final event types work at head. An intentionally unsupported event under a permissive drifted CHECK is a separate failure-injection scenario requiring extra empty target approval; never loosen live checks here. |
| DML rollback | Insert synthetic fixture inside transaction then roll back: no committed fixture remains, but sequence gaps are harmless; verify schema/revision unchanged. Do not label this migration rollback. |
| DDL failure/recovery | Simulate only under separate failure-injection approval: stop at first error; preserve partial schema/stage/exception; no automatic retry, stamp, drop or downgrade. Operator chooses reviewed forward completion or a newly authorized empty target. |
| Downgrade refusal | Verify history-preserving RuntimeError offline (already statically checked in Phase 3.1); do not run older destructive downgrade bodies online. Refusal is expected, not successful rollback. |

## Failure handling, backup and development approval

No real customer data is needed for the dedicated rehearsal. Protect even synthetic artifacts and keep integration secrets out. Before meaningful committed isolated stages, record schema/version/fixture baseline and retain reviewed recovery instructions; any dump/export/restore is separate approval, not silently part of this task. A fresh empty schema is not a backup of development. No backup or restore was created/performed here.

MySQL DDL may implicitly commit; rolling back a transaction cannot restore a partially applied chain. If any permission, CHECK, FK, collation, space or lock error occurs, stop; preserve safe error evidence and inspect partial state read-only. Do not retry CREATE TABLE against existing partial tables, disable checks, rewrite balances, stamp forward or invoke a destructive downgrade. Retain failed schema for investigation; cleanup/new-target creation needs explicit authorization and DBA action. No DROP privilege is required for the normal plan and none is requested.

Before changing lankapex_db later: obtain separate explicit approval naming that database and revisions; freshly verify live revision/schema/data preconditions; establish verified encrypted backup and independently tested restore path, maintenance/lock budget, application compatibility, recovery decision and custody. Confirm successful isolated rehearsal first. Nothing here authorizes a development migration or modifications to lankapex_test_db.

## Safe next action and authorization boundary

Safe now: inspect the documents/SQL template, rerun the existing database-free validator, and have an authorized DBA perform metadata/grant review privately. **No automatic database action follows this report.**

Next blocking action: DBA must confirm whether the preferred target exists, create it only if absent under separate approval, and grant the reviewed exact-schema access. After access/emptiness are confirmed and a standalone execution harness is reviewed, request **explicit authorization for migration execution and synthetic rehearsal solely in lankapex_migration_verify_20261107**. Do not request or send a MySQL administrator password. Until those gates are met, isolated migration execution verification remains **BLOCKED, NOT PASSED**.
