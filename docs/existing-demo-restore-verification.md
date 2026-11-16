# Existing demo restore: comparison and separate QR rehearsal

Prepared and offline-tested only. No database, credential or evidence was accessed
while implementing this workflow. Do not execute without separate authorization.

## Exact identities and account policy

- Source: localhost:3306/lankapex_demo_db, existing
  lankapex_demo_app@localhost, global USAGE plus exact escaped-schema
  SELECT, INSERT, UPDATE, DELETE only.
- Existing restore: localhost:3306/lankapex_demo_restore_verify_20261116 only.
  The operator must first provide and independently approve its exact existing
  username@localhost and privilege list. No real restore account is assumed.
  Source runtime/migrator accounts and root are rejected as restore identities.
- Restore grants must be exactly SELECT for comparison, or SELECT, INSERT,
  UPDATE, CREATE, ALTER, INDEX, REFERENCES with or without the explicitly
  acknowledged existing DELETE capability. No extra privileges, other schemas,
  roles, GRANT OPTION, proxy grants, unescaped wildcard schema or partial revokes.
  Rehearsal requires the DDL-capable contract. Do not add grants to make this pass.
  MYSQL CURRENT_USER and effective grants are checked on each exact connection.
  MySQL does not expose a Windows-style schema owner; independently approve the
  restore's provenance and administrative custody. This tool does not infer
  ownership from its name or from matching counts.

These operator inputs describe a reviewed account contract, not application or
frontend input. An unexpected authenticated account or grant fails closed.

## One consolidated comparison session

Before authorization: exclude source writers and source DDL, exclude restore
writers/DDL/account administration, and have a DBA review/drain active
transactions with adequate visibility. Keep that boundary throughout both source
captures and the restore capture. This is an operator-enforced pause, not a claim
that separate per-schema snapshots are atomic without it. No sessions are killed.

Require an approved public CA and verified IP SAN 127.0.0.1. Transport remains
direct IPv4 loopback, TLS >=1.2, chain/identity verified, with no plaintext fallback.
The tool does not load .env, application Settings, JWT/Groq configuration or DPAPI.
Passwords for the two independently approved accounts are entered through hidden
interactive prompts and held only in memory. Use a private terminal without
transcript, debugger, SQL tracing or memory capture. They are not comprehensively
erasable from Python/connector memory. Do not pass passwords as arguments.

Require privileged independent review that no routines/events/triggers or hidden
unsupported objects exist, and that metadata visibility is adequate. Runtime
zero counts alone do not establish their absence. The tool requires MySQL 8.0,
InnoDB tables, primary keys, strict SQL mode and active FK checks. It rejects
unsupported types/generated columns and caps the historical capture at 256 MiB
and one million rows. All private rows are read internally for full-row hashes;
no raw rows are printed or written into reports.

Default no-connection command:

```powershell
& .\backend\.venv\Scripts\python.exe -B -I .\backend\scripts\verify_existing_demo_restore.py
```

The next live action is ONE separately authorized read-only comparison session
plus exclusive private comparison-evidence creation. Replace placeholders with
reviewed nonsecret values; use a NEW 32-character lowercase hexadecimal evidence
ID and quote the CA path. Do not run this until the account/grants are known.

```powershell
& .\backend\.venv\Scripts\python.exe -B -I .\backend\scripts\verify_existing_demo_restore.py --execute --confirm-source lankapex_demo_db --confirm-restore lankapex_demo_restore_verify_20261116 --approved-restore-account '<APPROVED_EXISTING_RESTORE_USER>@localhost' --approved-restore-grants '<EXACT_COMMA_SEPARATED_GRANTS>' --tls-ca '<APPROVED_PUBLIC_CA_PEM>' --confirm-writer-ddl-pause --confirm-target-administration-pause --confirm-private-console --confirm-dba-object-review --evidence-id '<NEW_32_LOWERCASE_HEX_ID>'
```

The existing protected directory `.server-logs/private-demo-qr-migration` must
already satisfy operator ownership, operator/SYSTEM-only protected DACLs and safe
non-reparse ancestry. The reused Windows store holds paths against replacement
and uses exclusive CREATE_NEW with protected DACLs. No directories/ACLs are
created or changed. It writes only a new
`existing-restore-comparison-<ID>.json`, never historical evidence.

Checks reuse existing PK-ordered typed full-row fingerprints (Decimal, binary,
Unicode, NULL and dates preserved), full SHOW CREATE hashes, original financial
projections, reversal-aware signed balances, duplicate customer links, expanded
schema metadata and explicit FK orphan audits. Source is recaptured afterward.
Expanded schema comparison includes column defaults, PKs, indexes, constraints,
FK actions and checks. Only verified self-schema FK qualifications are normalized
for cross-schema comparison; actual connection identities are never rewritten.
External-schema FKs stop. Metadata/DDL is reread to detect concurrent drift.

## Distinct future rehearsal authorization

The comparison command cannot migrate. A separately authorized rehearsal uses
the SAME command with all of these additional flags:

```text
--rehearse --confirm-rehearsal --confirm-revision 7b9e4d2c8a15
```

Use a new evidence ID and a reviewed DDL-capable restore account. The tool first
repeats the complete source/restore comparison at 6e3f2c1a9b04. It acquires an
isolated-target advisory lock, rechecks identity/revision and duplicates, then
invokes only the reviewed QR migration operations on that restore connection.
The existing SQL gate permits exactly two CREATE TABLE statements, the QR index,
the profile unique constraint and one version UPDATE, in order. DELETE, DROP,
other DML/DDL, other connections, cross-schema writes, batches and binds outside
the approved sequence remain prohibited. The source cannot be the rehearsal
connection. No normal Alembic env or application engine is used.

Afterward, an independent read-only capture requires revision 7b9e4d2c8a15,
29 exact tables, complete QR metadata, empty new QR tables, unchanged complete
rows in all original application tables, unchanged financial fingerprints, exact
four new zero-orphan FKs, and no unrelated schema changes. Only Alembic version
row contents and the approved profile uniqueness addition are allowed to change.
The source is recaptured unchanged. The new private result is
`existing-restore-rehearsal-<ID>.json`.

On any STOP, preserve the databases and any partial evidence. MySQL DDL cannot
be assumed rolled back. There is no retry, restore, reset, cleanup, downgrade,
schema/account provisioning or automatic recovery. Repeating a completed
rehearsal is rejected by the predecessor-revision check. Review partial state
under the maintained pause before any separately authorized correction.

## Evidence compatibility boundary

The populated-demo migration guard and its exact rehearsal target were NOT changed.
They still require lankapex_demo_qr_rehearsal_20261115. This tool's report truthfully
names the existing 20261116 restore and is intentionally not accepted as that
guard's rehearsal proof. It also does not prove that this restored database came
from a particular SQL artifact: `backup_binding_verified=false`. Both demo/
production migration evidence compatibility flags remain false. Do not relabel
the target, copy hashes into a historical proof or assert migration readiness.

Successful results can establish actual preservation and rehearsal on the existing
restore, avoiding another restore solely for comparison. Accepting them for the
demo upgrade would still require a separately reviewed exact-target/evidence
contract adjustment and independent binding to the preserved backup artifact.
No new backup is automatically required: review the existing backup's checksum,
provenance and full restoration evidence before deciding it needs replacement.

Current recovery, runner, migration/dependency and verifier source hashes are
bound to new results. This source refactor changes earlier recovery bindings;
freeze reviewed files first. Never rewrite historical evidence to match new code.
Windows native protection, real account/grants/TLS and live behavior remain
unverified by the mocked offline tests.
