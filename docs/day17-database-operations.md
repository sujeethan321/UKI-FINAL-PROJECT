# Day 17 Step 17.2 — Database operations and recovery runbook

Scope: local preparation. No production connection, live backup, restore, scheduled
task, cloud change, destructive migration, balance repair or deployment is authorized
by this guide. AI remains deferred. Use the existing
[configuration guide](day17-production-configuration.md) for backend secrets/TLS.

## Migration execution verification: BLOCKED

Current access recheck and execution guidance: [Phase 3.2 isolated migration
plan](phase32-isolated-migration-verification-plan.md) and its
[DBA review SQL](sql/phase32-isolated-migration-dba-review.sql.example) supersede the old
setup/test commands below. On 2026-11-08 the preferred target still returned
MySQL 1044; its existence is unconfirmed because this account cannot see it.
The graph now has 14 revisions/head 14c0d3e2f782 and 25 modeled tables. Do not
run the old pytest rehearsal command: it connects to lankapex_test_db during
session startup and includes stale 20-table/head assertions. No such test was run.

MySQL rejected CREATE DATABASE for the configured application account (error 1044).
The isolated verification schema was not created. Offline SQL generation and
ordinary regression results are not evidence of a successful online migration.

The user explicitly instructed that this remain a documented blocker. Do not
retry database creation with elevated privileges, request or expose a MySQL
administrator password, or modify lankapex_db or lankapex_test_db to work around
the failure. Continue only checks that do not mutate either existing database.
AI Summary integration remains deferred.

Required DBA action: independently create the designated isolated empty schema
and grant the existing test connection account schema-scoped verification access,
using the template below. Full migration verification remains incomplete until
creation, actual target identity, access and emptiness are confirmed and the
guarded migration execution/schema comparison succeeds. This DBA action has not
been performed or verified by the agent; no elevated retry is authorized.

## Verified architecture and identities

- Established backend settings: APP_ENV, MYSQL_HOST/PORT/USER/PASSWORD/DATABASE,
  optional MYSQL_SSL_CA. SQLAlchemy URL.create, PyMySQL, pool pre-ping/recycle,
  parameter hiding and session closure remain in place.
- Local server, mysql and mysqldump: **MySQL 8.0.46**.
- Development: `lankapex_db`, revision `b8c4d7e6f126`; five newer tables absent.
- Automated tests: `lankapex_test_db`, revision `03b9c2d1e671`; all 20 model tables
  plus alembic_version present, inspected engines all InnoDB; metadata comparison
  reports no drift. Recheck engine types before every backup of another source.
- Production credentials, endpoint, account, version and storage are unknown;
  no production connection was attempted. No database backup or CI workflow existed.
- No separate CreditSale/Repayment/balance/statement tables: authoritative records
  are ledger_entries with credit_sale, repayment and reversal types; statements
  and outstanding amounts derive from that ledger.

## Identity and privilege gates

New maintenance tools require explicit development/testing mode and an exact
database identity, verified against engine.url and SELECT DATABASE(). Hostname
alone establishes no safety. Production and wildcard/empty/ambiguous names are
rejected by local maintenance guards.

New isolated names must match `lankapex_migration_verify_<8–32 lowercase letters/digits>`
or `lankapex_restore_verify_<8–32 lowercase letters/digits>` and use testing mode.
Existing development/test databases never qualify as restore or clean-migration
targets. The tools do not create, drop, truncate or restore databases.

The user approved creation of `lankapex_migration_verify_20261107`, but MySQL denied
CREATE DATABASE for the configured application account. No schema was created.
An authorized local DBA must create that **new** schema and provide only its
schema-scoped migration/test permissions to the existing test connection account.
Do not expand the ordinary application's production privileges.

DBA-only setup template: use the narrower, reviewed and deliberately commented
[Phase 3.2 SQL instructions](sql/phase32-isolated-migration-dba-review.sql.example).
They replace the earlier ALL PRIVILEGES example with purpose-specific privileges
and escaped underscores for exact database-level grant scope. Nothing was executed.

