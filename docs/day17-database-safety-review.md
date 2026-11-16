# Day 17 Step 17.2 — Database safety and recovery review

Date: 2026-11-07. **Overall result: PARTIAL. Migration execution verification: BLOCKED.** Preparation and executed checks pass;
clean online migration/restore verification remain unverified. The user approved
creation of a local migration-validation schema, but the application account lacks
CREATE DATABASE permission. The user then explicitly chose to leave this as a
documented blocker. No schema was created, and no additional privilege attempt
or database creation will be made without further instructions.

## A. Repository audit

Branch main, HEAD d917e4f (Day 14 shopping/credit integration); prior 43 Day 15
files remain staged. Prior Day 16/17.1 edits and unrelated changes were preserved.
No commit/push/staging. Step 17.1 implementation is present: explicit modes,
production validation/TLS/CORS/hosts, sanitized errors and frontend config guards.
Its documented blockers persist: production inputs, existing frontend lint issues,
and unfinished Day 16 reporting; no completion checkpoint exists in Git.

Inspected all 13 Alembic revisions, registration of 20 model tables, database
settings/engine/session, setup/fixture scripts, test guards and deployment docs.
No existing backup/restore tooling or CI workflow was found. Existing browser
fixture scripts delete their specifically created test records and require the
actual test database; they were reviewed, not run for this task. No new DROP,
TRUNCATE, reset or automatic repair routine was introduced.

Database variables remain MYSQL_HOST/PORT/USER/PASSWORD/DATABASE, optional
MYSQL_SSL_CA, and APP_ENV. Local MySQL server/client/dump tool are 8.0.46.
Actual local resources were checked without printing passwords/connection URLs:
development lankapex_db at b8c4d7e6f126, test lankapex_test_db at 03b9c2d1e671.
No production connection settings were supplied or contacted.

## B. Relational integrity

Metadata registers Users, Businesses/Members, CustomerProfiles/CreditAccounts,
LedgerEntries, approval audits, reminders, notifications, communications,
DriverProfiles, delivery requests/assignments/events, categories/products,
Orders/Items and AdminAudits. Stored vehicle fields belong to DriverProfiles.
Statements and balances are derived rather than separate stored financial tables.

Current test schema matches metadata: columns/types, FK/unique/index comparison
shows no drift. A focused physical inspection also confirms expected named CHECK
constraints exist. Generic read-only checks cover all metadata FK and unique
references, including nullable/composite FK semantics. Domain checks cover account
business ownership, order/account/customer identity, reciprocal order credit-sale
references/amount/type, linked debt, order/delivery and product/business links,
historical item totals, reversal consistency and Admin actor role.

The empty test DB had zero detected violations; that empty-state result alone is
not treated as populated-data verification. Synthetic populated order tests also
pass, and an intentionally cross-business account is detected without repair.
Development inspection stops as incomplete: products, product_categories, orders,
order_items and admin_audits are absent. No false clean development report issued.

Design limitations documented rather than silently changed: LedgerEntry.order_id
is an older nullable logical reference without an FK; order.credit_sale_id is a
real FK/unique reference, and the new checker detects orphaned/inconsistent reverse
links. Account/profile business consistency is service-enforced rather than a
composite FK. Admin target IDs are polymorphic, while actors have real FKs.
Consider forward constraint proposals only after auditing existing data, lifecycle
requirements and orphan preconditions. No model/migration rewrite was justified
by a confirmed existing-data violation in this task.

## C. Financial precision and reconciliation

SQL NUMERIC/DECIMAL and Python Decimal are retained. Product/unit prices use
12,2; order totals, item totals, ledger amounts and credit limits use 14,2;
reminder amount snapshots use 24,2. No float calculation or financial formula
change. Existing historical order snapshots/rounding remain untouched.

Authoritative account_balances/effective_entries functions are reused, including
same-account reversals. New reports emit counts and ledger/effective-balance hashes,
not raw financial rows. Synthetic credit approval posts once; repeated delivery
request does not change financial rows; cross-business corruption is detected;
repayment/reversal Decimal reconciliation passes. Full existing financial,
statement, idempotency and delivery regression also passed. No source/restored-copy
comparison or production balance recalculation is claimed.

## D. Alembic history and drift

One base (79d8d51548c6), one head (03b9c2d1e671), 13 connected revisions, no missing
parents/multiple heads. Current test database metadata drift: **zero operations**.
Order/delivery/Admin schema changes have revisions. Development's revision gap is
real and was not hidden with stamp or automatically migrated.

Offline base→head and b8c4d7e6f126→head SQL generation passed. These are SQL-generation
checks, not proof of a clean online upgrade. A guarded opt-in test is prepared to
upgrade an existing approved empty schema base→older revision→head, then compare
metadata. Its name gate and identity/emptiness checks prohibit reusing development,
normal test or production schemas. MySQL denied the approved CREATE DATABASE
attempt; no online clean or populated legacy upgrade was executed.

Alembic env.py now supports only guarded testing connections for isolated migration
verification. A regression exposed fileConfig disabling existing security logging;
disable_existing_loggers=False fixes that without weakening log sanitization.
No migration revision or business model was changed. MySQL DDL implicit commits
and forward-fix/backup requirements are documented; no destructive downgrade ran.

## E. Backup strategy

[Database operations runbook](day17-database-operations.md) documents the installed
MySQL tooling, InnoDB transactional snapshot policy, DDL freeze, consistent baseline
capture, privileges, private option-file credentials, verified TLS and schema/data/
stored-object coverage. All inspected test tables use InnoDB; another source must
be checked independently. The command planner rejects a nontransactional source.

