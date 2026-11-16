# Day 17 Step 17.4 — Deployment and monitoring preparation

Date: 2026-11-07. **LOCAL PREPARATION ONLY — NOT A DEPLOYMENT APPROVAL.**
No hosting account was accessed, service changed, production database connected,
migration run, backup created/uploaded, credential generated/rotated, commit made
or code pushed. AI Summary stays deferred with no SDK, key, provider or startup
dependency. Existing LankaPex UI, colors and Management headline are unchanged.

## A. Repository audit

Branch main, HEAD d917e4f; prior 43 staged Day 15 files and later working changes
remain preserved. Current HEAD is a Day 14 checkpoint, **not evidence of a deployed
known-good release**. No current deployment ID or rollback artifact is available.

Step 17.1 settings/TLS/CORS/hosts/error protection and Step 17.3 local quotas,
request bounds/correlation IDs/order batching are present. Prior full results were
1213 backend passed/1 skipped and 805 frontend passed. They are not substituted
for the current verification below. Step 17.2 online migration verification is
still **BLOCKED** by CREATE DATABASE permission; no evidence of resolution exists.
No elevation/DBA-password request or alternate use of lankapex_test_db for migration
verification was attempted. Step 16 operational reports/CSV/full Activity remain
unfinished, and existing frontend lint errors persist.

Actual frontend is frontend/package.json (Vite/React BrowserRouter), build output
frontend/dist, Axios uses validated VITE_API_URL. Actual backend is backend/app/main.py
with the app object `app`, Pydantic Settings, pinned backend/requirements.txt,
SQLAlchemy/PyMySQL and Alembic. No deployment manifests existed before this step.

## B. Vercel preparation

Set project root to **frontend**, use the checked-in frontend/vercel.json, `npm ci`,
`npm run build`, output **dist**, root URL base. Current local Node is 24.19.0;
select a compatible supported runtime before an authorized hosting build.
package-lock.json supplies dependency resolution. No account/project/domain was
created or inferred and no Vercel CLI command was run.

