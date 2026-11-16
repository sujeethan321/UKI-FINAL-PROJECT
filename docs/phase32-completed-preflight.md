# Phase 3.2: dedicated migration preflight and exact procedure

## Authorized isolated execution — 2026-11-09

**PASS: isolated migration chain and structural verification completed.** The user
explicitly authorized only lankapex_migration_verify_20261107. The supplied command
had a missing slash in backend.venv; the previously verified interpreter path
backend/.venv/Scripts/python.exe was used, as disclosed before execution.

The guarded script ran once with --execute and exact --confirm-target. All access,
emptiness, grant-scope and graph gates passed. It applied the full chain, reporting
successful stages c9d5e8f7a237, d0e6f9a8b348, e1f7a0b9c459, f2a8b1c0d560,
03b9c2d1e671 and 14c0d3e2f782. Process exit status: **0**. No errors reported.

| Requested verification | Actual result | Status |
|---|---|---|
| 25 application tables | 25, verified independently after execution | PASS |
| alembic_version exists | Present; 26 total tables including it | PASS |
| Final revision | One version row: 14c0d3e2f782 | PASS |
| Migration/model validation | Script compare_metadata returned no differences; expected CHECK names present | PASS |
| No application seed data | Independent SELECT COUNT(*) on all 25 application tables: total 0 rows, no nonempty application tables | PASS |
| Target identity | URL and SELECT DATABASE() matched exact dedicated target; CURRENT_USER matched lankapex_app@localhost | PASS |

The independent post-check used only read-only metadata and row counts against the
dedicated target, without exporting records. Neither lankapex_db nor
lankapex_test_db was migrated or modified. No seed data, downgrade, reset, cleanup,
retry, grant change, deployment or push occurred. The isolated schema is preserved.

This verifies the actual clean migration chain and structural model comparison;
it does not certify runtime constraint rejection, API authorization/concurrency,
populated legacy-data upgrade, backup restoration or recovery drills. Those were
NOT RUN. The vehicle-document self-supersession service requirement remains.
Earlier NOT RUN/BLOCKED statements below describe historical pre-execution status
and are superseded for this isolated chain/structural rehearsal only.

**Stop after this rehearsal. Any further database changes require separate scope
and authorization; the script will now refuse its nonempty target.**

## Final preflight after privilege correction — latest result

2026-11-08, subsequent to the historical observations below. The DBA correction
was independently rechecked using the script's **default read-only mode**.
**Access and grant-scope blockers are resolved. All execution prerequisites
checked here PASS; migration execution remains NOT RUN, awaiting explicit approval.**

| Prerequisite | Result | Fresh evidence |
|---|---|---|
| Authenticated account | PASS | CURRENT_USER() matched lankapex_app@localhost |
| Exact target and access | PASS | URL database and SELECT DATABASE() matched lankapex_migration_verify_20261107 |
| Empty target | PASS | Zero tables/views, routines and events in target metadata |
| Sufficient privileges | PASS | Exact target grant covers SELECT, INSERT, UPDATE, CREATE, ALTER, INDEX, REFERENCES |
| Corrected grant scope | PASS | Escaped target scope recognized with partial_revokes=OFF; old unescaped matching scope/global privilege gate did not trigger; no active roles |
| MySQL baseline | PASS | 8.0.46, strict mode and foreign_key_checks enabled |
| Complete Alembic chain | PASS | 14 unique revisions, one root 79d8d51548c6 and one head 14c0d3e2f782; expected pending tail intact |
| Matching model/migration definitions | PASS | 25 mappers; five design specifications and model/migration parity checks passed |
| Database target protection | PASS | Reviewed CLI exact-name choice, URL replacement, before-DBAPI-connect/engine/SQL guards, identity assertions and supplied Alembic connection |
| Protected DB rejection | PASS | Database-free guard tests rejected both lankapex_db and lankapex_test_db at connection boundaries and protected-database SQL references |
| Default preflight write rejection | PASS | Synthetic CREATE/UPDATE/DELETE/DROP statements rejected; only metadata reads/session read-only setting allowed |
| MySQL compatibility review | PASS for static preflight | FK types/keys/indexes, defaults and constraints compile; no-self CHECK limitation explicitly retained as future service responsibility |
| Recovery plan | PASS for preparation | Stop/preserve partial schema; no automatic downgrade, reset, stamp or retry; MySQL DDL not transactionally reversible |

Actual commands run: standalone script **without --execute**, and
validate_enhancement_schema.py. Both completed with exit status 0. Database-free
synthetic guard tests rejected 14 forbidden connection/SQL cases; no SQL was
executed by those tests. No code changes to the rehearsal script were needed.
No comparison with a prior complete grant snapshot was claimed for unrelated
schemas; no grants were changed by the agent.

Expected future command, **NOT EXECUTED** (repository root):

```powershell
.\backend\.venv\Scripts\python.exe .\backend\scripts\rehearse_isolated_migrations.py --database lankapex_migration_verify_20261107 --execute --confirm-target lankapex_migration_verify_20261107
```

