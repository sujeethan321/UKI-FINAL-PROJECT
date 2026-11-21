# Business subscriptions and approval trials

Step 346 update: the offline sandbox adapter and one additional prepared Checkout
table migration are described in [stripe-sandbox.md](stripe-sandbox.md). Payments
remain disabled until separately authorized migration and sandbox configuration.
The sections below describe the earlier internal-trial milestone; its live-test
and migration instructions are historical, not instructions to rerun those steps.

Implemented in source only. No MySQL connections, migrations, application-data
writes, Stripe calls or existing environment-file edits were performed.

## Policy and behavior

| Plan | Monthly | Yearly |
| --- | ---: | ---: |
| Free | LKR 0 forever | LKR 0 forever |
| Pro | LKR 499 | LKR 4,990 |
| Business | LKR 1,299 | LKR 12,990 |

Prices are authoritative server integer minor units (100 per LKR). No additional
fee, checkout authorization, card, Stripe customer or charge is created at approval.

All existing credit, repayment, customer, catalogue, order, delivery, report and
reminder features remain available on every tier. No differentiated restrictions
have been approved. The reusable server entitlement check checks ownership first
and denies unknown features. No ledger or order service is changed or placed
behind a paid gate. Future policy changes require explicit approval and endpoint
integration; merely hiding UI controls is insufficient.

First approval uses the existing business row FOR UPDATE lock. One UTC decision
timestamp is persisted in the approval audit and trial record in the same commit
as approval, the subscription and notifications. It represents the first approval
transaction timestamp, not a second, post-commit wall-clock reading. Rollback
leaves no trial. Repeated decisions return the existing 409; a later status reset
cannot reset or extend the immutable business-level trial entitlement.

Expiry is one calendar month later in Asia/Colombo, clamping to the last day of
short months and preserving local time. Datetimes are stored as naive UTC and
returned with UTC offsets. Existing MySQL DateTime columns store second precision.
Request-time evaluation uses the server UTC clock, even without an expiry worker.
At the exact end instant an unpaid business has effective Free access; the
historical grant remains untouched. Paid ACTIVE periods take precedence only
inside their bound period, with provider ownership identifiers present.

The migration inserts EXCLUDED eligibility markers for currently or previously
approved businesses, including approved legacy rows without audits. It does not
retroactively grant them trials. New pending businesses can receive their first
trial after deployment. Each business has independent state, even for one owner.

The Shop Owner dashboard shows the selected business's plan/trial. The new
`/shop-owner/subscription` page has business selection, monthly/yearly prices,
comparison, trial dates and remaining days, disabled billing actions and truthful
empty/error/loading states. English, Tamil and Sinhala labels are included.
History is unavailable rather than a fake successful payment or invoice.

## Payment integration boundary

No reviewed Sandbox credentials or eligible Price IDs were supplied to this task.
The permitted internal-trial fallback is implemented. `payment_configured=false`;
Checkout, Portal and webhook endpoints return 503 “Payment integration not
configured.” There are no external payment calls and no environment flag that can
accidentally enable live payments. No secret is read, printed or saved by this
module. Existing `.env` files were not edited or inspected for Stripe keys.

**Deferred, not claimed implemented:** Stripe-hosted sessions/portal, signed raw
webhook processing, provider state reconciliation, invoice lifecycle handling,
provider ownership checks and out-of-order-event handling. Payment-event primary
key uniqueness is prepared, but is not a claim of an operational webhook consumer.
Signature/idempotency integration tests require that future adapter. Offline tests
currently prove unconfigured and forged webhooks cannot change subscriptions.
No Checkout redirect can grant entitlements because no such activation path exists.

