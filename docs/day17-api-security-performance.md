# Day 17 Step 17.3 — API security and local performance review

Date: 2026-11-07. Local implementation and verification only. No deployment,
production traffic/database access, cloud operation, new external service, AI
integration, commit or push. This is not production performance certification.

## A. Repository audit

Branch main, HEAD d917e4f. Existing 43 staged Day 15 files and prior Day 16/17 work
are preserved. Step 17.1 configuration/security implementation is present; its
documented production inputs and frontend lint debt remain. Step 17.2 migration
execution verification remains **BLOCKED** by local MySQL CREATE DATABASE
permission; the user chose documentation, not elevation. This task never retries
that creation, requests a DBA password, runs migrations or changes development.

The user explicitly authorized isolated synthetic tests in lankapex_test_db for
this step. Before mutating tests, APP_ENV=testing, settings/engine database and
actual SELECT DATABASE() were verified. The existing session guard still rejects
other configured/actual resources. No reset/truncate/restore was performed.

Inspected routers/OpenAPI conventions, actual /api/v1 prefixes, auth/RBAC/ownership
dependencies, request/response schemas, CORS/error middleware, SQLAlchemy sessions,
query shapes/indexes, financial/concurrency tests and Axios error handling.
There was no rate limiter/shared limiter store. No upload, CSV import/export or
password-reset endpoint exists. Admin reports/CSV/full Activity remain missing
Day 16 features; the available overview and audit APIs are not described as those
missing features. Existing exports are customer-authorized statement PDFs and
authorized JSON statements/receipts.

## B. Implemented security changes

- Thread-safe, bounded local fixed-window quotas; explicit production external
  enforcement requirement; no Redis dependency/credential or infrastructure added.
- Bounded incoming mutation bodies before form/JSON parsing, including requests
  without Content-Length. Oversize returns 413, invalid length 400.
- Login identifier/password size checks before lookup/password verification.
- Unknown-account login performs a dummy Argon2 verification to reduce the obvious
  existing-vs-missing account work difference. It creates no account or credential;
  generic login errors and valid-token behavior are unchanged. This is not a claim
  of perfectly constant end-to-end login timing.
- Server-generated correlation IDs; client-supplied IDs are ignored. Safe 500 logs
  include exception class, method, route template and generated ID, not body,
  query, token, password or SQL values. Authenticated/auth responses get no-store.
- Existing CORS trust remains strict; only Retry-After/X-Request-ID exposure added.
- Old interactive customer/dashboard/statement analysis now fails explicitly when
  configured bounds are exceeded, instead of materializing unlimited histories or
  calculating a misleading partial balance.

## C. Risk classification and rate-limit policy

Actual routes below use the existing /api/v1 prefix. Role and ownership checks
remain independent of quotas; a record ID or business_id is never limiter identity.

| Risk / operation | Actual endpoints | Local key/policy |
| --- | --- | --- |
| High: login | POST /auth/login | Peer IP plus normalized identifier/peer pair; quotas 40/IP and 10/pair |
| High: registration | POST /auth/register/customer, /auth/register/shop-owner, /auth/register/driver | Shared registration scope, 10/peer IP across public roles |
| High: ledger writes | POST /shop-owner/credit-sales, /shop-owner/repayments | Authenticated user + operation template, 60 each |
| High: order decisions | POST /shop-owner/orders/{order_id}/decision | Authenticated user + operation, 60; existing role/approval checks retained |
| High: job acceptance | POST /driver/jobs/{job_id}/accept | Authenticated Driver ID + operation, 60; existing atomic acceptance retained |
| High: Admin decisions | PATCH /admin/businesses/{business_id}/decision, /admin/drivers/{user_id}/decision, /admin/users/{user_id}/status | Admin ID + operation, 60 |
| Medium: other authenticated actions | Existing customer/order/product/delivery/reminder creation, notification mutations, delivery status updates, POST quotes | Authenticated ID + registered write template, 60; body business_id cannot reset it |
| Medium: expensive reads | Customer /credit-accounts/{credit_account_id}/statement and statement.pdf; Owner /customers/{customer_id}/statement; Admin /audit-events | Authenticated ID, shared export/read budget 5 |
| Lower: normal reads/health | Authorized catalogue/list/dashboard reads; health | Not identically throttled; retain authorization/paging and upstream ingress protection |

