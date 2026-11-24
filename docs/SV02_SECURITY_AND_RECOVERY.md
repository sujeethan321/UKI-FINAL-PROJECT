# SV-02 security remediation and recovery procedure

Offline preparation only. The writer/DDL freeze remains ACTIVE. No backup,
restore, migration, credential rotation or feature activation was performed.
This procedure is separately versioned; Steps 391/400 and their historical
checkpoints must remain unchanged.

## Operator prerequisites

1. Revoke the exposed Groq credential in the provider console and replace it
   through approved backend secret configuration. Do not paste the replacement
   into chat, source, screenshots or command arguments. Revocation is NOT VERIFIED.
2. Keep Driver Finance, Support, Customer Address Book, Address Checkout and AI
   disabled. Their default flags remain false. A source revision is not evidence
   of the live database revision or trigger enforcement.
3. Obtain separate authorization before each database-changing recovery/rehearsal
   stage. Do not reuse historical backup waivers or assume the maintenance freeze
   has been released. Preserve partial state on every failure; no retry or cleanup.

## New trigger-aware recovery contract

The offline helper never connects to a database or executes a backup/restore:

```powershell
.\backend\.venv\Scripts\python.exe -B backend\scripts\security_recovery_plan.py --source lankapex_viva_db --observed-revision d15a8c902e64 --scratch lankapex_sv02_restore_20261123t000000z_1234abcd
```

The revision and new scratch name above are planning examples. Replace the
revision with the independently observed value. Never assume source head is
deployed. Reviewed inventories are: ae2b7c5f1d48 = 35 tables/0 triggers;
bf38d2a90176 = 40/10; c04d9e7a6201 = 44/16; d15a8c902e64 = 45/18.
Counts include alembic_version. Other revisions STOP for review.

An authorized DBA must capture a complete private inventory containing database,
host, port, server_uuid, revision, object_inventory_complete, and a tables map.
Each table records row_count, content_sha256, schema_sha256, columns, primary_key,
indexes, foreign_keys and checks. Also inventory views, routines, events and
triggers. Trigger entries require name, table, timing, event, orientation,
statement and definer. Preserve SHOW CREATE statements, SQL mode, character sets,
collations, CHECK ENFORCED status, trigger creation context and effective grants
in the full private evidence. Hashes must come from the same reviewed stable-row
serialization and complete schema capture before and after the operation.

Current source defines no views/routines/events. Their unexpected presence blocks
this contract until individually reviewed, including source-qualified references,
SQL SECURITY, DEFINER and scheduled execution risks. Do not silently omit them.

Validate a separately approved inventory without writing evidence:

```powershell
$inventory=Read-Host 'Private DBA inventory JSON path'
$approved=Read-Host 'Independently approved inventory SHA-256'
.\backend\.venv\Scripts\python.exe -B backend\scripts\security_recovery_plan.py --source lankapex_viva_db --observed-revision d15a8c902e64 --scratch lankapex_sv02_restore_20261123t000000z_1234abcd --inventory $inventory --approved-inventory-sha256 $approved
if($LASTEXITCODE -ne 0){throw 'STOP: preserve evidence; no retry'}
```

A syntactically valid inventory is not proof of its provenance, a writer freeze,
valid grants, or restore success. The helper is an offline contract, not an
execution authorization or replacement for a current DBA gate.

## Backup stage — NOT EXECUTED

Immediately beforehand an authorized DBA must independently verify exact
127.0.0.1:3306/lankapex_viva_db identity, server UUID, current Alembic revision,
table/trigger inventories, storage capacity and effective backup privileges.
Use fresh visibility into performance_schema.threads (TYPE foreground versus
background), current statements, information_schema.innodb_trx, data_locks,
metadata_locks, scheduled events and replication appliers. Explain every other
client, even idle ones; keep application/operator writers and DDL paused for
baseline capture, dump and post-capture. Observe background event writers
separately. No service changes are authorized by this document.

After separate execution authorization, create one NEW timestamp/GUID directory
outside the repository/public directories. Verify no existing target, symlink or
reparse ancestor. Set protected owner/operator and SYSTEM FullControl inheritance
only, verify exact SIDs/rules and empty contents. Use the reviewed Step 400 ACL
policy as a reference, not its obsolete dump/33-table verifier. Reserve an
exclusive attempt marker; create outputs exclusively and never overwrite.

