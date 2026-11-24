# MR-07 canonical migration contracts

Status: STATIC SOURCE PARITY PASS; independent review and real MySQL verification
still required. No connection, SQL execution, migration, backup, restore, service,
credential, provider, grant or feature activation occurred. Writer/DDL freeze is
unchanged. The MR-02/MR-03 real-execution blocker remains unconditional.

## Source contracts and framework DDL

New extension: backend/scripts/mr07_canonical.py.
New artifact: backend/contracts/MR07_CANONICAL_OBJECTS.json.

The extension reads the historical declaration builder, migration AST/literal DDL,
independent model AST and installed framework source. No application model,
configuration, engine or migration function is imported or executed. Original
declarations are retained alongside canonical stages. The artifact binds migration
and model hashes, canonicalizer/check-parser hashes, and framework source hashes.
It is an expected SOURCE contract, not an observed database inventory or approval
of a live deployment. It cannot enable the existing CLI or mock adapter.

Installed reviewed framework versions are Alembic 1.20.1 and SQLAlchemy 2.1.6;
other versions fail for review. Alembic's own version-table implementation defines
version_num VARCHAR(32) NOT NULL, no server default or autoincrement, and by default
a single-column PK. Its source PK name is alembic_version_pkc; MySQL's primary
index is PRIMARY and reflected constraint naming may differ. Compare PK columns,
preserve the actual name separately, and reject a missing PK. Framework DDL is
explicitly separate from application migration declarations. Its table options
are inherited/unknown; verify the actual existing framework table, including any
older creation-version differences. No framework or database upgrade ran here.

| Revision | Tables including framework | Triggers |
|---|---:|---:|
| 9d1a6f4e0c37 | 33 | 0 |
| ae2b7c5f1d48 | 35 | 0 |
| bf38d2a90176 | 40 | 10 |
| c04d9e7a6201 | 44 | 16 |
| d15a8c902e64 | 45 | 18 |

## Canonical rules

- NUMERIC and DECIMAL share exact precision/scale; MySQL 8 limits are checked.
  No float arithmetic or Decimal context rounding is used. Missing dimensions
  or unsupported precision/scale fail instead of becoming a default.
- Boolean represents signed TINYINT(1) storage, not a fabricated 0/1 CHECK.
  Boolean(create_constraint=True) is unsupported and stops for review. Actual
  range enforcement comes only from explicitly required CHECKs and services.
- Generic DateTime means DATETIME precision 0. MySQL DATETIME(fsp=6) retains 6;
  aware/timezone conversions are rejected. No historical timestamp conversion.
- VARCHAR/CHAR retain character lengths; CHAR >255 and VARCHAR >65535 are
  rejected. TEXT retains its 65535-byte capacity, not a made-up character limit.
  Actual charset/row-byte budgets remain MySQL verification requirements.
- Reviewed integer spellings/display-width variants are explicit. Unsigned
  remains significant. ZEROFILL, unreviewed widths, unknown types/options and
  ambiguous generic versus MySQL-specific constructors fail closed.
- Nullable rules use explicit declarations, PK behavior or Mapped annotations.
  Client-only ORM defaults are recorded separately and excluded from database
  default equality. Missing required SERVER defaults are rejected. Reviewed
  now()/CURRENT_TIMESTAMP spellings normalize with precision preserved.
- Autoincrement is resolved from explicit flags, a single numeric PK, and FK
  suppression; unsupported declarations fail. Raw SQL lacking AUTO_INCREMENT
  does not acquire it merely because a column is an integer PK.
- Original type/default/constraint declarations remain in the artifact. Canonical
  expressions are not broad text stripping: CHECK literal values, grouping and
  operators remain meaningful, including ENFORCED requirements.

## Options and seven model corrections

The subscription migration's actual literal options dictionary is checked before
its **options is expanded into InnoDB / utf8mb4 / utf8mb4_unicode_ci. The seven
model table definitions now declare exactly those migration-defined options:

business_join_links, customer_join_requests, customer_link_invitations,
subscription_trial_grants, business_subscriptions, subscription_payment_events,
subscription_checkout_attempts.

Only four model files' table metadata changed; no columns, defaults, relationships,
business logic or historical migrations were changed. This reconciles future
metadata-generated DDL intent; it does not change an existing table.

