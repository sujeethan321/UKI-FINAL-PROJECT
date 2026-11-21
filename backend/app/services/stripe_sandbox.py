"""Sandbox-only REST adapter. No SDK retries, secrets in errors, or raw card data.

All provider operations are invoked explicitly by billing requests; none at import.
"""
import hashlib
import hmac
import json
import re
import time
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException
from app.core.config import settings


def enabled():
    return bool(getattr(settings, 'STRIPE_SANDBOX_ENABLED', False))


def require_enabled():
    if not enabled():
        raise HTTPException(503, 'Payment integration not configured')


def price_map():
    return {(plan, interval): getattr(settings, f'STRIPE_{plan}_{interval.upper()}_PRICE', '')
            for plan in ('PRO', 'BUSINESS') for interval in ('month', 'year')}


def hosted_url(value, portal=False):
    parsed = urlsplit(value or '')
    if (parsed.scheme != 'https' or parsed.hostname != ('billing.stripe.com' if portal else 'checkout.stripe.com')
            or parsed.username or parsed.password or parsed.port not in (None, 443)):
        raise HTTPException(502, 'Invalid payment provider response')
    return value


class Provider:
    def call(self, method, path, data=None, key=None):
        require_enabled()
        secret = settings.STRIPE_TEST_SECRET_KEY.get_secret_value()
        if not secret.startswith('sk_test_') or not re.fullmatch(r'/[a-zA-Z0-9_/-]+', path):
            raise HTTPException(503, 'Invalid sandbox configuration')
        headers = {'Authorization': 'Bearer ' + secret, 'Stripe-Version': '2026-10-28.endive'}
        if key:
            headers['Idempotency-Key'] = key
        try:
            with httpx.Client(timeout=12, trust_env=False, follow_redirects=False,
                              transport=httpx.HTTPTransport(retries=0)) as client:
                response = client.request(method, 'https://api.stripe.com/v1' + path,
                    headers=headers, params=data if method == 'GET' else None,
                    data=data if method != 'GET' else None)
                if not 200 <= response.status_code < 300:
                    raise HTTPException(502, 'Sandbox provider request failed; reconcile before retrying')
                obj = response.json()
        except (httpx.HTTPError, ValueError):
            raise HTTPException(502, 'Sandbox provider outcome uncertain; reconcile before retrying') from None
        if not isinstance(obj, dict):
            raise HTTPException(502, 'Invalid payment provider response')
        if obj.get('livemode') is True:
            raise HTTPException(502, 'Live resources are forbidden')
        return obj

    def verify_price(self, price_id, plan, interval):
        price = self.call('GET', '/prices/' + price_id)
        amount = {('PRO', 'month'): 49900, ('PRO', 'year'): 499000,
                  ('BUSINESS', 'month'): 129900, ('BUSINESS', 'year'): 1299000}[(plan, interval)]
        if (price.get('livemode') is not False or not price.get('active')
                or price.get('currency') != 'lkr' or price.get('unit_amount') != amount
                or price.get('billing_scheme') != 'per_unit' or price.get('type') != 'recurring'
                or price.get('recurring', {}).get('interval') != interval
                or price['recurring'].get('interval_count') != 1
                or price['recurring'].get('usage_type') != 'licensed'):
            raise HTTPException(502, 'Sandbox price does not match the approved plan')
        return price

    def pages(self, path, params):
        # Exhaust pagination before concluding absence. Bounded, fail closed.
        items = []
        for _ in range(20):
            page = self.call('GET', path, {**params, 'limit': 100,
                **({'starting_after': items[-1]['id']} if items else {})})
            items.extend(page['data'])
            if not page.get('has_more'):
                return items
            if not page['data']:
                break
        raise HTTPException(502, 'Provider reconciliation requires operator review')


def signed_event(body, signature, now=None):
    require_enabled()
    try:
        parts = [part.split('=', 1) for part in (signature or '').split(',')]
        timestamps = [value for name, value in parts if name == 't']
        if len(timestamps) != 1:
            raise ValueError()
        stamp = timestamps[0]
        if abs((time.time() if now is None else now) - int(stamp)) > 300:
            raise ValueError()
        secret = settings.STRIPE_WEBHOOK_SECRET.get_secret_value().encode()
        expected = hmac.new(secret, stamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, value) for name, value in parts if name == 'v1'):
            raise ValueError()
        event = json.loads(body)
        if event.get('livemode') is not False or not str(event.get('id', '')).startswith('evt_'):
            raise ValueError()
        return event
    except (ValueError, TypeError, KeyError, AttributeError):
        raise HTTPException(400, 'Invalid webhook signature or sandbox event') from None
