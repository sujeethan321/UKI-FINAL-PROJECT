# Day 17 Step 17.5 — Final production readiness audit

Audit date: 2026-11-07. Repository: `main`, HEAD `d917e4f`
(`Day 14: complete customer shopping and credit order integration`).
This report describes the tested working tree, **not that commit alone**.

## A. Overall verification and release decisions

**PARTIAL verification; overall production release: NO-GO.** No deployment,
production connection, migration execution, database creation, backup, restore,
cloud configuration, commit or push was performed in this audit.

| Decision | Status | Evidence / prerequisite |
| --- | --- | --- |
| Code readiness | PARTIAL | Regression results below; frontend lint FAIL; Admin reports incomplete |
| Database migration readiness | BLOCKED | Isolated verification database creation previously denied |
| Backup/recovery readiness | NOT VERIFIED | Procedures exist; no backup/restore/reconciliation rehearsal |
| Deployment configuration readiness | PARTIAL | Local manifests/startup/health contracts tested; hosting unverified |
| Overall production release | NO-GO | Migration, recovery, production protection and operational gates unresolved |

AI Summary remains deliberately deferred and is not a release blocker. No AI
provider, SDK, key, endpoint or environment requirement was added.

## B. Day 17 implementation review

| Step | Status | Actual implementation |
| --- | --- | --- |
| 17.1 | PARTIAL | Environment validation, JWT/CORS/host/error controls and Vite URL validation; no real production environment verified |
| 17.2 | BLOCKED execution | Maintenance safeguards, schema/offline SQL checks and recovery guide exist; isolated upgrade and restore unverified |
| 17.3 | PARTIAL | Local quotas, body bounds, read caps and measured query batching; distributed enforcement not configured |
| 17.4 | PARTIAL | Vercel/Railway manifests, safe launcher, bounded readiness and runbook; no hosting execution |
| 17.5 | PARTIAL | Working-tree audit and local checks; release gates explicitly retained |

Reviewed configuration, authentication dependencies, JWT signing/validation, HTTP
controls, readiness service, launcher, frontend Axios/URL validation, test safety
hooks, migrations, dependency manifests, Git state and the four preceding guides.
Existing staged Day 15 files and unstaged/untracked Day 16–17 changes are interdependent.
No unrelated work was overwritten or included in a new checkpoint.

## C. Authentication, authorization and isolation

JWT uses a fixed HS256 algorithm, required sub/exp/iat claims and access-token
type; identity, active status and role are read from the database. No public
Administrator registration is introduced. Production startup rejects missing or
known placeholder signing configuration, weak/repetitive secrets, debug logging,
local production database targets and wildcard/insecure CORS configuration.

Suite coverage includes missing/expired/tampered JWT, inactive accounts,
Shop Owner/Customer/Driver/Admin cross-role denials, ownership/ID tampering,
business/driver approval restrictions and Admin action audit history. Backend
dependencies remain authoritative. Frontend tests exercise protected routes and
session handling; 403/409/413/422/429/timeouts do not falsely expire the session.

## D. Financial and fulfilment integrity

Existing synthetic suites cover Decimal precision, credit sale/repayment balances,
statements, approval idempotency and rollback, customer/business relationships,
cash and pending/rejected credit orders, price snapshots and stock validation.
Order/delivery tests cover unique linking, serialized creation/completion,
two-driver acceptance races, ownership, valid status transitions, customer
tracking and notification idempotency. Admin regression checks preserve posted
financial records/order snapshots during reads and account changes. Delivery
events do not settle the ledger. No financial formulas or real balances changed.

Admin overview, entity management/approvals and audit history exist. Full Activity,
operational reports, report date filters and report CSV workflows are incomplete;
their absence is not a passing report test or permission to fabricate data.

## E. Database and migration assessment

Before mutating tests, both settings/engine target and actual `SELECT DATABASE()`
were verified as **lankapex_test_db**. The session-start guard rejects any other
database/environment. Only existing synthetic fixtures and scoped cleanup ran.
An initial environment-only preflight was rejected before connecting because the
database override was absent; the documented test database override resolved it.
No development or production database was connected to by this audit.

The suite checks 13 unique revisions, one base and one head `03b9c2d1e671`, 20
registered model tables, offline upgrade SQL and test-schema metadata/constraints.
These checks do **not** prove clean migration execution. Previously recorded
development revision `b8c4d7e6f126` is historical evidence, not a fresh live read.

**Isolated migration-chain execution: BLOCKED, not PASSED.** MySQL previously
denied creation of `lankapex_migration_verify_20261107`; no new resolution evidence
exists. A local DBA must create that separate empty schema and grant the intended
test account access using the template in [database operations](day17-database-operations.md).
Confirm actual identity, access and emptiness before a separately authorized
verification. No elevated retry, administrator password request, reset or
substitution of the synthetic test database is permitted.

## F. Recovery