The future native dump command is below. `$dump` must be a new path in that
verified private directory. The account name is operator supplied and its grants
must cover the complete observed inventory; do not elevate the application account.
The native client prompts privately for the password; never put it in an argument.

```powershell
$backupUser=Read-Host 'Reviewed backup account name (not password)'
& 'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe' --no-defaults `
  --protocol=TCP --host=127.0.0.1 --port=3306 --user=$backupUser --password `
  --ssl-mode=REQUIRED --tls-version=TLSv1.2,TLSv1.3 --default-character-set=utf8mb4 `
  --single-transaction --quick --hex-blob --order-by-primary --set-gtid-purged=OFF `
  --no-tablespaces --column-statistics=0 --triggers --routines --events `
  --skip-add-drop-table --skip-add-locks --skip-disable-keys --skip-lock-tables `
  --result-file=$dump lankapex_viva_db
if($LASTEXITCODE -ne 0){throw 'STOP: preserve incomplete dump; no retry'}
$hash=(Get-FileHash -LiteralPath $dump -Algorithm SHA256).Hash
```

Do not use --databases, --skip-triggers or historical revision/table assumptions.
Verify nonempty complete output, complete object inventory, trigger bodies and
DEFINER dependencies, checksum readback and unchanged pre/post source row/content/
schema fingerprints. Write a new exclusive manifest only under separate backup
authorization. Recheck all resulting file ACLs, including the final result file.
An InnoDB snapshot alone does not protect against concurrent DDL or nontransactional
tables: stop for any non-InnoDB data table or unexplained writer.

## Isolated restore and protection rehearsal — NOT EXECUTED

Require separate provisioning authorization for one absent, distinct scratch name
accepted by the helper and a new scratch-only account. Escape underscores in
schema grant patterns. Inspect global, schema, table, role/default-role and
mandatory/inherited grants; verify source/development/test/recovery denial.
Never grant global privileges to the runtime account to accommodate DEFINERs.
Review trigger DEFINER dependencies before import; use a separately approved
isolated MySQL instance if same-server definer handling cannot remain scratch-only.

Before a separately authorized single restore, recheck checksum/ACL/manifest,
empty scratch objects, exact account/database identity, TLS and source fingerprints.
Review dump SQL with a reviewed SQL-aware inspection; reject database selection,
database creation, cross-schema writes and unreviewed stored-program behavior.
Do not rely on --one-database or a filename as isolation. Do not strip protection
triggers or silently rewrite DEFINER clauses.

Reuse the corrected shell-free subprocess pattern: Python Popen with an argument
list, shell=False, mysql.exe absolute path, --no-defaults, TCP 127.0.0.1, TLS
REQUIRED, the dedicated scratch user, --password (interactive native prompt) and
--database=<exact approved scratch>. Feed the binary dump file as stdin. Never
use cmd.exe, string-built shell commands, password arguments, MYSQL_PWD or a
credential-bearing temporary option file. Reserve one distinct exclusive marker;
nonzero exit or interruption preserves all state and requires a new decision.

Compare all restored rows/counts/content hashes and schema objects with the
approved dump baseline. Keep exact DDL hash differences visible; accept only
separately proven strict semantic equivalence with effective metadata checks.
Compare columns/defaults/types, keys, indexes, relationships, enforced CHECKs,
trigger timing/event/body/DEFINER, views/routines/events and Alembic revision.
Recheck foreign-key orphans and original source preservation. Partial DDL/object
sets or missing triggers FAIL; never reset, downgrade, drop or auto-retry.

Using fictional isolated fixtures only, independently test restricted runtime
UPDATE/DELETE denial on every protected financial, support and destination table.
Ensure a real matching fictional row is targeted (zero-row updates do not test
row triggers). Verify SQLSTATE 45000 and unchanged rows; test runtime cannot
disable/drop protection objects. This mutation rehearsal needs separate approval.
Recovery remains UNVERIFIED until isolated comparison and protection tests pass.

## Operational security gates

The repository has no complete shared ingress rate-limit policy. External mode
now retains a process-local backstop, but shared enforcement is UNVERIFIED.
Before release verify trusted-proxy identity, direct-origin denial, spoofed
forwarding headers, anonymous/authenticated per-IP/user limits, multipart size,
total/idle timeouts and slow/chunked traffic at ingress. Compare limits across
workers/replicas and restarts, including failure behavior.

