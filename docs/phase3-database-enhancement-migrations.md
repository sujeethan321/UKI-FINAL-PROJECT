# Phase 3.1: prepared database enhancement migrations

2026-11-08. **Prepared locally; NOT APPLIED. No database connections or writes were made in this task.**

## Files and scope

| File | Change |
|---|---|
| backend/app/models/enhancements.py | Five new SQLAlchemy mapped classes and all storage constraints/indexes |
| backend/app/models/__init__.py | Register the five classes alongside the existing 20; preserve prior imports |
| backend/alembic/versions/14c0d3e2f782_add_approved_enhancement_tables.py | Standalone additive revision with five table definitions; no imports from live model code |
| backend/scripts/validate_enhancement_schema.py | Repeatable database-free syntax/model/design/graph/FK/index/offline-DDL validation |
| docs/phase3-database-enhancement-migrations.md | This preparation report and execution prerequisites |

No existing model definition, historical migration, router, service, schema, UI or environment file was edited. The working tree already contains unrelated changes; none were reset, committed or pushed. Scope is only the five table additions from the [approved Phase 2 design](phase2-database-enhancement-schema-design.md). Existing-table extensions, active_vehicle_id/assignment vehicle selection, address snapshots, media fields, optional carts, earnings/payouts and advanced/AI functionality are not included.

| Model | Table | Purpose / key safeguards |
|---|---|---|
| CustomerAddress | customer_addresses | Private user addressbook, archival, coordinate pairing/ranges, composite address/user ownership key |
| UserPreference | user_preferences | One row per user; single same-owner default address FK; explicit boolean/theme/version checks |
| BusinessSetting | business_settings | One row per business; optional future-account defaults; nonnegative limit/positive terms/radius; delivery disabled by default |
| Vehicle | vehicles | Driver-owned vehicle history; active/retired and submitted/legacy values; no fabricated verification or global registration uniqueness |
| VehicleDocument | vehicle_documents | Private versioned document metadata; same-vehicle supersession FK, unique successor, pending review default and coherent review evidence |

All five use signed BIGINT keys matching existing parents, InnoDB, utf8mb4_unicode_ci (document SHA-256 uses ASCII CHAR(64)), DATETIME(6), CURRENT_TIMESTAMP(6) creation/update defaults and DECIMAL precision from the design. Settings PKs do not autoincrement. Nullable fields have SQL's implicit NULL default; no nullable financial field is backfilled to zero. Defaults are server defaults, not implicit updates or triggers. Future write services must supply UTC timestamps and maintain updated_at/version. There are no ORM cascades or table-dropping downgrade actions.

Each FK uses RESTRICT on update/delete. Explicit parent composite unique keys support default-address and document supersession ownership. The document composite supersession FK has an explicit supporting index in addition to the unique single-column successor key; the latter does not by itself cover the two-column FK. Reviewer index is explicit. All names are within MySQL's 64-character limit, with no model constraint-name collisions. No new uniqueness is imposed on any existing populated table.

## Dependency chain and current-revision evidence

The full Phase 2 design, all 20 existing mapped definitions and the four pending migration sources were reviewed. Static metadata resolution/configuration includes every old and new mapper. The existing graph remains linear with one root and one new head, **14 total revisions**. The new revision attaches to the prior repository head, not directly to the development revision:

```text
79d8d51548c6 -> b2a1c4d6e8f0 -> c3d9e2f1a601 -> d4e0f3a2b702
 -> e5f1a4b3c803 -> f6a2b5c4d904 -> a7b3c6d5e015 -> b8c4d7e6f126
 -> c9d5e8f7a237              last verified development revision
 -> d0e6f9a8b348              existing pending orders/items
 -> e1f7a0b9c459              existing pending order/delivery link
 -> f2a8b1c0d560              existing pending notification compatibility
 -> 03b9c2d1e671              existing pending Admin foundation; previous head
 -> 14c0d3e2f782              NEW five-table foundation; new repository head
```

The last direct database observation is the preceding read-only Phase 2 check: lankapex_db at c9d5e8f7a237, 17 application tables, missing orders/order_items/admin_audits. **It was not freshly queried in Phase 3.1**, because this task authorizes local source preparation and database-free validation only. Current source revision graph and prior observed live revision are not the same evidence. No unapplied migration is assumed to have run. The five new names did not occur in the prior actual schema inventory or original 20-table metadata; static registration now yields exactly 25.

Within the new revision, creation order is customer_addresses -> user_preferences -> business_settings -> vehicles -> vehicle_documents. This satisfies parent dependencies, including the self-referencing document composite key. PK/unique/FK/check constraints are declared at table construction; indexes follow their tables. Existing users, businesses and driver_profiles are the only external parents. No SELECT/INSERT/UPDATE/DELETE/backfill is in the revision. It does not skip existing prerequisites with checkfirst or silently accept a conflicting table definition.

## MySQL design correction and service boundaries