Quotas above apply per 60-second fixed window by default. A window begins with
the first request to a key; budget becomes available on expiry. Limits are local
development/test policy defaults to calibrate, not measured production abuse
thresholds. All authenticated POST/PUT/PATCH/DELETE requests entering the existing
identity dependency consume their operation budget, including read-only POST quotes.
Invalid JWTs still receive normal authentication errors. Ownership/role failures
can consume the authenticated caller's own quota, never another user's quota.

Keys use HMAC digests, not raw email/IP storage or logs. Forwarded/X-Forwarded-For
headers are not parsed by the limiter. It uses the ASGI client identity; keep server
proxy-header processing disabled until actual proxy CIDRs/ingress isolation are
verified, then configure narrow server trust. Never trust a client identity header.

429 response: `{"detail":"Too many requests. Please wait before retrying."}` with
integer Retry-After seconds. No account-existence information, limiter internals
or permanent account lock. CORS exposes Retry-After so approved browser clients
can inspect it. Existing Axios only expires sessions for matching-token 401 errors;
429 does not sign users out.

The lock makes per-process consumption atomic. Capacity is bounded at 4096 keys;
expired keys are purged, and capacity exhaustion rejects new keys temporarily
rather than evicting active budgets or growing without bound. Near-boundary bursts,
process restarts and multiple independent workers remain fixed-window/local limits.
The tests explicitly demonstrate independent application stores: this is **not**
distributed enforcement or protection against a fleet-wide attacker.

### Actual configuration variables

| Setting | Default | Validation / scope |
| --- | --- | --- |
| RATE_LIMIT_MODE | local | local or external; production rejects local |
| RATE_LIMIT_WINDOW_SECONDS | 60 | 1–3600, initialized on app creation |
| RATE_LIMIT_LOGIN | 10 | 1–100000, identifier + peer |
| RATE_LIMIT_LOGIN_IP | 40 | 1–100000, total login peer budget |
| RATE_LIMIT_REGISTRATION | 10 | 1–100000, public registration peer budget |
| RATE_LIMIT_MUTATION | 60 | 1–100000, authenticated operation budget |
| RATE_LIMIT_EXPORT | 5 | 1–100000, authenticated statement/audit budget |
| RATE_LIMIT_MAX_KEYS | 4096 | 16–65536, process memory bound |
| MAX_REQUEST_BODY_BYTES | 262144 | 1024–1048576, mutation body bytes |
| MAX_INTERACTIVE_CUSTOMERS | 1000 | 1–10000; legacy customer/account analysis |
| MAX_READ_LEDGER_ENTRIES | 5000 | 1–100000; explicitly bounded interactive analysis |

Restart after policy/window changes. These contain no private credentials and
belong only in backend configuration, not VITE variables.

**Production prerequisite:** there is no configured shared store or verified edge
policy in this repository. Production startup requires RATE_LIMIT_MODE=external;
that selects operator-owned enforcement and disables local counters. It is a
configuration declaration, not proof the policy exists. Do not deploy simply by
setting it. A reviewed shared backend/edge must enforce anonymous and authenticated
per-user operation budgets across all instances, cover direct-origin bypass and
all aliases, return safe 429/Retry-After, preserve idempotent retries and handle
store failure explicitly. Verified user identity must come from trusted JWT/server
verification, never a client user/business header. No external store is connected,
no shared enforcement is claimed, and production rate limiting remains unverified.

## D. Authentication and authorization

JWT signature/HS256 allowlist, required sub/iat/exp/type, user lookup, active status,
role guards and live ownership remain in place. No token storage/claim/expiry
rewrite or public Admin registration. Tests retain suspended, missing/expired/
invalid JWT, role and cross-business/customer/Driver denial coverage. Admin account
safeguards and restricted manual provisioning are unchanged.

