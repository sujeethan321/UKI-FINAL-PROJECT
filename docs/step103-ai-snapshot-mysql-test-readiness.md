# Step 103 — Dedicated MySQL snapshot integration-test readiness

Status: **source ready; live database setup and execution remain blocked**.

Use a new empty schema named `lankapex_ai_snapshot_test_db`. Never reuse
`lankapex_test_db`, whose QR browser fixture and evidence are protected. The
runtime account must be `lankapex_ai_snap_runtime@localhost`, with
global USAGE and exactly SELECT, INSERT, UPDATE and DELETE on the escaped scope
`lankapex\_ai\_snapshot\_test\_db`.*. It receives no DDL or privileges on any
other schema. A separate one-time migrator may receive SELECT, INSERT, UPDATE,
DELETE, CREATE, ALTER, INDEX and REFERENCES on that exact scope while applying
the reviewed 16-revision chain through `7b9e4d2c8a15`; do not grant DROP,
GRANT OPTION or global administrative rights.

DBA-reviewed setup template (enter passwords privately):

```sql
CREATE DATABASE `lankapex_ai_snapshot_test_db`
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'lankapex_ai_snap_runtime'@'localhost' IDENTIFIED BY '<private>';
GRANT SELECT, INSERT, UPDATE, DELETE
  ON `lankapex\_ai\_snapshot\_test\_db`.*
  TO 'lankapex_ai_snap_runtime'@'localhost';
```

Database creation, account creation, grants and migration each require separate
operator/DBA authorization. Use a dedicated exact-target migration runner; do
not run ordinary Alembic commands until that guard has been reviewed. After
migration, require 29 tables, revision `7b9e4d2c8a15`, and zero rows in all 28
application tables.

Store the runtime password with Windows CurrentUser DPAPI at
`.server-logs/private-ai-tests/ai-snapshot-test-runtime.dpapi`. The prepared
launcher is read-only by default:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\run_ai_snapshot_integration_tests.ps1
```

After database provisioning, migration, empty-schema evidence, writer-pause
confirmation and separate test execution authorization, the guarded command is:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\run_ai_snapshot_integration_tests.ps1 -Execute -ConfirmTarget lankapex_ai_snapshot_test_db
```

The preflight verifies environment, configured/engine/actual database and
account, revision, 29-table inventory, emptiness, and exact DML-only grants.
It forces AI disabled and masks the Groq key with an empty process value. Tests
create synthetic users, businesses, profiles, accounts and ledger rows inside
an outer transaction and roll it back. Before/after counts and SQLAlchemy
unit-of-work state verify snapshot assembly itself performs no writes.

Relationships exercised: active Customer `users.user_id` -> linked
`customer_profiles.user_id`; profile `business_id` -> approved business;
`credit_accounts.customer_id` -> profile; creditor business must equal profile
business; `ledger_entries.credit_account_id` -> account; reversal
`reverses_entry_id` -> original entry. Malformed, foreign, missing and inactive
relationships must produce generic 404 responses.