This approval would cover only the isolated chain/structural rehearsal: 25
application tables plus alembic_version, version 14c0d3e2f782, no application
seed rows. It does not authorize either existing database, grant changes,
reset/restore, financial fixtures or broader API/security testing. Script rechecks
identity/permissions/emptiness immediately before execution. Any later target or
grant drift must stop the run. Normal .env files remain unchanged. These guards
protect the reviewed script path; they do not revoke the account's unrelated
privileges or protect arbitrary separately executed DBA commands.

**Migration execution and runtime schema acceptance are NOT PASSED: NOT RUN.**
Explicit user authorization is required before the command above can execute.
The earlier grant-scope blocker statements below are historical, superseded by
this final preflight result. The recovery and self-supersession limitations remain.

2026-11-08. This report supersedes the earlier access-denied status in the [verification plan](phase32-isolated-migration-verification-plan.md). **Connection/access blocker resolved. Execution approval withheld; exact grant scope still requires DBA correction. No migrations or data writes were executed.**

## Fresh read-only observations

- Connected database: **lankapex_migration_verify_20261107**. Authenticated account matched **lankapex_app@localhost**, as supplied by the user.
- No tables/views, routines or events were visible in the dedicated schema. With the observed schema privileges this confirms the intended empty-table preflight; an authorized DBA should still exclude unexpected hidden stored objects and concurrent activity before execution.
- MySQL 8.0.46, foreign_key_checks=1, STRICT_TRANS_TABLES active, partial_revokes=OFF, lower_case_table_names=1. Session timezone is SYSTEM; rehearsal sets only its own session to +00:00 when execution is approved.
- Target grant includes SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, REFERENCES, INDEX, ALTER. The seven forward-chain requirements (SELECT, INSERT, UPDATE, CREATE, ALTER, INDEX, REFERENCES) are covered. DELETE/DROP exceed this clean forward rehearsal's needs and will not be used.
- **Scope issue:** the target database-level grant is unescaped `lankapex_migration_verify_20261107`.*. On this server, unescaped underscores are wildcard characters despite backticks. Privileges are sufficient, but scope is broader than the exact intended name. No grants were changed by the agent. [MySQL grant scoping](https://dev.mysql.com/doc/refman/8.0/en/grant.html).

The earlier diagnostic's first escaped-underscore check incorrectly expected four underscores; this name contains three. A follow-up inspected the target scope alone and confirmed all three were unescaped. No raw credential-bearing grants or passwords were printed.

## Required DBA scope correction

An authorized DBA should privately inspect all grants/roles, confirm the exact principal and target scope, revoke only the unintended wildcard-scope grant, and replace it with the exact escaped schema grant. The original grant includes DELETE/DROP, so the reviewed correction for this account is conceptually:

```sql
-- DBA REVIEW ONLY. Not executed. Review current grants before adapting/running.
REVOKE SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, REFERENCES, INDEX, ALTER
  ON `lankapex_migration_verify_20261107`.*
  FROM 'lankapex_app'@'localhost';
GRANT SELECT, INSERT, UPDATE, CREATE, ALTER, INDEX, REFERENCES
  ON `lankapex\_migration\_verify\_20261107`.*
  TO 'lankapex_app'@'localhost';
```

These account administration changes require separate DBA authorization. They do not alter schema/data but do change privileges; the agent is **not** authorized to execute them. Do not revoke unrelated grants to either existing application database, create users, request root passwords, or toggle global partial_revokes. If the DBA retains DELETE/DROP under a documented separate purpose, they are unnecessary for this script and never used; the exact-name scope remains mandatory. Reconnect and rerun the read-only preflight afterward. Its execution gate refuses a wildcard/global grant even though connection succeeds.

## Reviewed chain and compatibility

The existing Alembic configuration uses app.core.database.engine normally; with current development settings, a plain CLI upgrade would target lankapex_db. No normal env/config file was edited. The safe alternative is the existing env.py **Config.attributes['connection']** hook, which validates testing mode, allowed isolated naming and actual SELECT DATABASE().

The standalone script sets APP_ENV=testing and MYSQL_DATABASE=lankapex_test_db **inside its own child process only**, before loading normal Settings. This keeps existing Settings validation intact; it does not connect the ordinary test engine. It then creates a distinct URL with database replaced by the one allowed dedicated name. Engine-level before-DBAPI-connect and SQL guards reject fallback to either existing database. It preserves existing timeout/TLS options, uses no pytest fixtures and starts no server. Shell variables, backend/.env and Alembic configuration remain unchanged.

Graph verified: one root 79d8d51548c6, one head 14c0d3e2f782, 14 revisions. Tail:

```text
c9d5e8f7a237 -> d0e6f9a8b348 -> e1f7a0b9c459
 -> f2a8b1c0d560 -> 03b9c2d1e671 -> 14c0d3e2f782
```

The full chain and pending migration risks remain reviewed in the [Phase 3.2 plan](phase32-isolated-migration-verification-plan.md). Fresh database-free validator passed all checks: syntax, 25 mappers, approved column specifications, graph, model/migration parity, FK/index/unique ownership keys/defaults and offline MySQL rendering. Full-chain offline rendering from the preceding investigation compiled 25 application CREATE TABLE statements; this is not proof of online MySQL acceptance.

MySQL risks remain: enforced CHECK compatibility at each intermediate notification revision; FK/index/charset matching; nontransactional multi-statement DDL; partial failure; UTC session handling. The initially empty target avoids pre-existing incompatible notification data. No checks or strict mode are disabled. Document self-supersession is **not database-enforced** because CHECK cannot reference auto-increment document_id. Future write services must reject self/cycles, wrong document type/non-tip replacement, unauthorized ownership/reviewer actions and invalid SHA-256 formats. No such APIs are enabled by this rehearsal. [MySQL CHECK restrictions](https://dev.mysql.com/doc/refman/8.0/en/create-table-check-constraints.html).

## Prepared standalone command

Source: [backend/scripts/rehearse_isolated_migrations.py](../backend/scripts/rehearse_isolated_migrations.py). No application model/service/router or migration was changed.

From C:\Users\admin\Desktop\LankaPex, **read-only preflight** (safe to repeat while target remains empty):

```powershell
.\backend\.venv\Scripts\python.exe .\backend\scripts\rehearse_isolated_migrations.py --database lankapex_migration_verify_20261107
```

This command was executed **without --execute**. It confirmed identity, emptiness and graph, and reported `execution BLOCKED by grant scope`. A nonzero status for this condition is intentional. Its SQL allowlist permits only metadata SELECT/SHOW/DESCRIBE and the read-only session setting; it cannot create tables or run migrations.

**Proposed mutation command — NOT RUN; requires scope correction and explicit user approval first:**

```powershell
.\backend\.venv\Scripts\python.exe .\backend\scripts\rehearse_isolated_migrations.py --database lankapex_migration_verify_20261107 --execute --confirm-target lankapex_migration_verify_20261107
```

The confirmation flag is a mechanical safeguard, not authorization by itself. No caller-supplied alternate database, revision, SQL, seed, reset, downgrade or stamp option exists. The guarded execution mode rechecks identity/account, local host, MySQL 8.0/strict/FK settings, no active roles, exact grants and target emptiness; acquires a dedicated session advisory lock; rechecks empty tables/views; sets only its own session UTC; supplies that connection to Alembic; upgrades sequentially through c9d5e8f7a237, d0e6f9a8b348, e1f7a0b9c459, f2a8b1c0d560, 03b9c2d1e671 and 14c0d3e2f782. DBA/other sessions must remain quiescent; an advisory lock does not prevent unrelated DBA writes.

Expected effects **only after approval**:

- Creates the full existing + enhancement schema: **25 application tables plus alembic_version = 26 total tables**.
- Creates/updates the single Alembic version row, ending **14c0d3e2f782**. No application/financial seed records, legacy copies or backfills.
- Checks actual final table inventory, recorded version, SQLAlchemy metadata comparison and expected CHECK names. A mismatch stops execution and preserves evidence.
- Prints only stage/status and sanitized failure class/code, not URLs, secrets, raw SQL errors, grant identities beyond the approved expected account or financial rows.
- Does **not** establish positive/negative runtime CHECK enforcement, API/JWT isolation, concurrency, populated legacy preservation, backup/restore or complete UAT. Those planned drills require separate approval and tooling. A successful chain/structure result must not be reported as passing all those tests.

## Rollback and recovery

MySQL DDL cannot be rolled back as one transaction. The script creates no DROP/reset path and never calls downgrade/stamp. On failure it stops; no automatic retry is safe. Version and physical schema may differ if failure happened after some DDL but before version advancement. Preserve the isolated schema, safe error class/code and last recorded stage. Inspect metadata read-only; obtain approval for a reviewed forward correction or a separately DBA-created clean target. Do not drop partial tables, disable constraints, repair financial records or stamp past the error. Even a successfully migrated target is nonempty and the command deliberately refuses to run again.

No existing financial data needs restoration because this rehearsal never reads/copies/mutates it. No backup was made and no restore was tested. Retain baseline emptiness and reviewed migration files; separate destructive/reset/restore approval is required for any recreation of the dedicated database. Real development migration later still requires separate explicit approval, fresh schema/data preconditions, verified encrypted backup and tested restore path, maintenance budget and a forward recovery plan. Nothing here authorizes changes to lankapex_db or lankapex_test_db.

## Status and approval gate

Access/identity: **VERIFIED**. Empty target: **VERIFIED for accessible tables/views/routines/events**. Required privileges: **PRESENT**, but exact scope correction needed. Static validation: **PASS**. Migration execution: **NOT RUN / AWAITING APPROVAL**, with a grant-scope execution blocker. No schema, financial records, grants or environment files changed. AI remains deferred.

After the DBA narrows the grant and the default preflight passes, obtain explicit approval for the exact --execute command above, solely on lankapex_migration_verify_20261107. Stop here until that approval arrives.
