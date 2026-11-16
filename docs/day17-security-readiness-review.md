# Day 17 Step 17.1 — Security/configuration review

Date: 2026-11-07. Scope: local preparation only.

## A. Repository audit

Branch `main`, HEAD `d917e4f` (Day 14 shopping/credit integration). The existing
43 staged Day 15 files remain staged; Day 16 edits/untracked files and unrelated
`.gitignore` changes were preserved. No staging, commit or push was performed.
Day 16 Step 16.4 reports/date filters/CSV/full Activity exploration are absent;
Step 16.5 was partial and has no completion checkpoint. See the existing
[Day 16 review](day16-final-security-regression-review.md).

Inspected config, dotenv keys (without printing values), JWT/password handling,
auth guards, CORS, routers, schemas, SQLAlchemy engine/sessions, Alembic,
health endpoints, tests, Vite/Axios configuration and Git state/history.
There is no deployment manifest/Dockerfile/Procfile or approved hosting domain
configuration. Existing production gaps included unconditional dotenv loading,
hardcoded development CORS, missing production validation/TLS/host policies,
validation responses echoing submitted values, and an unguarded frontend base URL.

## B. Environment configuration

Existing MYSQL fields, JWT_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES and
REMINDER_COOLDOWN_SECONDS remain authoritative. New controls are APP_ENV,
APP_DEBUG, LOG_LEVEL, CORS_ALLOWED_ORIGINS, ALLOWED_HOSTS and optional MYSQL_SSL_CA.
No duplicate DATABASE_URL/JWT_ALGORITHM/FRONTEND_BASE_URL or AI setting was added.
The complete inventory and instructions are in the
[configuration guide](day17-production-configuration.md).

Development retains local defaults. Testing requires explicit testing mode and
the isolated database. Production ignores local dotenv, requires explicit
database/secret/origin/host values, and rejects debug logging, local resources,
weak/common placeholder JWT secrets and invalid origins/expiry. Startup failure
uses a fixed safe message without chained secret-bearing validation exceptions.

## C. Secrets

Local `.env` files and logs are ignored, confirmed using git check-ignore. No
environment file was deleted/overwritten and no secret was generated or rotated.
Examples use placeholders for credentials. Known local credentials were scanned
in memory against current source/examples, built assets and reachable historical
text blobs, without putting values into process arguments or reports. Findings:
**zero** in the final post-build scan: 421 current files/assets and 587 historical
text blobs, comparing two known local secret labels without disclosing values.

No hardcoded credential assignment candidates were found in backend application
ASTs. Common provider-token/private-key source patterns returned no candidate
files. Test fixtures deliberately contain non-live credentials. Git path-history
inspection found no committed backend/.env, frontend/.env.local or root .env.
This is a scoped audit, not proof that every unknown credential is absent;
short known values use literal/assignment matching to avoid arbitrary substring
false positives. No rotation/history remediation was indicated by these checks.
If later discovered, arrange authorized rotation and history remediation.

## D. Authentication

Existing JWT signature validation uses a fixed HS256 algorithm allowlist; required
sub/iat/exp, access-token type, expiry, live user existence, account status and
role checks remain unchanged. JWT payload stays minimal and expiry stays 30 minutes
by default. Customer/Owner/Driver/Admin auth, suspension denial and role isolation
are covered by the full backend/frontend suites. No token storage rewrite.

Existing pwdlib recommended Argon2 hashing/verification, registration length and
extra-field restrictions remain intact. No public Admin registration/default
Admin password; provisioning remains an explicit restricted CLI workflow.
Production JWT secrets now require at least 32 bytes and reject common placeholders.

## E. CORS

Explicit CSV/JSON origins; production HTTPS only, no wildcard/path/query/userinfo
or loopback aliases. Bearer authentication uses Authorization headers, not cookies,
so credentialed CORS is disabled. Allowed methods/headers retain existing API needs.
Tests verify permitted authorization preflight, rejected origins/no reflection,
401 WWW-Authenticate preservation and CORS headers on generic 500 errors.
Production host enforcement is independent of JWT/RBAC; CORS is not authorization.

## F. Database

URL.create, pre-ping, pool recycling, bounded default pooling and session closure
are preserved. SQL parameter logging is hidden. Production requires an explicit
verified SSLContext; supplied CA files must exist, otherwise system trust is used.
Local inspection of installed PyMySQL confirms explicit SSL refuses plaintext
fallback. Actual provider TLS compatibility remains unverified and must be
confirmed before deployment. No insecure TLS option was introduced.

Before mutating tests, mode, configured URL database and actual SELECT DATABASE()
were all verified as testing/lankapex_test_db. The session hook rejects non-testing
or wrong configured resources before connection, then verifies actual database.
Read-only schema checks: development `b8c4d7e6f126`, test `03b9c2d1e671`.
No reset, migration, production connection or financial business logic change.

## G. Frontend