Rate identities come from the validated database user, not unverified JWT claims,
path IDs or body fields. Login/registration limits execute before endpoint business
logic. A focused test caught Admin audit route templates excluding the outer
included-router prefix; the limiter now matches the correct template suffix and
the test confirms non-Admin 403 plus actual Admin 429. No test was weakened to
accept an unthrottled response.

## E. Input, pagination and file/export validation

Existing strict bounded order arrays (1–50), quantities (1–99), Decimal monetary
validation, publication/status enums, identifier constraints and date validation
remain. Catalogue q is bounded at 200 characters, Admin q at 100. Tests use the
actual q parameter and verify oversized q/page_size plus SQL metacharacter input.
Existing newer lists use page_size/limit at most 100 and stable server ordering;
there is no client SQL sort-expression API. Fixed server columns and parameterized
filters are retained. Unknown arbitrary query parameters are not claimed as
supported sort fields or interpreted as SQL.

Legacy Owner /customers keeps its existing response contract and stable ordering;
it is not silently truncated or represented as a newly paginated API. It returns
422 above the configured customer limit. Related accounts are scoped to those
actual customer IDs. Interactive Owner dashboard/customer/outstanding/statement
analysis loads at most the ledger limit + one sentinel row, then rejects overflow
before balance calculation. Financial write paths use the original full-history
locking/calculation default; optional read bounds do not change ledger formulas.
Businesses exceeding these interactive bounds need a separately designed paginated/
aggregate workflow; raising caps is not a substitute for capacity review.
The existing Customer statement 5000-entry preflight remains in addition to the
shared source read cap; the stricter bound applies. Its established limit was not
silently raised by introducing the Owner-side configurable bounds.

No uploads/imports/CSV endpoint exists: MIME/extension/CSV-formula checks are N/A,
not fake passing tests or newly invented functionality. Existing authorized PDF
generation uses escaped text, a controlled bundled font, typed date/ID filenames,
attachment/no-store/nosniff headers, bounded rows and generic failures. Server-side
rate/read limits apply to its statement source. Future CSV exports must sanitize
spreadsheet formula cells and bound columns/rows; no unrestricted export was added.

## F. Financial and delivery integrity

Existing Decimal arithmetic, historical price snapshots, reversal/statement policy,
credit-limit checks, idempotency keys, unique financial references, row locking,
commit/rollback behavior and server-authoritative amounts remain unchanged.
Read overflow returns a real 422, never a partial sum. SQL batching only changes
retrieval of existing projected order names/items, not prices, status or ledger.

Full existing financial/order/concurrency suites exercise duplicate approval,
repayment retry, rollback, accept-vs-cancel, double acceptance, pending approval,
last-owner/account suspension and cross-tenant protections. New synthetic GET
workload checks for no INSERT/UPDATE/DELETE and compares financial snapshots before
and after all reads/login. Driver vehicle eligibility uses the existing stored
vehicle/approval policy; no unsupported job vehicle-matching feature was invented.

## G. Query performance and indexes

Confirmed issue: order listing fetched related names/items per order. Baseline
synthetic one-order page: 4 SQL calls; 20-order page: 42. It now uses the existing
scoped count query, one projected joined page query and one batched ordered item
query: **3 SQL calls for both nonempty page sizes**. Empty pages use two. Customer
and Owner scoping/stable order and response fields are preserved; no private user
relationship is eagerly exposed. A query-count regression enforces constant growth.

Twenty sequential service measurements on the same 20-order/20-item synthetic
dataset originally gave p50 87.64 ms, p95 99.50 ms. The first optimized measurement
gave p50 11.34 ms, p95 14.15 ms. Later runs vary with host/test load; final measured
values are recorded below. This demonstrates local query reduction, not a server
capacity/production SLA guarantee or statistically controlled cross-host study.

Local EXPLAIN for the existing customer order filter/order used ref access and
ix_order_customer_created with estimated 20 rows; Extra: Using index; Using
filesort. No duplicate/speculative index was added. A (customer_user_id, order_id)
index might reduce sorting for that exact order, but needs representative volume,
plan comparison, write/storage impact and isolated migration verification before
recommendation. The existing isolation/migration blocker prevents claiming that
an index migration has been validated.