The account/host placeholders must identify an already existing approved local
account. Do not create a new password or share DBA credentials in chat. Verify
schema absence first; do not use IF NOT EXISTS to silently reuse unknown data.
The scoped grant is for the disposable verification schema only; it is not the
recommended privilege set for a production application or backup account.

## Migration procedure

1. Review branch/worktree and the complete revision graph. Current 13-revision
   chain has one base/head and no missing parent or branch conflict:
   79d8d51548c6 → b2a1c4d6e8f0 → c3d9e2f1a601 → d4e0f3a2b702 → e5f1a4b3c803
   → f6a2b5c4d904 → a7b3c6d5e015 → b8c4d7e6f126 → c9d5e8f7a237 → d0e6f9a8b348
   → e1f7a0b9c459 → f2a8b1c0d560 → 03b9c2d1e671.
2. Require a verified recent encrypted backup plus a proven restore path before a
   real-data migration. Confirm source identity, schema revision and maintenance
   window; freeze schema changes during a dump. Review SQL and data preconditions.
3. From backend with the selected local environment, inspect using the project's
   `python -m alembic heads`, `history`, `current` and `check` conventions. Offline
   `python -m alembic upgrade head --sql` emits SQL without connecting; protect any
   output outside source/public directories. Never stamp over schema drift.
4. Run clean upgrade only on an approved existing empty verification schema.
   From the project root in PowerShell, after DBA setup:

```powershell
$env:APP_ENV = 'testing'
$env:MYSQL_DATABASE = 'lankapex_test_db'
$env:PYTHONPATH = (Join-Path (Get-Location) 'backend')
$env:LANKAPEX_MIGRATION_VERIFY_DATABASE = 'lankapex_migration_verify_20261107'
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_database_operations.py::test_clean_isolated_upgrade_when_operator_provides_empty_target -q
```

The opt-in test verifies identity and emptiness, upgrades base → development's
older revision → head using Alembic, and compares against full registered metadata.
It leaves the schema in place for inspection; it never resets it for repeat runs.
Remove the opt-in variable for ordinary regression runs. Repeating clean validation
requires a newly approved empty schema, not dropping existing records.

5. Review nullable/new columns, constraints, lock duration, free space and MySQL
   DDL implicit commits. If failure occurs, stop writes and inspect actual schema
   and revision; do not assume transaction rollback undid DDL. Prefer a reviewed
   forward fix. Newer revisions explicitly refuse destructive downgrades.
6. Production application/migration credentials must be separate, verified TLS
   required, and migration execution manually reviewed. This task did not migrate
   development or production. Representative populated legacy upgrade remains
   unverified; offline SQL generation does not replace live upgrade verification.

Alembic's supplied-connection test hook accepts only guarded migration verification
names in testing mode. Normal engine routing remains unchanged. Alembic logging
now preserves existing application loggers instead of disabling them during
programmatic/offline checks.

## Read-only integrity and financial reconciliation

From the root, explicitly set APP_ENV, MYSQL_DATABASE and PYTHONPATH as above,
then run:

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/inspect_database_integrity.py --environment testing --database lankapex_test_db
```

For authorized read-only development inspection, select development and lankapex_db
in **both** process variables and flags. The script starts a consistent READ ONLY
transaction. Missing schema elements are reported before querying unavailable
tables; an incomplete schema cannot receive a clean integrity result.

Checks include every registered FK/unique key, customer/account business ownership,
credit-sale type/account/amount/order reciprocity, inappropriate order-linked debt,
order/delivery business links, product/order business, historical item totals,
reversal account/type/amount consistency and Admin actor role. Results are counts,
not private rows. Review flagged records through a separately authorized process;
never auto-delete, reprice or repair financial records.

The existing account_balances/effective_entries rules are reused: reversed original
sales/repayments are excluded, effective sales increase and repayments reduce
the ledger balance using Decimal. Ledger/balance SHA-256 fingerprints and table
counts allow comparison with a source baseline. No alternative balance formula
or stored financial amount is introduced. There is no persisted balance to
"repair". Snapshot prices and rounding remain unchanged.

For an authorized restored schema, keep APP_ENV=testing and MYSQL_DATABASE set to
lankapex_test_db, then use the explicit isolated target flag:

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/inspect_database_integrity.py --environment testing --purpose restore --database <designated-restore-database>
```