Only VITE_API_URL is approved public config. Vite rejects additional VITE_ variables
without printing values. Shared Vite/Axios validation requires an absolute URL,
no userinfo/query/fragment, and /api/v1 once; production builds require HTTPS and
non-local hosts even with custom Vite modes. Local development remains usable.
Axios auth/session-expiry handling is preserved. No routes, designs, colors or
branding changed; the landing headline remains Management. SPA hosting rewrites
remain a documented deployment input, not an unverified routing change.

## H. Error handling and logging

Request validation removes submitted input/context while retaining field errors.
Unhandled current JSON request exceptions return generic HTTP 500. Safe operational
logs preserve class/method/route template without raw exception, body, URL query,
SQL parameters, JWT or password. Existing HTTP statuses/business errors are retained.
No request body logging or monitoring integration was added. Streaming/background
errors after response start are outside this JSON-request middleware scope.

Application responses gain nosniff/referrer policy. Trusted hosts apply in
production. Proxy trust, HSTS and CSP are deferred until ingress/domain/asset
details are verified. The guide recommends no raw access logs and no wildcard
forwarded-header trust. Existing liveness/readiness routes were reviewed and kept:
`/api/v1/health`, `/api/v1/health/database` (generic 503 failure, SELECT 1 only).

## I. Tests and static checks

Final full backend: **1167 passed, zero failed/skipped**, in 248.88 seconds.
This includes all **44 new configuration/HTTP/isolation tests**, existing JWT/RBAC,
financial integrity, idempotency, order/delivery and Administrator regression.
One existing warning comes from the deliberately short wrong key in
test_jwt.py::test_tampered_token_rejected; production configuration rejects short keys.
Earlier full backend run: 1157 passed before the last added guard/edge cases;
the focused suite passed 38/38 before the final six additional cases.
An initial collection syntax error was corrected; an initial temporary-directory
permission error was resolved using a fresh ignored workspace temporary directory.
Neither is counted as a final passing check or silently reported as a skip.

Full frontend: **804 passed, zero failed/skipped/cancelled** on the final run.
Changed-file frontend lint passes. Full lint remains **8 existing errors and
1 warning**, in ShopOwnerCustomers.jsx, ShopOwnerDashboard.jsx and
tests/repayments.test.js. These unrelated findings were not weakened or hidden.
There is no configured backend linter/typechecker or frontend typecheck command.
Final Python AST syntax check passed for 134 app/test/script files.
Changed-file git diff --check passed; the index still contains the prior 43 files.
Separate-process checks also passed: production configuration import rejected a
missing JWT secret while ignoring dotenv, without leaking a sentinel password;
the real Vite build rejected a private VITE variable without printing its value.
The startup check imported configuration only and opened no database connection.
No browser/end-to-end or exact viewport verification is claimed; frontend tests
include existing Node/React SSR/service tests rather than a live browser session.

## J. Build

Ordinary production build against existing local dotenv: **rejected as intended**
because its API URL is local HTTP. A process-only, nonresolving `.invalid` test
endpoint then verified a Vite production build: **passed**, 2218 modules,
JS 803.78 kB (217.84 kB gzip), CSS 62.61 kB (12.95 kB gzip).
Existing >500 kB chunk warning persists. The test-URL bundle is not a release
artifact and must be rebuilt with the real approved API endpoint before deployment.
Local dotenv was not edited. No deployment was attempted.

## K. Files created or modified for this step

- backend/.env.example — safe variable template.
- backend/app/core/config.py — environment separation and validation.
- backend/app/core/database.py — verified TLS options and parameter hiding.
- backend/app/core/http_security.py — CORS, host checks, safe errors/headers/logging.
- backend/app/main.py — wire settings/security; preserve earlier router edits.
- backend/tests/conftest.py — explicit testing-mode gate.
- backend/tests/test_production_config.py — configuration/HTTP/isolation tests.
- backend/scripts/audit_known_secrets.py — read-only known-value source/history/asset scan.
- frontend/src/utils/apiConfig.js — shared public API/environment validation.
- frontend/src/services/api.js — validated Axios base URL.
- frontend/vite.config.js — build/public environment checks.
- frontend/tests/apiConfig.test.js — public config/production URL tests.
- docs/day17-production-configuration.md — operational/configuration guide.
- docs/day17-security-readiness-review.md — this A–M report.

No migration or dependency change. Earlier staged/unrelated changes remain intact.

## L. Deferred infrastructure actions

Need approved frontend/API origins and backend hosts; actual MySQL TLS endpoint,
CA and least-privilege credentials; managed signing secret provisioning; platform
port/start command; proxy trust; SPA rewrite and frontend security headers;
verified HTTPS termination/HSTS/CSP; health registration; backup/restore and
monitoring policy. No cloud action, credential rotation or AI configuration occurred.

## M. Next step / completion status

**Security/configuration tests pass. Overall readiness remains PARTIAL** because
full repository lint fails and Day 16 reporting/production configuration gaps remain.
Local hardening is implemented;
this is not a production deployment approval. Step 17.2 can begin with read-only
schema/migration/backup planning, using the documented schema gap and strict test
isolation. Live migrations, backup operations and deployment require reviewed real
provider/environment inputs; no completion checkpoint has been fabricated.
