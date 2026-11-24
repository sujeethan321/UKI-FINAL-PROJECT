# Purpose: Coordinate sandbox checkout, recovery, portal access, and verified webhook updates with local subscription records.
"""Durable Checkout and authoritative sandbox reconciliation; billing tables only.

The Business FOR UPDATE lock serializes provider operations and webhook applies.
Provider failures never trigger an automatic mutation retry or new request key.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import Business
from app.models.subscription import BusinessSubscription, SubscriptionCheckoutAttempt as Attempt, SubscriptionPaymentEvent
from app.services.subscription_service import authorize_business, subscription_state, utc_now
from app.services.stripe_sandbox import Provider, require_enabled, price_map, hosted_url
from app.core.config import settings


# Raise the billing error used to stop an unsupported or conflicting operation.
def stop(message, code=409):
    raise HTTPException(code, message)


# Resolve lock using a row lock so the caller can coordinate concurrent changes.
def lock(db, business_id):
    return db.scalar(select(Business).where(Business.business_id == business_id)
                     .with_for_update().execution_options(populate_existing=True))


# Resolve or create the provider customer associated with the business billing record.
def provider_customer(provider, customer_id, business_id):
    customer = provider.call('GET', '/customers/' + customer_id)
    if (customer.get('livemode') is not False or customer.get('deleted')
            or customer.get('metadata', {}).get('business_id') != str(business_id)):
        stop('Provider customer binding mismatch', 502)


def reconcile_subscription(db, business_id, provider):
    """Ignore event snapshots/order; always fetch current provider state under lock."""
    sub = db.get(BusinessSubscription, business_id, populate_existing=True)
    if not sub or not sub.stripe_customer_id:
        return
    provider_customer(provider, sub.stripe_customer_id, business_id)
    objects = provider.pages('/subscriptions', {'customer': sub.stripe_customer_id,
        'status': 'all', 'expand[]': 'data.latest_invoice'})
    for obj in objects:
        if (obj.get('livemode') is not False or obj.get('customer') != sub.stripe_customer_id
                or obj.get('metadata', {}).get('business_id') != str(business_id)):
            stop('Provider subscription binding mismatch', 502)
    active = [obj for obj in objects if obj['status'] not in ('canceled', 'incomplete_expired')]
    if len(active) > 1:
        stop('Multiple provider subscriptions require operator review', 502)
    obj = active[0] if active else max(objects, key=lambda item: item.get('created', 0), default=None)
    if obj is None:
        if sub.stripe_subscription_id:
            stop('Previously bound subscription missing at provider', 502)
        return
    entries = obj.get('items', {})
    items = entries.get('data', [])
    if entries.get('has_more') or len(items) != 1 or items[0].get('quantity') != 1:
        stop('Unsupported subscription items', 502)
    item = items[0]
    price_id = item['price']['id']
    choice = next((choice for choice, configured in price_map().items() if configured == price_id), None)
    if not choice:
        stop('Unapproved provider price', 502)
    provider.verify_price(price_id, *choice)
    start = datetime.fromtimestamp(item['current_period_start'], timezone.utc).replace(tzinfo=None)
    end = datetime.fromtimestamp(item['current_period_end'], timezone.utc).replace(tzinfo=None)
    if end <= start:
        stop('Invalid provider period', 502)
    invoice = obj.get('latest_invoice')
    if isinstance(invoice, str):
        invoice = provider.call('GET', '/invoices/' + invoice)
    paid = bool(invoice and invoice.get('livemode') is False and invoice.get('status') == 'paid'
                and invoice.get('customer') == sub.stripe_customer_id and invoice.get('currency') == 'lkr')
    # No Stripe trial, browser redirect, incomplete or unpaid invoice grants paid access.
    sub.plan, sub.billing_interval = choice
    sub.stripe_subscription_id = obj['id']
    sub.status = ('ACTIVE' if obj['status'] == 'active' and paid else
                  'CANCELLED' if obj['status'] in ('canceled', 'incomplete_expired', 'unpaid', 'paused') else 'PAST_DUE')
    sub.started_at = start
    sub.paid_through = end if sub.status == 'ACTIVE' else None
    sub.updated_at = utc_now()
    # active + cancel_at_period_end retains access until the verified period ends.


# Return checkout attempt state and expose a hosted URL only when the attempt is open.
def session_result(attempt, session):
    return {'attempt_id': attempt.attempt_id, 'status': attempt.status,
            'url': hosted_url(session['url']) if attempt.status == 'OPEN' else None}


# Verify the provider session belongs to this local checkout attempt before adopting its identifiers and status.
def adopt_session(attempt, session):
    if (session.get('livemode') is not False or session.get('mode') != 'subscription'
            or session.get('metadata', {}).get('attempt_id') != attempt.attempt_id
            or session.get('client_reference_id') != str(attempt.business_id)
            or session.get('customer') != attempt.stripe_customer_id
            or (attempt.stripe_session_id and session['id'] != attempt.stripe_session_id)
            or not session.get('id', '').startswith('cs_test_')):
        stop('Checkout Session binding mismatch', 502)
    status = {'open': 'OPEN', 'complete': 'VERIFYING', 'expired': 'EXPIRED'}.get(session.get('status'))
    if not status:
        stop('Unexpected Checkout Session state', 502)
    attempt.stripe_session_id = session['id']
    attempt.status, attempt.error_code, attempt.reconciled_at = status, None, utc_now()
    attempt.active_business_id = attempt.business_id if status in ('OPEN', 'VERIFYING') else None


# Update the local checkout attempt only after the provider session has been verified.
def finish_verified_session(db, attempt, session):
    # Keep the active slot during eventual consistency: completing Checkout is
    # not proof that its subscription has been observed/reconciled yet.
    sub = db.get(BusinessSubscription, attempt.business_id)
    subscription_id = session.get('subscription')
    if isinstance(subscription_id, dict):
        subscription_id = subscription_id.get('id')
    if (attempt.status == 'VERIFYING' and subscription_id and sub
            and sub.stripe_subscription_id == subscription_id):
        attempt.status, attempt.active_business_id = 'COMPLETE', None


def run_attempt(db, attempt, provider):
    """Called under the business lock; recover before any repeat provider POST."""
    try:
        if price_map().get((attempt.plan, attempt.billing_interval)) != attempt.price_id:
            stop('Checkout configuration changed; operator reconciliation required')
        provider.verify_price(attempt.price_id, attempt.plan, attempt.billing_interval)
        sub = db.get(BusinessSubscription, attempt.business_id, populate_existing=True)
        if (sub and sub.stripe_customer_id and attempt.stripe_customer_id
                and sub.stripe_customer_id != attempt.stripe_customer_id):
            stop('Checkout Customer binding changed; operator review required')
        if not attempt.stripe_customer_id:
            if sub and sub.stripe_customer_id:
                attempt.stripe_customer_id = sub.stripe_customer_id
            else:
                # Never repeat customer creation outside Stripe's retention window.
                if utc_now() - attempt.created_at >= timedelta(hours=23):
                    stop('Uncertain customer creation requires operator reconciliation')
                customer = provider.call('POST', '/customers',
                    {'metadata[business_id]': str(attempt.business_id)}, 'lp-customer-' + attempt.attempt_id)
                if customer.get('livemode') is not False:
                    stop('Invalid sandbox customer', 502)
                attempt.stripe_customer_id = customer['id']
            if sub is None:
                sub = BusinessSubscription(business_id=attempt.business_id, plan='FREE', status='FREE',
                    provider_mode='sandbox', created_at=utc_now(), updated_at=utc_now())
                db.add(sub)
            sub.stripe_customer_id = attempt.stripe_customer_id
            db.flush()
        provider_customer(provider, attempt.stripe_customer_id, attempt.business_id)
        reconcile_subscription(db, attempt.business_id, provider)
        if attempt.stripe_session_id:
            session = provider.call('GET', '/checkout/sessions/' + attempt.stripe_session_id)
        else:
            sessions = provider.pages('/checkout/sessions', {'customer': attempt.stripe_customer_id})
            found = [s for s in sessions if s.get('metadata', {}).get('attempt_id') == attempt.attempt_id]
            if len(found) > 1:
                stop('Multiple matching Sessions require operator review', 502)
            if found:
                session = found[0]
            else:
                if any(s.get('status') == 'open' for s in sessions):
                    stop('Another provider Checkout is open; operator reconciliation required')
                existing = provider.pages('/subscriptions', {'customer': attempt.stripe_customer_id, 'status': 'all'})
                if any(s['status'] not in ('canceled', 'incomplete_expired') for s in existing):
                    stop('Existing provider subscription must be managed in the Portal')
                if utc_now() >= attempt.expires_at - timedelta(minutes=30):
                    stop('Uncertain Session outcome requires operator reconciliation')
                # Exact immutable parameters and key, including expiry, survive restarts.
                origin = attempt.return_origin
                base = origin + '/shop-owner/subscription?business_id=' + str(attempt.business_id)
                session = provider.call('POST', '/checkout/sessions', {
                    'mode': 'subscription', 'customer': attempt.stripe_customer_id,
                    'line_items[0][price]': attempt.price_id, 'line_items[0][quantity]': '1',
                    'client_reference_id': str(attempt.business_id),
                    'metadata[attempt_id]': attempt.attempt_id,
                    'subscription_data[metadata][business_id]': str(attempt.business_id),
                    'subscription_data[metadata][attempt_id]': attempt.attempt_id,
                    'expires_at': str(int(attempt.expires_at.replace(tzinfo=timezone.utc).timestamp())),
                    'success_url': base + '&checkout=success', 'cancel_url': base + '&checkout=cancelled',
                }, 'lp-checkout-' + attempt.attempt_id)
        adopt_session(attempt, session)
        if attempt.status == 'VERIFYING':
            reconcile_subscription(db, attempt.business_id, provider)
            finish_verified_session(db, attempt, session)
        result = session_result(attempt, session)
    except HTTPException:
        # Classify provider outcomes only. Database errors are NOT retried: the
        # durable CREATING record survives a failed flush/commit or process crash.
        attempt.status, attempt.error_code = 'UNCERTAIN', 'RECONCILE_REQUIRED'
        attempt.active_business_id = attempt.business_id
        attempt.reconciled_at = utc_now()
        db.commit()
        raise
    db.commit()
    return result


# Query checkout data for the subscription billing workflow.
def checkout(db, user, business_id, payload, provider=None):
    authorize_business(db, user, business_id, manage=True)
    require_enabled()
    provider = provider or Provider()
    lock(db, business_id)
    if subscription_state(db, business_id)['trial_active']:
        stop('Use your complimentary trial first; paid Checkout is available after it expires')
    old = db.scalar(select(Attempt).where(Attempt.request_key == payload.request_id))
    if old:
        if (old.business_id, old.plan, old.billing_interval) != (business_id, payload.plan, payload.billing_interval):
            stop('Checkout request key already used')
        if old.status in ('COMPLETE', 'EXPIRED'):
            stop('Checkout attempt is terminal; refresh subscription before starting another')
        return run_attempt(db, old, provider)
    active = db.scalar(select(Attempt).where(Attempt.active_business_id == business_id))
    if active:
        stop('Checkout already pending; reconcile the existing attempt')
    sub = db.get(BusinessSubscription, business_id)
    if sub and sub.stripe_subscription_id:
        reconcile_subscription(db, business_id, provider)
        if sub.status != 'CANCELLED':
            stop('Manage the existing subscription in the Portal')
    attempt = Attempt(attempt_id=str(uuid4()), business_id=business_id, active_business_id=business_id,
        request_key=payload.request_id, plan=payload.plan, billing_interval=payload.billing_interval,
        price_id=price_map()[(payload.plan, payload.billing_interval)], status='CREATING',
        return_origin=settings.STRIPE_RETURN_ORIGIN,
        created_at=utc_now().replace(microsecond=0), expires_at=(utc_now() + timedelta(hours=1)).replace(microsecond=0))
    db.add(attempt)
    try:
        db.commit()  # Durable intent BEFORE any provider mutation.
    except IntegrityError:
        db.rollback()
        stop('Concurrent Checkout request; reconcile existing attempt')
    lock(db, business_id)
    db.refresh(attempt)
    return run_attempt(db, attempt, provider)


# Query recover data for the subscription billing workflow.
def recover(db, user, business_id, provider=None):
    authorize_business(db, user, business_id, manage=True)
    require_enabled()
    lock(db, business_id)
    attempt = db.scalar(select(Attempt).where(Attempt.active_business_id == business_id))
    if not attempt:
        reconcile_subscription(db, business_id, provider or Provider())
        db.commit()
        return {'status': 'NO_PENDING_ATTEMPT', 'url': None}
    return run_attempt(db, attempt, provider or Provider())


# Create the authorized provider portal session for the business subscription.
def portal(db, user, business_id, provider=None):
    authorize_business(db, user, business_id, manage=True)
    require_enabled()
    lock(db, business_id)
    sub = db.get(BusinessSubscription, business_id)
    if not sub or not sub.stripe_customer_id or not sub.stripe_subscription_id:
        stop('No provider subscription to manage')
    provider = provider or Provider()
    provider_customer(provider, sub.stripe_customer_id, business_id)
    config = provider.call('GET', '/billing_portal/configurations/' + settings.STRIPE_PORTAL_CONFIGURATION)
    if config.get('livemode') is not False or not config.get('active'):
        stop('Invalid sandbox Portal configuration', 502)
    # Until a plan-change/proration policy is approved, Portal permits methods
    # and period-end cancellation only; prevent arbitrary products/prices.
    features = config.get('features', {})
    if (features.get('subscription_update', {}).get('enabled')
            or not features.get('subscription_cancel', {}).get('enabled')
            or not features.get('payment_method_update', {}).get('enabled')
            or features.get('subscription_cancel', {}).get('mode') != 'at_period_end'):
        stop('Portal must disable plan changes and use period-end cancellation', 502)
    obj = provider.call('POST', '/billing_portal/sessions', {'customer': sub.stripe_customer_id,
        'configuration': settings.STRIPE_PORTAL_CONFIGURATION,
        'return_url': settings.STRIPE_RETURN_ORIGIN + '/shop-owner/subscription?business_id=' + str(business_id)})
    return {'url': hosted_url(obj['url'], portal=True)}


EVENTS = {'checkout.session.completed', 'customer.subscription.created', 'customer.subscription.updated',
          'customer.subscription.deleted', 'invoice.paid', 'invoice.payment_failed'}


# Query webhook data for the subscription billing workflow.
def webhook(db, event, provider=None):
    if event['type'] not in EVENTS:
        return {'received': True, 'ignored': True}
    obj = event['data']['object']
    customer = obj.get('customer')
    sub = db.scalar(select(BusinessSubscription).where(BusinessSubscription.stripe_customer_id == customer)) if customer else None
    if not sub:
        stop('Customer binding not ready; provider should redeliver', 503)
    lock(db, sub.business_id)
    if db.get(SubscriptionPaymentEvent, event['id']):
        return {'received': True, 'duplicate': True}
    provider = provider or Provider()
    if event['type'] == 'checkout.session.completed':
        attempt_id = obj.get('metadata', {}).get('attempt_id')
        attempt = db.get(Attempt, attempt_id) if attempt_id else None
        if not attempt or attempt.business_id != sub.business_id:
            stop('Checkout event binding mismatch', 400)
        # Fetch the Session too; never trust an old event snapshot as current state.
        session = provider.call('GET', '/checkout/sessions/' + obj['id'])
        adopt_session(attempt, session)
    reconcile_subscription(db, sub.business_id, provider)
    pending = db.scalar(select(Attempt).where(Attempt.active_business_id == sub.business_id))
    if pending and pending.status == 'VERIFYING' and pending.stripe_session_id:
        session = provider.call('GET', '/checkout/sessions/' + pending.stripe_session_id)
        adopt_session(pending, session)
        finish_verified_session(db, pending, session)
    amount = obj.get('amount_paid', 0) if event['type'] == 'invoice.paid' else 0
    if (type(amount) is not int or not 0 <= amount <= 2147483647
            or (event['type'].startswith('invoice.') and obj.get('currency') != 'lkr')):
        stop('Unsupported payment receipt', 400)
    db.add(SubscriptionPaymentEvent(event_id=event['id'], business_id=sub.business_id,
        event_type=event['type'], provider_mode='sandbox', currency='lkr', amount_minor=amount, received_at=utc_now()))
    db.commit()  # Receipt + reconciled state are atomic; failures remain retryable.
    return {'received': True}
