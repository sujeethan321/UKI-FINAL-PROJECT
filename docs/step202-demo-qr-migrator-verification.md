# Step 202: Dedicated demo QR migrator verification

Source preparation only. No live verification, secret access, provisioning,
grants, migration, backup, or private evidence operation was performed.

## Reviewed sources and privileges

Reviewed Step 201 upgrade_populated_demo_qr.py/.ps1,
demo_qr_migration_guard.py, check_demo_qr_private_path.ps1, the QR migration
7b9e4d2c8a15_customer_qr_join.py, Step 201 runbook, and the older
upgrade_populated_demo_invitation.py convention. The old migrator's DELETE and
superset privilege policy is not suitable for this operation.

The exact account is lankapex_demo_qr_migrator@localhost (25-character username).
The exact schema is lankapex_demo_db at localhost:3306. The required allowlist is
SELECT, INSERT, UPDATE, CREATE, ALTER, INDEX, REFERENCES, scoped to
`lankapex\_demo\_db`.* with every underscore escaped.

SELECT supports duplicate/preservation checks; CREATE creates the two QR tables;
ALTER/INDEX add the profile uniqueness constraint and request index; REFERENCES
supports foreign keys. UPDATE updates the existing Alembic revision row. INSERT
is retained as the reviewed Alembic bookkeeping allowance; this specific
already-versioned one-revision transition normally updates the version row.
No application row inserts are planned. DELETE, DROP, GRANT OPTION, global
privileges beyond USAGE, roles, proxy/dynamic privileges and object-level grants
are unnecessary and rejected. No permissions on other schemas are accepted.

## Offline command (no prompts, connection, or private-file access)

From the project root:

```powershell
& .\backend\.venv\Scripts\python.exe -I .\backend\scripts\verify_demo_qr_migrator.py
```

Expected: PASS: offline account verification preparation; no credentials or database accessed

## Future separately authorized DBA metadata verification

Use an existing authorized DBA account with metadata visibility. Replace only
AUTHORIZED_DBA_USERNAME below with its login name. The hidden interactive prompt
accepts its existing password; never put passwords in arguments, environment
variables, chat, clipboard, files, or output. No DPAPI file is opened by this tool.

```powershell
& .\backend\.venv\Scripts\python.exe -I .\backend\scripts\verify_demo_qr_migrator.py --execute --confirm-target lankapex_demo_db --mode dba-metadata --dba-user AUTHORIZED_DBA_USERNAME
```

This connection selects no default schema. It reads only exact-account metadata
from mysql.user (Host/account_locked only), role_edges, default_roles,
global_grants, proxies_priv, SHOW GRANTS for the exact target account, and exact
schema existence metadata. mysql.user access must succeed before account absence
can be reported. It does not inspect password hashes/authentication strings or
application data. A read-only transaction is used; privilege DDL must remain
paused because MySQL grant metadata is not a historical transactional snapshot.
The DBA session itself must have no active or mandatory roles; if authorized DBA
access requires roles, STOP and separately review an appropriate metadata method.
Do not change roles or permissions automatically to make this tool pass.

MySQL 8.0 and partial_revokes=OFF are required, matching the migration guard.
SHOW GRANTS is parsed using an exact recipient, escaped schema scope and exact
privilege set. Object-level, global, role, grant-option or unfamiliar grant
forms fail closed. Metadata permission failures never mean "account absent".

## Optional separate credential-based verification

Only if the operator already has the existing migrator password available for
secure hidden entry:

```powershell
& .\backend\.venv\Scripts\python.exe -I .\backend\scripts\verify_demo_qr_migrator.py --execute --confirm-target lankapex_demo_db --mode credential
```

This connects explicitly to the exact schema and verifies DATABASE(),
CURRENT_USER(), login username, server port, roles, grant semantics and SHOW
GRANTS. It does not establish complete inactive-role/proxy metadata absence;
require the DBA metadata check as well. A 1045 response reports
authentication_rejected_existence_unknown, never "account missing".

If only the protected DPAPI credential is available, do not print or export it
to feed the prompt. This new tool does not implement DPAPI transfer. Use the
existing separately authorized Step 201 wrapper for that later stage, after all
of its evidence prerequisites exist. Step 208 now resolves its credential to
<verified operator profile>/AppData/Local/LankaPex/PrivateDemoQr/demo-qr-migrator.dpapi
through the shared storage helper. The old repository credential location is
not accepted for QR provisioning or migration. Strict operator/SYSTEM ACLs,
ownership, ancestor integrity and no-reparse checks apply. See the Step 207/208
storage runbook. The directory has not been created; preparation and credential
creation need separate authorization. Existing runtime/JWT paths are unchanged.
Credential-file absence or decryption unavailability is not proof of missing
MySQL account. No credential existence check was performed in Step 202.

Successful live modes print only:
PASS: exact QR migrator account and schema-scoped privileges; read-only check complete

Failures print STOP: QR migrator verification category=<fixed category> and exit
nonzero. Categories distinguish account_missing, credential_unavailable,
insufficient_privileges, excessive_privileges, wrong_database_scope,
wrong_account_identity, conflicting_account_identity, active_or_mandatory_roles,
unexpected_effective_privileges and metadata_or_connection_unavailable.
No raw grants, credentials, identities from the server or exception text are
printed. No retry, reset or repair is attempted. Teardown requests rollback and
close. Python strings cannot provide guaranteed memory zeroization: run in a
dedicated short-lived operator console without tracing or debugging.

## Provisioning plan only; not implemented

If authoritative metadata confirms absence, separately authorize creation of
only the exact localhost account with a fresh private password and the seven
exact-schema privileges. Verify global USAGE only and escaped schema scope;
then separately authorize CurrentUser DPAPI storage at the Step 201 path with
exclusive creation and strict private ACLs. If the account exists with missing,
extra, conflicting or role-derived permissions, STOP for separate DBA review;
do not recreate it or automatically revoke/grant anything. Preserve the DML-only
lankapex_demo_app account unchanged. No CREATE USER/GRANT commands are included
in this verifier. Account verification is not migration authorization: backup
recoverability, isolated rehearsal, writer/DDL pause and preservation proofs
remain mandatory under Step 201.