When Sandbox configuration is separately provided, implement and offline-test the
adapter before changing `payment_configured`. Server-select and verify each exact
LKR recurring test Price; never accept frontend amounts, Price IDs or redirects.
Use an explicitly authorized Checkout request, signed raw webhook validation,
business/customer/subscription binding, unique event IDs and authoritative current
provider state for reconciliation. No automatic second Stripe trial.
Primary references: [Stripe webhook guidance](https://docs.stripe.com/webhooks),
[Stripe subscription webhooks](https://docs.stripe.com/billing/subscriptions/webhooks).

## Offline verification

From repository root:

```powershell
.\backend\.venv\Scripts\python.exe backend\offline_tests\subscription_suite.py
Set-Location frontend
npx.cmd eslint src/hooks/useSubscription.js src/hooks/useTrialDisplay.js src/utils/subscription.js src/services/subscriptionService.js src/components/shopOwner/SubscriptionSummary.jsx src/pages/shopOwner/SubscriptionBilling.jsx src/pages/shopOwner/ShopOwnerDashboard.jsx src/components/shopOwner/ShopOwnerSidebar.jsx src/layouts/ShopOwnerLayout.jsx src/App.jsx
node --test --test-concurrency=2
```

The backend suite supplies an isolated SQLite Base/session and synthetic settings;
it never imports the real dotenv configuration or MySQL engine. Network attempts
are blocked, apart from Windows asyncio's internal wake-up socketpair. SQLite
tests atomic approval rollback, grant uniqueness under concurrent writers and
API authorization. MySQL FOR UPDATE SQL is compiled/reviewed, not live-tested.
Do not run `backend/tests`: its conftest deliberately connects to MySQL.

The production build uses a temporary process-only HTTPS placeholder API URL to
satisfy existing production URL validation. It does not contact that endpoint.
No connected browser was available for rendered mobile/desktop visual QA.

Final checks: 976 frontend tests passed; scoped ESLint and production build passed
(the existing large-chunk warning remains). Backend offline tests cover the
approval transaction, grant constraints/concurrency, time boundaries, independent
tenants, response contracts and the fail-closed unconfigured payment boundary.

## Separately authorized viva migration and live demonstration

**Do not run the commands below without separate authorization.** Do not rerun
Step 322. The live database remains at 29 tables/head `7b9e4d2c8a15` until then.
Review source and stop the local write-capable backend before migration, so no
business can be approved during the eligibility snapshot. Preserve the existing
approved records; do not reset them to obtain trials.

New revision `8c0f5e3d9b26` follows `7b9e4d2c8a15` and creates three tables only,
bringing the expected total to 32. No existing application table is altered.
The existing scoped migrator needs CREATE, SELECT, INSERT, INDEX and REFERENCES
(plus UPDATE on alembic_version through the existing database-scoped grants).
Runtime uses its existing SELECT/INSERT/UPDATE/DELETE grants. No grant change is
requested. MySQL DDL may commit partially; destructive downgrade is blocked.

Prepared operator command from repository root, after separate authorization:

```powershell
.\backend\.venv\Scripts\python.exe backend\scripts\migrate_viva_subscriptions.py --apply-authorized-viva-migration
```

The private terminal collects the existing migrator password with getpass. The
child process replaces MYSQL settings with exact viva settings, verifies runtime
TLS/identity/scoped grants through the existing guards, checks the old head/table
count, executes one pinned upgrade using normal env.py and verifies new head/count
and zero retroactive trials. It disables pre-ping/reconnects, writes no credentials
or logs and never retries. It never targets lankapex_db or lankapex_demo_db.

STOP on any mismatch, lost connection, partial DDL, duplicate, unexpected revision
or unconfirmed mutation. Keep all partial state; do not rerun, downgrade, delete,
stamp or repair automatically. Review the actual state read-only before another
authorization. Application startup does not run this script or migrations.

After successful migration, separately authorize a live synthetic test:

1. Restart using the existing isolated viva runtime launcher and frontend launcher.
   Existing approved businesses must show Free and EXCLUDED eligibility, no trial.
2. Through existing workflows, register one fictional pending business and approve
   it once as Admin. Confirm PRO/TRIALING, one grant and audit-identical UTC dates.
3. Repeat the approval request once only as an explicitly authorized idempotency
   test: expect 409 and unchanged dates. Do not automatically repeat failures.
4. On the owner dashboard and billing page, select each owned business and verify
   independent plans; unrelated owners/customers/drivers must be denied access.
5. Verify exact monthly/yearly pricing and disabled payments. Do not manipulate
   live trial dates to test expiry: use the offline injected clock tests instead.
6. Run the already approved four-role demo workflows. Subscription changes must
   not alter financial balances, repayments, orders, delivery access or history.

The old Step 327 verifier was pinned to 29 tables and the old model/head snapshot;
it is not the final verifier for this newly prepared 32-table revision. Review a
new full metadata/constraint comparison before declaring live schema verification
complete. This task does not claim that migration or live QA has happened.
