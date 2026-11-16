# Step 302 — Original database read-only inventory

Source preparation only. No live inventory was performed in this step.

## Operator review before authorization

The source is exactly localhost:3306/lankapex_db in development mode. Confirm the
authorized account with the DBA: historical evidence identifies
`lankapex_app@localhost`, but current identity and grants remain unverified.
Obtain and approve its exact existing schema privilege list. Do not expand grants
for this audit. Only SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX and
REFERENCES can be approved; SELECT is required. Unexpected/global privileges,
roles, proxy grants, GRANT OPTION and other-schema scopes cause STOP. Every
underscore in schema-level grants must be escaped. A grant containing privileges
outside this allowlist is a blocker requiring separate review, not a reason to
weaken the guard. The account should ideally be SELECT-only; the script performs
no application writes even when the reviewed existing account has broader rights.

Normal backend Settings loads environment and backend/.env. The operator must
privately establish the intended existing configuration without printing secrets.
No credentials are provided as arguments or written to files. Normal backend
TLS behavior applies: configured MYSQL_SSL_CA enables certificate validation.
This script neither configures TLS nor proves the transport is encrypted. Do not
remove an existing TLS requirement to make it run. No connection retry is added.

## Commands — future authorization only

No-connection default (not executed during implementation):

```powershell
& .\backend\.venv\Scripts\python.exe -I .\.server-logs\phase33-development-audit.py
```

One future read-only execution, after separately authorizing configuration/credential
loading and database reads. Replace the account and privilege placeholders with
the exact DBA-approved values; do not paste placeholders literally:

```powershell
& .\backend\.venv\Scripts\python.exe -I .\.server-logs\phase33-development-audit.py --execute --confirm-host localhost --confirm-port 3306 --confirm-database lankapex_db --confirm-account '<APPROVED_USER>@localhost' --confirm-privileges '<EXACT_COMMA_SEPARATED_PRIVILEGES>'
```

The script creates no evidence file and does not overwrite the historical JSON.
Do not redirect its output into historical evidence. Optional evidence output is
intentionally not implemented. Terminal output contains aggregate findings,
sanitized schema metadata and preservation hashes; treat hashes as private
operational evidence rather than publishing them.

## Behavior and boundaries

Explicit checks replace Python assertions. Effective configuration is checked
before connection; actual database/account/port, roles, partial revokes and exact
grants are checked before table reads. The transaction uses REPEATABLE READ and a
consistent READ ONLY snapshot. The initial connection commit completes only the
read-only session setup; no financial work is committed. SQLAlchemy/driver
connection initialization occurs before its statement event guard. Later
application statements are SELECT/SHOW/DESCRIBE or three reviewed transaction
setup statements only. No locks, migrations, DDL, account changes or financial
writes are performed. Closing the connection rolls back on failure.

The current target revision is 7b9e4d2c8a15, with 28 application tables plus
alembic_version. Older connected revisions are inventoried and pending revisions
reported; inventory completion is not schema compatibility or migration approval.
Unknown/multiple revisions or incompatible missing columns can stop collection.
The original all-row serialization, ledger fingerprint and authoritative
reversal-aware account_balances calculation remain unchanged.

Added findings include active users by each role, approved businesses, active
credit accounts, published/available products, approved active Driver profiles,
Driver profile vehicle prerequisites, available delivery requests, duplicate
non-null customer links, and explicit orphan audits for discovered foreign keys.
Counts do not prove one complete usable owner/customer/product/driver scenario.
Customer credit eligibility, stock/category constraints, vehicle-document rules,
specific role access and end-to-end behavior require later separate verification.

Schema compatibility checks cover expected tables, column type/nullability drift
and QR profile uniqueness; detailed FK/index/check metadata is also reported.
They are not a full Alembic autogenerate equivalence proof. Stored-object metadata
can be privilege-limited and must not be treated as independently verified absence.
DDL changes concurrent with inventory can invalidate metadata consistency; exclude
concurrent schema administration for the authorized run. Snapshot guarantees apply
to InnoDB; non-InnoDB tables cause STOP. All rows are read into memory for the
historical fingerprints, so review dataset size/capacity first.

On STOP: preserve all state, report only the fixed category, and obtain separate
authorization before another execution or any repair. No automatic retries,
cleanup, grant changes or resets. The demo database and its migration remain
outside scope.