Other reviewed patterns: catalogue batches category-name projections; customer
dashboard uses scoped SQL aggregates; Admin overview is one query with scoped
count subqueries. Owner dashboard's older history materialization now has explicit
bounds. Driver history's per-row finish lookup remains a bounded optimization
candidate; no unmeasured improvement is claimed. DB-side scan/sort cost can still
grow with history despite result-memory bounds; production timeouts and query
capacity require representative-volume work.

## H. Controlled synthetic workload

Method: Python/FastAPI TestClient in-process, local MySQL 8.0.46, rollback-isolated
synthetic fixtures, Windows 10 build 19045, four logical CPUs, concurrency **1**.
RAM/disk/network capacity were not benchmarked. No external URL/service was loaded.
Datasets: 20 orders, one item/order, 20 products, 20 ledger rows and 20 available
jobs, two synthetic businesses plus fixture users/profiles. Authorization remains
enabled using synthetic JWTs; login uses one non-live fixture account.

Eight read scenarios × 10 requests plus 3 login requests = **83 HTTP calls**.
Each response status is measured and checked, failures are counted, GET SQL is
checked for writes and financial snapshots compared. HTTP SQL-call counts include
fixture savepoint/authorization overhead; they are not the three-query service-only
metric. Latency uses perf_counter and nearest-rank p50/p95; with 10 observations
the p95 is effectively the maximum, not a robust tail-capacity estimate. A separate
40-call/8-thread quota test verifies local atomicity; it is not a load-capacity test.

Final recorded synthetic HTTP results (milliseconds):

| Scenario | Requests | p50 | p95 | Maximum SQL calls | Errors |
| --- | --- | --- | --- | --- | --- |
| Shop catalogue list | 10 | 18.90 | 25.67 | 5 | 0 |
| Products | 10 | 22.56 | 33.16 | 6 | 0 |
| Customer order history | 10 | 29.13 | 30.40 | 6 | 0 |
| Customer transactions | 10 | 35.38 | 45.96 | 5 | 0 |
| Customer dashboard | 10 | 46.07 | 53.47 | 7 | 0 |
| Owner dashboard | 10 | 30.10 | 42.51 | 8 | 0 |
| Driver available jobs | 10 | 16.30 | 32.67 | 6 | 0 |
| Admin overview | 10 | 15.00 | 17.40 | 4 | 0 |
| Synthetic account login | 3 | 107.18 | 113.51 | 3 | 0 |

Total measured error rate: **0/83 (0%)**, with the limitations above. Final
service-only 20-order measurement: p50 **10.79 ms**, p95 **12.68 ms**, 3 queries,
20 measured calls and zero errors. Ignored local artifacts retain baseline,
service-query and HTTP measurements under .server-logs/day17-3-*.json; they contain
measurements, not credentials, request payloads or raw SQL parameters.
Targets (read p95 <500 ms, standard mutation <1 s, complex reports <3 s) remain
planning/evaluation targets. Financial mutation/report throughput was not load
tested; missing Admin reports are not benchmarked. No production SLA is inferred.

## I. Tests and static checks

Focused security/configuration after the Admin quota correction: **56 passed**.
Earlier focused hardening/performance run before that additional Admin case:
13 passed. Final full backend: **1213 passed, zero failed, 1 skipped**, in
202.85 seconds. The one warning is the existing deliberately short wrong HMAC
key in test_jwt.py::test_tampered_token_rejected; production still rejects short
signing keys. The opt-in clean-migration test
remains skipped/blocked by the previously documented privilege issue, not passed.
No DBA elevation or creation attempt was made during this step.

Final frontend suite: **805 passed, zero failed/skipped/cancelled**. Added actual
Axios interceptor checks for 403/409/413/422/429/500/timeout preserving the session;
existing matching-token 401 expiry checks remain. Existing UI/SSR/service tests
still cover the landing headline Management, roles and business modules.
No actual browser/viewport verification is claimed.

