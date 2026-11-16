# Day 17 Step 17.1 — Local production configuration hardening

This guide describes local preparation. No Railway/Vercel resources were accessed,
no deployment was performed, and no production database connection was attempted.
AI Summary remains deferred and requires no environment settings.

Step 17.3 adds configurable local rate limits, request/read bounds and a production
startup prerequisite: **RATE_LIMIT_MODE=external**. This selects operator-managed
shared/edge enforcement; it does not configure or verify that enforcement. Local
counters are not permitted as production's only limiter. See the
[API security/performance guide](day17-api-security-performance.md) for the full
policy, variables, validation results and unresolved production requirements.

## Environment inventory

| Backend variable | Secret? | Policy |
| --- | --- | --- |
| `APP_ENV` | No | `development` (default), `testing`, `production`. Set production in the process environment before importing the app. |
| `MYSQL_HOST`, `MYSQL_PORT` | No, backend only | Existing fields; default localhost/3306 only suitable for development. Production host must be explicit and non-loopback. Port 1–65535. |
| `MYSQL_USER` | Backend only | Required. Use a provider-supported application account with least privilege; reserve migration privileges for a separate operational procedure. |
| `MYSQL_PASSWORD` | **Yes** | Required; production rejects empty/common placeholder values. Keep in backend platform secret configuration. |
| `MYSQL_DATABASE` | Backend only | Required. Testing accepts only `lankapex_test_db`; production rejects both local database names. |
| `MYSQL_SSL_CA` | No, backend file path | Optional existing CA file. Production always requires verified TLS using this CA or system trust roots. Never disable hostname/certificate verification. |
| `JWT_SECRET_KEY` | **Yes** | Required. Production minimum 32 bytes and nonrepetitive/non-placeholder. Supply a securely managed signing secret; none was generated or rotated here. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Existing 30-minute default preserved; must be positive. HS256 remains a code-controlled allowlist, not a second environment setting. |
| `REMINDER_COOLDOWN_SECONDS` | No | Existing 86400 default; range 0–31536000 preserved. |
| `CORS_ALLOWED_ORIGINS` | No | Exact origins, comma-separated or JSON string array. Production requires explicit nonempty HTTPS origins; no wildcard, credentials, paths, queries or local origins. |
| `ALLOWED_HOSTS` | No | Exact backend hostnames, comma-separated or JSON array; no scheme/port/wildcards. Explicit nonempty production list required; used by TrustedHostMiddleware. |
| `APP_DEBUG` | No | Defaults false; true rejected in production. Named to avoid collision with an existing machine-level `DEBUG` variable. |
| `LOG_LEVEL` | No | Security logger severity; INFO default. DEBUG rejected in production. Configure ASGI server logging separately as described below. |

The sole approved public frontend variable is **`VITE_API_URL`**. It contains the
approved backend HTTPS origin followed by `/api/v1` exactly once. It is embedded
in public assets and must never contain credentials, a query string or a fragment.
No backend secret belongs in a `VITE_` variable. Any unreviewed `VITE_` variable
fails Vite configuration validation without printing its value.

`backend/.env.example` contains placeholders and local defaults only.
`frontend/.env.example` contains the established local API URL. Neither is a
deployable production configuration. Existing local environment files were preserved.
Production Settings ignores dotenv even when `_env_file` is explicitly supplied.
Selecting production inside dotenv is rejected; select it externally instead.

## Development and testing

From `backend`, use the existing virtual environment and install the pinned
requirements if needed. Supply local credentials in ignored `backend/.env`.
Development startup: `python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000`.
From `frontend`: `npm.cmd run dev`. Existing localhost frontend origins remain
available in development/testing; authentication remains JWT Bearer in sessionStorage.

From the project root, run isolated tests in PowerShell:

```powershell
$env:APP_ENV = 'testing'
$env:MYSQL_DATABASE = 'lankapex_test_db'
$env:PYTHONPATH = (Join-Path (Get-Location) 'backend')
.\backend\.venv\Scripts\python.exe -m pytest backend/tests -q
```

The test session rejects other environment modes or configured database names
before opening a connection, then checks `SELECT DATABASE()` before collection.
Use an existing, migrated, isolated test database. This task did not reset data
or run migrations. If the machine's normal pytest temporary directory is not
accessible, supply a fresh ignored path with `--basetemp`; do not reuse a path
containing valuable files because pytest manages that directory.

## Production startup and database transport

Supply required variables through backend service configuration, with real
user-approved origins and hostnames. Do not copy local dotenv files into a release.
Invalid startup configuration fails with a fixed explanatory message that omits
values and suppresses chained validation exceptions. Secret fields are excluded
from Settings repr. Keep `APP_DEBUG=false` and avoid server debug logging.