The plan uses one explicit database and excludes default DROP TABLE statements,
GTID changes and tablespace export. Commands are argument lists and never executed
by the helpers. Documentation references the official
[MySQL 8.0 mysqldump manual](https://dev.mysql.com/doc/refman/8.0/en/mysqldump.html)
for transactional consistency, DDL limitations and privilege review.

Proposal only: hourly recovery points; retain 24 hourly/7 daily/4 weekly/12 monthly;
encrypted offsite copy, monthly/after-schema restore rehearsals; RPO one hour,
RTO four hours as **unverified planning targets**. Require business/privacy/cost
approval, authenticated encryption/private storage/keys, failure and backup-age
alerts, approved retention cleanup. No backup, upload, cleanup or schedule enabled.

## F. Restore plan and actual verification

Restore is separate and explicitly authorized, only into a designated empty
lankapex_restore_verify_* schema, never over either existing database. Validate
provenance, encryption/decryption, source/version/schema metadata, byte size and
SHA-256 before reading trusted SQL. Review cross-schema SQL and definers and use
a schema-confined restore account: a --database flag does not contain arbitrary SQL.

The manifest validator checks readability, nonempty recognized dump header,
timezone-aware/nonfuture timestamps, strict metadata, version/revision formats,
size and checksum; tests detect tampering and malformed metadata without exposing
sentinels. The planner does not perform restoration. A synthetic dump-like file
was used for format/checksum tests only; it is not claimed as a restorable backup.

The runbook separates creation, artifact validation and verified restoration,
including table counts, ledger hashes, established reconciliation, real application
connectivity, isolated integrations and measured recovery time. No safe source
backup or authorized separate restore target was available. No live-data or
synthetic SQL restore was executed. No recovery capability/RPO/RTO is certified.

## G. Railway readiness

Railway skill used for planning only; no platform account/service connection.
Actual image/version, volume persistence, network/TLS, backup feature eligibility,
retention/export, restore privileges, secret/key recovery and service dependencies
must be confirmed in the real account. No particular MySQL backup/PITR feature
is assumed. Replication/HA is not represented as a backup. Production TLS/provider
compatibility remains a Step 17.1 deployment input.

## H. Actual verification results

| Check | Result |
| --- | --- |
| New maintenance suite | 32 passed, 1 skipped |
| Combined maintenance + Step 17.1 security suite | 76 passed, 1 skipped, zero failures |
| Final full backend | **1199 passed, 1 skipped, zero failures**, 205.94 seconds |
| Backend warning | One existing short wrong HMAC key warning in tampered-token test |
| Online clean/legacy migration | **BLOCKED**, not passed: CREATE DATABASE permission denied; opt-in test skipped |
| Offline clean/legacy SQL generation | Passed |
| Physical test schema/CHECK constraints + metadata comparison | Passed, no detected drift |
| Test integrity inspection | Passed; empty-state limitation and synthetic populated tests noted above |
| Development read-only inspection | Correctly reports incomplete schema, not a pass |
| Backup/restore execution | Not run; manifest/command safety tested only |
| Frontend build | Passed, Vite 8.3.5, 2218 modules, test-only API URL; existing large-chunk warning |
| Frontend tests/lint | Not rerun: no frontend/shared client files changed; prior 804-test result and lint debt remain documented in Step 17.1 |
| Python syntax / changed tracked diff whitespace | Passed |
| Known-secret scan | No findings in current source/assets or reachable Git text blobs; never a guarantee against unknown credentials |

The first full regression found one logging failure (1198 passed, 1 failed,
1 skipped); the Alembic logging correction passed both focused and final full
regression. No test assertions were weakened. The skip is an explicit safety gate,
not a fabricated clean-upgrade result. New tests also check target denial,
foreign/unique/model constraints, Decimal precision, financial isolation and
metadata/checksum failures. No browser session or restored-app smoke test claimed.

## I. Files created or modified for this step

- .gitignore — backup artifact exclusions; preserve previous unrelated edits.
- backend/alembic/env.py — guarded isolated migration hook and logging fix.
- backend/app/core/db_maintenance.py — environment/name/identity/emptiness guards.
- backend/app/services/backup_manifest.py — nonexecuting plans and safe artifact validation.
- backend/app/services/database_integrity.py — read-only FK/unique/domain/financial reports.
- backend/scripts/inspect_database_integrity.py — explicit read-only inspection CLI.
- backend/tests/test_database_operations.py — safety/integrity/migration/backup tests.
- docs/day17-database-operations.md — operator and disaster recovery runbook.
- docs/day17-database-safety-review.md — this A–K report.

No dependency/frontend/model/revision change. No development/production mutation,
backup, restore, deployment, new secret, AI feature, commit or push.

## J. Risks and manual decisions

1. Clean online upgrade remains unverified: the approved local schema was not
   created because of MySQL privileges. User chose to document the blocker.
2. Restore execution and restored-application access remain unverified; the RPO/RTO
   and retention proposal need approval and measured rehearsals.
3. Development is behind five table introductions; do not start current workflows
   against it expecting those modules to work before a reviewed backup/migration.
4. Production endpoint, credentials, TLS/CA, persistent storage, backup availability
   and recovery operators remain unknown. No production readiness claim.
5. Existing Day 16 reporting and frontend lint debt persist, outside this database
   preparation scope. Historical shared changes remain uncommitted.
6. Read-only full ledger hashing currently materializes ledger rows in memory;
   scope it to controlled operational sessions and assess capacity on large data.
   It is not exposed as a public health or API endpoint.

## K. Next step

**Step 17.2 is not marked complete.** Step 17.3 API/security/performance work can
proceed locally using the verified test database, carrying the above blockers.
Clean upgrade requires DBA-created empty schema and access; restore certification
requires a separately approved target, trusted backup and measured application
rehearsal. User-directed documentation of the privilege blocker ends further
creation attempts for this task. No unsafe workaround or data reset was used.
