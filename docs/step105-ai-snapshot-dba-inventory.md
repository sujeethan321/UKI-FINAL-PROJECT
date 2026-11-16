# Step 105 — Read-only AI snapshot database inventory

Status: **prepared, not executed**. The inventory reads MySQL metadata only. It does not create schemas or accounts, grant privileges, migrate, read application rows, create credentials, or contact GroqCloud.

The reviewed script is `backend/scripts/inventory_ai_snapshot_dba.sql`. It checks:

- exact schema `lankapex_ai_snapshot_test_db`;
- exact accounts `lankapex_ai_snap_runtime@localhost` and `lankapex_ai_snap_migrator@localhost`;
- former rejected names `lankapex_ai_snapshot_test_runtime` and `lankapex_ai_snapshot_test_migrator`, which always block continuation if unexpectedly present;
- tables/views, routines, events, and triggers in the exact schema if it exists;
- similarly named schemas and accounts as separate results;
- database, global dynamic, role, table, and column grant metadata for either exact account;
- whether the DBA session has `SHOW DATABASES` or global `SELECT` metadata visibility.

It never selects `authentication_string`, password hashes, credentials, application records, or protected database data. Exact equality establishes target identity; escaped `LIKE` expressions are used only to report additional similarly named objects.

## Operator command

Use an existing, administrator-managed MySQL Login Path with complete metadata visibility. `lankapex-dba` below is the reviewed example name; select the authorized local DBA Login Path configured by the operator. The command does not place a password on the command line:

```powershell
Get-Content -LiteralPath .\backend\scripts\inventory_ai_snapshot_dba.sql -Raw |
  & mysql.exe --login-path=lankapex-dba --batch --raw
```

Alternatively, open the SQL file in MySQL Workbench under the authorized DBA connection and execute the complete file once. Do not paste credentials into the worksheet or transcript.

Expected absent-state final row:

```text
PASS_EXACT_TARGET_AND_ACCOUNTS_ABSENT
```

Any MySQL access-denied or missing-table error, `STOP_METADATA_VISIBILITY_UNPROVEN`, `STOP_EXISTING_OR_SIMILAR_OBJECT_REQUIRES_REVIEW`, former-name row, similarly named object row, or grant row is a STOP. The already-created empty target database also makes the general absent-state result STOP by design; its Step 107 partial-state continuation requires a separate review of exact emptiness and all four account identities. Preserve sanitized metadata output. A zero count from an account without complete metadata visibility is not proof of absence.

Provisioning remains separately blocked until an authorized DBA has reviewed this output and explicitly authorizes schema/account creation and grants. DPAPI credential creation, migration, and integration-test execution each remain separate operations.