Full frontend lint still has **8 existing errors/1 warning** in ShopOwnerCustomers,
ShopOwnerDashboard and repayments.test.js. Changed frontend test lint passes.
Python AST checks passed for 143 app/test/script files; no backend linter/typecheck
or frontend typecheck is configured.
Final changed-file whitespace and Python syntax checks passed. Known local-secret
comparison against current source/assets and reachable Git text blobs found zero
matches (433 current files/assets and 609 historical text blobs at the recorded
scan). The scanner is scoped evidence, not proof against unknown credentials.

Intermediate runs are not represented as final passes: the first full run passed
1211 tests before the last additions; the next run found the Admin read-quota
template bug (1212 passed, 1 failed, 1 skipped). After the actual matcher fix,
focused and final full runs passed. A focused attempt also encountered the known
machine pytest temp-directory permission issue; subsequent runs used fresh ignored
workspace temp paths. The oversized-search test was corrected to use the actual
existing q field rather than an unsupported search parameter.

## J. Build

Vite 8.3.5 production build passed: 2218 modules, JS 803.78 kB (217.84 kB gzip),
CSS 62.61 kB (12.95 kB gzip). Existing >500 kB chunk warning remains. Only a
process-scoped, nonresolving .invalid API URL was used for offline verification;
the generated bundle is not a release-ready endpoint configuration. Local dotenv
files and UI/colors were not changed. No platform deploy/build was performed.

## K. Files changed in this step

- backend/.env.example — local quota/body/read-bound examples and production warning.
- backend/app/core/config.py — validated quotas/bounds and explicit external production mode.
- backend/app/core/rate_limit.py — bounded local quotas, peer and authenticated scopes.
- backend/app/core/request_limits.py — actual streamed-body bound before parsing.
- backend/app/core/http_security.py — wire controls, generated request IDs and safe headers/logging.
- backend/app/core/auth_dependencies.py — quota after active database-user authentication.
- backend/app/core/security.py — non-account dummy password hash for missing-login work.
- backend/app/routers/auth.py — public quota dependencies and dummy verification.
- backend/app/services/order_service.py — batched scoped order projections.
- backend/app/services/ledger_service.py — optional read-only load bounds; write default unchanged.
- backend/app/services/shop_owner_customer_service.py — bounded customer/read scope.
- backend/app/services/shop_owner_dashboard_service.py — bounded legacy analysis.
- backend/app/services/shop_owner_financial_documents_service.py — bounded statement reads.
- backend/tests/conftest.py — reset only volatile limiter state between test cases.
- backend/tests/test_production_config.py — valid production fixture selects external policy explicitly.
- backend/tests/test_api_hardening.py — quota/body/identity/overflow/auth/API regressions.
- backend/tests/test_api_performance.py — synthetic measurements/query count/no-read-write checks.
- frontend/tests/authenticationRoles.test.js — non-401/timeout session compatibility.
- docs/day17-production-configuration.md — link new controls/prerequisite.
- docs/day17-api-security-performance.md — this guide and A–M report.

No schema/index/dependency migration. Prior staged/shared changes are preserved.

## L. Remaining risks

Production shared/edge enforcement and verified proxy trust are not configured;
external mode alone provides no application quota. Production domains/TLS/service
configuration remain user inputs. No public/distributed load testing, real gateway
header testing or shared-store outage verification has occurred.

Migration execution remains **BLOCKED**, not passed; development remains behind
current schema and untouched. Full backup/restore verification remains unperformed.
Day 16 reports/CSV/full Activity and existing frontend lint remain incomplete.
Interactive read caps protect memory but do not implement a large-data UI or
prove production DB query capacity. No external cache for financial/private data,
public file storage, unsafe forwarding trust or new AI dependency was introduced.

## M. Next step / completion status

**Local security and regression verification passed; overall readiness remains
PARTIAL.** Step 17.3 is not marked fully complete: distributed production
enforcement is unconfigured, full frontend lint still fails, and the inherited
migration/reporting blockers remain. Step 17.4 can prepare deployment/monitoring configuration
locally while carrying these explicit blockers. No deployment or live monitoring
action is authorized or performed by this report.