[Database operations](day17-database-operations.md) documents private defaults-file
credentials, protected/encrypted storage, retention, provenance/checksums,
separate restore target, financial fingerprints/reconciliation and incident steps.

| Recovery stage | Status |
| --- | --- |
| Procedure documented | PASS |
| Real backup created in this work | NOT VERIFIED / not performed |
| Backup integrity verified | NOT VERIFIED |
| Isolated restore succeeded | NOT VERIFIED |
| Restored financial records reconciled | NOT VERIFIED |
| Measured RPO/RTO | NOT VERIFIED |

## G. API security, dependencies and performance

Tests exercise process-local quota concurrency/expiry/capacity, 429/Retry-After,
spoofed forwarding headers, body bounds including streamed input, request IDs,
safe errors, Pydantic/search/page bounds and authorization-scoped SQL. Legacy
read caps reject overflow rather than returning partial financial balances.
The production launcher disables forwarded-header trust and raw access logs.

Production requires `RATE_LIMIT_MODE=external`; this flag does not implement
shared/edge protection. Actual external enforcement and ingress trust remain
unverified and must be demonstrated before release. No external infrastructure
was added. Existing CSV/file safeguards are covered where implemented; missing
Admin exports are not certified.

[Step 17.3 measurements](day17-api-security-performance.md) document a local
synthetic 83-request workload, zero measured errors, and 20-order projection SQL
reduction from 42 queries to 3. Its final service-only p50 10.79 ms / p95 12.68 ms
are historical local measurements, **not freshly measured Step 17.5 values**.
Small samples are not production tail-latency/capacity evidence. No new index,
production load test or SLA claim is made.

The full Step 17.5 run also re-executed the benchmark fixtures and refreshed their
ignored JSON artifacts. Synthetic dataset: 20 orders, items, products, ledger
entries and jobs; Windows host, four CPUs, concurrency one. Eight read scenarios
with ten calls each plus three logins again returned **0/83 errors**. Fresh HTTP
measurements (milliseconds; small-sample p95 is effectively maximum):

| Scenario | p50 | p95 | Maximum SQL calls |
| --- | --- | --- | --- |
| Shops | 22.59 | 31.00 | 5 |
| Products | 24.43 | 44.59 | 6 |
| Order history | 23.26 | 29.99 | 6 |
| Transactions | 29.15 | 60.98 | 5 |
| Customer dashboard | 40.14 | 43.06 | 7 |
| Owner dashboard | 28.45 | 32.21 | 8 |
| Driver jobs | 23.58 | 41.40 | 6 |
| Admin overview | 25.28 | 77.27 | 4 |
| Login (3 calls) | 213.05 | 318.71 | 3 |

Artifacts: `.server-logs/day17-3-http-benchmark.json` and
`.server-logs/day17-3-order-benchmark.json` (existing fixture filenames, refreshed
by this run). Tests verify read scenarios issue no INSERT/UPDATE/DELETE and
preserve financial fingerprints. EXPLAIN selected `ix_order_customer_created`
with a filesort; this is not evidence all query plans are optimal.
Fresh service-only order projection: 20 requests, zero errors, p50 9.62 ms,
p95 11.01 ms, maximum three SQL calls for both small and 20-order pages.

Backend requirements are pinned; frontend has a package lock and manifest version
ranges. Local `pip check` passed. This is dependency consistency, **not a current
advisory vulnerability audit**. No fresh registry/advisory audit, clean Linux
dependency install or hosted Python runtime test was performed; those remain
NOT VERIFIED. No packages were installed or upgraded.

Known-local-secret scanning found **zero findings** across 441 current files/assets
and 631 reachable historical text blobs, against two known local secret labels.
Private dotenv files, keys, logs, dumps, node_modules and dist are ignored; no such
artifacts appear in the staged path review. The scanner checks known values and
uses limited matching for short values; unknown secrets are not ruled out.
No secret values were printed or rotated and Git history was not rewritten.
An additional scan of the actual Git index content, rather than only working-tree
versions, reviewed all 43 staged paths and found zero known-secret matches.

## H. Deployment, health and operations

Frontend root `frontend`: `npm ci`, `npm run build`, output `dist`.
`vercel.json` provides extensionless SPA fallback excluding API/assets/file paths.
Axios requires the explicit `/api/v1` base and production HTTPS; only VITE_API_URL
is approved public configuration. No production URL was invented.

Backend root `backend`: `python scripts/start_production.py`, production-only,
valid platform PORT, `0.0.0.0`, reload disabled. Dependencies and Python pin match
the local preparation; Linux/platform support is not certified. No automatic
migration command is configured. Production database settings preserve verified
TLS and safe parameter hiding.

`GET /api/v1/health` is liveness without a database query.
`GET /api/v1/health/database` is readiness with SELECT 1, no-store and generic
503 on failure. Dedicated connections, socket limits, a response deadline and a
single outstanding worker bound probe resource use. A stalled underlying driver
thread cannot be forcibly terminated. Readiness does not certify schema or backup
state. Railway configuration points to the readiness path; actual hosting is
unverified.