For missing migration options, value=null and origin=inherited_unknown are
explicit. The intended environment policy is InnoDB / utf8mb4 /
utf8mb4_unicode_ci, but is NOT claimed as the observed value. Canonical inspection
counts 20 application tables plus alembic_version with inherited engine options.
This includes orders and order_items, whose literal CREATE TABLE tails are empty.
Column charset/collation null likewise means not explicitly declared, not proof
of the effective server setting. Preserve declared versus effective observations
separately. A future collector must inspect effective table/column settings and
validate approved inheritance before accepting them; it may not copy expectations
into an observed catalog to manufacture equivalence.

## Relationships, names and supporting indexes

Every inline/unnamed FK recovers its actual owning local column. FK signatures
include ordered local columns, referenced table/columns and update/delete actions.
NO ACTION and omitted actions normalize to the reviewed InnoDB RESTRICT semantics;
other actions remain distinct. All stage FK targets/columns and required parent
unique identities are checked statically. Composite ownership is never reduced
to a count or a single column.

UNIQUE signatures preserve ordered columns and MySQL's nullable-UNIQUE behavior;
explicit indexes preserve ordered columns and uniqueness. Source names remain
required when declared. For unnamed objects, structural identity is authoritative
and actual database-generated names are retained without arbitrary name matching.
PK names are handled separately from required PK column identity.

Only nonunique, full-column supporting indexes matching a required FK's EXACT
local column sequence may be implicit, and only where source PK/UNIQUE/explicit
indexes do not already supply a suitable leading prefix. At most one such extra
index per sequence is accepted. Arbitrary extra columns, unique substitutes,
duplicate extra support and missing explicit indexes fail. Real index prefix,
creation/reuse/removal and generated-name behavior must be verified on MySQL;
unexpected leftovers require review, never silent widening of this policy.

Three existing model naming omissions remain documented: business_join_links,
customer_join_requests and customer_link_invitations leave some FK names
unspecified while migrations name them. Structural relationships/actions match.
The SOURCE contract retains the migration names for actual-schema checks; model
comparison does not pretend that omission is an explicit matching model name.
All explicitly named model objects must match source names and definitions.

## Independent tests and observed verification

mr07_canonical_suite.py contains separately hand-authored fictional migration
expectations and catalog observations. Observations are NOT generated from the
expected table or canonical source builder. Negative tests cover missing/wrong FK,
FK action, UNIQUE, CHECK/enforcement, decimal scale, nullability, server default,
options, explicit/implicit indexes and framework PK, plus unsupported conversions.

Observed focused results: MR-02 29, MR-03 35, MR-05 24, MR-07 29 passed: 117 total.
Static comparison reports 44 application models / 424 columns, all 118 CHECKs and
all relationship/UNIQUE/index signatures consistent, with no semantic differences
under the reviewed rules. The three naming observations above are not hidden.
Python compilation was also checked. No unrelated frontend/full-project suite ran.

The historical MR-05 artifact is unchanged. Its test now explicitly distinguishes
the four authorized model metadata source-hash changes from historical evidence;
all migration declarations and other source hashes must still match it. The new
MR-07 artifact binds the current source. Old backup/manifest approvals do not
silently become approvals of changed model/tool source.

## Remaining gates

The canonical comparator accepts already canonical, independently captured metadata;
it is NOT a live reflection adapter. Existing MR-02/MR-03 mocked DTOs are not
automatically promoted into this format. A separately reviewed collector must
translate actual MySQL observations, retain raw DDL/name/context evidence and
validate effective inherited settings without filling missing observations from
expected contracts. Historical MR-05 blocker metadata is not rewritten to claim
a deployment PASS.

Still required: independent source/policy review; actual effective options,
constraint/index/PK reflection and CHECK enforcement; trigger DEFINER, SQL mode,
charset/collation and UPDATE/DELETE denial; DBA grants/freeze evidence; approved
backup and runtime identity/preservation checks; real evidence-sink trust/ACLs;
and separately authorized rehearsal using a separately reviewed adapter release.
No live adapter was implemented or enabled. Ready for independent contract review,
NOT for MySQL rehearsal.

Changed files: four model files named above; backend/scripts/mr07_canonical.py;
backend/contracts/MR07_CANONICAL_OBJECTS.json; backend/offline_tests/
mr07_canonical_suite.py and mr05_contract_suite.py; this document.