SQLAlchemy retains URL.create encoding, pre-ping, 1800-second pool recycling,
default bounded pooling, echo=false, and session closure/rollback-on-close.
Parameter hiding is enabled. Production passes an SSLContext with certificate
and hostname verification enabled to PyMySQL. The installed PyMySQL 1.2.3 treats
an explicit SSL context as required TLS and refuses servers without SSL support.
This was inspected locally; no remote handshake was attempted.

**Provider compatibility is unresolved:** confirm the actual MySQL endpoint,
TLS support, certificate chain and hostname with the provider before deployment.
Supply the provider CA when system trust is insufficient. A provider without
verified TLS support cannot use this production configuration; do not bypass
verification or silently fall back to plaintext. Do not assume Railway private
networking or any provider default establishes certificate-verified TLS.

Run Uvicorn from the backend root, bind the platform-provided port, disable reload,
use `--log-level info`, and initially use `--no-proxy-headers --no-access-log`.
The latter avoids logging raw URLs/query strings. Configure safe platform access
logging/redaction separately before enabling it. No trusted proxy address is
known yet: do not set forwarded trust to `*`. Enable forwarded headers only after
verifying the actual proxy network and ingress restrictions with the host.
There is no repository deployment manifest or approved production command/port
mapping yet. No hosting hostname or port has been invented here.

## HTTP policy, errors and health

CORS permits explicit configured origins and Authorization/Content-Type/Accept
headers with GET/POST/PUT/PATCH/DELETE/OPTIONS. Cookies are not used, so credentialed
CORS is disabled. CORS is a browser policy, not an authentication boundary;
untrusted-origin requests still require ordinary JWT/RBAC enforcement.

JWT signature/expiry/required-claim checks, active-account lookup, role enforcement,
Argon2 password handling and restricted Admin provisioning remain unchanged.
Unhandled request errors return HTTP 500 with `Internal server error`; operational
logs retain exception class, method and route template without body, raw exception,
SQL, token or password. Existing HTTP errors retain status/detail. Validation
responses preserve type/location/message and remove submitted input/context.
If a future custom validator embeds private values in its message, it must be
sanitized at the source; current validators were reviewed for this pattern.
The middleware is intended for the current JSON API; streaming/background-task
failures after headers have been sent need their own safe logging policy.

API responses receive `X-Content-Type-Options: nosniff` and
`Referrer-Policy: strict-origin-when-cross-origin`. Production enforces configured
backend hosts. HSTS, HTTPS redirects and a frontend CSP were deliberately deferred
until actual HTTPS termination, asset/API origins and domain ownership are known.
Configure equivalent frontend headers at the hosting platform and verify assets,
API requests and authentication before enforcing CSP. Configure the SPA fallback
to index.html for React Router deep links without swallowing real static assets;
no routing behavior or host rewrite was changed in this task.

Existing routes:

- `GET /api/v1/health`: inexpensive liveness, no database query.
- `GET /api/v1/health/database`: readiness using SELECT 1; generic 503 on database
  failure, no connection details; excluded from OpenAPI.

## Frontend release build

Use a user-approved production API URL ending in `/api/v1`, set `VITE_API_URL` in
the build environment, then run `npm.cmd run build` from `frontend`.
Build commands reject localhost/HTTP/missing/malformed URLs even with custom
Vite modes. The local `.env.local` is not overwritten: an ordinary build against
its local URL intentionally fails. A nonresolving `.invalid` endpoint was used
only to verify bundling offline; those generated assets are **not release-ready**.

Run `python backend/scripts/audit_known_secrets.py` from the root after building.
It reads known local secret values in memory and compares current source/examples,
assets and reachable Git text blobs, reporting labels/paths only. Short values
use literal/assignment matching to limit false positives. This does not prove
the absence of unknown credentials. A separate source pattern review is required.
If a real secret is found in history: arrange authorized rotation and history
remediation; do not simply delete the current file or rewrite history automatically.

## Rollback and outstanding inputs

No schema change was made, so code/config rollback requires no database rollback.
Preserve signing secrets to avoid unexpected session invalidation. Keep the
previous reviewed artifact and its environment settings; validate a rollback
against its supported schema before release. Never downgrade TLS or CORS merely
to make a rollback start.

User/operator input is still required for approved frontend/API origins, backend
hosts, MySQL endpoint/CA/TLS support, least-privilege account, signing-secret
provisioning, port/start command, proxy trust, SPA rewrites, HTTPS/HSTS/CSP,
health-check registration, backups/restore verification and monitoring.
Database/migration/backup planning belongs to Step 17.2; no live actions were taken.