[Deployment guide](day17-deployment-readiness.md) covers environment setup,
migration/backup gates, backend-first release/health then frontend/API smoke,
monitoring and rollback. Availability/error/latency/database/login/quota/backup/
migration/financial/order/assignment signals are planned, **not active monitoring**.
No third-party monitoring service was connected. Rollback requires known-good
artifact IDs and schema compatibility; none is certified deployed. Code rollback
does not reverse database writes/DDL. No downgrade or restore was run.

## I. Test evidence

Fresh Step 17.5 results are recorded below. Backend
execution includes auth/RBAC, finance, orders/deliveries, notifications, Admin,
database safety, configuration, rate limits, performance and health contracts.
Tests for unavailable Admin reports and browser viewport execution are not implied.

- Frontend full suite: **806 passed, 0 failed, 0 skipped** (37.32 seconds).
- Frontend lint: **FAIL — 8 errors, 1 warning**, reproduced in
  ShopOwnerCustomers.jsx, ShopOwnerDashboard.jsx and tests/repayments.test.js.
  Includes synchronous effect-state updates, unused imports and a hook dependency.
  No rule suppression or test weakening was applied.
- Backend full suite: **1227 passed, 0 failed, 1 skipped**, 214.06 seconds.
  The skipped clean migration execution remains **BLOCKED**, not passed.
  Two warnings: intentionally short wrong HMAC key in the tampered-JWT test,
  and an existing pytest cache-path creation conflict. Neither was suppressed.
- `pip check`: PASS, no broken requirements found.
- Tracked whitespace check: PASS.

## J. Build, responsive and accessibility verification

Fresh Vite build: **PASS**, 2218 modules, 4.05 seconds. JS 803.78 kB
(217.84 kB gzip), CSS 62.61 kB (12.95 kB gzip). Existing >500 kB chunk warning
remains. Process-only `https://api.example.invalid/api/v1` was used to verify
build behavior; the generated artifacts are **not release-ready endpoint configuration**.
No dotenv values, designs or LankaPex colors were changed. The landing headline
retains **Management** and its regression suite passed.

Browser discovery returned no available browser; a follow-up browser selection
also returned `No browser is available`. Native app control is disabled in this
session. Therefore visual/keyboard/screen-reader verification at **1536, 1366,
1024, 768 and 375 px is BLOCKED**, not passed. Component/route tests are useful
integration evidence but do not establish responsive layout, focus order, table/
dialog overflow or real assistive-technology behavior. No production browser
session or live-data UI was used.

## K. Git safety and checkpoint

Branch `main`; HEAD `d917e4f`; message recorded at the top. Working tree remains
dirty, including 43 previously staged Day 15 paths plus Day 16/17 unstaged and
untracked work. `.gitignore` also has prior changes. Existing `%SystemDrive%/`
and `.vite/` untracked paths were left untouched. No generated backup, environment
secret, node_modules or dist path was found in the staged path listing.

**Local completion checkpoint withheld:** configured lint still fails, and a
standalone Day 17 commit would depend on earlier uncommitted Day 15/16 changes.
Committing the existing index would include work outside the requested checkpoint.
No staging, unstaging, commit, amend, reset, history rewrite or push was performed.
The passing suites validate the working tree, not an isolated committed artifact.

## L. Release recommendation

**NO-GO for production.** Passing regression/build checks do not resolve migration
execution, recovery, external abuse protection, missing report functionality,
lint, clean runtime packaging, responsive verification or live operational gates.

## M. Required follow-up actions

1. Obtain DBA creation/access for the isolated migration target, confirm emptiness
   and execute the guarded chain verification; preserve the permission blocker
   until actual evidence exists.
2. Authorize a separate isolated restore rehearsal, verify provenance/integrity,
   reconcile financial records and measure recovery objectives.
3. Resolve lint with focused regression checks; finish or explicitly defer missing
   Admin reporting scope. Do not fabricate release coverage.
4. Run current dependency advisory review and clean Linux/runtime packaging checks.
5. Verify all five requested viewports, keyboard/focus and accessible labels in an
   available browser using an isolated synthetic backend.
6. In a separately authorized environment, configure and prove shared/edge quotas,
   exact domains/CORS/TLS/proxy policy, hosting routes, monitoring/alerts and a
   schema-compatible rollback artifact. No deployment is authorized by this report.
7. Review dependent Day 15/16/17 changes into intentional Git checkpoints after
   failing code checks are resolved; do not accidentally commit the inherited index.

## N. Recommended next milestone

Recommend **Day 18: close release blockers and rehearse an isolated staging
release/recovery**, then repeat the GO/NO-GO review. Do not start deployment or AI
integration as part of this audit.