The approved design specifies prevention of document self-supersession. A CHECK comparing supersedes_document_id to document_id would reference an AUTO_INCREMENT column, which MySQL prohibits. Therefore **no invalid ck_document_not_self is emitted**. The invariant is explicitly retained as a **required future service validation**, together with cycle prevention, same-document-type/current-tip supersession and reviewer authorization. This is a documented enforcement-location difference from a literal database CHECK reading of the design, not a claim that FK/unique keys prevent self-reference. A direct SQL writer could otherwise create a self-reference. No write API is enabled here; require this validation before enabling any document writes. If a database-only guarantee is required, approve a separate trigger/identifier design first; no trigger or identifier redesign was invented in this step. [MySQL CHECK expression restrictions](https://dev.mysql.com/doc/refman/8.0/en/create-table-check-constraints.html).

The schema enforces same-vehicle supersession and one direct successor; it does not enforce that a superseded record is the current tip or prevent arbitrary longer cycles by itself. SHA-256 length/ASCII storage is specified; hexadecimal format remains a required service validation, as allowed by the design, without an optional REGEXP CHECK. File MIME/size/malware rules, ownership-authorized downloads, retention and reviewer audit support remain prerequisites for future document APIs. Existing Admin audit target/action checks are not expanded by this revision.

Other future service requirements remain unchanged: JWT identity/role, active owner membership, address default/archive eligibility, customer-only preferred address, driver ownership and approval, optimistic version checks, mandatory notices, non-retroactive business defaults, duplicate-active-vehicle rules and document review concurrency. Database defaults do not implement those workflows. No driver is automatically approved. Legacy vehicle strings stay in driver_profiles, with no copy/backfill or active selection. Financial ledger balances, partial/full repayment, reversal, cash/credit state, exactly-once order approval and delivery lifecycle are untouched.

## Static validation: actual results

Command from repository root:

```powershell
backend\.venv\Scripts\python.exe backend/scripts/validate_enhancement_schema.py
```

| Check | Result |
|---|---|
| In-memory Python syntax compilation of model files, all revisions and validator | PASS: 31 files |
| Normal app.models import and configure_mappers | PASS: 25 tables / 25 mappers |
| Independently parsed five approved column specifications: order/names/types/nullability/defaults/PK behavior | PASS |
| ScriptDirectory revision inspection without env.py | PASS: 14 revisions, single root/head; all four older prerequisites retained |
| New revision interpreted by in-memory recorder, compared with mapped columns/PK/FK/unique/check/index/table options | PASS: exact model/migration parity |
| Additive operation allowlist and parent creation order | PASS: only create_table/create_index on the five additions |
| Referenced keys/types, FK support indexes and RESTRICT actions | PASS |
| Constraint-name collisions/identifier lengths/MySQL AUTO_INCREMENT CHECK restriction | PASS for the five additions |
| In-memory MySQL SQL rendering through offline MigrationContext/Operations | PASS: five CREATE TABLE statements compiled, not sent to a database |
| Downgrade refusal using recorder | PASS: raises before any operation |
| Actual MySQL migration execution / runtime CHECK/FK enforcement / live-schema comparison | **NOT RUN**; execution verification remains **BLOCKED** |

The validator patches SQLAlchemy Engine.connect/raw_connection, Pool.connect and socket connect operations to fail if attempted. It imports the normal model package (not a replacement Base), never executes Alembic env.py, and compiles SQL into StringIO only. It does not run a CLI upgrade/downgrade/stamp. SQL rendering is not server execution or proof that MySQL accepts the complete chain. No existing database-writing pytest fixtures were invoked.

The first validator run found a validation-script comparison issue (MySQL compilation spells INT as INTEGER); the comparator was corrected and the full validation rerun passed. No application/database defect was inferred from that first failure.

## Downgrade and operational risks

Downgrade intentionally raises RuntimeError, matching existing history-preserving migration policy. Addresses, preferences and vehicle documents can contain PII or administrative review evidence; automatic DROP TABLE is unsafe even though these are not ledger tables. Any future removal/restoration needs separate approval and retention review. There is no destructive downgrade to accidentally invoke.

MySQL DDL can commit/lock and a multi-table migration can fail partway. This revision is not an idempotent repair tool. After partial failure, operators must inspect actual schema and follow an approved forward recovery/restore procedure; do not rerun blindly, drop conflicting tables or stamp past missing structures. Existing pending notification CHECK replacements must be preflighted against each intermediate allowed set, not merely the final one. Backup/restore and maintenance plans are still necessary for additive changes.

## Exact prerequisites before any execution

1. Obtain **new explicit authorization** to execute migrations against a named verified target; current authorization covers source files only. Recheck APP_ENV, configured target, SELECT DATABASE(), actual revision, current tables and unexpected name collisions under that authorization. Neither development nor test database may be changed by this preparation task.
2. Resolve the previously documented empty isolated migration-verification database permission failure through the DBA action in [database operations](day17-database-operations.md). Creation/access is still **BLOCKED**; no elevated retry, new database or administrator-password request was made. Access must be confirmed before declaring full execution verification complete.
3. Confirm supported MySQL version with enforced CHECKs, InnoDB/charset/collation and matching signed parent keys. Independently review the full current chain, schema drift, notification data compatibility and table/constraint-name collisions. Last observed database revision is not a substitute for a fresh preflight.
4. Rehearse the full chain and representative legacy upgrade in a separately authorized isolated database; verify resulting PK/FK/index/check/default behavior and new-table count. Compile-only validation cannot replace this. Do not use lankapex_db or a populated test database as a fresh-chain substitute.
5. Establish verified backup/restore, retention approvals, least-privilege migration credentials, maintenance/lock budget and forward recovery plan. Review non-destructive downgrade refusal. Do not expose credentials in command logs or documentation.
6. For eventual development advancement, apply the four existing prerequisites in dependency order before the new revision, only under that new approval. Expected end state is 25 application tables excluding alembic_version, assuming the same verified baseline. Verify actual schema after each approved stage; never assume migration success from source inspection.
7. Keep all new feature write endpoints disabled/unimplemented until their authorization, validation, versioning and audit prerequisites are implemented and separately tested. Resolve the document self-reference enforcement decision before enabling writes. No schema preparation authorizes a financial repair, approval bypass or UI fabrication.

Preparation is complete. **No migrations were applied. Full migration execution verification remains BLOCKED.** AI, carts, payouts, subscriptions, group purchases and disputes remain deferred/outside this change.
