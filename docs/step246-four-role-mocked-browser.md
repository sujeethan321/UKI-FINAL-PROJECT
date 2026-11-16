# Four-role mocked visual verification (port 5173)

Preparation only; browser execution has not been performed. No application code,
authentication, route guard, backend configuration or existing fixture is changed.

## Offline preparation

From the repository root:

```powershell
node .\frontend\scripts\verifyFourRoleMockBrowser.mjs
```

Expected: `PASS: offline preparation only; no HTTP, browser or output writes`.
This does **not** attest that the running server has been verified.

## Separately authorized execution

```powershell
node .\frontend\scripts\verifyFourRoleMockBrowser.mjs --execute --confirm-origin http://127.0.0.1:5173 --confirm-output .server-logs/four-role-mock-browser
```

The command never starts/restarts a frontend/backend server. It first requests
only `/`, `/src/main.jsx`, `/src/App.jsx` and `/src/services/api.js` from 5173,
rejecting redirects. Served inline source maps must match the local source files.
The served API module must contain the exact effective public configuration
`http://127.0.0.1:8001/api/v1`, with no other VITE variables. This is the existing
demo frontend launcher's API target, **not** permission to contact that backend.
Missing source maps, a different API target or another app means STOP; no fallback.

Chrome must already be installed (default Windows Chrome path, or operator-set
CHROME_PATH). Debug port 9241 must be unused. The runner creates its own headless
Chrome process and unique synthetic profile; it never attaches to normal Chrome.
Only this child process is closed afterwards; no application server is stopped.

## Isolation and output authorization

Execution requires approval for frontend-only HTTP reads, Chrome startup, loopback
debugging on 9241, and new directories/profile/PNG/results files under:

`.server-logs/four-role-mock-browser/<random-run-id>/`

Screenshots contain deterministic synthetic data only. File writes are exclusive;
existing runs are not overwritten or deleted. Partial files are preserved on STOP.
No credentials, real JWTs, DPAPI files or existing private evidence are used.

All page requests are intercepted before navigation. Only reviewed frontend module,
asset and local-font paths may continue to 5173. Every supported API request is
fulfilled in memory; unknown endpoints, roles, methods or query parameters STOP.
No API requests continue to 8001. Vite HMR is replaced only in the test response
with a no-network CSS-compatible stub. WebSocket/EventSource/worker/SW creation and
popups are blocked; unexpected attached targets remain paused and STOP the run.
Chrome background networking/extensions/proxies are disabled and external DNS is
blocked. This is application-test isolation, not an OS-wide firewall attestation.

The real login form is filled with fixed, explicitly synthetic input. Only the
intercepted login and auth/me responses establish the session. No real session is
fabricated in production storage, and route guards remain enabled. Cross-role
navigation must redirect to the fixture role's own dashboard. Non-login mutation
requests are unsupported, including approval, credit, repayment and delivery writes.

## Coverage and limits

Reuse the existing Customer/Driver/Admin fixture factories and current parsers.
Owner credit totals are synthetic `100.25` outstanding and `30.10` collected, with
two recent transactions. Customer fixtures retain `100.25` outstanding, `1000.00`
limit and `899.75` available; recent synthetic order total is `12.50`. There is no
financial calculation or persisted record creation.

All four dashboards, Customer My Shops, Driver Jobs/Deliveries and Admin pending
business/Driver approval pages run in en/ta/si at 1366, 768 and 375px. Checks cover
document language, loaded synthetic records, layout overflow, clipped labels,
replacement characters, links/route guards, login draft preservation, mobile menus,
unsubmitted Admin confirmation dialogs and injected 503 visible errors.

Expect up to 111 PNGs plus results.json and the synthetic Chrome profile. PASS
reports metrics, not raw page bodies, tokens or requests. STOP prints a sanitized
message and never retries a scenario, submits an approval or deletes partial output.
Actual fonts, screenshots and browser compatibility remain unverified until the
separately approved run. Human screenshot review is required for glyph quality,
natural wrapping and translation quality; geometry checks cannot prove these.
