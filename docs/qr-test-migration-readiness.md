# QR linking — isolated test migration preparation

Status: **prepared, not authorized for execution**. Source revision `6e3f2c1a9b04` to `7b9e4d2c8a15` only. No database or grant was changed while preparing this tooling. `lankapex_db`, `lankapex_demo_db`, rehearsal schemas, and the earlier invitation endpoints remain untouched.

## DDL and privileges

The single revision creates `business_join_links` and `customer_join_requests`, adds an index on the new request table, and adds `uq_customer_profile_business_user` to the existing `customer_profiles` table. It first queries for non-null `(business_id, user_id)` duplicates and aborts if any exist. It has no `DROP`, data backfill, ledger update, credit-account change, or repayment calculation change. MySQL DDL is not transactionally reversible; preserve any partial state after a failure and do not retry, stamp, or downgrade automatically.

The minimum database-scoped privileges for this reviewed runner are **SELECT, INSERT, UPDATE, CREATE, ALTER, INDEX, REFERENCES** on the exact test schema. `SELECT` covers identity/schema/data audits and postchecks, `INSERT`/`UPDATE` cover Alembic's existing version row, and the remaining privileges cover the two tables, foreign keys, index, and unique constraint. Global **USAGE only**. `DROP`, `DELETE`, `GRANT OPTION`, global administrative rights, and privileges on other schemas are neither required nor accepted by the runner.

## Manual DBA setup — separate authorization required

An authorized DBA first checks whether the account already exists and reviews its grants. These are read-only:

```sql
SELECT UTC_TIMESTAMP(6) AS checked_utc, CURRENT_USER() AS checking_account;
SELECT User, Host FROM mysql.user
 WHERE User = 'lankapex_qr_test_migrator' AND Host = 'localhost';
SHOW GRANTS FOR 'lankapex_qr_test_migrator'@'localhost';
```

If the account is absent, the DBA may **separately authorize and execute** the following template. Enter the password privately in a local administrator session; do not paste it into chat or retain substituted SQL in a shared log. Do not run the literal placeholder. If the account already exists, stop and review it rather than replacing it.

```sql
CREATE USER 'lankapex_qr_test_migrator'@'localhost'
  IDENTIFIED BY '<private password entered locally by DBA>';
GRANT SELECT, INSERT, UPDATE, CREATE, ALTER, INDEX, REFERENCES
  ON `lankapex\_test\_db`.*
  TO 'lankapex_qr_test_migrator'@'localhost';
SHOW GRANTS FOR 'lankapex_qr_test_migrator'@'localhost';
```

Every underscore in the database name is escaped in the grant pattern. The runner requires the exact escaped grant and rejects a broad or unescaped pattern. The existing `lankapex_app` grants are not modified.

The DBA/operator should verify the new account locally, without recording credentials:

```sql
SELECT UTC_TIMESTAMP(6) AS checked_utc, DATABASE() AS selected_database,
       CURRENT_USER() AS effective_account, CURRENT_ROLE() AS active_role;
SHOW GRANTS FOR CURRENT_USER();
SELECT version_num FROM alembic_version;
SELECT business_id, user_id, COUNT(*) AS copies
  FROM customer_profiles WHERE user_id IS NOT NULL
 GROUP BY business_id, user_id HAVING COUNT(*) > 1;
```

Expected: exact `lankapex_test_db`, `lankapex_qr_test_migrator@localhost`, role `NONE`, revision `6e3f2c1a9b04`, and zero duplicate rows. The guarded preflight also verifies MySQL 8.0 strict mode, foreign-key checks, exactly 27 starting tables (26 application tables plus Alembic), and zero application rows.

## Private credential and read-only preflight

After the DBA account is approved, the Windows admin operator creates `.server-logs\private-test` with an access-controlled ACL and stores a DPAPI **CurrentUser** blob named `qr-test-migrator.dpapi`. This is a distinct file and must not overwrite any existing credential. Run from the repository root under the Windows account that will run the preflight. Review the directory ACL before proceeding if it already exists; do not replace an existing credential.

```powershell
$privateDir = Join-Path (Resolve-Path '.server-logs').Path 'private-test'
if (-not (Test-Path -LiteralPath $privateDir)) {
    New-Item -ItemType Directory -Path $privateDir | Out-Null
    $acl = Get-Acl -LiteralPath $privateDir
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($principal in @([Security.Principal.WindowsIdentity]::GetCurrent().Name, 'NT AUTHORITY\SYSTEM')) {
        $rule = New-Object Security.AccessControl.FileSystemAccessRule($principal, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $privateDir -AclObject $acl
}
$secretPath = Join-Path $privateDir 'qr-test-migrator.dpapi'
if (Test-Path -LiteralPath $secretPath) { throw 'QR migrator credential already exists; do not overwrite.' }
$secret = Read-Host 'QR test migrator password' -AsSecureString
try { $secret | ConvertFrom-SecureString | Set-Content -LiteralPath $secretPath -Encoding ASCII -NoNewline }
finally { $secret.Dispose() }
```

Keep the directory outside Git and do not print the blob. Only the same Windows account can decrypt it. The wrapper never edits `backend/.env`.

From the repository root, the exact **read-only** command is:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\backend\scripts\preflight_qr_test_schema.ps1
```

Expected only after account setup:

```text
PASS: exact empty test target/account/grant, revision, duplicate audit and 16-revision graph
READ-ONLY PREFLIGHT COMPLETE; no migration executed
```

Any `STOP` blocks execution. No preflight has been run against MySQL with the new account yet.

## Remaining execution gates

Before separate execution approval, obtain **either** a fresh private backup of the *current* `6e3f2c1a9b04` schema with a verified SHA-256 and recovery plan, **or** explicit operator approval that only this zero-row test schema is disposable. The old `03b9c2d1e671` dump does not satisfy the current-backup gate. Verify no test runner, application writer, DBA DDL, or other schema-changing process is active, and maintain that pause through migration and validation. The execution mode requires `--execute`, exact target confirmation, a pause flag, and exactly one recovery-policy flag. It reruns the full preflight immediately before the one revision. A flag records operator confirmation; the script cannot independently establish the writer pause or grant approval.

The runner's SQL allowlist accepts only reads, the two reviewed `CREATE TABLE` statements, the new request index, the profile unique constraint, and Alembic's version-row update. It refuses other schemas, `DROP`, `DELETE`, `TRUNCATE`, database/global commands, and unrelated writes. After success it checks revision `7b9e4d2c8a15`, 28 modeled application tables plus `alembic_version`, zero application rows, and SQLAlchemy model/schema consistency. On error, preserve partial state for operator review; do not automatically retry or restore.