This remains read-only and never performs a restore. Inspect restores using the
CLI/database layer, not a production HTTP server. Production Settings isolation
and pytest's normal database gate are never disabled to run the application
against a recovered copy. A full restored-application smoke test needs separately
reviewed test-mode configuration and is not claimed here.

## Backup plan: creation is distinct from validation

No live backup was started. `app.services.backup_manifest.backup_command` constructs
an argument list for the installed mysqldump; it does not execute it. Use one exact
source database, never --all-databases/--databases. Options include
--single-transaction, --quick, --skip-lock-tables, --skip-add-drop-table,
--no-tablespaces, --set-gtid-purged=OFF, --column-statistics=0, --hex-blob,
--routines, --events, --triggers, utf8mb4 and --result-file. The last avoids
PowerShell redirection changing dump encoding. GTID exclusion suits this logical
recovery plan; it is not a replication/PITR bootstrap procedure.

For the consistency/privilege implications, consult the
[MySQL 8.0 mysqldump manual](https://dev.mysql.com/doc/refman/8.0/en/mysqldump.html).
Transactional snapshots suit InnoDB; they do not make nontransactional tables
consistent. Freeze DDL during dumps. Basic privileges include SELECT and, where
objects exist, SHOW VIEW/TRIGGER; stored routines/events need separately reviewed
definition/export privileges. --no-tablespaces avoids the PROCESS requirement.
Confirm exact requirements with the DBA rather than granting global privileges
to the application account. Use an isolated backup identity.

Inspect source version, engines, stored objects/definers and available disk first.
The plan refuses a nontransactional source until a reviewed consistency method
exists. If exact baseline counts/fingerprints must match the dump, quiesce writes
and DDL while collecting baseline and dump: two independently started snapshots
do not necessarily contain the same data. Hot backup without that coordination
must not compare its counts to an unrelated later live state.

Keep connection credentials in a private option file outside the repository,
readable only by the operator/service identity; --defaults-file must be first.
Use verified TLS (VERIFY_IDENTITY with the actual provider CA where required).
Do not put passwords in command arguments, shell history, logs or frontend vars.
Confirm option-file ACLs and private encrypted storage before invoking any dump.

Check the dump process exit status and errors. Mark a failed/partial dump invalid.
Record UTC creation time, source/environment, exact MySQL version, Alembic revision,
byte size and SHA-256. Protect manifests as private operational information.
The validator accepts this reviewed **8.0.x** format; another major/minor version
requires compatibility review and updated tests, not a blind version-string edit.

Manifest keys: format_version=1, format=mysql-logical-sql, created_at (timezone-aware),
source_environment, source_database, mysql_version, schema_revision, sha256,
size_bytes. No arbitrary extra fields or credentials. Validation requires an
existing readable nonempty dump, MySQL header, sensible timestamp, known field
formats and matching size/hash. It does not execute SQL, authenticate provenance,
prove encryption or prove restoration. Store provenance/signature verification
through the selected secure storage workflow, not a checksum alone.

## Encryption, storage, retention and monitoring

Planning proposal, not an enabled schedule or a verified hosting capability:

| Item | Initial proposal requiring owner approval |
| --- | --- |
| Frequency | Hourly logical recovery points, plus a pre-migration backup |
| Retention | 24 hourly, 7 daily, 4 weekly, 12 monthly copies |
| RPO | At most 1 hour of data loss, **planning target only** |
| RTO | Restore service within 4 hours, **planning target only**, to be measured |
| Offsite | Encrypted copy in a separate failure domain/account with restricted access |
| Restore rehearsal | Monthly and after material schema/MySQL changes |
| Failure alert | Failed creation/checksum/restore or missing expected backup; backup age over 90 minutes as an initial alert threshold |

Approve cost, privacy, business/legal retention and recovery targets before
scheduling. Never prune the only verified recovery point. Cleanup should act on
approved manifest identifiers in one private backup directory after replacement
verification; no wildcard database/path deletion routine was added.

Protect plaintext staging on an access-controlled encrypted volume; encrypt the
artifact before offsite transfer with an approved authenticated encryption/KMS
workflow and keys outside the backup store. Record both encrypted-container and
decrypted-payload checksums where relevant. Do not label data encrypted because a
filename ends in .enc. Verify decryption during rehearsals. Local backups share
machine-loss risk; managed backups require verified retention/exportability,
permissions, encryption and restore tests. Repository .gitignore excludes common
dump formats and backups directories; this is defense in depth, not encryption.
Never store dumps under frontend/public/dist or serve them from the web host.

Monitor connectivity/pool exhaustion, storage headroom, slow queries, schema
revision, backup age/exit status/hash/provenance and restore-rehearsal history.
Existing health endpoints expose no records or credentials. No external monitoring,
scheduler, messages or cloud upload was configured.

## Restore rehearsal and failure recovery

1. Use a trusted approved backup, its private manifest and recorded restore history.
   Authenticate provenance, verify encrypted-container checksum, decrypt privately,
   then validate plaintext metadata/checksum. Stop on any mismatch.
2. Verify matching source/target MySQL support, SQL mode, charset/collation,
   time-zone handling and stored-object definers. A checksum is not SQL safety.
3. Obtain explicit creation authorization for a new isolated restore schema. Never
   reuse lankapex_db, lankapex_test_db or a production schema. Verify actual
   identity and emptiness before loading anything.
4. Inspect SQL for USE/CREATE DATABASE, cross-schema statements, definers, users,
   grants and unexpected executable content. Use a restore account confined to
   the isolated schema; --database alone does not confine arbitrary SQL. Do not
   use a privileged DBA account to import an untrusted dump. Keep events/side
   effects disabled and external integrations disconnected in the rehearsal.
5. `restore_command` builds mysql with a private defaults file, binary mode,
   utf8mb4 and the exact designated target. It does not open/read/import a dump.
   An approved operator would stream the validated SQL through stdin with no
   shell concatenation, no --force, and inspect exit status. Do not run it simply
   because the plan exists.
6. Compare restored schema/revision, constraints, table counts and exact financial
   fingerprints against the baseline from the same backup snapshot. Run all
   relational/domain checks and established ledger/statement/idempotency tests.
   Verify cash/credit snapshots, reversals and delivery isolation. Test account
   access in a reviewed non-production harness with integrations disabled.
7. Record backup ID, check results, target identity, versions, start/end UTC,
   measured RPO/RTO, operator and cleanup approval. Mark **restore verified** only
   after all checks, including application connectivity, succeed. No live-data
   restore or full restored-application smoke test was performed here.
8. During an incident: pause affected writes, preserve evidence/artifacts, identify
   the last verified recovery point, restore into a separate target, reconcile,
   obtain cutover approval, then switch reviewed connection settings. Maintain a
   rollback decision and avoid dual writers. Do not overwrite the damaged source
   or run a destructive downgrade in an attempt to recover.

## Railway readiness without platform access

No Railway account/service was contacted. Confirm actual service MySQL image and
version, persistent volume and capacity, private/public connectivity, verified TLS,
secret management, backup feature eligibility/schedule/retention/export and restore
permissions in the actual account before relying on them. Private networking
alone does not establish certificate-verified TLS. HA/replication is not a backup;
no particular managed backup or PITR feature is assumed for MySQL. Confirm recovery
dependencies (database, volumes, keys, app config, DNS/ingress, operators) and
separate backup/restore permissions before deployment.