Manifest fallback is limited to extensionless SPA paths and excludes /api and
/assets. Existing static files keep filesystem precedence; missing assets/API
paths are not deliberately rewritten to index.html. There is no backend API proxy
or redirect to loop. The routing-pattern unit test checks root/login/role deep
links and API/static exclusions; this is not a live Vercel routing certification.
The manifest prepares nosniff/referrer policy only. HSTS/CSP and cache tuning need
verified domains/assets/API/HTTPS behavior before enforcement.
See [Vercel's configuration reference](https://vercel.com/docs/project-configuration/vercel-json).

VITE_API_URL is the **only approved public frontend variable**, ends with /api/v1
exactly once and must use the real approved HTTPS backend for a release. No query,
userinfo, private host or credentials. Preview environments must use a separately
approved non-production backend and explicit origin list; preview deployments must
not gain wildcard access to production. Build again after setting real values.
No real deployment URL is supplied in this guide.

## C. Railway preparation and backend startup

Set service root to **backend** and explicitly select **backend/railway.json** as
the repository config file; confirm effective source paths/settings in a future
authorized release. Config prepares Railpack, installation from the pinned
requirements, start command and readiness gate. No platform build was run.
The configuration uses the documented
[Railway config-as-code fields](https://docs.railway.com/config-as-code/reference).

Prepared commands from backend:

```text
python -m pip install --no-cache-dir -r requirements.txt
python scripts/start_production.py
```

The launcher requires production mode and a valid platform PORT; binds 0.0.0.0,
imports **app.main:app**, disables reload, proxy-header trust and raw access logs,
and uses INFO server logging. It validates application settings without connecting
to MySQL or running Alembic. Missing/invalid configuration exits safely without
printing values. It is a production launcher, not a replacement for the existing
local development command. A separate-process local check confirmed development
mode is rejected; no production listener was started.

backend/.python-version pins the locally tested **3.14.7** runtime. Linux wheel
availability, provider support for that exact runtime, immutable builder selection
and a clean Linux install/import remain unverified. requirements are version-pinned
but not artifact-hash locked. pip check passes locally; that alone does not prove
a hosting build. Review those packaging inputs before release.

The manifest gates release on /api/v1/health/database with a 60-second deployment
health window. Railway's documented health Host is **healthcheck.railway.app**;
when used, include that documented host explicitly alongside the actual backend
host in ALLOWED_HOSTS. This is provider health infrastructure, not an invented
application domain. Deployment healthchecks are not continuous monitoring.
See [Railway healthchecks](https://docs.railway.com/deployments/healthchecks).

No pre-deploy or startup migration is configured. RATE_LIMIT_MODE=external is
still a production prerequisite, not an implemented external policy: verify a
real shared/edge limiter and direct-origin protection before deploying.

## D. Database, migration and backup gates

Test mode/configured URL/actual SELECT DATABASE() were verified as lankapex_test_db
before synthetic fixtures. Development was not connected to or modified in this
step; earlier known revision is b8c4d7e6f126, behind the current head. No test DB
reset or schema upgrade. The test database is never the blocked migration target.
Production MySQL endpoint/account/TLS/version remain unknown and untouched.

Main engine preserves pre-ping, recycle, parameter hiding, echo=false and session
cleanup. MYSQL_CONNECT_TIMEOUT_SECONDS bounds socket connection setup; ordinary
pool/statement capacity still needs production calibration. Production TLS uses
verified SSLContext/system roots or an approved MYSQL_SSL_CA. No verification
bypass or plaintext production fallback. Driver timeouts are not a guarantee
of bounded DNS resolution or every business query/lock duration.

Mandatory future release gates:

1. Resolve **BLOCKED** isolated migration verification through an independently
   authorized DBA; verify actual empty target/access, run the guarded test and
   compare resulting schema. Do not claim offline SQL generation is execution.
2. Review exact revisions, data compatibility/DDL locks, storage headroom and the
   application/schema compatibility matrix. No stamp to conceal drift.
3. Produce a verified encrypted pre-schema-change backup, verify checksum/provenance
   and a successful isolated restore/application rehearsal. Existing restore/RPO/
   RTO are planning only, not certified capabilities.
4. Assign one release owner and one exclusive migration runner through a reviewed
   release/job lock. Never let each app replica perform upgrades on startup.
5. Perform schema changes only through a separately authorized process. Inspect
   actual schema/revision after failure; MySQL DDL is not safely undone by assuming
   a transaction rollback. Prefer reviewed forward fixes. No destructive downgrade.

See [database operations](day17-database-operations.md) and
[Step 17.2 review](day17-database-safety-review.md). They contain the permission
failure/DBA action, encrypted retention proposal, restore plan and recovery-owner
requirements. No backup/restore or scheduler has been enabled.

## E. Health checks and bounded readiness

| Existing route | Contract | Work |
| --- | --- | --- |
| GET /api/v1/health | Public 200, existing minimal application/status message | No DB or auth dependency |
| GET /api/v1/health/database | Public 200 with status/database connected, otherwise generic 503 Database unavailable | SELECT 1 only; no schema, users, balances or credentials |

Both return Cache-Control: no-store and existing response security headers.
Readiness remains excluded from OpenAPI. It is an intentionally minimal component
availability check, not proof of schema migration, distributed throttling, backup
health or overall release approval. Liveness can stay up during a database outage;
readiness prevents promotion while database connectivity is unavailable.

New readiness worker has a configurable response deadline (3 seconds default),
dedicated NullPool connection, and 2-second connect/read/write socket timeouts.
Only **one** probe per process can be outstanding; timeout/busy/error returns 503.
An underlying blocking driver/DNS call cannot be forcibly killed by cancelling
the async wait. The one-worker gate prevents queued/orphaned-probe accumulation
until it finishes; deployment shutdown/DNS behavior still needs hosting validation.
No application connection-pool slot is consumed by the probe. Connections close
through a context manager, including errors; no table creation, migration or
business mutation is performed.

Tests verify liveness does not call DB, ready/unavailable payload minimization,
exception handling, response deadline and no backlog, actual test SELECT 1,
startup port/mode controls and no migration command in the manifest.

## Configuration inventory — names only

Backend connection/secret controls:
`APP_ENV`, `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`,
`MYSQL_DATABASE`, `MYSQL_SSL_CA`, `MYSQL_CONNECT_TIMEOUT_SECONDS`,
`JWT_SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`.

Backend operational controls:
`APP_DEBUG`, `LOG_LEVEL`, `CORS_ALLOWED_ORIGINS`, `ALLOWED_HOSTS`,
`READINESS_DB_TIMEOUT_SECONDS`, `READINESS_TIMEOUT_SECONDS`,
`REMINDER_COOLDOWN_SECONDS`, `RATE_LIMIT_MODE`, `RATE_LIMIT_WINDOW_SECONDS`,
`RATE_LIMIT_LOGIN`, `RATE_LIMIT_LOGIN_IP`, `RATE_LIMIT_REGISTRATION`,
`RATE_LIMIT_MUTATION`, `RATE_LIMIT_EXPORT`, `RATE_LIMIT_MAX_KEYS`,
`MAX_REQUEST_BODY_BYTES`, `MAX_INTERACTIVE_CUSTOMERS`, `MAX_READ_LEDGER_ENTRIES`.

Platform startup: `PORT`. Public frontend build: `VITE_API_URL`.
MYSQL_PASSWORD/JWT_SECRET_KEY and any future private service credential must remain
backend-only managed secrets. No payment or AI variables are added/required.
Examples contain placeholders for credentials; local dotenv files are unchanged.
Production ignores dotenv and requires explicit safe values. See
[configuration](day17-production-configuration.md) and
[API security policy](day17-api-security-performance.md) for validation/defaults.

## F. Operational logs, metrics and proposed monitoring

Existing application logs record exception class/method/route template plus a
generated request ID; no body, raw JWT, password, SQL values or unrestricted
financial records. Uvicorn raw access logging is disabled by the launcher. A
future structured ingress logger must redact queries/credentials and preserve
safe IDs/status/duration. No third-party logger/monitoring integration is installed.

Proposed initial alerts, **not active services or measured SLAs**:

| Signal | Proposed condition / operator action |
| --- | --- |
| Frontend availability/deep link/static asset | Two consecutive one-minute external checks fail; inspect artifact/CDN/config |
| Backend liveness | Two consecutive one-minute failures; inspect startup/process/port |
| Database readiness | Three failures in a minute; inspect network/TLS/account/pool without logging credentials |
| API 5xx | Over 1% for five minutes with at least 100 requests, or repeated failures at low volume; correlate safe IDs |
| Latency | Read p95 over 500 ms or ordinary mutation over 1 s for ten minutes; review representative query plans/capacity |
| Authentication failures | Above established baseline for five minutes; assess abuse without collecting raw emails/passwords |
| 429 activity | Over 5% for five minutes; distinguish legitimate bursts, incorrect proxy identity and abuse |
| Backup freshness | Missed scheduled point/over 90 minutes for proposed hourly plan; page the designated recovery owner |
| Migration state | Unexpected revision or failed exclusive release job; halt promotion and inspect actual schema |
| Order/credit processing | Spike in 5xx/unconfirmed approvals; investigate using authorized references and idempotency, never replay blindly |
| Delivery assignment conflicts | Sudden increase beyond normal contention; distinguish expected 409 from system errors |

Baselines, low-volume handling, retention/access controls, alert ownership and
communication destinations need operator approval. Ordinary 401/403/409/422/429
are not automatically incidents; do not hide them as 200. No real metrics, alert
delivery or continuous monitoring results are claimed.

## G. Future release sequence and smoke checklist

All steps here are **future instructions**, not executed cloud actions.

1. Select a reviewed release artifact/reference with passing security/build/static
   checks; the current lint/feature/dependency/platform blockers must be decided.
2. Complete migration/backup/restore prerequisites and compatibility review; assign
   recovery/migration/cutover owners, maintenance window and abort criteria.
3. Prepare backend secrets, exact origins/hosts, verified MySQL TLS, PORT/runtime,
   shared throttling, ingress/proxy policy and health-host compatibility.
4. Validate configuration and install/package in an isolated supported Linux build.
   Any schema job is separately authorized/exclusive, never part of normal app boot.
5. Through a future explicitly authorized process, deploy backend, check live/ready
   and revision manually, then prepare/deploy frontend with the approved API URL.
6. Run authorized non-financial-mutating smoke checks and review errors/latency;
   abort promotion or roll back compatible artifacts if gates fail.

Future smoke evidence checklist:

- Frontend root, role deep links and static assets load; missing API/assets do not
  return SPA HTML. No secret or obsolete localhost API destination in the bundle.
- Liveness and readiness behave correctly, including unavailable DB handling.
- Approved origin preflight/Authorization works; unknown origins get no reflection.
- Synthetic/approved login, matching identity and all four role dashboard guards
  work. Verify missing/invalid JWT 401 and wrong-role 403.
- Authorized Owner customer/statement reads; Customer catalogue/order history/
  credit views; Driver jobs/history; Admin overview/management/audit reads work.
  Verify scoped identifier tampering is denied.
- Check 400/404/409/422/429/500/503 and client timeout handling with safe fixtures;
  no stack/SQL/credential leakage or non-401 session clearing.
- Compare authorized ledger reads without creating sales, repayments, approvals,
  new orders, assignments or customer financial mutations in production.
- **Admin reports/CSV smoke remains BLOCKED by missing Day 16 features.** Overview
  and audit tests are not a substitute. Record absent functionality rather than
  mark that checklist item passed.
- Capture safe request IDs/build IDs/schema revision and get release-owner signoff.

Local evidence is ASGI TestClient/MySQL synthetic integration plus existing Axios/
SSR tests, not a live browser or a deployed frontend/backend connection. Hosting
deep-link/proxy/HTTPS behavior requires a future authorized staging verification.

### Rollback and incident response

Record a last-known-good **deployed artifact ID/reference**, its environment names,
schema compatibility and verified recovery point before release. None exists in
the supplied deployment evidence; do not label HEAD d917e4f as a verified production
rollback. Preserve the previous frontend/backend artifact and signing secret.

On failure, stop promotion; pause unsafe writes if financial outcomes are uncertain;
preserve logs/artifacts and use request IDs. Assign an incident owner and approved
communication channel without exposing customer payloads. Roll back frontend and
backend independently only when the older code supports the current schema.
Old code does not undo MySQL DDL or financial writes. Never run destructive
downgrades/restore over source data to force a rollback. If recovery is needed,
restore to a separate approved target, reconcile and obtain cutover approval.
Verify health, login/RBAC, read-only ledger/order/delivery checks, errors and API
connectivity after rollback; document outcome and follow-up.

## H. Security review

JWT/active-account/RBAC/ownership and no public Admin registration remain enforced.
No financial formulas or token policy changed. CORS remains exact-origin and
Bearer-based (not credentialed cookies); explicit preview allowlists only.
Forwarded headers are disabled until an approved proxy policy exists. HTTPS/TLS
verification remains mandatory for production configuration. HSTS/CSP are deferred
until actual termination/domain/asset policy is known, not blindly enabled.

Known local-secret source/history/bundle checks and request/config/error redaction
tests run without printing values. Expected localhost strings in frontend URL
validation are not a localhost production API destination. No private backend
URL/credential is supplied to Vite. No external logging, backup upload or AI key.

## I. Tests and packaging

Focused initial deployment/config checks: **57 passed**; SPA routing pattern:
**1 passed**. The additional synthetic health/login/CORS/identity smoke is included
in full regression. Final backend: **1227 passed, zero failed, 1 skipped** in
242.74 seconds. One existing warning comes from the deliberately short wrong HMAC
key in the tampered-token test. Migration execution test remains skipped,
**BLOCKED**, not passed. All 14 added backend cases are included in this full run.

Frontend: **806 passed, zero failed/skipped/cancelled**. Full lint: **8 existing
errors and 1 warning** in ShopOwnerCustomers.jsx, ShopOwnerDashboard.jsx and
repayments.test.js. New routing test lint passes. No configured typecheck/backend
linter. Python syntax checks: **146 files passed**. `pip check`: **No broken
requirements found**. This verifies the local environment, not a new Linux install.
JSON manifests parse; routing tests do not certify platform execution.
Final known-secret scan: **zero findings**, 441 current files/assets and 622
reachable historical text blobs checked against two known local secret labels
without printing values. This is scoped evidence, not a guarantee against unknown
credentials. Changed tracked whitespace and new documentation checks pass. Branch
HEAD remains d917e4f and the previous 43 staged files remain unchanged in count.

## J. Production build

Local Vite 8.3.5 build passed in 7.36 seconds: 2218 modules, JS 803.78 kB (217.84 kB
gzip), CSS 62.61 kB (12.95 kB gzip). Existing large-chunk warning and a plugin timing
notice were emitted; they were not hidden. A process-only nonresolving test API URL
was supplied; **these artifacts are not a deployable production configuration**.
No dotenv or design changes. Asset/secret checks are recorded with final results.

## K. Open blockers

- Isolated migration database permission/execution verification **BLOCKED**; no
  complete chain execution/legacy-data migration certification.
- Backup/restore rehearsal unverified; no certified recovery/RPO/RTO or known-good
  deployed artifact. Development schema remains behind and untouched.
- Shared/edge throttling, actual domains, TLS/provider capability, ingress/proxy
  trust, runtime support/Linux packaging and hosting behavior unverified.
- Existing frontend lint failures and missing Day 16 reports/CSV/full Activity.
- No continuous monitoring/alerts or actual browser/staging/cloud smoke tests.

## L. Files created or modified in this step

- frontend/vercel.json — local build/output/SPA routing and safe header preparation.
- frontend/tests/deploymentRouting.test.js — deep-link vs asset/API routing checks.
- backend/railway.json — backend build/start/readiness configuration only.
- backend/.python-version — locally tested Python runtime pin.
- backend/scripts/start_production.py — safe PORT/environment-gated launcher.
- backend/app/core/config.py — validated connection/readiness timeout settings.
- backend/app/core/database.py — bounded socket connection setup, TLS preserved.
- backend/app/services/readiness.py — deadline, dedicated connections, one-worker gate.
- backend/app/routers/health.py — preserved public contracts, no-store and bounded readiness.
- backend/.env.example — nonsecret timeout variable defaults.
- backend/tests/test_production_config.py — connection-option expectation updated.
- backend/tests/test_deployment_readiness.py — health/startup/synthetic connectivity tests.
- docs/day17-deployment-readiness.md — this deployment/runbook and A–M review.

## M. Next step

**Overall readiness remains PARTIAL.** Do not mark Step 17.4 complete while required
local checks fail (full lint still fails) or describe this preparation as a live
deployment. Step 17.5 can audit the prepared changes and carry explicit blockers;
no completion checkpoint, commit or deployment is automatically authorized.
