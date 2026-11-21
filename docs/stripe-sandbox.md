# Stripe Sandbox billing — prepared offline (Step 346)

No MySQL connection, migration, Stripe API operation, service restart or secret
file edit is part of this implementation. Step 344 live trial testing is still
partial. Existing ledger/order/delivery code and records are outside billing.

## Additive migration

Prepared revision `9d1a6f4e0c37` follows `8c0f5e3d9b26`. It creates only
`subscription_checkout_attempts` and its business index. After a separately
authorized migration the expected total is 33 tables. No existing table is altered.
Do not rerun the earlier migration helper: it is pinned to the previous milestone.

The table stores UUID intent ID, business FK, globally unique request key,
server-selected plan/interval/Price ID and fixed return origin, optional unique Stripe Session ID,
Customer ID, status, creation/expiry/reconciliation times and a safe error code.
A nullable unique `active_business_id` plus CHECK constraints permits exactly one
CREATING/UNCERTAIN/OPEN/VERIFYING attempt per business; terminal rows release that slot.
MySQL permits multiple NULLs in this unique index. The Business row lock serializes
Checkout, recovery, Portal and webhook reconciliation across worker processes.
No destructive downgrade is provided; preserve evidence and review partial DDL.

## Checkout recovery

1. Commit a local CREATING intent before contacting Stripe. All provider POSTs
   use fixed request parameters and an attempt-derived idempotency key.
2. Reuse the business's bound Customer; validate its test mode and business
   metadata. A newly created Customer uses its own stable attempt-derived key.
3. Fetch existing Sessions for the Customer with full bounded pagination and
   match attempt metadata before repeating any Session creation. Known IDs are
   retrieved directly. Conflicting open Sessions block new creation.
4. A lost response or process crash leaves a durable CREATING/UNCERTAIN record.
   The owner explicitly selects **Reconcile pending Checkout**. Recovery adopts
   an already-created Session; it does not invent a new key or retry automatically.
5. A missing Customer response can be recovered with the same key only inside
   23 hours. A missing Session can be replayed only while its original one-hour
   expiration is at least 30 minutes away. After those windows, an unresolvable
   outcome stays blocked for operator investigation. Time passing alone never
   releases an uncertain intent. A provider-confirmed expired Session does.
6. A completed Session enters VERIFYING and retains its active slot until its
   exact subscription ID is observed and reconciled. This blocks duplicate
   Checkout during provider eventual consistency. It does not unconditionally
   activate access. Browser success/cancel query parameters only display notices.

Internal complimentary trials remain unchanged. Checkout is rejected while the
trial is active. The owner can purchase afterward; no Stripe trial is added.
Existing nonterminal Stripe subscriptions must use the Portal rather than create
a second subscription. Provider-confirmed canceled subscriptions may purchase
again with a new explicit attempt.

## Webhook and entitlement rules

`POST /api/v1/subscriptions/webhook` verifies the timestamped HMAC-SHA256 signature
over the exact raw bytes, with 300-second tolerance and constant-time comparison.
Only test-mode events are accepted. Receipt PK uniqueness and the business lock
deduplicate supported events. Receipt insertion and reconciled state commit
together; errors do not acknowledge a processed receipt. No raw event/card data
is stored. Unknown event types are acknowledged without mutations.

Supported events: checkout.session.completed, customer.subscription.created,
updated/deleted, invoice.paid and invoice.payment_failed. Events are hints: under
the lock, retrieve current Customer/subscription/invoice/Price state. Do not apply
the event's old subscription snapshot. This prevents reordered deliveries from
restoring stale entitlements. Unknown bindings, multiple nonterminal subscriptions,
unsupported prices/items or incomplete pagination fail closed for review.

Paid access requires the configured test LKR price, quantity one, active provider
subscription, a paid latest invoice and a current bounded billing period.
Past-due, unpaid, incomplete, paused, external trials and canceled subscriptions
do not activate paid benefits. An active subscription scheduled to cancel at
period end retains its verified paid period; request-time expiry removes paid
access even without another webhook. Renewal refreshes that bound period.
The immutable internal trial grant is never reset. Existing feature access remains
preserved on all tiers, including Free, as required by the existing policy.

## Operator configuration — do not enable yet

Following separate migration/configuration authorization, supply process-only
backend values through the existing private launch mechanism (not frontend or
tracked files):

| Setting | Required value |
| --- | --- |
| STRIPE_SANDBOX_ENABLED | true only after migration and approved sandbox setup |
| STRIPE_TEST_SECRET_KEY | private `sk_test_…` key |
| STRIPE_WEBHOOK_SECRET | private `whsec_…` endpoint signing secret |
| STRIPE_PRO_MONTH_PRICE | test recurring LKR 49,900 minor units/month |
| STRIPE_PRO_YEAR_PRICE | test recurring LKR 499,000 minor units/year |
| STRIPE_BUSINESS_MONTH_PRICE | test recurring LKR 129,900 minor units/month |
| STRIPE_BUSINESS_YEAR_PRICE | test recurring LKR 1,299,000 minor units/year |
| STRIPE_RETURN_ORIGIN | exact approved CORS origin, e.g. http://127.0.0.1:5176 for local development |
| STRIPE_PORTAL_CONFIGURATION | active test `bpc_…` configuration |

Prices must be distinct, active, recurring, licensed, per-unit, interval_count=1.
The backend retrieves and verifies them; it never accepts a client amount/Price
ID. Secret fields are masked. No publishable key is needed for hosted redirects.
The adapter uses pinned Stripe API `2026-10-28.endive`, HTTPS with normal certificate
verification, no proxy environment, no redirects and no automatic HTTP retries.
Live secret keys and live-mode resources are rejected.

Configure Portal payment-method updates and period-end cancellation; disable
subscription plan changes until a proration/change policy is separately approved.
Portal customer binding and configuration are checked on each explicit request.
Do not create products/prices/endpoints or call Stripe as part of this step.

## Offline validation

From repository root:

```powershell
.\backend\.venv\Scripts\python.exe backend\offline_tests\subscription_suite.py
.\backend\.venv\Scripts\python.exe backend\offline_tests\billing_suite.py
Set-Location frontend
node --test tests/subscription.test.js tests/billing.test.js
node node_modules/eslint/bin/eslint.js src/pages/shopOwner/SubscriptionBilling.jsx src/services/subscriptionService.js src/utils/billing.js
```

Backend tests block application network connections and use SQLite, mock provider
responses and synthetic configuration only. Real MySQL row-lock behavior, pinned
provider contracts, rendered browser flows and actual Sandbox payments require a
separately authorized live test. No live readiness or payment success is claimed.

Primary references: [Checkout API](https://docs.stripe.com/api/checkout/sessions/create),
[idempotency retention](https://docs.stripe.com/api/idempotent_requests),
[webhook signatures and retries](https://docs.stripe.com/events/manage-webhook-endpoints),
[subscription item periods](https://docs.stripe.com/api/subscriptions/object).