AI's existing concurrency/attempt limits are process-local. A shared atomic quota
needs reserve-before-call, user/business and provider-wide budgets, expiring
in-flight reservations, bounded TTLs and fail-closed unavailable-store behavior.
No shared service is invented here. An alternative requires explicit approval of
one process AND one replica, no autoscaling, a reviewed provider budget and
monitoring; local limits still are not a provider-wide quota. Keep AI disabled.

CHECK readiness now compares reviewed expression structure and MySQL ENFORCED
metadata/session integrity settings. Independent DBA trigger/grant attestation
and exact revision checks still apply. Real MySQL reflection, resource protection,
deadlock/concurrency and trigger behavior require isolated rehearsal.

## Reproducible tests and packaging

Security test Python/JS source is eligible for Git; generated artifacts, .env,
credentials and private evidence remain excluded. Review files before staging;
do not archive the whole workstation tree. .gitattributes excludes private/local
artifacts from git archive and retains sanitized .env.example templates. No
commit, archive, push or deployment is performed by this step.

Use offline_tests entry points; ordinary backend/tests/conftest.py connects MySQL
and must not be used during the freeze. The historical *_migration_readiness.py
operator suites and backend/ai_snapshot_integration depend on local reviewed
output fixtures and intentionally are not the clean-checkout acceptance baseline.
Run source-only suites and frontend node tests from the reviewed checkout with
its locked dependencies. Never package dumps or customer/document fixtures.

## Completed offline verification

391 backend checks passed: 260 unittest checks across 18 offline suites plus 131
mocked AI pytest checks with --noconftest. This includes the 20 focused remediation
checks and 6 pure recovery-contract checks. The subscription suite's stale source
head/count assertion was updated from ae2b7c5f1d48/19 to d15a8c902e64/22, retaining
the original predecessor assertions and adding all three prepared successors.
No migration was executed. The final complete subscription suite passed 17/17.

Frontend: 1,103 tests passed; ESLint passed; production build passed with the
existing large-chunk warning. Build used a process-only fictional HTTPS API URL.
Python compilation passed for 15 changed/new Python files. Static migration graph:
22 revisions, one chain, sole source head d15a8c902e64. Live revision NOT VERIFIED.

Covered suites: security_remediation, security_recovery_plan, driver_registration,
driver_documents, admin_driver_documents, support, customer_address,
address_checkout, driver_finance_integrity, reports, admin_reports, profile,
package_entitlements, secure_ai, subscription, aging, dashboard_due and billing;
plus run_ai_unit_tests. No real provider or database credentials were used.

Files changed for this step (pre-existing working-tree changes were preserved):

- .gitignore and .gitattributes: reviewable test source, private release exclusions.
- backend/app/core/config.py, http_security.py, rate_limit.py and request_limits.py:
  general body deadline and local rate-limit backstop in external mode.
- backend/app/services/driver_document_storage.py and driver_vehicle_service.py:
  request-owned candidate cleanup after proven pre-commit rollback only.
- backend/app/services/support_service.py: ascending participating User locks.
- backend/app/services/schema_integrity.py, driver_finance_rollout.py,
  support_rollout.py and customer_address_rollout.py: reviewed CHECK definition
  and MySQL enforcement validation; no new runtime privileges.
- backend/scripts/security_recovery_plan.py: offline-only inventory/target contract.
- backend/offline_tests/security_remediation_suite.py,
  security_recovery_plan_suite.py and subscription_suite.py: regression coverage.
- docs/SV02_SECURITY_AND_RECOVERY.md: this procedure and verification record.

No frontend source, migration, historical checkpoint or actual private-storage
file was changed by this step. Secret configuration is backend-only, redacted
Settings/adapter behavior passed the mocked tests, and no frontend source contains
the Groq key setting or key prefix. Private .env files are not tracked; their
values were not read. Credential revocation remains an operator responsibility.

Remaining release blockers: operator credential revocation/replacement; current
DBA identity/revision/grant/trigger attestation; a separately authorized complete
trigger-aware backup/isolated restore and restricted-runtime protection rehearsal;
real MySQL lock/concurrency/reflection checks; verified shared ingress limits and
global AI quota (or explicitly approved restricted single-process/replica mode).
Optional feature gates remain false by default and were not enabled. The current
process/deployed flags were not inspected or changed. The maintenance freeze
remains active.
